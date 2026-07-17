"""关键词提炼：基于论文标题、摘要与原始关键词，提炼适合专家检索的关键词。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agent.chain import _build_llm, _extract_json

_SYSTEM_PROMPT = """你是学术审稿人推荐系统的关键词提炼助手。

系统会用关键词调用 CSCD 学者检索接口召回候选审稿人，因此关键词粒度直接决定召回效果。
请根据论文标题、摘要和作者提供的原始关键词，提炼出 3-6 个最适合检索同行专家的中文关键词。

粒度原则（最重要）：走「领域中位」——不要太垂直，也不要太宽泛。
- 太垂直（应避免）：仅少数人会写进研究方向的细分说法、论文特有的方法变体、数据集名、指标名、过长复合短语
  例：变分数阶混沌有限时间自适应滑模、Dice系数、BraTS2021、融合注意力的U-Net改进
- 太宽泛（应避免）：几乎任何学科都能匹配的空词
  例：深度学习、机器学习、人工智能、神经网络、优化、建模、研究、分析、应用
- 合适粒度：领域内常见、能筛出同一子方向同行的规范术语
  例：医学图像分割、混沌同步、滑模控制、半监督学习、图像分割

提炼要求：
1. 优先改写/收敛原始关键词到中位粒度，必要时从标题与摘要补充 1-2 个同级词；
2. 尽量覆盖：研究对象/问题、核心任务、方法族（方法用“族”名，不用论文私有变体）；
3. 单个关键词一般 2-8 个字，避免生造长串；
4. 同一概念只保留一个词，按检索价值从高到低排序；
5. 若原始词已合适则保留，不要为了“看起来更专业”而过度细化。

只输出 JSON，格式如下：
{
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "reasoning": "一句话说明如何把过细/过宽的词调到中位粒度"
}"""


def refine_keywords(
    title: str,
    abstract: str = "",
    keywords: str = "",
) -> Dict[str, Any]:
    """调用 LLM 提炼关键词，返回 {"keywords": [...], "reasoning": "..."}。"""
    payload = {
        "论文标题": title.strip(),
        "论文摘要": abstract.strip() or "（未提供）",
        "原始关键词": keywords.strip() or "（未提供）",
    }

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
    if not cleaned:
        raise ValueError("关键词提炼结果为空")

    return {
        "keywords": cleaned[:6],
        "reasoning": str(data.get("reasoning", "")).strip(),
    }
