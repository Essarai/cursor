import re
from datetime import datetime
from typing import Any, Iterable


def reviewer_key(reviewer: dict[str, Any]) -> str:
    return str(
        reviewer.get("id")
        or f"{reviewer.get('authorName', '')}|{reviewer.get('org', '')}"
    )


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def normalize_text(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").casefold())


def split_keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[;,，；、|/\n]+", str(value or ""))
    return [item.strip() for item in raw if str(item).strip()]


def keyword_overlap(core_keywords: list[str], reviewer_keywords: Any) -> float:
    if not core_keywords:
        return 0.0
    reviewer_items = [
        normalized
        for item in split_keywords(reviewer_keywords)
        if (normalized := normalize_text(item))
    ]
    matched = 0
    for keyword in core_keywords:
        variants = keyword_variants(keyword)
        if not variants:
            continue
        if any(
            _keywords_match(variant, item)
            for variant in variants
            for item in reviewer_items
        ):
            matched += 1
    return matched / len(core_keywords) * 100


def minmax_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        score = 100.0 if maximum > 0 else 0.0
        return [score] * len(values)
    return [(value - minimum) / (maximum - minimum) * 100 for value in values]


def stage1_filter(
    candidates: list[dict[str, Any]],
    core_keywords: list[str],
    manuscript_organizations: list[str],
    keep_count: int = 10,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """初筛：按相对分排序，保留前 ``keep_count`` 名。

    H-index 缺失不淘汰：缺失者初筛分完全由关键词分决定；
    有 H-index 者按 关键词 70% + H-index 30% 计算。
    """
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for candidate in candidates:
        item = dict(candidate)
        if same_organization(item.get("org"), manuscript_organizations):
            item["rejection_reason"] = "与稿件作者同机构"
            rejected.append(item)
            continue
        item["hindex_value"] = parse_number(item.get("hindex"))
        item["keyword_overlap_raw"] = keyword_overlap(
            core_keywords,
            item.get("keyword"),
        )
        eligible.append(item)

    overlap_scores = minmax_scores(
        [float(item["keyword_overlap_raw"]) for item in eligible]
    )
    # H-index 只在有值的候选人之间归一化，缺失者不参与也不受惩罚
    with_hindex = [item for item in eligible if item["hindex_value"] is not None]
    hindex_scores = minmax_scores(
        [float(item["hindex_value"]) for item in with_hindex]
    )
    hindex_score_by_key = {
        reviewer_key(item): score
        for item, score in zip(with_hindex, hindex_scores, strict=True)
    }

    for item, overlap_score in zip(eligible, overlap_scores, strict=True):
        item["keyword_score"] = round(overlap_score, 2)
        hindex_score = hindex_score_by_key.get(reviewer_key(item))
        if hindex_score is None:
            item["hindex_score"] = None
            item["stage1_score"] = round(overlap_score, 2)
        else:
            item["hindex_score"] = round(hindex_score, 2)
            item["stage1_score"] = round(
                overlap_score * 0.7 + hindex_score * 0.3, 2
            )

    eligible.sort(key=lambda item: item["stage1_score"], reverse=True)
    selected = eligible[: max(0, keep_count)]

    for rank, item in enumerate(selected, start=1):
        item["stage1_rank"] = rank

    for item in eligible[len(selected):]:
        item["rejection_reason"] = f"初筛相对分排名未进入前 {keep_count}"
        rejected.append(item)
    return selected, rejected


def same_organization(
    reviewer_org: Any,
    manuscript_organizations: list[str],
) -> bool:
    reviewer = normalize_text(reviewer_org)
    if not reviewer:
        return False
    for organization in manuscript_organizations:
        manuscript_org = normalize_text(organization)
        if not manuscript_org:
            continue
        if reviewer == manuscript_org:
            return True
        if min(len(reviewer), len(manuscript_org)) >= 6 and (
            reviewer in manuscript_org or manuscript_org in reviewer
        ):
            return True
    return False


def publication_year(article: dict[str, Any]) -> int | None:
    for key in ("year", "publicationYear", "publishYear"):
        value = article.get(key)
        if value is not None:
            match = re.search(r"(?:19|20)\d{2}", str(value))
            if match:
                return int(match.group())
    citation = str(article.get("citation") or "")
    years = re.findall(r"(?:19|20)\d{2}", citation)
    return int(years[-1]) if years else None


def is_recent_article(
    article: dict[str, Any],
    current_year: int | None = None,
) -> bool:
    year = publication_year(article)
    current = current_year or datetime.now().year
    return year is not None and current - 2 <= year <= current


def lexical_article_match(
    article: dict[str, Any],
    core_keywords: list[str],
) -> bool:
    searchable = normalize_text(
        " ".join(
            str(article.get(key) or "")
            for key in ("title", "keywords", "abstract")
        )
    )
    return any(
        variant in searchable
        for keyword in core_keywords
        for variant in keyword_variants(keyword)
    )


def has_coauthor_conflict(
    reviewer: dict[str, Any],
    recent_articles: Iterable[dict[str, Any]],
    manuscript_authors: list[str],
) -> bool:
    normalized_authors = [
        normalized
        for author in manuscript_authors
        if (normalized := normalize_text(author))
    ]
    if not normalized_authors:
        return False
    reviewer_name = normalize_text(reviewer.get("authorName"))
    if reviewer_name and reviewer_name in normalized_authors:
        return True
    for article in recent_articles:
        article_authors = normalize_text(article.get("authors"))
        if any(author in article_authors for author in normalized_authors):
            return True
    return False


def stage2_filter(
    candidates: list[dict[str, Any]],
    articles_by_reviewer: dict[str, list[dict[str, Any]]],
    relevant_ids_by_reviewer: dict[str, set[str]],
    manuscript_authors: list[str],
    keep_count: int = 5,
    current_year: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """终筛：按相对分排序，保留前 ``keep_count`` 名。"""
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for candidate in candidates:
        item = dict(candidate)
        key = reviewer_key(item)
        articles = articles_by_reviewer.get(key, [])
        recent = [
            article
            for article in articles
            if is_recent_article(article, current_year=current_year)
        ]
        if has_coauthor_conflict(item, recent, manuscript_authors):
            item["rejection_reason"] = "近三年存在共同作者利益冲突"
            rejected.append(item)
            continue
        relevant_ids = relevant_ids_by_reviewer.get(key, set())
        item["recent_article_count"] = len(recent)
        item["relevant_article_count"] = len(relevant_ids)
        item["relevant_articles"] = [
            article
            for article in articles
            if str(article.get("cscdId") or "") in relevant_ids
        ][:5]
        eligible.append(item)

    relevance_scores = minmax_scores(
        [float(item["relevant_article_count"]) for item in eligible]
    )
    recent_scores = minmax_scores(
        [float(item["recent_article_count"]) for item in eligible]
    )
    for item, relevance_score, recent_score in zip(
        eligible,
        relevance_scores,
        recent_scores,
        strict=True,
    ):
        item["relevant_article_score"] = round(relevance_score, 2)
        item["recent_article_score"] = round(recent_score, 2)
        item["final_score"] = round(relevance_score * 0.7 + recent_score * 0.3, 2)

    eligible.sort(key=lambda item: item["final_score"], reverse=True)
    selected = eligible[: max(0, keep_count)]

    for rank, item in enumerate(selected, start=1):
        item["final_rank"] = rank

    for item in eligible[len(selected):]:
        item["rejection_reason"] = f"终筛相对分排名未进入前 {keep_count}"
        rejected.append(item)
    return selected, rejected


def _keywords_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 3:
        return False
    return left in right or right in left


def keyword_variants(value: Any) -> list[str]:
    parts = re.split(r"[\(（\)）/／、]+", str(value or ""))
    return [
        normalized
        for part in parts
        if (normalized := normalize_text(part))
    ]
