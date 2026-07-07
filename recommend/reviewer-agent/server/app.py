"""FastAPI 后端：流式 NDJSON 审稿人推荐接口。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent.runner import iter_agent_events
from agent.types import PaperInput
from server.schemas import HealthResponse, RecommendRequest

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
load_dotenv(ROOT / ".env")

app = FastAPI(
    title="CSCD 审稿人推荐 Agent",
    description="三阶段审稿人推荐：Python 硬过滤 + 数据补全 + LLM 语义精筛",
    version="1.0.0",
)

_cors_origins = [
    origin.strip()
    for origin in os.getenv("API_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/api/v1/recommend/reviewers", tags=["recommend"])
def recommend_reviewers(body: RecommendRequest) -> StreamingResponse:
    """流式返回 NDJSON 事件（与 CLI stdout 格式一致）。"""
    paper = PaperInput(
        title=body.title,
        keywords=body.keywords,
        author_org=body.author_org,
        extra=body.extra,
    )

    def generate() -> bytes:
        for event in iter_agent_events(paper):
            line = json.dumps(event, ensure_ascii=False) + "\n"
            yield line.encode("utf-8")

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


if WEB_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=WEB_DIR, html=True),
        name="web",
    )
