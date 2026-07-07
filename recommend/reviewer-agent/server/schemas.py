"""API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    title: str = Field(..., min_length=1, description="待审论文标题")
    keywords: str = Field(..., min_length=1, description="论文关键词，逗号分隔")
    author_org: str = Field(default="", description="原作者机构（选填，触发 COI 熔断）")
    extra: str = Field(default="", description="补充说明")


class HealthResponse(BaseModel):
    status: str = "ok"
