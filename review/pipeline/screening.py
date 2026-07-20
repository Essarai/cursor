"""阶段三：LangChain 语义精筛链（Prompt | LLM，无工具调用）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from json_repair import repair_json
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from pipeline.golden_cases import load_golden_cases

PLACEHOLDER = "[Historical_Golden_Cases]"
_THINK_END = "\u003c/redacted_thinking\u003e"
_THINK_START = "\u003credacted_thinking\u003e"
_THINK_END_ALT = "\u003c/think\u003e"
_THINK_START_ALT = "\u003cthink\u003e"


class ReviewerItem(BaseModel):
    name: str
    email: str
    matched_paper: str
    reason: str


class ScreeningOutput(BaseModel):
    reviewers: List[ReviewerItem]


def load_system_prompt(template_path: str, golden_cases_path: Path | None = None) -> str:
    template = Path(template_path).read_text(encoding="utf-8").strip()
    golden = load_golden_cases(golden_cases_path).strip()
    if not golden:
        golden = "（暂无历史黄金案例，请仅依据候选人数据与论文信息进行精筛。）"
    return template.replace(PLACEHOLDER, golden)


def _build_llm(minimax_config: dict[str, Any]) -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": minimax_config["model"],
        "api_key": minimax_config["api_key"],
        "base_url": minimax_config["base_url"],
        "temperature": minimax_config.get("temperature", 0.2),
    }
    if minimax_config.get("json_mode", True):
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


def build_screening_chain(system_prompt: str, minimax_config: dict[str, Any]):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}"),
            (
                "human",
                "以下 JSON 为阶段一/二处理后的候选数据。"
                "请严格按 system 要求，仅输出一个 JSON 对象，"
                "不要 Markdown、不要代码块、不要解释文字。\n\n{input_json}",
            ),
        ]
    ).partial(system_prompt=system_prompt)
    return prompt | _build_llm(minimax_config) | StrOutputParser()


def run_semantic_screening(
    llm_payload: Dict[str, Any],
    system_prompt: str,
    minimax_config: dict[str, Any],
) -> Dict[str, Any]:
    chain = build_screening_chain(system_prompt, minimax_config)
    input_json = json.dumps(llm_payload, ensure_ascii=False, indent=2)

    last_error: Exception | None = None
    for attempt in range(2):
        payload = input_json
        if attempt == 1:
            payload = (
                input_json
                + "\n\n【再次提醒】只输出 JSON 对象，格式为 "
                + '{"reviewers":[{"name":"","email":"","matched_paper":"","reason":""}]}'
            )
        try:
            raw = chain.invoke({"input_json": payload})
            parsed = _parse_screening_output(raw)
            return {
                "reviewers": [
                    {
                        "name": item.name.strip(),
                        "email": item.email.strip(),
                        "matched_paper": item.matched_paper.strip(),
                        "reason": item.reason.strip(),
                    }
                    for item in parsed.reviewers
                    if item.name.strip()
                ]
            }
        except (ValueError, Exception) as exc:
            last_error = exc
            continue

    raise ValueError(f"阶段三精筛失败: {last_error}")
