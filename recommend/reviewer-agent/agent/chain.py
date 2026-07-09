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


def _build_llm(*, streaming: bool = False) -> ChatOpenAI:
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
    if not streaming and os.getenv("LLM_JSON_MODE", "1").strip() not in (
        "0",
        "false",
        "False",
    ):
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

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
        name = str(candidate.get("name") or "").strip()
        if name:
            index[name] = candidate
    return index


def _merge_reviewer_profile(
    item: ReviewerItem,
    profile: Dict[str, Any] | None,
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
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
    """流式输出阶段三思考过程与精筛 JSON（NDJSON 事件）。"""
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
    _to_recommendations(parsed)

    profiles = _candidate_index(llm_payload.get("candidates") or [])

    emit(
        "stage3_done",
        {
            "reviewers": [
                _merge_reviewer_profile(item, profiles.get(item.name.strip()))
                for item in parsed.reviewers
                if item.name.strip()
            ],
        },
    )
