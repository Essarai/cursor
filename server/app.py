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
from langsmith import Client

from agent.author_pubs import fetch_author_pub_stats
from agent.keyword_refine import refine_keywords
from agent.runner import iter_agent_events
from agent.types import PaperInput
from cscd.client import diagnose_cscd
from server.logging_setup import get_logger
from server.schemas import (
    AuthorPubsRequest,
    AuthorPubsResponse,
    CscdStatusResponse,
    HealthResponse,
    RecommendRequest,
    RefineKeywordsRequest,
    RefineKeywordsResponse,
    ReviewerCopyFeedbackRequest,
)

logger = get_logger("api")

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
load_dotenv(ROOT / ".env")

# Railway 等平台会注入 PORT；本地默认 8000
PORT = int(os.getenv("PORT") or os.getenv("API_PORT", "8000"))
HOST = os.getenv("API_HOST", "0.0.0.0")

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


@app.get(
    "/api/v1/cscd/status",
    response_model=CscdStatusResponse,
    tags=["system"],
)
def cscd_status() -> CscdStatusResponse:
    """排查线上 CSCD：出口 IP、凭证是否配置、getApiCode 是否成功（不返回码）。"""
    return CscdStatusResponse(**diagnose_cscd())


@app.post(
    "/api/v1/keywords/refine",
    response_model=RefineKeywordsResponse,
    tags=["recommend"],
)
def refine_paper_keywords(body: RefineKeywordsRequest) -> RefineKeywordsResponse:
    """依据论文标题、摘要与原始关键词提炼检索关键词，供用户确认后使用。"""
    title = body.title.strip()
    logger.info(
        "keywords_refine request title=%r keywords=%r retry=%s",
        title[:80],
        (body.keywords or "").strip()[:80] or "-",
        bool((body.previous_keywords or "").strip()),
    )
    try:
        result = refine_keywords(
            title=body.title,
            abstract=body.abstract,
            keywords=body.keywords,
            previous_keywords=body.previous_keywords,
            retry_note=body.retry_note,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("keywords_refine failed title=%r", title[:80])
        raise HTTPException(status_code=502, detail=f"关键词提炼失败：{exc}") from exc
    refined = result.get("keywords") or []
    logger.info("keywords_refine ok title=%r result=%s", title[:80], refined)
    return RefineKeywordsResponse(**result)


@app.post(
    "/api/v1/authors/publications/stats",
    response_model=AuthorPubsResponse,
    tags=["authors"],
)
def author_publication_stats(body: AuthorPubsRequest) -> AuthorPubsResponse:
    """按作者姓名与机构拉发文，并按年聚合一作/通讯/其他。"""
    author = body.author.strip()
    institute = body.institute.strip()
    pub_year = (body.pub_year or "").strip() or "default-20y"
    logger.info(
        "author_pubs request author=%r institute=%r pub_year=%s author_id=%s",
        author,
        institute,
        pub_year,
        (body.author_id or "").strip() or "-",
    )
    try:
        result = fetch_author_pub_stats(
            author=body.author,
            institute=body.institute,
            pub_year=body.pub_year,
            author_id=body.author_id,
            keywords=body.keywords,
        )
    except ValueError as exc:
        logger.warning(
            "author_pubs rejected author=%r institute=%r detail=%s",
            author,
            institute,
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "author_pubs failed author=%r institute=%r",
            author,
            institute,
        )
        raise HTTPException(status_code=502, detail=f"发文查询失败：{exc}") from exc

    totals = result.get("totals") or {}
    logger.info(
        "author_pubs ok author=%r institute=%r identity_verified=%s "
        "total=%s fetched=%s matched=%s first=%s corresponding=%s other=%s",
        result.get("author"),
        result.get("institute"),
        result.get("identity_verified"),
        result.get("total"),
        result.get("fetched"),
        result.get("keyword_matched"),
        totals.get("first", 0),
        totals.get("corresponding", 0),
        totals.get("other", 0),
    )
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
    logger.info(
        "recommend start title=%r keywords=%r author_org=%r",
        paper.title.strip()[:80],
        paper.keywords.strip()[:120],
        (paper.author_org or "").strip()[:80] or "-",
    )

    def generate() -> bytes:
        for event in iter_agent_events(paper):
            if event.get("event") == "error":
                logger.error(
                    "recommend error stage=%s title=%r message=%s",
                    event.get("stage"),
                    paper.title.strip()[:80],
                    event.get("message"),
                )
            elif event.get("event") == "stage1_done":
                logger.info(
                    "recommend stage1_done title=%r selected=%s total_from_api=%s",
                    paper.title.strip()[:80],
                    event.get("selected_count"),
                    event.get("total_from_api"),
                )
            elif event.get("event") == "stage3_done":
                reviewers = event.get("reviewers") or []
                logger.info(
                    "recommend stage3_done title=%r reviewers=%s",
                    paper.title.strip()[:80],
                    len(reviewers) if isinstance(reviewers, list) else reviewers,
                )
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


@app.post("/api/v1/feedback/reviewer-copy", tags=["feedback"])
def record_reviewer_copy(body: ReviewerCopyFeedbackRequest) -> dict[str, bool]:
    """记录最终推荐审稿人被复制，即编辑认为候选人可邀请。"""
    try:
        Client().create_feedback(
            run_id=body.langsmith_run_id,
            trace_id=body.langsmith_trace_id or None,
            key="reviewer_copied",
            score=1,
            value={
                "candidate_id": body.candidate_id,
                "candidate_name": body.candidate_name,
                "candidate_rank": body.candidate_rank,
                "copy_type": body.copy_type,
            },
            comment="复制审稿人信息，视为可邀请",
        )
    except Exception as exc:
        logger.exception("reviewer copy feedback failed")
        raise HTTPException(status_code=502, detail="复制反馈记录失败") from exc
    return {"ok": True}


if WEB_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=WEB_DIR, html=True),
        name="web",
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "server.app:app",
        host=HOST,
        port=PORT,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
