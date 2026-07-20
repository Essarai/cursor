import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .cscd_client import CscdClient
from .reviewer_models import (
    ArticleRelevanceBatch,
    KeywordExtraction,
    ManuscriptInput,
    ReviewerAgentState,
)
from .reviewer_scoring import (
    lexical_article_match,
    reviewer_key,
    stage1_filter,
    stage2_filter,
)


DEFAULT_MINIMAX_API_KEY = (
    "sk-cp-cLMZQs9GoZlEMSB13KHy1AgVQaWFxv3y_NrjGcAuofOccNRM7Pec1o-"
    "tWLAgE6A0ZpMNsuC1_v-jHsTDo9CF2XeOV1_Z7CEP8q-q_LfAafLOLZxpwM4jxTs"
)
DEFAULT_MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_MINIMAX_MODEL = "MiniMax-M3"


class ReviewerSelectionAgent:
    """完全由 LangGraph 编排的两阶段审稿人筛选 Agent。"""

    def __init__(
        self,
        llm: Any,
        client: CscdClient | None = None,
        checkpointer: MemorySaver | None = None,
        stage1_keep: int = 10,
        final_keep: int = 5,
        semantic_check_top: int = 5,
        fetch_workers: int = 5,
    ) -> None:
        self.llm = llm
        self.client = client or CscdClient()
        self.stage1_keep = stage1_keep
        self.final_keep = final_keep
        self.semantic_check_top = semantic_check_top
        self.fetch_workers = fetch_workers
        self.keyword_extractor = llm.with_structured_output(
            KeywordExtraction,
            method="function_calling",
        )
        self.relevance_judge = llm.with_structured_output(
            ArticleRelevanceBatch,
            method="function_calling",
        )
        self.graph = self._build_graph(checkpointer or MemorySaver())

    def _build_graph(self, checkpointer: MemorySaver):
        builder = StateGraph(ReviewerAgentState)
        builder.add_node("validate_input", self._validate_input)
        builder.add_node("extract_keywords", self._extract_keywords)
        builder.add_node("confirm_keywords", self._confirm_keywords)
        builder.add_node("fetch_candidates", self._fetch_candidates)
        builder.add_node("stage1_filter", self._stage1_filter)
        builder.add_node("fetch_articles", self._fetch_articles)
        builder.add_node("stage2_filter", self._stage2_filter)
        builder.add_node("generate_report", self._generate_report)

        builder.add_edge(START, "validate_input")
        builder.add_edge("validate_input", "extract_keywords")
        builder.add_edge("extract_keywords", "confirm_keywords")
        builder.add_edge("confirm_keywords", "fetch_candidates")
        builder.add_edge("fetch_candidates", "stage1_filter")
        builder.add_edge("stage1_filter", "fetch_articles")
        builder.add_edge("fetch_articles", "stage2_filter")
        builder.add_edge("stage2_filter", "generate_report")
        builder.add_edge("generate_report", END)
        return builder.compile(checkpointer=checkpointer)

    def start(
        self,
        manuscript: ManuscriptInput | dict[str, Any],
        thread_id: str | None = None,
    ) -> tuple[str, Iterable[dict[str, Any]]]:
        run_id = thread_id or uuid.uuid4().hex
        payload = (
            manuscript.model_dump()
            if isinstance(manuscript, ManuscriptInput)
            else manuscript
        )
        events = self.graph.stream(
            {"manuscript": payload, "warnings": []},
            self.config(run_id),
            stream_mode="updates",
        )
        return run_id, events

    def resume_keywords(
        self,
        thread_id: str,
        keywords: list[str] | None = None,
    ) -> Iterable[dict[str, Any]]:
        decision: dict[str, Any] = {"approved": keywords is None}
        if keywords is not None:
            decision["keywords"] = keywords
        return self.graph.stream(
            Command(resume=decision),
            self.config(thread_id),
            stream_mode="updates",
        )

    @staticmethod
    def config(thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}

    def _validate_input(self, state: ReviewerAgentState) -> dict[str, Any]:
        manuscript = ManuscriptInput.model_validate(state["manuscript"])
        warnings = list(state.get("warnings", []))
        if not manuscript.authors:
            warnings.append("未提供稿件作者，跳过共同作者利益冲突检查。")
        if not manuscript.organizations:
            warnings.append("未提供稿件机构，跳过同机构利益冲突检查。")
        return {"manuscript": manuscript.model_dump(), "warnings": warnings}

    def _extract_keywords(self, state: ReviewerAgentState) -> dict[str, Any]:
        manuscript = ManuscriptInput.model_validate(state["manuscript"])
        prompt = {
            "title": manuscript.title,
            "abstract": manuscript.abstract,
            "original_keywords": manuscript.keywords,
        }
        result = self.keyword_extractor.invoke(
            [
                SystemMessage(
                    content=(
                        "你是学术主题分析专家。请从论文标题、摘要和原始关键词中"
                        "提炼 1 到 4 个最核心、最有区分度、适合检索审稿人的关键词。"
                        "合并同义词，避免过宽泛的词，并简要说明提炼依据。"
                        "keywords 中每项只能包含一个术语，不要附加英文翻译、括号或斜杠。"
                    )
                ),
                HumanMessage(content=json.dumps(prompt, ensure_ascii=False)),
            ]
        )
        extraction = KeywordExtraction.model_validate(result)
        # 模型输出超过 4 个时静默截断，避免整个流程失败
        keywords = _clean_keywords(extraction.keywords, limit=4)
        if not 1 <= len(keywords) <= 4:
            raise ValueError("模型生成的有效核心关键词数量必须为 1-4 个")
        return {
            "core_keywords": keywords,
            "keyword_reasoning": extraction.reasoning.strip(),
        }

    def _confirm_keywords(self, state: ReviewerAgentState) -> dict[str, Any]:
        decision = interrupt(
            {
                "type": "keyword_confirmation",
                "keywords": state["core_keywords"],
                "reasoning": state["keyword_reasoning"],
                "instruction": "确认关键词，或提交修改后的 1-4 个关键词。",
            }
        )
        keywords = state["core_keywords"]
        if isinstance(decision, dict) and decision.get("keywords") is not None:
            # 人工提交的关键词严格校验数量，不做静默截断
            keywords = _clean_keywords(decision["keywords"])
        if not 1 <= len(keywords) <= 4:
            raise ValueError("人工确认后的核心关键词数量必须为 1-4 个")
        return {"core_keywords": keywords}

    def _fetch_candidates(self, state: ReviewerAgentState) -> dict[str, Any]:
        candidates = self.client.get_peer_reviewer_candidates(
            " ".join(state["core_keywords"]),
            max_results=100,
        )
        warnings = list(state.get("warnings", []))
        if len(candidates) < 100:
            warnings.append(f"接口 2 仅返回 {len(candidates)} 名候选人。")
        return {"candidates": candidates, "warnings": warnings}

    def _stage1_filter(self, state: ReviewerAgentState) -> dict[str, Any]:
        manuscript = ManuscriptInput.model_validate(state["manuscript"])
        selected, rejected = stage1_filter(
            state.get("candidates", []),
            state["core_keywords"],
            manuscript.organizations,
            keep_count=self.stage1_keep,
        )
        warnings = list(state.get("warnings", []))
        if not selected:
            warnings.append("初筛后没有可用候选人。")
        return {
            "stage1_candidates": selected,
            "stage1_rejected": rejected,
            "warnings": warnings,
        }

    def _fetch_articles(self, state: ReviewerAgentState) -> dict[str, Any]:
        articles_by_reviewer: dict[str, list[dict[str, Any]]] = {}
        warnings = list(state.get("warnings", []))
        candidates = state.get("stage1_candidates", [])

        def fetch(reviewer: dict[str, Any]) -> list[dict[str, Any]]:
            return self.client.get_author_articles(
                str(reviewer.get("authorName") or ""),
                str(reviewer.get("org") or ""),
                max_results=100,
            )

        if candidates:
            with ThreadPoolExecutor(
                max_workers=min(self.fetch_workers, len(candidates))
            ) as executor:
                futures = {
                    reviewer_key(reviewer): (reviewer, executor.submit(fetch, reviewer))
                    for reviewer in candidates
                }
                for key, (reviewer, future) in futures.items():
                    try:
                        articles_by_reviewer[key] = future.result()
                    except Exception as exc:
                        articles_by_reviewer[key] = []
                        warnings.append(
                            f"获取 {reviewer.get('authorName', key)} 的发文失败：{exc}"
                        )
        return {
            "articles_by_reviewer": articles_by_reviewer,
            "warnings": warnings,
        }

    def _stage2_filter(self, state: ReviewerAgentState) -> dict[str, Any]:
        manuscript = ManuscriptInput.model_validate(state["manuscript"])
        warnings = list(state.get("warnings", []))

        # 全员先做词面匹配
        lexical_by_key: dict[str, list[dict[str, Any]]] = {}
        for reviewer in state.get("stage1_candidates", []):
            key = reviewer_key(reviewer)
            articles = state.get("articles_by_reviewer", {}).get(key, [])
            lexical_by_key[key] = [
                article
                for article in articles
                if lexical_article_match(article, state["core_keywords"])
            ]

        # 仅对词面匹配数最高的前 N 人做 LLM 语义复核（并行），其余直接采用词面结果
        check_keys = {
            key
            for key, _ in sorted(
                lexical_by_key.items(),
                key=lambda pair: len(pair[1]),
                reverse=True,
            )[: self.semantic_check_top]
            if lexical_by_key[key]
        }

        relevant_ids: dict[str, set[str]] = {
            key: {
                str(article.get("cscdId") or index)
                for index, article in enumerate(matches)
            }
            for key, matches in lexical_by_key.items()
            if key not in check_keys
        }

        if check_keys:
            with ThreadPoolExecutor(max_workers=len(check_keys)) as executor:
                futures = {
                    key: executor.submit(
                        self._judge_relevant_articles,
                        manuscript,
                        state["core_keywords"],
                        lexical_by_key[key],
                        warnings,
                    )
                    for key in check_keys
                }
                for key, future in futures.items():
                    relevant_ids[key] = future.result()

        checked_names = [
            str(reviewer.get("authorName") or reviewer_key(reviewer))
            for reviewer in state.get("stage1_candidates", [])
            if reviewer_key(reviewer) in check_keys
        ]
        if checked_names:
            warnings.append(
                "以下候选人的相关发文经过 LLM 语义复核，"
                f"其余仅使用词面匹配：{'、'.join(checked_names)}"
            )

        selected, rejected = stage2_filter(
            state.get("stage1_candidates", []),
            state.get("articles_by_reviewer", {}),
            relevant_ids,
            manuscript.authors,
            keep_count=self.final_keep,
        )
        if not selected:
            warnings.append("终筛后没有可推荐的审稿人。")
        return {
            "final_reviewers": selected,
            "stage2_rejected": rejected,
            "warnings": warnings,
        }

    def _judge_relevant_articles(
        self,
        manuscript: ManuscriptInput,
        core_keywords: list[str],
        articles: list[dict[str, Any]],
        warnings: list[str],
    ) -> set[str]:
        relevant_ids: set[str] = set()
        for batch in _chunks(articles, 25):
            article_payload = [
                {
                    "article_id": str(article.get("cscdId") or index),
                    "title": article.get("title"),
                    "keywords": article.get("keywords"),
                    "abstract": str(article.get("abstract") or "")[:500],
                }
                for index, article in enumerate(batch)
            ]
            try:
                result = self.relevance_judge.invoke(
                    [
                        SystemMessage(
                            content=(
                                "判断候选论文是否与待审稿件的核心研究主题相关。"
                                "逐篇返回 article_id、relevant 和简短理由。"
                            )
                        ),
                        HumanMessage(
                            content=json.dumps(
                                {
                                    "manuscript_title": manuscript.title,
                                    "core_keywords": core_keywords,
                                    "articles": article_payload,
                                },
                                ensure_ascii=False,
                            )
                        ),
                    ]
                )
                assessment = ArticleRelevanceBatch.model_validate(result)
                valid_ids = {
                    str(article.get("cscdId") or index)
                    for index, article in enumerate(batch)
                }
                relevant_ids.update(
                    item.article_id
                    for item in assessment.assessments
                    if item.relevant and item.article_id in valid_ids
                )
            except Exception as exc:
                warnings.append(f"语义复核失败，回退到词面匹配结果：{exc}")
                relevant_ids.update(
                    str(article.get("cscdId") or index)
                    for index, article in enumerate(batch)
                )
        return relevant_ids

    def _generate_report(self, state: ReviewerAgentState) -> dict[str, Any]:
        manuscript = ManuscriptInput.model_validate(state["manuscript"])
        reviewers = state.get("final_reviewers", [])
        lines = [
            f"# 审稿人筛选报告：{manuscript.title}",
            "",
            f"- 核心关键词：{'、'.join(state.get('core_keywords', []))}",
            f"- 接口候选人数：{len(state.get('candidates', []))}",
            f"- 初筛入选人数：{len(state.get('stage1_candidates', []))}",
            f"- 最终推荐人数：{len(reviewers)}",
            "",
            "> 说明：各项评分为本批候选人内部的相对分（Min-Max 归一化），"
            "仅用于排序，不代表绝对水平；请结合每人的原始指标判断。",
            "",
        ]
        if state.get("warnings"):
            lines.extend(["## 数据与流程提示"])
            lines.extend(f"- {warning}" for warning in state["warnings"])
            lines.append("")

        lines.append("## 推荐排名")
        if not reviewers:
            lines.append("没有符合条件的审稿人。")
        for reviewer in reviewers:
            lines.extend(_reviewer_report_lines(reviewer))
        return {"report": "\n".join(lines).strip() + "\n"}


def build_default_agent() -> ReviewerSelectionAgent:
    llm = init_chat_model(
        DEFAULT_MINIMAX_MODEL,
        model_provider="openai",
        api_key=os.getenv("MINIMAX_API_KEY", DEFAULT_MINIMAX_API_KEY),
        base_url=os.getenv("MINIMAX_BASE_URL", DEFAULT_MINIMAX_BASE_URL),
    )
    return ReviewerSelectionAgent(llm=llm)


def run_reviewer_selection(
    manuscript: ManuscriptInput | dict[str, Any],
    keyword_override: list[str] | None = None,
    agent: ReviewerSelectionAgent | None = None,
) -> dict[str, Any]:
    """同步执行完整工作流；不修改关键词时自动确认模型结果。"""
    selection_agent = agent or build_default_agent()
    thread_id, events = selection_agent.start(manuscript)
    list(events)
    snapshot = selection_agent.graph.get_state(selection_agent.config(thread_id))
    if any(task.interrupts for task in snapshot.tasks):
        list(selection_agent.resume_keywords(thread_id, keyword_override))
    final_state = selection_agent.graph.get_state(selection_agent.config(thread_id))
    return dict(final_state.values)


def _clean_keywords(values: Any, limit: int | None = None) -> list[str]:
    if isinstance(values, str):
        values = values.replace("，", ",").replace("；", ",").split(",")
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        without_translation = re.sub(
            r"\s*[\(（][^()（）]*[\)）]\s*",
            "",
            str(value),
        )
        for piece in re.split(r"\s*[/／、]\s*", without_translation):
            keyword = piece.strip()
            normalized = keyword.casefold()
            if keyword and normalized not in seen:
                seen.add(normalized)
                result.append(keyword)
    return result if limit is None else result[:limit]


def _chunks(values: list[dict[str, Any]], size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _reviewer_report_lines(reviewer: dict[str, Any]) -> list[str]:
    name = reviewer.get("authorName") or "未知姓名"
    organization = reviewer.get("org") or "未知机构"
    hindex_value = reviewer.get("hindex_value")
    hindex_text = "无数据" if hindex_value is None else f"{hindex_value:g}"
    overlap_raw = reviewer.get("keyword_overlap_raw", 0) or 0
    lines = [
        f"### {reviewer.get('final_rank', '-')}. {name}",
        f"- 机构：{organization}",
        f"- 最终相对分：{reviewer.get('final_score', 0):.2f}"
        f"（初筛相对分 {reviewer.get('stage1_score', 0):.2f}）",
        (
            f"- 原始指标：关键词重合率 {overlap_raw:.0f}%，"
            f"H-index {hindex_text}，"
            f"近三年发文 {reviewer.get('recent_article_count', 0)} 篇，"
            f"相关发文 {reviewer.get('relevant_article_count', 0)} 篇"
        ),
        (
            "- 推荐理由：研究关键词匹配度、学术影响力及近期相关发文表现"
            "达到本批候选人的推荐标准。"
        ),
    ]
    evidence = reviewer.get("relevant_articles", [])
    if evidence:
        lines.append("- 相关论文证据：")
        lines.extend(
            f"  - {article.get('title') or article.get('citation') or '未知题名'}"
            for article in evidence
        )
    lines.append("")
    return lines
