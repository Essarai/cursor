"""审稿人推荐三阶段管线入口（方案 A：Python 阶段一/二 + LLM 阶段三精筛）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cscd_tools import ensure_cscd_api_code, get_cscd_client, load_config
from pipeline.pipeline import run_pipeline
from pipeline.screening import load_system_prompt, run_semantic_screening
from pipeline.types import PaperInput


def load_system_prompt_path(config: dict) -> str:
    rel_path = config.get("agent", {}).get(
        "system_prompt", "prompts/system_prompt.md"
    )
    return str(Path(__file__).parent / rel_path)


def run_reviewer_pipeline(paper: PaperInput) -> dict:
    config = load_config()
    agent_cfg = config.get("agent", {})
    recent_paper_years = int(agent_cfg.get("recent_paper_years", 3))

    ensure_cscd_api_code()
    client = get_cscd_client()


    pipeline_result = run_pipeline(paper, client, recent_paper_years)
    stage1 = pipeline_result["stage1"]


    minimax = dict(config["minimax"])
    minimax["temperature"] = agent_cfg.get("temperature", 0.2)
    minimax["json_mode"] = agent_cfg.get("json_mode", True)

    prompt_path = load_system_prompt_path(config)
    golden_path = Path(__file__).parent / agent_cfg.get(
        "golden_cases", "prompts/golden_cases.md"
    )
    system_prompt = load_system_prompt(prompt_path, golden_path)

    reviewers = run_semantic_screening(
        pipeline_result["llm_payload"],
        system_prompt,
        minimax,
    )


    return {
        "stage1_summary": {
            "total_from_api": stage1["total_from_api"],
            "coi_filtered_count": stage1["coi_filtered_count"],
            "stage1_selected_count": len(pipeline_result["enriched"]),
        },
        "reviewers": reviewers["reviewers"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CSCD 审稿人推荐三阶段管线")
    parser.add_argument("--title", required=True, help="待审论文标题")
    parser.add_argument("--keywords", required=True, help="论文关键词，分号分隔")
    parser.add_argument("--author-org", default="", help="原作者机构（用于 COI 剔除）")
    parser.add_argument("--extra", default="", help="补充说明")
    args = parser.parse_args()

    paper = PaperInput(
        title=args.title,
        keywords=args.keywords,
        author_org=args.author_org,
        extra=args.extra,
    )

    result = run_reviewer_pipeline(paper)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
