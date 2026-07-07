"""硬性过滤与阶段一粗筛（Python 工程层）。"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from agent.types import ReviewerCandidate

_SPLIT_RE = re.compile(r"[;；,，、\n]+")


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
    expanded: set[str] = set()
    for token in tokens:
        token = token.strip().lower()
        if not token:
            continue
        expanded.add(token)
        for part in re.split(r"[/\s·]+", token):
            if len(part) >= 2:
                expanded.add(part)
    return expanded


def keyword_overlap_score(
    paper_keywords: Sequence[str],
    paper_title: str,
    reviewer_keywords: Sequence[str],
) -> float:
    paper_tokens = _expand_tokens(paper_keywords)
    title_lower = paper_title.strip().lower()
    for kw in paper_keywords:
        if kw and kw in title_lower:
            paper_tokens.add(kw)

    reviewer_tokens = _expand_tokens(reviewer_keywords)
    if not paper_tokens or not reviewer_tokens:
        return 0.0

    hits = 0
    for pt in paper_tokens:
        for rt in reviewer_tokens:
            if pt == rt or pt in rt or rt in pt:
                hits += 1
                break

    return hits / len(paper_tokens)


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
) -> tuple[List[ReviewerCandidate], List[ReviewerCandidate]]:
    """按重合度排序，并将重合度最高档的候选人全部选入阶段二。"""
    all_ranked = rank_candidates(candidates, paper_keywords, paper_title)
    if not all_ranked:
        return [], []

    max_overlap = max(c.overlap_score for c in all_ranked)
    selected = [c for c in all_ranked if c.overlap_score >= max_overlap]
    return all_ranked, selected
