"""关键词提炼：基于论文标题、摘要与原始关键词，提炼适合专家检索的关键词。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agent.chain import _build_llm, _extract_json

_TARGET_KEYWORD_COUNT = 3

_SYSTEM_PROMPT = """你是 CSCD 审稿人推荐系统的关键词提炼助手。

## 任务
根据论文标题、摘要与原始关键词，提炼恰好 3 个中文检索关键词，供 CSCD 学者检索。

## 输出（必须严格遵守）
- 只输出一个 JSON 对象，不要输出任何其他文字。
- 禁止输出思考过程、分析、解释、Markdown、代码块。
- 禁止输出 reasoning / explanation / 说明 等字段。
- JSON 格式固定为：
{"keywords":["关键词1","关键词2","关键词3"]}

## 数量与粒度
- keywords 长度必须恰好为 3。
- 同一概念只保留一个词；按检索价值从高到低排序。
- 走领域中位粒度：不要过细（论文私有方法/指标/数据集），也不要过宽（深度学习、优化、研究等空词）。
- 三词分工：对象或问题域 / 核心任务或现象 / 方法族。
- 单个词一般 2–8 个汉字。

## 重试
若输入含「上次检索关键词」，在仍输出恰好 3 个词的前提下略放宽粒度，尽量与上次不完全相同。
"""


def refine_keywords(
    title: str,
    abstract: str = "",
    keywords: str = "",
    previous_keywords: str = "",
    retry_note: str = "",
) -> Dict[str, Any]:
    """调用 LLM 提炼关键词，返回恰好 3 个关键词。"""
    payload = {
        "论文标题": title.strip(),
        "论文摘要": abstract.strip() or "（未提供）",
        "原始关键词": keywords.strip() or "（未提供）",
        "数量要求": f"必须恰好输出 {_TARGET_KEYWORD_COUNT} 个关键词",
        "输出要求": '只返回 {"keywords":["...","...","..."]}，不要 reasoning',
    }
    if previous_keywords.strip():
        payload["上次检索关键词"] = previous_keywords.strip()
        payload["重试原因"] = (
            retry_note.strip()
            or "上次关键词召回后阶段一入选专家不足，请在仍输出恰好 3 个词的前提下略放宽粒度"
        )

    llm = _build_llm(
        streaming=False,
        json_mode=True,
        temperature=0.2,
        disable_thinking=True,
    )
    message = llm.invoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2)),
        ]
    )

    data = _extract_json(str(message.content))
    if not isinstance(data, dict):
        raise ValueError(f"关键词提炼输出格式错误: {data!r}")

    raw_keywords = data.get("keywords")
    if not isinstance(raw_keywords, list):
        raise ValueError(f"关键词提炼缺少 keywords 列表: {data!r}")

    cleaned: List[str] = []
    for item in raw_keywords:
        word = str(item).strip().strip(",，")
        if word and word not in cleaned:
            cleaned.append(word)

    if len(cleaned) < _TARGET_KEYWORD_COUNT:
        raise ValueError(
            f"关键词提炼数量不足：期望 {_TARGET_KEYWORD_COUNT} 个，实际 {len(cleaned)} 个"
        )

    return {
        "keywords": cleaned[:_TARGET_KEYWORD_COUNT],
        "reasoning": "",
    }
