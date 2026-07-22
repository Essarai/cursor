"""硬性过滤与阶段一粗筛（Python 工程层）。"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from agent.types import ReviewerCandidate

_SPLIT_RE = re.compile(r"[;；,，、\n]+")
_PART_SPLIT_RE = re.compile(r"[/\s·]+")

STAGE1_MIN_OVERLAP = float(os.getenv("AGENT_STAGE1_MIN_OVERLAP", "0.5"))
STAGE1_MAX_SELECTED = int(os.getenv("AGENT_STAGE1_MAX_SELECTED", "25"))
# 多词聚合：最佳命中权重 + 均值权重（需和为 1）
_OVERLAP_MAX_WEIGHT = float(os.getenv("AGENT_OVERLAP_MAX_WEIGHT", "0.6"))
_OVERLAP_MEAN_WEIGHT = 1.0 - _OVERLAP_MAX_WEIGHT

# 分层计分
_EXACT_SCORE = 1.0
_SUBSTRING_SCORE = 0.7
_MIN_SUBSTRING_LEN = 2
_MIN_SUBSTRING_COVERAGE = 0.5  # 较短词长度 / 较长词长度，抑制「同步」命中「自适应同步」
_MIN_BIGRAM_TOKEN_LEN = 3  # bigram 软匹配要求两侧都足够长
_BIGRAM_FLOOR = 0.2
_BIGRAM_SCORE_MIN = 0.3
_BIGRAM_SCORE_MAX = 0.65


def parse_keywords(text: str) -> List[str]:
    return [p.strip().lower() for p in _SPLIT_RE.split(text.strip()) if p.strip()]


def _normalize_org(org: str) -> str:
    return re.sub(r"\s+", "", org.strip().lower())


def is_coi_conflict(candidate_org: str, author_org: str) -> bool:
    """机构熔断：同一单位或上下级学院视为利益冲突。"""
    if not author_org.strip() or not candidate_org.strip():
        return False

    left = _normalize_org(author_org)
    right = _normalize_org(candidate_org)
    if not left or not right:
        return False

    return left in right or right in left


def filter_coi(
    candidates: Sequence[ReviewerCandidate],
    author_org: str,
) -> List[ReviewerCandidate]:
    if not author_org.strip():
        return list(candidates)
    return [c for c in candidates if not is_coi_conflict(c.org, author_org)]


def _expand_tokens(tokens: Iterable[str]) -> set[str]:
    """保留整词，并按 /、空格、· 拆出长度≥2 的片段。"""
    expanded: set[str] = set()
    for token in tokens:
        token = token.strip().lower()
        if not token:
            continue
        expanded.add(token)
        for part in _PART_SPLIT_RE.split(token):
            if len(part) >= 2:
                expanded.add(part)
    return expanded


def _keyword_terms(keywords: Sequence[str]) -> List[str]:
    """有序去重的关键词列表（含 / 等分隔的片段）。"""
    terms: List[str] = []
    seen: set[str] = set()
    for token in keywords:
        token = str(token).strip().lower()
        if not token:
            continue
        parts = [token, *_PART_SPLIT_RE.split(token)]
        for part in parts:
            part = part.strip()
            if len(part) < 2 or part in seen:
                continue
            seen.add(part)
            terms.append(part)
    return terms


def _char_bigrams(text: str) -> set[str]:
    t = text.strip().lower()
    if not t:
        return set()
    if len(t) < 2:
        return {t}
    return {t[i : i + 2] for i in range(len(t) - 1)}


def _bigram_jaccard(left: str, right: str) -> float:
    a = _char_bigrams(left)
    b = _char_bigrams(right)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


def _bigram_soft_score(jaccard: float) -> float:
    if jaccard < _BIGRAM_FLOOR:
        return 0.0
    # 将 [floor, 1] 线性映射到 [BIGRAM_SCORE_MIN, BIGRAM_SCORE_MAX]
    span = 1.0 - _BIGRAM_FLOOR
    ratio = (jaccard - _BIGRAM_FLOOR) / span if span > 0 else 0.0
    return _BIGRAM_SCORE_MIN + (_BIGRAM_SCORE_MAX - _BIGRAM_SCORE_MIN) * ratio


def token_pair_score(paper_token: str, reviewer_token: str) -> float:
    """单个论文词 vs 单个审稿人词的分层相似度。"""
    pt = paper_token.strip().lower()
    rt = reviewer_token.strip().lower()
    if not pt or not rt:
        return 0.0
    if pt == rt:
        return _EXACT_SCORE

    shorter, longer = (pt, rt) if len(pt) <= len(rt) else (rt, pt)
    coverage = len(shorter) / len(longer) if longer else 0.0
    if (
        len(shorter) >= _MIN_SUBSTRING_LEN
        and coverage >= _MIN_SUBSTRING_COVERAGE
        and shorter in longer
    ):
        return _SUBSTRING_SCORE

    # 两侧都够长才做 bigram，避免双字短词靠局部字面重合刷分
    if len(pt) >= _MIN_BIGRAM_TOKEN_LEN and len(rt) >= _MIN_BIGRAM_TOKEN_LEN:
        return _bigram_soft_score(_bigram_jaccard(pt, rt))
    return 0.0


def aggregate_term_scores(scores: Sequence[float]) -> float:
    """将各论文词的最佳命中分聚合成总重合度。

    ``0.6 * max + 0.4 * mean``：
    - 只精确命中 1/2 词 → 0.80（不再 soft-OR 拉满 1.0）
    - 一词精确 + 一词子串 → ~0.94
    - 两词都精确 → 1.0
    - 三词只命中专有词 → ~0.73（仍高于入选阈值，不被均值拖死）
    """
    if not scores:
        return 0.0
    clamped = [max(0.0, min(1.0, float(score))) for score in scores]
    max_s = max(clamped)
    mean_s = sum(clamped) / len(clamped)
    return _OVERLAP_MAX_WEIGHT * max_s + _OVERLAP_MEAN_WEIGHT * mean_s


def keyword_overlap_score(
    paper_keywords: Sequence[str],
    paper_title: str,
    reviewer_keywords: Sequence[str],
) -> float:
    """
    论文关键词 vs 审稿人研究方向的精细重合度。

    对每个论文词取与审稿人词的最大分层分，再按「最佳命中 + 整体覆盖」聚合：
    - 精确相等 → 1.0
    - 互为子串，且较短词长度占比 ≥ 0.5 → 0.7
      （「自适应」可命中「自适应同步」，「同步」不能）
    - 两侧词长 ≥ 3 且字 bigram Jaccard ≥ 0.2 → 映射到 0.30–0.65
    - 聚合：``0.6 * max(s_i) + 0.4 * mean(s_i)``，避免单点 1.0 或均值过低
    """
    paper_terms = _keyword_terms(paper_keywords)
    title_lower = paper_title.strip().lower()
    if title_lower:
        for kw in paper_keywords:
            kw = str(kw).strip().lower()
            if kw and kw in title_lower and kw not in paper_terms:
                paper_terms.append(kw)

    reviewer_terms = list(_expand_tokens(reviewer_keywords))
    if not paper_terms or not reviewer_terms:
        return 0.0

    scores: List[float] = []
    for pt in paper_terms:
        best = max(token_pair_score(pt, rt) for rt in reviewer_terms)
        scores.append(best)
    return aggregate_term_scores(scores)


def rank_candidates(
    candidates: Sequence[ReviewerCandidate],
    paper_keywords: Sequence[str],
    paper_title: str,
) -> List[ReviewerCandidate]:
    """关键词重合度 + H 指数加权，返回完整排序列表。"""
    if not candidates:
        return []

    max_h = max((c.hindex for c in candidates), default=0.0) or 1.0
    scored: List[tuple[float, ReviewerCandidate]] = []

    for candidate in candidates:
        overlap = keyword_overlap_score(
            paper_keywords,
            paper_title,
            candidate.research_keywords,
        )
        h_norm = candidate.hindex / max_h
        composite = overlap * 0.7 + h_norm * 0.3
        candidate.overlap_score = round(overlap, 4)
        scored.append((composite, candidate))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored]


def select_highest_overlap(
    candidates: Sequence[ReviewerCandidate],
    paper_keywords: Sequence[str],
    paper_title: str,
) -> Tuple[List[ReviewerCandidate], List[ReviewerCandidate], Dict[str, Any]]:
    """按重合度排序，overlap ≥ 阈值入选；超过上限则取综合排名前 N。"""
    all_ranked = rank_candidates(candidates, paper_keywords, paper_title)
    if not all_ranked:
        return [], [], {
            "min_overlap": STAGE1_MIN_OVERLAP,
            "max_selected": STAGE1_MAX_SELECTED,
            "max_overlap": 0.0,
            "capped": False,
            "passed_min_overlap_count": 0,
        }

    max_overlap = max(c.overlap_score for c in all_ranked)
    passed = [c for c in all_ranked if c.overlap_score >= STAGE1_MIN_OVERLAP]
    capped = len(passed) > STAGE1_MAX_SELECTED
    selected = all_ranked[:STAGE1_MAX_SELECTED] if capped else passed

    return all_ranked, selected, {
        "min_overlap": STAGE1_MIN_OVERLAP,
        "max_selected": STAGE1_MAX_SELECTED,
        "max_overlap": max_overlap,
        "capped": capped,
        "passed_min_overlap_count": len(passed),
    }
