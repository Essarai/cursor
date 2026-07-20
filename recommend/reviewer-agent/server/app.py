"""FastAPI 后端：流式 NDJSON 审稿人推荐接口。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent.author_pubs import fetch_author_pub_stats
from agent.keyword_refine import refine_keywords
from agent.runner import iter_agent_events
from agent.types import PaperInput
from server.schemas import (
    AuthorPubsRequest,
    AuthorPubsResponse,
    HealthResponse,
    RecommendRequest,
    RefineKeywordsRequest,
    RefineKeywordsResponse,
)

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


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()


@app.post(
    "/api/v1/keywords/refine",
    response_model=RefineKeywordsResponse,
    tags=["recommend"],
)
def refine_paper_keywords(body: RefineKeywordsRequest) -> RefineKeywordsResponse:
    """依据论文标题、摘要与原始关键词提炼检索关键词，供用户确认后使用。"""
    try:
        result = refine_keywords(
            title=body.title,
            abstract=body.abstract,
            keywords=body.keywords,
            previous_keywords=body.previous_keywords,
            retry_note=body.retry_note,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"关键词提炼失败：{exc}") from exc
    return RefineKeywordsResponse(**result)


@app.post(
    "/api/v1/authors/publications/stats",
    response_model=AuthorPubsResponse,
    tags=["authors"],
)
def author_publication_stats(body: AuthorPubsRequest) -> AuthorPubsResponse:
    """按作者姓名拉发文，并用论文关键词筛选后按年聚合一作/通讯/其他。"""
    try:
        result = fetch_author_pub_stats(
            author=body.author,
            keywords=body.keywords,
            org=body.org,
            pub_year=body.pub_year,
            author_id=body.author_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"发文查询失败：{exc}") from exc
    return AuthorPubsResponse(**result)


@app.post("/api/v1/recommend/reviewers", tags=["recommend"])
def recommend_reviewers(body: RecommendRequest) -> StreamingResponse:
    """流式返回 NDJSON 事件（与 CLI stdout 格式一致）。"""
    extra = body.extra.strip()
    abstract = body.abstract.strip()
    if abstract:
        abstract_note = f"论文摘要：{abstract}"
        extra = f"{abstract_note}\n{extra}" if extra else abstract_note

    paper = PaperInput(
        title=body.title,
        keywords=body.keywords,
        author_org=body.author_org,
        extra=extra,
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
