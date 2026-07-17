"""阶段三 Tool-use Agent（ReAct 决策循环）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool, tool
from pydantic import ValidationError

from agent.chain import (
    ReviewerItem,
    ScreeningOutput,
    _build_llm,
    _merge_reviewer_profile,
    _resolve_candidate,
    validate_and_normalize_reviewers,
)
from agent.emit import emit
from agent.golden_cases import load_golden_cases
from agent.scoring import pub_year_range_last_n
from agent.tools import fetch_author_info_with_memory
from cscd.client import init_api_code

ROOT = Path(__file__).resolve().parents[1]
AGENT_PROMPT_PATH = ROOT / "prompt" / "agent.md"
PLACEHOLDER = "[Historical_Golden_Cases]"


def load_agent_prompt(
    *,
    max_steps: int,
    max_tool_calls: int,
    max_tools_per_step: int,
) -> str:
    template = AGENT_PROMPT_PATH.read_text(encoding="utf-8")
    golden = load_golden_cases().strip()
    if not golden:
        golden = "（暂无历史黄金案例，请仅依据候选人数据与论文信息进行精筛。）"
    text = template.replace(PLACEHOLDER, golden)
    return (
        text.replace("{max_steps}", str(max_steps))
        .replace("{max_tool_calls}", str(max_tool_calls))
        .replace("{max_tools_per_step}", str(max_tools_per_step))
    )


def _compact_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "candidate_id": c.get("candidate_id"),
            "name": c.get("name"),
            "org": c.get("org"),
            "email": c.get("email"),
            "overlap_score": c.get("overlap_score"),
            "fusion_score": c.get("fusion_score"),
            "hindex": c.get("hindex"),
            "activity_score": c.get("activity_score"),
            "pubs_last_2_years": c.get("pubs_last_2_years"),
            "research_keywords": (c.get("research_keywords") or [])[:8],
            "has_recent_papers": bool(c.get("recent_papers")),
        }
        for c in candidates
    ]


def _select_tool_calls(
    tool_calls: List[Dict[str, Any]],
    remaining_budget: int,
    max_tools_per_step: int,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """提交工具始终优先且不占探索预算；其余工具按预算截断。"""
    active: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    exploration_slots = max(0, min(max_tools_per_step, remaining_budget))
    submit_call = next(
        (call for call in tool_calls if call.get("name") == "submit_reviewers"),
        None,
    )
    if submit_call is not None:
        return [submit_call], [call for call in tool_calls if call is not submit_call]

    for tool_call in tool_calls:
        if exploration_slots > 0:
            active.append(tool_call)
            exploration_slots -= 1
        else:
            skipped.append(tool_call)

    return active, skipped


def _agent_temperature() -> float:
    raw = os.getenv("AGENT_STAGE3_TEMPERATURE", "0.1").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.1


def run_decision_agent(
    llm_payload: Dict[str, Any],
    api_code: Optional[str] = None,
) -> None:
    """Agent 决策：工具循环 → submit_reviewers → stage3_done。"""
    session_code = (api_code or "").strip() or init_api_code()
    candidates: List[Dict[str, Any]] = list(llm_payload.get("candidates") or [])
    pub_year = pub_year_range_last_n(int(os.getenv("AGENT_RECENT_PAPER_YEARS", "3")))
    max_steps = int(os.getenv("AGENT_STAGE3_MAX_STEPS", "4"))
    max_tool_calls = int(os.getenv("AGENT_STAGE3_MAX_TOOL_CALLS", "6"))
    max_tools_per_step = int(os.getenv("AGENT_STAGE3_MAX_TOOLS_PER_STEP", "3"))

    submitted_reviewers: Optional[List[ReviewerItem]] = None
    tool_call_count = 0

    @tool
    def get_candidate_detail(candidate_id: str = "", name: str = "") -> str:
        """从当前候选池查询学者完整信息（机构、keywords、overlap、recent_papers 等）。"""
        profile = _resolve_candidate(
            candidates,
            candidate_id=candidate_id,
            name=name,
        )
        if profile is None:
            return json.dumps(
                {"error": f"未找到唯一候选人：candidate_id={candidate_id}, name={name}"},
                ensure_ascii=False,
            )
        return json.dumps(profile, ensure_ascii=False, indent=2)

    @tool
    def fetch_author_publications(
        candidate_id: str = "",
        name: str = "",
        org: str = "",
    ) -> str:
        """从 CSCD 拉取候选人近年论文；优先传 candidate_id，org 仅兼容旧调用。"""
        profile = _resolve_candidate(
            candidates,
            candidate_id=candidate_id,
            name=name,
        )
        if profile is None:
            return json.dumps(
                {"error": f"未找到唯一候选人：candidate_id={candidate_id}, name={name}"},
                ensure_ascii=False,
            )
        canonical_id = str(profile.get("candidate_id") or "").strip()
        canonical_name = str(profile.get("name") or "").strip()
        canonical_org = str(profile.get("org") or "").strip()
        response = fetch_author_info_with_memory(
            author=canonical_name,
            org=canonical_org,
            pub_year=pub_year,
            page=1,
            limit=10,
            api_code=session_code,
            author_id=canonical_id,
            strict_identity=True,
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

        profile["recent_papers"] = papers

        return json.dumps(
            {
                "candidate_id": canonical_id,
                "name": canonical_name,
                "paper_count": len(papers),
                "papers": papers,
            },
            ensure_ascii=False,
            indent=2,
        )

    def _submit_reviewers_impl(reviewers: List[ReviewerItem]) -> str:
        nonlocal submitted_reviewers
        try:
            submitted_reviewers = validate_and_normalize_reviewers(
                reviewers,
                candidates,
            )
        except ValueError as exc:
            return f"提交失败：{exc}"
        payload = ScreeningOutput(reviewers=submitted_reviewers)
        emit("stage3_result", {"chunk": payload.model_dump_json(indent=2)})
        return "提交成功，任务完成。"

    submit_reviewers = StructuredTool.from_function(
        func=_submit_reviewers_impl,
        name="submit_reviewers",
        description="提交最终审稿人名单（3–5 人），调用后任务结束。",
        args_schema=ScreeningOutput,
    )

    tools = [get_candidate_detail, fetch_author_publications, submit_reviewers]
    tools_by_name = {item.name: item for item in tools}
    llm = _build_llm(
        streaming=False,
        json_mode=False,
        temperature=_agent_temperature(),
    ).bind_tools(tools)

    paper = llm_payload.get("paper") or {}
    meta = llm_payload.get("pipeline_meta") or {}
    initial_payload = {
        "paper": paper,
        "pipeline_meta": meta,
        "candidates_summary": _compact_candidates(candidates),
        "instruction": (
            f"请审阅候选人，在 {max_steps} 轮 / {max_tool_calls} 次探索工具调用预算内完成精筛，"
            "最后必须调用 submit_reviewers 提交 3–5 位审稿人。禁止冗长文字输出。"
        ),
        "budget": {
            "max_steps": max_steps,
            "max_tool_calls": max_tool_calls,
            "max_tools_per_step": max_tools_per_step,
        },
    }

    emit(
        "stage3_thinking",
        {
            "thinking": {
                "summary": (
                    f"阶段三 Agent 模式：对 {len(candidates)} 位候选人启动 ReAct 决策"
                    f"（最多 {max_steps} 轮 / {max_tool_calls} 次探索工具调用）。"
                    "可用工具：get_candidate_detail、fetch_author_publications、submit_reviewers。"
                ),
            },
        },
    )

    messages: List[Any] = [
        SystemMessage(
            content=load_agent_prompt(
                max_steps=max_steps,
                max_tool_calls=max_tool_calls,
                max_tools_per_step=max_tools_per_step,
            )
        ),
        HumanMessage(content=json.dumps(initial_payload, ensure_ascii=False, indent=2)),
    ]

    for step in range(1, max_steps + 1):
        ai_msg: AIMessage = llm.invoke(messages)
        messages.append(ai_msg)

        tool_calls = ai_msg.tool_calls or []
        if not tool_calls:
            if submitted_reviewers is not None:
                break
            if step >= max_steps:
                break
            messages.append(
                HumanMessage(content="请直接调用 submit_reviewers 提交最终审稿人名单。")
            )
            continue

        remaining_budget = max(0, max_tool_calls - tool_call_count)
        all_tool_calls = list(tool_calls)
        active_calls, skipped_calls = _select_tool_calls(
            all_tool_calls,
            remaining_budget,
            max_tools_per_step,
        )
        active_exploration_count = sum(
            call.get("name") != "submit_reviewers" for call in active_calls
        )

        for tool_call in active_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args") or {}
            tool_id = tool_call.get("id") or f"call-{step}"
            if tool_name != "submit_reviewers":
                tool_call_count += 1

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
                try:
                    result = str(tool_fn.invoke(tool_args))
                except (ValidationError, TypeError, ValueError) as exc:
                    result = f"工具执行失败，请修正参数：{exc}"

            messages.append(ToolMessage(content=result, tool_call_id=tool_id))

        for tool_call in skipped_calls:
            tool_id = tool_call.get("id") or f"skip-{step}"
            messages.append(
                ToolMessage(
                    content="工具调用因提交优先或探索预算限制被跳过。",
                    tool_call_id=tool_id,
                )
            )

        if skipped_calls and submitted_reviewers is None:
            messages.append(
                HumanMessage(
                    content=(
                        f"本轮执行了 {active_exploration_count} 次探索调用（预算限制）。"
                        "请基于已有信息尽快调用 submit_reviewers。"
                    )
                )
            )

        if submitted_reviewers is not None:
            break

        if tool_call_count >= max_tool_calls and submitted_reviewers is None:
            messages.append(
                HumanMessage(
                    content="工具调用预算已用尽，请立即调用 submit_reviewers 提交最终名单。"
                )
            )

    if not submitted_reviewers:
        raise ValueError("Agent 未在步数限制内成功调用 submit_reviewers")

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
                for item in submitted_reviewers
                if item.name.strip()
            ],
        },
    )
