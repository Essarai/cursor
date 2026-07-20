"""学者活跃度等指标计算。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from cscd_client import CscdClient
from pipeline.types import EnrichedCandidate, RecentPaper, ReviewerCandidate

ACTIVITY_PUB_WEIGHT = 0.6
ACTIVITY_H_WEIGHT = 0.4


def current_year() -> int:
    return datetime.now().year


def pub_year_range_last_n(years: int) -> str:
    end = current_year()
    start = end - years + 1
    return f"{start}-{end}"


def _parse_year(article: Dict[str, Any]) -> int | None:
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
    return round(
        pubs_last_2_years * ACTIVITY_PUB_WEIGHT + hindex * ACTIVITY_H_WEIGHT,
        2,
    )


def _to_recent_paper(article: Dict[str, Any]) -> RecentPaper:
    issue = article.get("issue") or {}
    return RecentPaper(
        title=str(article.get("title") or "").strip(),
        year=str(issue.get("year") or "").strip(),
        abstract=str(article.get("abstract") or "").strip(),
        keywords=str(article.get("keywords") or "").strip(),
    )


def fetch_author_articles(
    client: CscdClient,
    author: str,
    org: str,
    pub_year: str,
) -> Dict[str, Any]:
    response = client.search_articles(
        author=author,
        org=org or None,
        pub_year=pub_year,
        page=1,
        limit=20,
    )
    result = response.get("result") or {}
    total = result.get("total") or 0
    if response.get("success") and total == 0 and org.strip():
        response = client.search_articles(
            author=author,
            org=None,
            pub_year=pub_year,
            page=1,
            limit=20,
        )
    return response


def enrich_candidate(
    client: CscdClient,
    candidate: ReviewerCandidate,
    pub_year: str,
) -> EnrichedCandidate:
    response = fetch_author_articles(client, candidate.name, candidate.org, pub_year)
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
