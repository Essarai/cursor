"""MCP Server: 依据关键词获取审稿人（getPeerReviewers）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP

from agent.tools import fetch_reviewers_with_memory

mcp = FastMCP("cscd-reviewers")


@mcp.tool()
def get_recommend_reviewers(keywords: str, api_code: str = "") -> str:
    """依据论文关键词从 CSCD 获取推荐审稿人，最多 100 位。

    Args:
        keywords: 论文关键词，多个可用逗号/分号分隔，内部会转为 CSCD 的 ;; 格式
        api_code: CSCD ApiCode，可留空则从环境变量 CSCD_API_CODE 读取
    """
    response = fetch_reviewers_with_memory(keywords, api_code or None)
    return json.dumps(response, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
