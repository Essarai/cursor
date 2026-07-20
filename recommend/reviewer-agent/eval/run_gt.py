"""Ground Truth 评测：关键词召回 100 人（缓存）→ 阶段一/二/三全链路。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.chain import stream_semantic_screening
from agent.emit import clear_emit_sink, set_emit_sink
from agent.filters import parse_keywords
from agent.pipeline import build_llm_payload, run_stage1_from_candidates, run_stage2
from agent.types import PaperInput, ReviewerCandidate
from cscd.client import init_api_code
from eval.recall_cache import fetch_recalled_candidates

EVAL_DIR = Path(__file__).resolve().parent
GT_DIR = EVAL_DIR / "ground_truth"


def load_gt(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics(gt_names: List[str], candidate_names: List[str]) -> Dict[str, Any]:
    gt_set: Set[str] = set(gt_names)
    pred_set: Set[str] = set(candidate_names)
    hits = sorted(gt_set & pred_set)
    return {
        "hit_count": len(hits),
        "gt_count": len(gt_set),
        "pred_count": len(pred_set),
        "recall": round(len(hits) / len(gt_set), 4) if gt_set else 0.0,
        "precision": round(len(hits) / len(pred_set), 4) if pred_set else 0.0,
        "hits": hits,
        "missed": sorted(gt_set - pred_set),
        "extra": sorted(pred_set - gt_set),
    }


def _candidate_brief(candidate: ReviewerCandidate) -> Dict[str, Any]:
    return {
        "author_id": candidate.id,
        "name": candidate.name,
        "org": candidate.org,
        "hindex": candidate.hindex,
        "overlap_score": candidate.overlap_score,
        "research_keywords": candidate.research_keywords[:8],
    }


def run_gt_case(gt_path: Path, *, refresh_recall: bool = False) -> Dict[str, Any]:
    gt = load_gt(gt_path)
    case_id = str(gt.get("case_id") or gt_path.stem)
    paper = PaperInput(
        title=gt["paper"]["title"],
        keywords=gt["paper"]["keywords"],
        author_org=gt["paper"].get("author_org", ""),
        extra=gt["paper"].get("extra", ""),
    )
    search_keywords = gt.get("search_keywords") or paper.keywords
    gt_names = [item["name"] for item in gt.get("accepted_reviewers") or []]
    gt_ids = {str(item["author_id"]) for item in gt.get("accepted_reviewers") or []}

    session_code = init_api_code() if refresh_recall else None
    recalled, recall_meta = fetch_recalled_candidates(
        case_id=case_id,
        search_keywords=search_keywords,
        api_code=session_code,
        refresh=refresh_recall,
    )
    if session_code is None:
        session_code = init_api_code()

    recalled_ids = {c.id for c in recalled}
    missing_gt_in_recall = sorted(gt_ids - recalled_ids)

    events: List[Dict[str, Any]] = []

    def sink(payload: Dict[str, Any]) -> None:
        events.append(payload)

    token = set_emit_sink(sink)
    try:
        stage1 = run_stage1_from_candidates(paper, recalled)
        enriched = run_stage2(stage1["selected"], session_code)
        payload = build_llm_payload(paper, enriched, stage1)
        stream_semantic_screening(payload)
    finally:
        clear_emit_sink(token)

    stage3_done = next((e for e in events if e.get("event") == "stage3_done"), None)
    predicted: List[Dict[str, str]] = (stage3_done or {}).get("reviewers") or []
    pred_names = [item["name"] for item in predicted]

    return {
        "case_id": case_id,
        "gt_path": str(gt_path),
        "mode": "full_pipeline_from_cached_recall",
        "paper_keywords": parse_keywords(paper.keywords),
        "search_keywords": search_keywords,
        "recall": recall_meta,
        "recall_pool": {
            "count": len(recalled),
            "candidates": [_candidate_brief(c) for c in recalled],
            "metrics": _metrics(gt_names, [c.name for c in recalled]),
            "missing_gt_author_ids": missing_gt_in_recall,
        },
        "stage1": {
            "selected_count": len(stage1["selected"]),
            "metrics": _metrics(gt_names, [c.name for c in stage1["selected"]]),
            "selected": [_candidate_brief(c) for c in stage1["selected"]],
            "thinking_summary": stage1["thinking"]["summary"],
        },
        "stage2": {
            "candidate_count": len(enriched),
            "metrics": _metrics(gt_names, [c.name for c in enriched]),
        },
        "stage3": {
            "predicted": pred_names,
            "metrics": _metrics(gt_names, pred_names),
            "reviewers": predicted,
        },
        "ground_truth": gt_names,
        "predicted": pred_names,
        "metrics": _metrics(gt_names, pred_names),
        "events": events,
        "reviewers": predicted,
    }


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(
        description="Ground Truth 全链路评测（关键词召回 100 人，本地缓存复用）"
    )
    parser.add_argument(
        "--gt",
        default=str(GT_DIR / "chaos_sync_control.json"),
        help="Ground truth JSON 路径",
    )
    parser.add_argument(
        "--report",
        default="",
        help="可选：将完整报告写入 JSON 文件",
    )
    parser.add_argument(
        "--refresh-recall",
        action="store_true",
        help="忽略本地缓存，重新调用 CSCD 召回 100 位审稿人",
    )
    args = parser.parse_args()

    report = run_gt_case(Path(args.gt), refresh_recall=args.refresh_recall)

    print(
        json.dumps(
            {
                "case_id": report["case_id"],
                "recall": report["recall"],
                "recall_pool_metrics": report["recall_pool"]["metrics"],
                "stage1_metrics": report["stage1"]["metrics"],
                "stage3_metrics": report["stage3"]["metrics"],
                "ground_truth": report["ground_truth"],
                "predicted": report["predicted"],
                "reviewers": report["reviewers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n完整报告已写入: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
