"""学者活跃度等指标算法化计算。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.tools import fetch_author_info_with_memory
from agent.types import EnrichedCandidate, RecentPaper, ReviewerCandidate

ACTIVITY_PUB_WEIGHT = 0.6
ACTIVITY_H_WEIGHT = 0.4


def current_year() -> int:
    return datetime.now().year


def pub_year_range_last_n(years: int) -> str:
    end = current_year()
    start = end - years + 1
    return f"{start}-{end}"


def _parse_year(article: Dict[str, Any]) -> Optional[int]:
    issue = article.get("issue") or {}
    year_raw = issue.get("year")
    if not year_raw:
        return None
    try:
        return int(str(year_raw)[:4])
    except ValueError:
        return None


def count_pubs_last_2_years(articles: List[Dict[str, Any]]) -> int:
    threshold = current_year() - 1
    return sum(
        1
        for article in articles
        if (year := _parse_year(article)) is not None and year >= threshold
    )


def activity_score(pubs_last_2_years: int, hindex: float) -> float:
    return round(pubs_last_2_years * ACTIVITY_PUB_WEIGHT + hindex * ACTIVITY_H_WEIGHT, 2)


def _to_recent_paper(article: Dict[str, Any]) -> RecentPaper:
    issue = article.get("issue") or {}
    return RecentPaper(
        title=str(article.get("title") or "").strip(),
        year=str(issue.get("year") or "").strip(),
        abstract=str(article.get("abstract") or "").strip(),
        keywords=str(article.get("keywords") or "").strip(),
    )


def fetch_author_articles(
    author: str,
    org: str,
    pub_year: str,
    api_code: Optional[str] = None,
) -> Dict[str, Any]:
    return fetch_author_info_with_memory(
        author=author,
        org=org,
        pub_year=pub_year,
        page=1,
        limit=20,
        api_code=api_code,
    )


def enrich_candidate(
    candidate: ReviewerCandidate,
    pub_year: str,
    api_code: Optional[str] = None,
) -> EnrichedCandidate:
    response = fetch_author_articles(candidate.name, candidate.org, pub_year, api_code)
    articles: List[Dict[str, Any]] = []
    if response.get("success"):
        articles = (response.get("result") or {}).get("data") or []

    pubs_last_2 = count_pubs_last_2_years(articles)
    score = activity_score(pubs_last_2, candidate.hindex)
    recent_papers = [_to_recent_paper(a) for a in articles[:10] if a.get("title")]

    email = candidate.email
    if not email:
        for article in articles:
            for author in article.get("authors") or []:
                if author.get("authorName") == candidate.name and author.get("email"):
                    email = str(author.get("email"))
                    break
            if email:
                break

    return EnrichedCandidate(
        name=candidate.name,
        org=candidate.org,
        email=email,
        hindex=candidate.hindex,
        activity_score=score,
        pubs_last_2_years=pubs_last_2,
        research_keywords=candidate.research_keywords,
        recent_papers=recent_papers,
        overlap_score=candidate.overlap_score,
        subject=candidate.subject,
    )


def enriched_to_llm_dict(candidate: EnrichedCandidate) -> Dict[str, Any]:
    return {
        "name": candidate.name,
        "org": candidate.org,
        "email": candidate.email,
        "hindex": candidate.hindex,
        "activity_score": candidate.activity_score,
        "pubs_last_2_years": candidate.pubs_last_2_years,
        "overlap_score": candidate.overlap_score,
        "subject": candidate.subject,
        "research_keywords": candidate.research_keywords,
        "recent_papers": [
            {
                "title": p.title,
                "year": p.year,
                "abstract": p.abstract[:500] if p.abstract else "",
                "keywords": p.keywords,
            }
            for p in candidate.recent_papers
        ],
    }
