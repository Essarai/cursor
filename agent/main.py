"""审稿人推荐 Agent 主入口。

输出格式：NDJSON 事件流
- stage1_thinking / stage1_done：候选专家（不经 LLM）
- stage2_thinking / stage3_thinking：背景补全与 AI 精筛
- stage3_result：阶段三 JSON 结果片段（流式）
- stage3_done：最终结构化推荐列表
- error：失败事件；stage=stage1|ai，AI 失败不影响已发出的候选专家
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.runner import iter_agent_events
from agent.types import PaperInput


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CSCD 审稿人推荐 Agent（Python 硬过滤 + LLM 流式精筛）"
    )
    parser.add_argument("--title", required=True, help="待审论文标题")
    parser.add_argument("--keywords", required=True, help="论文关键词")
    parser.add_argument(
        "--author-org",
        default="",
        help="排查机构（选填，填写则触发利益冲突筛选，排除对应机构）",
    )
    parser.add_argument("--extra", default="", help="补充说明")
    return parser.parse_args()


def main() -> None:
    load_dotenv(ROOT / ".env")
    args = parse_args()

    paper = PaperInput(
        title=args.title,
        keywords=args.keywords,
        author_org=args.author_org,
        extra=args.extra,
    )

    exit_code = 0
    stage1_ok = False
    for event in iter_agent_events(paper):
        try:
            sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            sys.exit(0)
        name = event.get("event")
        if name in ("stage1_thinking", "stage1_done"):
            stage1_ok = True
        if name == "error":
            # 仅阶段一失败视为整体失败；AI 精荐失败时候选专家仍可用
            if event.get("stage") != "ai" or not stage1_ok:
                exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
