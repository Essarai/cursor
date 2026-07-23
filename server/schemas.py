"""API 请求/响应模型。"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    title: str = Field(default="", description="待审论文标题（智能提炼时建议填写）")
    keywords: str = Field(..., min_length=1, description="论文关键词，逗号分隔")
    abstract: str = Field(default="", description="论文摘要（选填）")
    author_org: str = Field(default="", description="原作者机构（选填，触发 COI 熔断）")
    extra: str = Field(default="", description="补充说明")


class RefineKeywordsRequest(BaseModel):
    title: str = Field(..., min_length=1, description="待审论文标题")
    abstract: str = Field(default="", description="论文摘要（选填）")
    keywords: str = Field(default="", description="原始关键词，逗号分隔（选填）")
    previous_keywords: str = Field(
        default="",
        description="上次用于检索的关键词（入选不足时重试提炼用）",
    )
    retry_note: str = Field(default="", description="重试原因说明")


class RefineKeywordsResponse(BaseModel):
    keywords: List[str] = Field(..., description="提炼后的关键词列表")
    reasoning: str = Field(default="", description="提炼思路说明")


class AuthorPubsRequest(BaseModel):
    author: str = Field(..., min_length=1, description="作者姓名")
    keywords: str = Field(..., min_length=1, description="论文关键词，逗号分隔，用于筛选相关发文")
    org: str = Field(default="", description="作者机构（可选，用于消歧）")
    author_id: str = Field(default="", description="CSCD 作者 ID（可选）")
    pub_year: str = Field(
        default="",
        description="发表年份范围，如 2010-2026；空则默认近 20 年",
    )


class AuthorPubsYearBucket(BaseModel):
    year: int
    first: int = 0
    corresponding: int = 0
    other: int = 0


class AuthorPubsPaperItem(BaseModel):
    title: str = ""
    year: int | None = None
    journal: str = ""
    doi: str = ""
    article_url: str = ""
    author_sequence: int | None = None
    author_count: int = 0
    role: str = "other"
    role_label: str = ""
    authors: List[str] = Field(default_factory=list)


class AuthorPubsResponse(BaseModel):
    author: str
    org: str = ""
    keywords: List[str] = Field(default_factory=list)
    pub_year: str
    identity_verified: bool = False
    total: int = 0
    fetched: int = 0
    keyword_matched: int = 0
    used_fallback: bool = False
    unmatched: int = 0
    role_note: str = ""
    totals: Dict[str, int]
    by_year: List[AuthorPubsYearBucket]
    series: Dict[str, List[int]]
    papers: List[AuthorPubsPaperItem] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"


class CscdStatusResponse(BaseModel):
    base_url: str
    has_cscd_user: bool
    has_cscd_password: bool
    has_static_api_code: bool
    static_api_code_ignored: bool
    egress_ip: str | None = None
    get_api_code_ok: bool
    get_api_code_message: str = ""
    used_cached_api_code: bool = False
    hint: str = ""
