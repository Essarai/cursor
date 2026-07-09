"""阶段三 Tool-use Agent（ReAct 决策循环）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import ValidationError

from agent.chain import (
    ScreeningOutput,
    _build_llm,
    _candidate_index,
    _merge_reviewer_profile,
)
from agent.emit import emit
from agent.golden_cases import load_golden_cases
from agent.scoring import pub_year_range_last_n
from agent.tools import fetch_author_info_with_memory
from cscd.client import init_api_code

ROOT = Path(__file__).resolve().parents[1]
AGENT_PROMPT_PATH = ROOT / "prompt" / "agent.md"
PLACEHOLDER = "[Historical_Golden_Cases]"


def load_agent_prompt() -> str:
    template = AGENT_PROMPT_PATH.read_text(encoding="utf-8")
    golden = load_golden_cases().strip()
    if not golden:
        golden = "（暂无历史黄金案例，请仅依据候选人数据与论文信息进行精筛。）"
    return template.replace(PLACEHOLDER, golden)


def _compact_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "name": c.get("name"),
            "org": c.get("org"),
            "email": c.get("email"),
            "overlap_score": c.get("overlap_score"),
            "hindex": c.get("hindex"),
            "activity_score": c.get("activity_score"),
            "pubs_last_2_years": c.get("pubs_last_2_years"),
            "research_keywords": (c.get("research_keywords") or [])[:8],
            "has_recent_papers": bool(c.get("recent_papers")),
        }
        for c in candidates
    ]


def _resolve_profile(profiles: Dict[str, Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    key = name.strip()
    if key in profiles:
        return profiles[key]
    for candidate_name, profile in profiles.items():
        if key in candidate_name or candidate_name in key:
            return profile
    return None


def run_decision_agent(
    llm_payload: Dict[str, Any],
    api_code: Optional[str] = None,
) -> None:
    """Agent 决策：工具循环 → submit_reviewers → stage3_done。"""
    session_code = (api_code or "").strip() or init_api_code()
    candidates: List[Dict[str, Any]] = list(llm_payload.get("candidates") or [])
    profiles = _candidate_index(candidates)
    pub_year = pub_year_range_last_n(int(os.getenv("AGENT_RECENT_PAPER_YEARS", "3")))
    max_steps = int(os.getenv("AGENT_STAGE3_MAX_STEPS", "8"))

    submitted_reviewers: Optional[List[Any]] = None

    @tool
    def get_candidate_detail(name: str) -> str:
        """从当前候选池查询学者完整信息（机构、keywords、overlap、recent_papers 等）。"""
        profile = _resolve_profile(profiles, name)
        if profile is None:
            return json.dumps({"error": f"未找到候选人：{name}"}, ensure_ascii=False)
        return json.dumps(profile, ensure_ascii=False, indent=2)

    @tool
    def fetch_author_publications(name: str, org: str = "") -> str:
        """从 CSCD 拉取学者近年论文（标题/年份/摘要），用于核实研究方向。name 必填，org 可空。"""
        response = fetch_author_info_with_memory(
            author=name.strip(),
            org=org.strip(),
            pub_year=pub_year,
            page=1,
            limit=10,
            api_code=session_code,
        )
        if not response.get("success"):
            return json.dumps(
                {"error": response.get("message") or "CSCD 查询失败"},
                ensure_ascii=False,
            )

        articles = (response.get("result") or {}).get("data") or []
        papers = [
            {
                "title": str(article.get("title") or "").strip(),
                "year": str((article.get("issue") or {}).get("year") or "").strip(),
                "abstract": str(article.get("abstract") or "")[:500],
                "keywords": str(article.get("keywords") or ""),
            }
            for article in articles[:10]
            if article.get("title")
        ]

        profile = _resolve_profile(profiles, name)
        if profile is not None:
            profile["recent_papers"] = papers

        return json.dumps(
            {"name": name.strip(), "paper_count": len(papers), "papers": papers},
            ensure_ascii=False,
            indent=2,
        )

    @tool
    def submit_reviewers(reviewers_json: str) -> str:
        """提交最终审稿人 JSON 字符串，格式 {"reviewers":[{"name","email","matched_paper","reason"},...]}。"""
        nonlocal submitted_reviewers
        try:
            data = json.loads(reviewers_json)
            parsed = ScreeningOutput.model_validate(data)
            submitted_reviewers = parsed.reviewers
            emit("stage3_result", {"chunk": reviewers_json})
            return "提交成功，任务完成。"
        except (json.JSONDecodeError, ValidationError) as exc:
            return f"提交失败，请修正 JSON：{exc}"

    tools = [get_candidate_detail, fetch_author_publications, submit_reviewers]
    tools_by_name = {item.name: item for item in tools}
    llm = _build_llm(streaming=False).bind_tools(tools)

    paper = llm_payload.get("paper") or {}
    meta = llm_payload.get("pipeline_meta") or {}
    initial_payload = {
        "paper": paper,
        "pipeline_meta": meta,
        "candidates_summary": _compact_candidates(candidates),
        "instruction": (
            "请审阅候选人，必要时调用工具核实论文方向，"
            "最后必须调用 submit_reviewers 提交 3-5 位审稿人。"
        ),
    }

    emit(
        "stage3_thinking",
        {
            "thinking": {
                "summary": (
                    f"阶段三 Agent 模式：对 {len(candidates)} 位候选人启动 ReAct 决策"
                    f"（最多 {max_steps} 步）。可用工具：get_candidate_detail、"
                    "fetch_author_publications、submit_reviewers。"
                ),
            },
        },
    )

    messages: List[Any] = [
        SystemMessage(content=load_agent_prompt()),
        HumanMessage(content=json.dumps(initial_payload, ensure_ascii=False, indent=2)),
    ]

    for step in range(1, max_steps + 1):
        ai_msg: AIMessage = llm.invoke(messages)
        messages.append(ai_msg)

        content = str(ai_msg.content or "").strip()
        if content:
            emit("stage3_thinking", {"chunk": content + "\n"})

        tool_calls = ai_msg.tool_calls or []
        if not tool_calls:
            if submitted_reviewers is not None:
                break
            messages.append(
                HumanMessage(content="请调用 submit_reviewers 提交最终审稿人名单。")
            )
            continue

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args") or {}
            tool_id = tool_call.get("id") or f"call-{step}"

            emit(
                "stage3_thinking",
                {
                    "thinking": {
                        "summary": (
                            f"[步骤 {step}] {tool_name}"
                            f"({json.dumps(tool_args, ensure_ascii=False)})"
                        ),
                    },
                },
            )

            tool_fn = tools_by_name.get(tool_name)
            if tool_fn is None:
                result = f"未知工具：{tool_name}"
            else:
                result = str(tool_fn.invoke(tool_args))

            messages.append(ToolMessage(content=result, tool_call_id=tool_id))

        if submitted_reviewers is not None:
            break

    if not submitted_reviewers:
        raise ValueError("Agent 未在步数限制内成功调用 submit_reviewers")

    emit(
        "stage3_done",
        {
            "reviewers": [
                _merge_reviewer_profile(item, profiles.get(item.name.strip()))
                for item in submitted_reviewers
                if item.name.strip()
            ],
        },
    )
