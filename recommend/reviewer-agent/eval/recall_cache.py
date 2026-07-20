"""评测用审稿人召回缓存：关键词召回最多 100 人，落盘复用。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from agent.tools import fetch_reviewers_with_memory
from agent.types import ReviewerCandidate, parse_reviewer, reviewer_from_dict, reviewer_to_dict

EVAL_DIR = Path(__file__).resolve().parent
CACHE_DIR = EVAL_DIR / "cache"
MAX_RECALL = 100


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def recall_cache_path(case_id: str) -> Path:
    return CACHE_DIR / f"{case_id}_recalled.json"


def load_recall_cache(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_recall_cache(
    path: Path,
    *,
    case_id: str,
    search_keywords: str,
    candidates: List[ReviewerCandidate],
    raw_result: List[Dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case_id,
        "search_keywords": search_keywords,
        "max_recall": MAX_RECALL,
        "count": len(candidates),
        "fetched_at": _utc_now(),
        "candidates": [reviewer_to_dict(item) for item in candidates],
        "raw_result": raw_result,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_recalled_candidates(
    *,
    case_id: str,
    search_keywords: str,
    api_code: str | None = None,
    refresh: bool = False,
) -> tuple[List[ReviewerCandidate], Dict[str, Any]]:
    """按关键词召回审稿人；优先读本地缓存，避免重复调用 CSCD。"""
    cache_path = recall_cache_path(case_id)
    if cache_path.exists() and not refresh:
        cached = load_recall_cache(cache_path)
        candidates = [
            reviewer_from_dict(item) for item in cached.get("candidates") or []
        ]
        meta = {
            "source": "cache",
            "cache_path": str(cache_path),
            "search_keywords": cached.get("search_keywords") or search_keywords,
            "count": len(candidates),
            "fetched_at": cached.get("fetched_at"),
        }
        return candidates, meta

    response = fetch_reviewers_with_memory(search_keywords, api_code)
    if not response.get("success"):
        raise RuntimeError(response.get("message") or "getPeerReviewers 失败")

    raw_result = list(response.get("result") or [])
    candidates = [
        parse_reviewer(item) for item in raw_result if item.get("authorName")
    ][:MAX_RECALL]

    save_recall_cache(
        cache_path,
        case_id=case_id,
        search_keywords=search_keywords,
        candidates=candidates,
        raw_result=raw_result[:MAX_RECALL],
    )

    meta = {
        "source": "api",
        "cache_path": str(cache_path),
        "search_keywords": search_keywords,
        "count": len(candidates),
        "fetched_at": _utc_now(),
    }
    return candidates, meta
