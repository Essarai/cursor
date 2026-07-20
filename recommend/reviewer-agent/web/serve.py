#!/usr/bin/env python3
"""启动前端静态页面（默认 http://127.0.0.1:5173）。"""

from __future__ import annotations

import argparse
import http.server
import os
import socketserver
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self) -> None:
        # 开发期禁止缓存，避免旧 JS 导致「开始检索后确认区消失」等行为回退
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reviewer Agent 前端静态服务")
    parser.add_argument("--host", default=os.getenv("WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WEB_PORT", "5173")))
    args = parser.parse_args()

    class ReuseServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReuseServer((args.host, args.port), Handler) as httpd:
        url = f"http://{args.host}:{args.port}"
        print(f"前端已启动: {url}")
        print("后端 API 默认指向 http://127.0.0.1:8000")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
