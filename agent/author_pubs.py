"""按作者姓名拉取历史发文，并用论文关键词筛选相关文献后按年聚合角色。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from agent.tools import fetch_author_info_with_memory

ROLE_NOTE = (
    "一作按 authorSequence=1；通讯暂按末位作者近似"
    "（CSCD 接口无通讯作者字段）；其余记为其他。同一篇论文只计入一类。"
    "统计范围：作者发文中与论文关键词匹配的文献。"
)

_MAX_PAGES = 40
_PAGE_SIZE = 50


def _normalize_name(name: str) -> str:
    return "".join(str(name or "").split()).casefold()


def _parse_keywords(keywords: str) -> List[str]:
    parts = []
    for chunk in str(keywords or "").replace("；", ",").replace(";", ",").replace("，", ",").split(","):
        word = chunk.strip()
        if word and word not in parts:
            parts.append(word)
    return parts


def _parse_year(article: Dict[str, Any]) -> Optional[int]:
    issue = article.get("issue") or {}
    year_raw = issue.get("year")
    if not year_raw:
        return None
    try:
        return int(str(year_raw)[:4])
    except ValueError:
        return None


def _match_author(
    target: str,
    authors: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    target_norm = _normalize_name(target)
    if not target_norm:
        return None
    for author in authors:
        if _normalize_name(author.get("authorName")) == target_norm:
            return author
    return None


def _author_sequence_info(
    author_name: str,
    authors: List[Dict[str, Any]],
) -> Tuple[Optional[int], int, Optional[str]]:
    """返回 (作者序位, 作者总数, 角色 first/corresponding/other)。"""
    if not authors:
        return None, 0, None
    matched = _match_author(author_name, authors)
    if matched is None:
        return None, len(authors), None

    try:
        seq = int(matched.get("authorSequence") or 0)
    except (TypeError, ValueError):
        seq = 0

    sequences: List[int] = []
    for item in authors:
        try:
            sequences.append(int(item.get("authorSequence") or 0))
        except (TypeError, ValueError):
            continue
    author_count = len(authors)
    max_seq = max(sequences) if sequences else seq

    if seq <= 0:
        return None, author_count, "other"
    if seq == 1:
        return seq, author_count, "first"
    if seq == max_seq:
        return seq, author_count, "corresponding"
    return seq, author_count, "other"


def classify_author_role(
    author_name: str,
    authors: List[Dict[str, Any]],
) -> Optional[str]:
    """互斥分类：first > corresponding > other。"""
    _, _, role = _author_sequence_info(author_name, authors)
    return role


def _role_label(role: Optional[str], sequence: Optional[int], author_count: int) -> str:
    if sequence is None:
        return "未匹配"
    if role == "first":
        return f"第{sequence}作者 · 一作"
    if role == "corresponding":
        return f"第{sequence}作者 · 通讯(末位)"
    return f"第{sequence}/{author_count}作者"


def _to_paper_item(author: str, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    authors = article.get("authors") or []
    sequence, author_count, role = _author_sequence_info(author, authors)
    if role is None and sequence is None:
        return None

    year = _parse_year(article)
    journal = article.get("journal") or {}
    author_names = [
        str(item.get("authorName") or "").strip()
        for item in authors
        if str(item.get("authorName") or "").strip()
    ]
    return {
        "title": str(article.get("title") or "").strip(),
        "year": year,
        "journal": str(journal.get("journalName") or "").strip(),
        "doi": str(article.get("doi") or "").strip(),
        "article_url": str(article.get("articleUrl") or "").strip(),
        "author_sequence": sequence,
        "author_count": author_count,
        "role": role or "other",
        "role_label": _role_label(role, sequence, author_count),
        "authors": author_names,
    }


def _article_matches_keywords(article: Dict[str, Any], keywords: List[str]) -> bool:
    if not keywords:
        return True
    haystack = " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("keywords") or "").replace(";;", " "),
            str(article.get("abstract") or ""),
        ]
    ).casefold()
    return any(kw.casefold() in haystack for kw in keywords)


def _fetch_all_articles(
    author: str,
    org: str,
    pub_year: str,
    *,
    author_id: str = "",
) -> Tuple[List[Dict[str, Any]], int, bool]:
    articles: List[Dict[str, Any]] = []
    total = 0
    identity_verified = False

    for page in range(1, _MAX_PAGES + 1):
        response = fetch_author_info_with_memory(
            author=author,
            org=org,
            pub_year=pub_year,
            page=page,
            limit=_PAGE_SIZE,
            author_id=author_id,
            strict_identity=bool(org.strip()),
        )
        if not response.get("success"):
            message = response.get("message") or "CSCD 发文检索失败"
            raise RuntimeError(message)

        identity_verified = bool(response.get("identity_verified"))
        result = response.get("result") or {}
        total = int(result.get("total") or 0)
        batch = result.get("data") or []
        if not isinstance(batch, list):
            break
        articles.extend(batch)
        if len(articles) >= total or len(batch) < _PAGE_SIZE:
            break

    return articles, total, identity_verified


def fetch_author_pub_stats(
    author: str,
    keywords: str = "",
    org: str = "",
    pub_year: str = "",
    *,
    author_id: str = "",
) -> Dict[str, Any]:
    """按姓名拉发文，再用关键词筛选后按年聚合角色统计。"""
    author = author.strip()
    org = org.strip()
    keywords = keywords.strip()
    pub_year = pub_year.strip()
    author_id = author_id.strip()
    keyword_list = _parse_keywords(keywords)

    if not author:
        raise ValueError("请填写作者姓名")
    if not keyword_list:
        raise ValueError("请提供论文关键词，用于筛选相关发文")

    if not pub_year:
        end = datetime.now().year
        pub_year = f"{end - 19}-{end}"

    articles, total, identity_verified = _fetch_all_articles(
        author,
        org,
        pub_year,
        author_id=author_id,
    )

    matched_articles = [
        article for article in articles if _article_matches_keywords(article, keyword_list)
    ]
    # 关键词过严导致 0 命中时回退全量，避免弹窗空白
    used_fallback = False
    scoped = matched_articles
    if not scoped and articles:
        scoped = articles
        used_fallback = True

    by_year: Dict[int, Dict[str, int]] = defaultdict(
        lambda: {"first": 0, "corresponding": 0, "other": 0}
    )
    papers: List[Dict[str, Any]] = []
    unmatched = 0
    for article in scoped:
        paper = _to_paper_item(author, article)
        if paper is None:
            unmatched += 1
            continue
        papers.append(paper)
        year = paper.get("year")
        role = paper.get("role") or "other"
        if year is not None:
            by_year[int(year)][role] += 1

    # 最近年份优先；同年保持原相对顺序
    papers.sort(key=lambda item: item.get("year") or 0, reverse=True)

    years = sorted(by_year.keys())
    series = {
        "years": years,
        "first": [by_year[y]["first"] for y in years],
        "corresponding": [by_year[y]["corresponding"] for y in years],
        "other": [by_year[y]["other"] for y in years],
    }
    totals = {
        "first": sum(series["first"]),
        "corresponding": sum(series["corresponding"]),
        "other": sum(series["other"]),
    }

    note = ROLE_NOTE
    if used_fallback:
        note += " 关键词未命中文献，已回退为该作者全部发文。"

    return {
        "author": author,
        "org": org,
        "keywords": keyword_list,
        "pub_year": pub_year,
        "identity_verified": identity_verified,
        "total": total,
        "fetched": len(articles),
        "keyword_matched": len(matched_articles),
        "used_fallback": used_fallback,
        "unmatched": unmatched,
        "role_note": note,
        "totals": totals,
        "by_year": [
            {
                "year": year,
                "first": by_year[year]["first"],
                "corresponding": by_year[year]["corresponding"],
                "other": by_year[year]["other"],
            }
            for year in years
        ],
        "series": series,
        "papers": papers,
    }
