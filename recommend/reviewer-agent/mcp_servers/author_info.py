"""MCP Server: 依据作者姓名和机构查询历史发文（searchArticles）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP

from agent.tools import fetch_author_info_with_memory

mcp = FastMCP("cscd-author-info")


@mcp.tool()
def get_author_info(
    author: str,
    org: str = "",
    page: int = 1,
    limit: int = 50,
    pub_year: str = "",
    api_code: str = "",
) -> str:
    """依据作者姓名和机构查询 CSCD 历史发文信息。

    Args:
        author: 作者姓名（必填）
        org: 作者机构，用于消歧；海外学者或机构名不匹配时可留空
        page: 页码，默认 1
        limit: 每页条数，最大 50
        pub_year: 出版年范围，如 2022-2025
        api_code: CSCD ApiCode，可留空则从环境变量 CSCD_API_CODE 读取
    """
    response = fetch_author_info_with_memory(
        author=author,
        org=org,
        pub_year=pub_year,
        page=page,
        limit=limit,
        api_code=api_code or None,
    )
    return json.dumps(response, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
