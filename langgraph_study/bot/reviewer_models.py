from typing import Any, TypedDict

from pydantic import BaseModel, Field, field_validator


class ManuscriptInput(BaseModel):
    title: str = Field(min_length=1)
    abstract: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)

    @field_validator("title", "abstract")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("内容不能为空")
        return stripped

    @field_validator("keywords", "authors", "organizations")
    @classmethod
    def clean_string_list(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = str(value).strip()
            normalized = stripped.casefold()
            if stripped and normalized not in seen:
                seen.add(normalized)
                result.append(stripped)
        return result


class KeywordExtraction(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=4)
    reasoning: str = Field(min_length=1)


class ArticleAssessment(BaseModel):
    article_id: str
    relevant: bool
    reason: str


class ArticleRelevanceBatch(BaseModel):
    assessments: list[ArticleAssessment]


class ReviewerAgentState(TypedDict, total=False):
    manuscript: dict[str, Any]
    core_keywords: list[str]
    keyword_reasoning: str
    candidates: list[dict[str, Any]]
    stage1_candidates: list[dict[str, Any]]
    stage1_rejected: list[dict[str, Any]]
    articles_by_reviewer: dict[str, list[dict[str, Any]]]
    final_reviewers: list[dict[str, Any]]
    stage2_rejected: list[dict[str, Any]]
    warnings: list[str]
    report: str
