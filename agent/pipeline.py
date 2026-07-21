"""两阶段管线编排：Python 硬过滤 + 数据补全。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from agent.emit import emit
from agent.filters import filter_coi, parse_keywords, select_highest_overlap
from agent.tools import fetch_reviewers_with_memory
from agent.scoring import (
    FUSION_ACTIVITY_WEIGHT,
    FUSION_OVERLAP_WEIGHT,
    enrich_candidate,
    enriched_to_llm_dict,
    pub_year_range_last_n,
    rerank_enriched_candidates,
)
from agent.types import EnrichedCandidate, PaperInput, ReviewerCandidate, parse_reviewer
from cscd.client import init_api_code

RECENT_PAPER_YEARS = int(os.getenv("AGENT_RECENT_PAPER_YEARS", "3"))


def fetch_reviewers(keywords: str, api_code: Optional[str] = None) -> List[ReviewerCandidate]:
    response = fetch_reviewers_with_memory(keywords, api_code)
    if not response.get("success"):
        message = response.get("message") or "getPeerReviewers 调用失败"
        raise RuntimeError(message)

    raw_list = response.get("result") or []
    return [parse_reviewer(item) for item in raw_list if item.get("authorName")]


def _expert_dict(candidate: ReviewerCandidate, rank: int, *, selected: bool) -> Dict[str, Any]:
    keywords = candidate.research_keywords[:8]
    return {
        "rank": rank,
        "id": candidate.id,
        "name": candidate.name,
        "org": candidate.org,
        "email": candidate.email,
        "hindex": candidate.hindex,
        "subject": candidate.subject,
        "overlap_score": candidate.overlap_score,
        "research_keywords": keywords,
        "selected": selected,
        "reason": (
            f"关键词重合度 {candidate.overlap_score:.2f}，H 指数 {candidate.hindex:.0f}，"
            f"综合排名第 {rank}"
        ),
    }


def _build_stage1_thinking(
    paper: PaperInput,
    all_candidates: List[ReviewerCandidate],
    after_coi: List[ReviewerCandidate],
    all_ranked: List[ReviewerCandidate],
    selected_candidates: List[ReviewerCandidate],
    stage1_meta: Dict[str, Any],
) -> Dict[str, Any]:
    coi_count = len(all_candidates) - len(after_coi)
    max_overlap = stage1_meta.get("max_overlap", 0.0)
    min_overlap = stage1_meta.get("min_overlap", 0.5)
    max_selected = stage1_meta.get("max_selected", 25)
    passed_count = stage1_meta.get("passed_min_overlap_count", len(selected_candidates))
    capped = stage1_meta.get("capped", False)

    lines = [
        f"调用 get_recommend_reviewers，关键词：{paper.keywords}，返回 {len(all_candidates)} 位候选人。",
    ]
    if paper.author_org.strip():
        lines.append(
            f"COI 机构熔断：原作者机构「{paper.author_org}」，剔除同单位 {coi_count} 人，剩余 {len(after_coi)} 人。"
        )
    else:
        lines.append("未填写原作者机构，跳过 COI 熔断。")

    cap_note = f"，超过上限 {max_selected} 人，按综合分截取 Top {max_selected}" if capped else ""
    lines.append(
        f"对 {len(all_ranked)} 位候选人完成关键词重合度 + H 指数加权排序；"
        f"重合度 ≥ {min_overlap:.2f} 共 {passed_count} 人{cap_note}，"
        f"最终 {len(selected_candidates)} 人进入阶段二（最高重合度 {max_overlap:.2f}）。"
    )

    selected_keys = {(c.name, c.org) for c in selected_candidates}
    experts = [
        _expert_dict(c, i, selected=(c.name, c.org) in selected_keys)
        for i, c in enumerate(all_ranked, 1)
    ]
    selected = [item for item in experts if item["selected"]]

    return {
        "summary": "\n".join(lines),
        "total_from_api": len(all_candidates),
        "after_coi": len(after_coi),
        "coi_filtered_count": coi_count,
        "ranked_count": len(all_ranked),
        "max_overlap_score": max_overlap,
        "min_overlap_threshold": min_overlap,
        "passed_min_overlap_count": passed_count,
        "stage1_capped": capped,
        "selected_count": len(selected_candidates),
        "experts": experts,
        "selected": selected,
    }


def _build_stage2_thinking(
    enriched: List[EnrichedCandidate],
    pub_year: str,
) -> Dict[str, Any]:
    lines = [
        f"对 {len(enriched)} 位候选人调用 get_author_info（pub_year={pub_year}），"
        "计算 activity_score = 近2年发文量×0.6 + H指数×0.4；"
        f"按融合分重排（overlap×{FUSION_OVERLAP_WEIGHT:g} + activity_norm×{FUSION_ACTIVITY_WEIGHT:g}）。",
    ]

    candidates = []
    for i, c in enumerate(enriched, 1):
        top_paper = c.recent_papers[0].title if c.recent_papers else ""
        candidates.append(
            {
                "rank": i,
                "name": c.name,
                "org": c.org,
                "pubs_last_2_years": c.pubs_last_2_years,
                "hindex": c.hindex,
                "activity_score": c.activity_score,
                "fusion_score": c.fusion_score,
                "overlap_score": c.overlap_score,
                "recent_papers_count": len(c.recent_papers),
                "top_paper": top_paper,
                "reason": (
                    f"近2年发文 {c.pubs_last_2_years} 篇，H 指数 {c.hindex:.0f}，"
                    f"activity_score={c.activity_score:.2f}，"
                    f"融合分 {c.fusion_score:.2f}（overlap {c.overlap_score:.2f}）"
                ),
            }
        )

    lines.append(f"已完成 {len(enriched)} 位学者背景补全，进入阶段三 LLM 语义精筛。")

    return {
        "summary": "\n".join(lines),
        "pub_year": pub_year,
        "candidates": candidates,
    }


def run_stage1_from_candidates(
    paper: PaperInput,
    all_candidates: List[ReviewerCandidate],
) -> Dict[str, Any]:
    """阶段一：对已有候选人做 COI 熔断与 overlap 阈值筛选。"""
    after_coi = filter_coi(all_candidates, paper.author_org)
    paper_keywords = parse_keywords(paper.keywords)
    all_ranked, selected_candidates, stage1_meta = select_highest_overlap(
        after_coi,
        paper_keywords,
        paper.title,
    )

    thinking = _build_stage1_thinking(
        paper,
        all_candidates,
        after_coi,
        all_ranked,
        selected_candidates,
        stage1_meta,
    )
    emit("stage1_thinking", {"thinking": thinking})

    return {
        "total_from_api": len(all_candidates),
        "after_coi": len(after_coi),
        "selected": selected_candidates,
        "coi_filtered_count": len(all_candidates) - len(after_coi),
        "thinking": thinking,
        "stage1_meta": stage1_meta,
    }


def run_stage1(paper: PaperInput, api_code: Optional[str] = None) -> Dict[str, Any]:
    """阶段一：拉取候选人 → COI 熔断 → overlap 阈值筛选（可截断 Top N）。"""
    all_candidates = fetch_reviewers(paper.keywords, api_code)
    return run_stage1_from_candidates(paper, all_candidates)


def run_stage2(
    candidates: List[ReviewerCandidate],
    api_code: Optional[str] = None,
) -> List[EnrichedCandidate]:
    """阶段二：批量拉取发文背景并计算 activity_score。"""
    pub_year = pub_year_range_last_n(RECENT_PAPER_YEARS)
    enriched: List[EnrichedCandidate] = []
    for candidate in candidates:
        item = enrich_candidate(candidate, pub_year, api_code)
        enriched.append(item)
        emit(
            "stage2_thinking",
            {
                "thinking": {
                    "progress": f"{len(enriched)}/{len(candidates)}",
                    "name": item.name,
                    "org": item.org,
                    "pubs_last_2_years": item.pubs_last_2_years,
                    "activity_score": item.activity_score,
                    "recent_papers_count": len(item.recent_papers),
                    "reason": (
                        f"{item.name}：近2年发文 {item.pubs_last_2_years} 篇，"
                        f"activity_score={item.activity_score:.2f}"
                    ),
                },
            },
        )

    enriched = rerank_enriched_candidates(enriched)

    emit(
        "stage2_thinking",
        {"thinking": _build_stage2_thinking(enriched, pub_year)},
    )
    return enriched


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


def run_pipeline(paper: PaperInput, api_code: Optional[str] = None) -> Dict[str, Any]:
    session_code = (api_code or "").strip() or init_api_code()
    stage1 = run_stage1(paper, session_code)
    enriched = run_stage2(stage1["selected"], session_code)
    payload = build_llm_payload(paper, enriched, stage1)
    return {
        "stage1": stage1,
        "enriched": enriched,
        "llm_payload": payload,
    }
