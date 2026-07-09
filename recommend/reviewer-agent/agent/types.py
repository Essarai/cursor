"""Agent 数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PaperInput:
    title: str
    keywords: str
    author_org: str = ""
    extra: str = ""


@dataclass
class ReviewerCandidate:
    id: str
    name: str
    org: str
    email: str
    hindex: float
    research_keywords: List[str] = field(default_factory=list)
    subject: str = ""
    overlap_score: float = 0.0


@dataclass
class RecentPaper:
    title: str
    year: str
    abstract: str
    keywords: str = ""


@dataclass
class EnrichedCandidate:
    name: str
    org: str
    email: str
    hindex: float
    activity_score: float
    pubs_last_2_years: int
    research_keywords: List[str]
    recent_papers: List[RecentPaper]
    overlap_score: float = 0.0
    subject: str = ""


def parse_reviewer(raw: Dict[str, Any]) -> ReviewerCandidate:
    keyword_text = raw.get("keyword") or ""
    keywords = [
        k.strip()
        for k in keyword_text.replace(";;", ";").split(";")
        if k.strip()
    ]
    hindex_raw = raw.get("hindex")
    try:
        hindex = float(hindex_raw) if hindex_raw not in (None, "", "null") else 0.0
    except (TypeError, ValueError):
        hindex = 0.0

    return ReviewerCandidate(
        id=str(raw.get("id") or ""),
        name=str(raw.get("authorName") or "").strip(),
        org=str(raw.get("org") or "").strip(),
        email=str(raw.get("email") or "").strip(),
        hindex=hindex,
        research_keywords=keywords,
        subject=str(raw.get("subject") or "").strip(),
    )
