"""关键词提炼：基于论文标题、摘要与原始关键词，提炼适合专家检索的关键词。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agent.chain import _build_llm, _extract_json

_TARGET_KEYWORD_COUNT = 3

_SYSTEM_PROMPT = """你是 CSCD 审稿人推荐系统的关键词提炼助手。

## 任务
根据论文标题、摘要与原始关键词，提炼出恰好 3 个中文检索关键词，供 CSCD 学者检索接口召回候选审稿人。

## 硬性数量约束（必须遵守）
- keywords 数组长度必须恰好为 3，不多不少。
- 禁止输出 1、2、4 个或更多。
- 同一概念只保留一个词；按检索价值从高到低排序。

## 粒度原则（最重要）
走「领域中位」：不要太垂直，也不要太宽泛。

太垂直（禁止）：
- 仅少数人写进研究方向的细分说法、论文私有方法变体、数据集名、指标名、过长复合短语
- 例：变分数阶混沌有限时间自适应滑模、Dice系数、BraTS2021、融合注意力的U-Net改进

太宽泛（禁止）：
- 跨学科都能匹配的空词
- 例：深度学习、机器学习、人工智能、神经网络、优化、建模、研究、分析、应用

合适粒度：
- 领域内常见、能筛出同一子方向同行的规范术语
- 例：医学图像分割、混沌同步、滑模控制、半监督学习、图像分割

## 三个词的分工
第 1 词：研究对象或问题域（谁/什么对象）
第 2 词：核心任务或现象（做什么）
第 3 词：方法族或技术路线（怎么做；用方法族名，不用论文私有变体）

若原始词已处于中位粒度，可直接保留并补齐到恰好 3 个；不要为了“更专业”而过度细化。
单个关键词一般 2–8 个汉字，避免生造长串。

## 重试场景
若输入中带有「上次检索关键词」与「重试原因」，说明上次召回入选人数不足。
此时在仍输出恰好 3 个词的前提下，略放宽粒度或替换过细词，以提高召回，但仍禁止落到空泛大词。
尽量避免与上次关键词完全相同。

## 输出格式
只输出 JSON，不要输出其他文字：
{
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "reasoning": "一句话说明三个词分别覆盖对象/任务/方法，以及如何把过细或过宽的词调到中位粒度"
}
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
    }
    if previous_keywords.strip():
        payload["上次检索关键词"] = previous_keywords.strip()
        payload["重试原因"] = (
            retry_note.strip()
            or "上次关键词召回后阶段一入选专家不足，请在仍输出恰好 3 个词的前提下略放宽粒度"
        )

    llm = _build_llm(streaming=False, json_mode=True, temperature=0.2)
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
        "reasoning": str(data.get("reasoning", "")).strip(),
    }
