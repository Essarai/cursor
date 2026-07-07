"""CSCD 工具调用（含长期记忆缓存）。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agent.memory import get_memory_store
from cscd.client import get_api_code, get_peer_reviewers, search_articles

NS_REVIEWERS = "reviewers"
NS_AUTHOR_INFO = "author_info"


def _resolve_api_code(api_code: Optional[str]) -> str:
    return (api_code or "").strip() or get_api_code()


def fetch_reviewers_with_memory(
    keywords: str,
    api_code: Optional[str] = None,
) -> Dict[str, Any]:
    store = get_memory_store()
    cache_key = store.reviewers_key(keywords)
    cached = store.get(NS_REVIEWERS, cache_key)
    if cached is not None:
        return cached

    code = _resolve_api_code(api_code)
    response = get_peer_reviewers(code, keywords)
    if response.get("success"):
        store.put(
            NS_REVIEWERS,
            cache_key,
            response,
            metadata={"keywords": keywords},
        )
    return response


def fetch_author_info_with_memory(
    author: str,
    org: str = "",
    pub_year: str = "",
    page: int = 1,
    limit: int = 20,
    api_code: Optional[str] = None,
) -> Dict[str, Any]:
    store = get_memory_store()
    cache_key = store.author_info_key(author, org, pub_year, page, limit)
    cached = store.get(NS_AUTHOR_INFO, cache_key)
    if cached is not None:
        return cached

    code = _resolve_api_code(api_code)
    response = search_articles(
        code,
        author=author,
        org=org or None,
        page=page,
        limit=limit,
        pub_year=pub_year or None,
    )
    result = response.get("result") or {}
    total = result.get("total") or 0

    if response.get("success") and total == 0 and org.strip():
        retry_key = store.author_info_key(author, "", pub_year, page, limit)
        retry_cached = store.get(NS_AUTHOR_INFO, retry_key)
        if retry_cached is not None:
            return retry_cached

        response = search_articles(
            code,
            author=author,
            org=None,
            page=page,
            limit=limit,
            pub_year=pub_year or None,
        )
        cache_key = retry_key

    if response.get("success"):
        store.put(
            NS_AUTHOR_INFO,
            cache_key,
            response,
            metadata={
                "author": author,
                "org": org,
                "pub_year": pub_year,
                "page": page,
                "limit": limit,
            },
        )

    return response
