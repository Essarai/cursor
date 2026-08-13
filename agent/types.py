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
    pubs_last_5_years: int = 0
    research_keywords: List[str] = field(default_factory=list)
    subject: str = ""
    position: str = ""
    resume: str = ""
    overlap_score: float = 0.0


@dataclass
class RecentPaper:
    title: str
    year: str
    abstract: str
    keywords: str = ""


@dataclass
class EnrichedCandidate:
    id: str
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
    position: str = ""
    fusion_score: float = 0.0


def reviewer_to_dict(candidate: ReviewerCandidate) -> Dict[str, Any]:
    return {
        "id": candidate.id,
        "name": candidate.name,
        "org": candidate.org,
        "email": candidate.email,
        "hindex": candidate.hindex,
        "pubs_last_5_years": candidate.pubs_last_5_years,
        "research_keywords": candidate.research_keywords,
        "subject": candidate.subject,
        "position": candidate.position,
        "resume": candidate.resume,
        "overlap_score": candidate.overlap_score,
    }


def reviewer_from_dict(data: Dict[str, Any]) -> ReviewerCandidate:
    return ReviewerCandidate(
        id=str(data.get("id") or ""),
        name=str(data.get("name") or "").strip(),
        org=str(data.get("org") or "").strip(),
        email=str(data.get("email") or "").strip(),
        hindex=float(data.get("hindex") or 0.0),
        pubs_last_5_years=int(float(data.get("pubs_last_5_years") or 0)),
        research_keywords=list(data.get("research_keywords") or []),
        subject=str(data.get("subject") or "").strip(),
        position=str(data.get("position") or "").strip(),
        resume=str(data.get("resume") or "").strip(),
        overlap_score=float(data.get("overlap_score") or 0.0),
    )


def _normalize_resume(raw: Any) -> str:
    text = str(raw or "").replace(";;", "\n").replace("\r\n", "\n")
    lines = [line.strip() for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines if line and line.lower() != "null")
    return cleaned.strip()


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

    papers_raw = raw.get("numAllpaper")
    try:
        pubs_last_5_years = (
            int(float(papers_raw))
            if papers_raw not in (None, "", "null")
            else 0
        )
    except (TypeError, ValueError):
        pubs_last_5_years = 0

    return ReviewerCandidate(
        id=str(raw.get("id") or ""),
        name=str(raw.get("authorName") or "").strip(),
        org=str(raw.get("org") or "").strip(),
        email=str(raw.get("email") or "").strip(),
        hindex=hindex,
        pubs_last_5_years=pubs_last_5_years,
        research_keywords=keywords,
        subject=str(raw.get("subject") or "").strip(),
        position=str(raw.get("position") or "").strip(),
        resume=_normalize_resume(raw.get("resume")),
    )
