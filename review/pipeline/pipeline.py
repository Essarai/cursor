"""三阶段管线：阶段一/二 Python 硬过滤与补全。"""

from __future__ import annotations

from typing import Any, Dict, List

from cscd_client import CscdClient
from pipeline.filters import filter_coi, parse_keywords, select_highest_overlap
from pipeline.scoring import enrich_candidate, enriched_to_llm_dict, pub_year_range_last_n
from pipeline.types import EnrichedCandidate, PaperInput, ReviewerCandidate, parse_reviewer


def fetch_reviewers(client: CscdClient, keywords: str) -> List[ReviewerCandidate]:
    response = client.get_peer_reviewers(keywords)
    if not response.get("success"):
        message = response.get("message") or "getPeerReviewers 调用失败"
        raise RuntimeError(message)

    raw_list = response.get("result") or []
    return [parse_reviewer(item) for item in raw_list if item.get("authorName")]


def run_stage1(paper: PaperInput, client: CscdClient) -> Dict[str, Any]:
    all_candidates = fetch_reviewers(client, paper.keywords)
    after_coi = filter_coi(all_candidates, paper.author_org)
    paper_keywords = parse_keywords(paper.keywords)
    _all_ranked, selected_candidates = select_highest_overlap(
        after_coi,
        paper_keywords,
        paper.title,
    )

    return {
        "total_from_api": len(all_candidates),
        "after_coi": len(after_coi),
        "selected": selected_candidates,
        "coi_filtered_count": len(all_candidates) - len(after_coi),
    }


def run_stage2(
    candidates: List[ReviewerCandidate],
    client: CscdClient,
    recent_paper_years: int,
) -> List[EnrichedCandidate]:
    pub_year = pub_year_range_last_n(recent_paper_years)
    return [enrich_candidate(client, candidate, pub_year) for candidate in candidates]


def build_llm_payload(
    paper: PaperInput,
    enriched: List[EnrichedCandidate],
    stage1_meta: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "paper": {
            "title": paper.title,
            "keywords": parse_keywords(paper.keywords),
            "author_org": paper.author_org or None,
            "extra": paper.extra or None,
        },
        "pipeline_meta": {
            "total_from_api": stage1_meta["total_from_api"],
            "coi_filtered_count": stage1_meta["coi_filtered_count"],
            "stage1_selected_count": len(enriched),
        },
        "candidates": [enriched_to_llm_dict(c) for c in enriched],
    }


def run_pipeline(
    paper: PaperInput,
    client: CscdClient,
    recent_paper_years: int = 3,
) -> Dict[str, Any]:
    stage1 = run_stage1(paper, client)
    enriched = run_stage2(stage1["selected"], client, recent_paper_years)
    payload = build_llm_payload(paper, enriched, stage1)
    return {
        "stage1": stage1,
        "enriched": enriched,
        "llm_payload": payload,
    }
