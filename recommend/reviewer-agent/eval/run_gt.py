"""Ground Truth 评测：跳过阶段一，直接用编辑选定候选人跑阶段二/三。"""

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
from agent.pipeline import build_llm_payload, run_stage2
from agent.tools import fetch_reviewers_with_memory
from agent.types import PaperInput, ReviewerCandidate, parse_reviewer
from cscd.client import init_api_code

EVAL_DIR = Path(__file__).resolve().parent
GT_DIR = EVAL_DIR / "ground_truth"


def load_gt(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_candidates_by_ids(
    gt: Dict[str, Any],
    api_code: str | None = None,
) -> List[ReviewerCandidate]:
    accepted = gt.get("accepted_reviewers") or []
    target_ids = {str(item["author_id"]) for item in accepted}
    keywords = gt.get("search_keywords") or gt["paper"]["keywords"]

    response = fetch_reviewers_with_memory(keywords, api_code)
    if not response.get("success"):
        raise RuntimeError(response.get("message") or "getPeerReviewers 失败")

    by_id: Dict[str, ReviewerCandidate] = {}
    for raw in response.get("result") or []:
        candidate = parse_reviewer(raw)
        if candidate.id in target_ids:
            by_id[candidate.id] = candidate

    missing = target_ids - set(by_id)
    if missing:
        raise RuntimeError(f"CSCD 召回结果中未找到 author_id: {sorted(missing)}")

    # 保持 GT 文件中的顺序
    ordered: List[ReviewerCandidate] = []
    for item in accepted:
        ordered.append(by_id[str(item["author_id"])])
    return ordered


def run_gt_case(gt_path: Path) -> Dict[str, Any]:
    gt = load_gt(gt_path)
    paper = PaperInput(
        title=gt["paper"]["title"],
        keywords=gt["paper"]["keywords"],
        author_org=gt["paper"].get("author_org", ""),
        extra=gt["paper"].get("extra", ""),
    )

    session_code = init_api_code()
    selected = pick_candidates_by_ids(gt, session_code)

    events: List[Dict[str, Any]] = []

    def sink(payload: Dict[str, Any]) -> None:
        events.append(payload)

    token = set_emit_sink(sink)
    try:
        enriched = run_stage2(selected, session_code)
        stage1_meta = {
            "total_from_api": len(selected),
            "coi_filtered_count": 0,
        }
        payload = build_llm_payload(paper, enriched, stage1_meta)
        stream_semantic_screening(payload)
    finally:
        clear_emit_sink(token)

    stage3_done = next((e for e in events if e.get("event") == "stage3_done"), None)
    predicted: List[Dict[str, str]] = (stage3_done or {}).get("reviewers") or []

    gt_names = [item["name"] for item in gt.get("accepted_reviewers") or []]
    pred_names = [item["name"] for item in predicted]
    gt_set: Set[str] = set(gt_names)
    pred_set: Set[str] = set(pred_names)

    return {
        "case_id": gt.get("case_id"),
        "gt_path": str(gt_path),
        "paper_keywords": parse_keywords(paper.keywords),
        "input_candidates": [
            {
                "author_id": c.id,
                "name": c.name,
                "org": c.org,
                "hindex": c.hindex,
                "research_keywords": c.research_keywords[:8],
            }
            for c in selected
        ],
        "events": events,
        "ground_truth": gt_names,
        "predicted": pred_names,
        "metrics": {
            "hit_count": len(gt_set & pred_set),
            "gt_count": len(gt_set),
            "pred_count": len(pred_set),
            "recall": round(len(gt_set & pred_set) / len(gt_set), 4) if gt_set else 0.0,
            "precision": round(len(gt_set & pred_set) / len(pred_set), 4) if pred_set else 0.0,
            "missed": sorted(gt_set - pred_set),
            "extra": sorted(pred_set - gt_set),
        },
        "reviewers": predicted,
    }


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Ground Truth 评测（跳过阶段一）")
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
    args = parser.parse_args()

    report = run_gt_case(Path(args.gt))

    print(json.dumps({
        "case_id": report["case_id"],
        "ground_truth": report["ground_truth"],
        "predicted": report["predicted"],
        "metrics": report["metrics"],
        "reviewers": report["reviewers"],
    }, ensure_ascii=False, indent=2))

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n完整报告已写入: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
