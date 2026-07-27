"""LangChain 语义精筛链（阶段三）。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from json_repair import repair_json
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agent.emit import emit
from agent.golden_cases import load_golden_cases

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompt" / "system.md"
PLACEHOLDER = "[Historical_Golden_Cases]"

_THINK_END = "\u003c/redacted_thinking\u003e"
_THINK_START = "\u003credacted_thinking\u003e"
_THINK_END_ALT = "\u003c/think\u003e"
_THINK_START_ALT = "\u003cthink\u003e"


class ReviewerItem(BaseModel):
    candidate_id: str = Field(description="候选人唯一 ID")
    name: str = Field(description="学者姓名")
    email: str = Field(description="联系邮箱")
    matched_paper: str = Field(description="近3年最相关的代表作题目")
    reason: str = Field(description="推荐理由")


class ScreeningOutput(BaseModel):
    reviewers: List[ReviewerItem] = Field(description="3-5 位推荐审稿人")


def load_system_prompt() -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    golden = load_golden_cases().strip()
    if not golden:
        golden = "（暂无历史黄金案例，请仅依据候选人数据与论文信息进行精筛。）"
    return template.replace(PLACEHOLDER, golden)


def _build_llm(
    *,
    streaming: bool = False,
    json_mode: bool | None = None,
    temperature: float | None = None,
    disable_thinking: bool = False,
) -> ChatOpenAI:
    api_key = (
        os.getenv("MINIMAX_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    if not api_key:
        raise RuntimeError("请设置环境变量 MINIMAX_API_KEY 或 OPENAI_API_KEY")

    base_url = (
        os.getenv("MINIMAX_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
        or "https://api.minimaxi.com/v1"
    )
    model = (
        os.getenv("MINIMAX_MODEL", "").strip()
        or os.getenv("LLM_MODEL", "").strip()
        or "MiniMax-M3"
    )

    kwargs: Dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": 0.2,
        "streaming": streaming,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    use_json_mode = json_mode
    if use_json_mode is None:
        use_json_mode = os.getenv("LLM_JSON_MODE", "1").strip() not in (
            "0",
            "false",
            "False",
        )
    model_kwargs: Dict[str, Any] = {}
    if not streaming and use_json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}
    # MiniMax-M3：关闭思考链，显著缩短简单任务延迟
    if disable_thinking:
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs

    return ChatOpenAI(**kwargs)


def _strip_thinking_tags(text: str) -> str:
    patterns = [
        rf"{re.escape(_THINK_START)}[\s\S]*?{re.escape(_THINK_END)}",
        rf"{re.escape(_THINK_START_ALT)}[\s\S]*?{re.escape(_THINK_END_ALT)}",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


def _thinking_started(text: str) -> bool:
    lowered = text.lower()
    return _THINK_START.lower() in lowered or _THINK_START_ALT.lower() in lowered


def _in_thinking_block(text: str) -> bool:
    lowered = text.lower()
    starts = sum(
        1
        for marker in (_THINK_START.lower(), _THINK_START_ALT.lower())
        if marker in lowered
    )
    ends = sum(
        1
        for marker in (_THINK_END.lower(), _THINK_END_ALT.lower())
        if marker in lowered
    )
    return starts > ends


def _iter_stage3_stream(chunks: Iterable[str]) -> List[str]:
    """分流输出：思考过程 → stage3_thinking，JSON → stage3_result。"""
    carry = ""
    mode = "detect"  # detect | thinking | result
    result_parts: List[str] = []

    for chunk in chunks:
        if not chunk:
            continue
        carry += chunk

        if mode == "detect":
            if _thinking_started(carry):
                mode = "thinking"
            elif carry.lstrip().startswith("{") or carry.lstrip().startswith("["):
                mode = "result"

        if mode == "thinking":
            for marker in (_THINK_END, _THINK_END_ALT):
                if marker in carry:
                    thinking_text, carry = carry.split(marker, 1)
                    thinking_text = thinking_text.replace(_THINK_START, "").replace(
                        _THINK_START_ALT, ""
                    )
                    if thinking_text.strip():
                        emit("stage3_thinking", {"chunk": thinking_text})
                    mode = "result"
                    break
            else:
                # 思考块尚未结束，流式输出当前 chunk（去掉起始标签）
                visible = chunk.replace(_THINK_START, "").replace(_THINK_START_ALT, "")
                if visible:
                    emit("stage3_thinking", {"chunk": visible})
                carry = ""
                continue

        if mode == "result" and carry:
            emit("stage3_result", {"chunk": carry})
            result_parts.append(carry)
            carry = ""

    if carry:
        if _in_thinking_block(carry) or mode == "thinking":
            visible = _strip_thinking_tags(carry)
            if visible:
                emit("stage3_thinking", {"chunk": visible})
        else:
            visible = _strip_thinking_tags(carry)
            if visible:
                emit("stage3_result", {"chunk": visible})
                result_parts.append(visible)

    return result_parts


def _extract_json(text: str) -> Any:
    text = _strip_thinking_tags(text.strip())
    if not text:
        raise ValueError("LLM 返回为空")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return json.loads(fenced.group(1).strip())

    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return json.loads(repair_json(snippet))

    raise ValueError(f"无法解析 LLM JSON 输出: {text[:300]}")


def _parse_screening_output(raw: str) -> ScreeningOutput:
    data = _extract_json(raw)
    if isinstance(data, list):
        data = {"reviewers": data}
    return ScreeningOutput.model_validate(data)


def _to_recommendations(result: ScreeningOutput) -> None:
    reviewers = [item for item in result.reviewers if item.name.strip()]
    if not reviewers:
        raise ValueError("精筛结果为空，请检查 LLM 输出格式")


def _candidate_index(candidates: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        name = str(candidate.get("name") or "").strip()
        key = candidate_id or name
        if key:
            index[key] = candidate
    return index


def _resolve_candidate(
    candidates: List[Dict[str, Any]],
    *,
    candidate_id: str = "",
    name: str = "",
) -> Dict[str, Any] | None:
    normalized_id = candidate_id.strip()
    if normalized_id:
        for candidate in candidates:
            if str(candidate.get("candidate_id") or "").strip() == normalized_id:
                return candidate
        return None

    normalized_name = name.strip()
    matches = [
        candidate
        for candidate in candidates
        if str(candidate.get("name") or "").strip() == normalized_name
    ]
    return matches[0] if len(matches) == 1 else None


def validate_and_normalize_reviewers(
    reviewers: List[ReviewerItem],
    candidates: List[Dict[str, Any]],
) -> List[ReviewerItem]:
    if not (3 <= len(reviewers) <= 5):
        raise ValueError(f"审稿人数量须为 3–5 人，当前 {len(reviewers)} 人")

    normalized: List[ReviewerItem] = []
    seen: set[str] = set()
    for item in reviewers:
        if not item.candidate_id.strip():
            raise ValueError(f"{item.name or '未知候选人'} 缺少 candidate_id")
        profile = _resolve_candidate(
            candidates,
            candidate_id=item.candidate_id,
            name=item.name,
        )
        if profile is None:
            raise ValueError(
                f"候选人不存在或姓名不唯一：candidate_id={item.candidate_id!r}, "
                f"name={item.name!r}"
            )

        candidate_id = str(profile.get("candidate_id") or "").strip()
        canonical_name = str(profile.get("name") or "").strip()
        if not candidate_id:
            raise ValueError(f"{canonical_name} 的候选数据缺少 candidate_id")
        if item.name.strip() != canonical_name:
            raise ValueError(
                f"candidate_id={candidate_id} 对应姓名为 {canonical_name}，"
                f"不是 {item.name.strip()}"
            )
        identity_key = candidate_id or (
            f"{canonical_name}|{str(profile.get('org') or '').strip()}"
        )
        if identity_key in seen:
            raise ValueError(f"审稿人重复：{canonical_name}")
        seen.add(identity_key)

        canonical_email = str(profile.get("email") or "").strip()
        submitted_email = item.email.strip()
        if not canonical_email and not submitted_email:
            raise ValueError(f"{canonical_name} 缺少可核实邮箱")
        if canonical_email and submitted_email and canonical_email != submitted_email:
            raise ValueError(f"{canonical_name} 的邮箱与候选数据不一致")

        matched_paper = item.matched_paper.strip()
        valid_papers = {
            str(paper.get("title") or "").strip()
            for paper in profile.get("recent_papers") or []
            if isinstance(paper, dict) and paper.get("title")
        }
        if matched_paper and matched_paper not in valid_papers:
            raise ValueError(f"{canonical_name} 的代表作不在已核实论文中")

        normalized.append(
            item.model_copy(
                update={
                    "candidate_id": candidate_id,
                    "name": canonical_name,
                    "email": canonical_email or submitted_email,
                    "matched_paper": matched_paper,
                    "reason": item.reason.strip(),
                }
            )
        )

    return normalized


def _merge_reviewer_profile(
    item: ReviewerItem,
    profile: Dict[str, Any] | None,
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "candidate_id": item.candidate_id.strip(),
        "name": item.name.strip(),
        "email": item.email.strip(),
        "matched_paper": item.matched_paper.strip(),
        "reason": item.reason.strip(),
    }
    if not profile:
        return merged

    recent_papers = profile.get("recent_papers") or []
    merged.update(
        {
            "org": str(profile.get("org") or "").strip(),
            "hindex": profile.get("hindex", 0),
            "subject": str(profile.get("subject") or "").strip(),
            "position": str(profile.get("position") or "").strip(),
            "research_keywords": profile.get("research_keywords") or [],
            "pubs_last_2_years": profile.get("pubs_last_2_years", 0),
            "recent_papers": [
                {
                    "title": str(p.get("title") or "").strip(),
                    "year": str(p.get("year") or "").strip(),
                }
                for p in recent_papers
                if isinstance(p, dict) and p.get("title")
            ],
        }
    )
    return merged


def build_screening_chain(*, streaming: bool = False):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}"),
            ("human", "{input_json}"),
        ]
    ).partial(system_prompt=load_system_prompt())
    return prompt | _build_llm(streaming=streaming) | StrOutputParser()


def stream_semantic_screening(llm_payload: Dict[str, Any]) -> None:
    """流式输出阶段三思考过程与精筛结果（NDJSON 事件）。"""
    mode = os.getenv("AGENT_STAGE3_MODE", "oneshot").strip().lower()
    if mode == "agent":
        try:
            from agent.decision_agent import run_decision_agent

            run_decision_agent(llm_payload)
            return
        except Exception as exc:
            emit(
                "stage3_thinking",
                {
                    "thinking": {
                        "summary": (
                            f"Agent 模式失败（{exc}），回退到 one-shot 精筛模式。"
                        ),
                    },
                },
            )

    _stream_oneshot_screening(llm_payload)


def _stream_oneshot_screening(llm_payload: Dict[str, Any]) -> None:
    """单次 LLM JSON 精筛（原阶段三实现）。"""
    emit(
        "stage3_thinking",
        {
            "thinking": {
                "summary": (
                    f"开始对 {len(llm_payload.get('candidates') or [])} 位候选人"
                    "进行 LLM 语义精筛，以下为模型思考过程："
                ),
            },
        },
    )

    chain = build_screening_chain(streaming=True)
    input_json = json.dumps(llm_payload, ensure_ascii=False, indent=2)
    parts = _iter_stage3_stream(chain.stream({"input_json": input_json}))

    raw = "".join(parts)
    parsed = _parse_screening_output(raw)
    candidates = llm_payload.get("candidates") or []
    normalized_reviewers = validate_and_normalize_reviewers(
        parsed.reviewers,
        candidates,
    )
    parsed = ScreeningOutput(reviewers=normalized_reviewers)
    _to_recommendations(parsed)

    emit(
        "stage3_done",
        {
            "reviewers": [
                _merge_reviewer_profile(
                    item,
                    _resolve_candidate(
                        candidates,
                        candidate_id=item.candidate_id,
                        name=item.name,
                    ),
                )
                for item in parsed.reviewers
                if item.name.strip()
            ],
        },
    )
