import threading
import time
from typing import Any

import requests


class CscdClient:
    """中国科学引文数据库接口客户端。"""

    BASE_URL = "http://sciencechina.cn/cscdboot/CscdService"
    API_CODE_IDLE_TIMEOUT = 10 * 60
    ARTICLE_PAGE_SIZE = 50

    def __init__(
        self,
        user: str = "academax",
        password: str = "d8ckjs2w",
        timeout: float = 30,
    ) -> None:
        self.user = user
        self.password = password
        self.timeout = timeout
        self._api_code: str | None = None
        self._last_used_at: float | None = None
        self._api_code_lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
                "Accept": "*/*",
            }
        )

    def get_api_code(self, force_refresh: bool = False) -> str:
        """获取 APIcode；未过期时直接返回缓存值。并发安全。"""
        with self._api_code_lock:
            if not force_refresh and self._api_code_is_valid():
                assert self._api_code is not None
                return self._api_code

            response = self._session.get(
                f"{self.BASE_URL}/getApiCode",
                params={"user": self.user, "password": self.password},
                timeout=self.timeout,
            )
            response.raise_for_status()

            self._api_code = self._extract_api_code(self._response_data(response))
            self._last_used_at = time.monotonic()
            return self._api_code

    def get_peer_reviewers(self, keywords: str) -> Any:
        """根据关键词获取审稿人信息。"""
        return self._authenticated_get(
            "getPeerReviewers",
            params={"keywords": keywords},
        )

    def get_peer_reviewer_candidates(
        self,
        keywords: str,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """获取并规范化审稿人候选人，最多返回 ``max_results`` 人。"""
        payload = self.get_peer_reviewers(keywords)
        items = self._extract_result_list(payload)
        return [
            self._normalize_mapping(item)
            for item in items[:max(0, max_results)]
            if isinstance(item, dict)
        ]

    def search_articles(
        self,
        author: str,
        org: str,
        page: int = 1,
        limit: int = ARTICLE_PAGE_SIZE,
    ) -> Any:
        """分页获取作者发文信息。服务端单页最多返回 50 篇。"""
        return self._authenticated_get(
            "searchArticles",
            params={
                "author": author,
                "org": org,
                "page": str(max(1, page)),
                "limit": str(min(max(1, limit), self.ARTICLE_PAGE_SIZE)),
            },
        )

    def get_author_articles(
        self,
        author: str,
        org: str,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """分页获取并规范化作者发文，默认最多返回前 100 篇。"""
        articles: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        page = 1

        while len(articles) < max_results:
            payload = self.search_articles(
                author,
                org,
                page=page,
                limit=self.ARTICLE_PAGE_SIZE,
            )
            result = payload.get("result", {}) if isinstance(payload, dict) else {}
            items = result.get("data", []) if isinstance(result, dict) else []
            if not isinstance(items, list) or not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_mapping(item)
                article_id = str(normalized.get("cscdId") or "")
                if article_id and article_id in seen_ids:
                    continue
                if article_id:
                    seen_ids.add(article_id)
                articles.append(normalized)
                if len(articles) >= max_results:
                    break

            total = self._to_int(result.get("total"))
            if len(articles) >= max_results or len(items) < self.ARTICLE_PAGE_SIZE:
                break
            if total is not None and page * self.ARTICLE_PAGE_SIZE >= total:
                break
            page += 1

        return articles

    def _authenticated_get(self, path: str, params: dict[str, str]) -> Any:
        api_code = self.get_api_code()
        response = self._session.get(
            f"{self.BASE_URL}/{path}",
            params=params,
            headers={"ApiCode": api_code},
            timeout=self.timeout,
        )

        if response.status_code in {401, 403}:
            api_code = self.get_api_code(force_refresh=True)
            response = self._session.get(
                f"{self.BASE_URL}/{path}",
                params=params,
                headers={"ApiCode": api_code},
                timeout=self.timeout,
            )

        response.raise_for_status()
        self._last_used_at = time.monotonic()
        return self._response_data(response)

    def _api_code_is_valid(self) -> bool:
        if self._api_code is None or self._last_used_at is None:
            return False
        return time.monotonic() - self._last_used_at < self.API_CODE_IDLE_TIMEOUT

    @staticmethod
    def _response_data(response: requests.Response) -> Any:
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            return response.text.strip()

    @classmethod
    def _extract_api_code(cls, payload: Any) -> str:
        if isinstance(payload, str) and payload.strip():
            return payload.strip().strip('"')

        if isinstance(payload, dict):
            normalized = {str(key).lower(): value for key, value in payload.items()}
            for key in ("apicode", "api_code", "data", "result", "code"):
                if key in normalized:
                    try:
                        return cls._extract_api_code(normalized[key])
                    except ValueError:
                        continue

        raise ValueError(f"无法从响应中解析 APIcode：{payload!r}")

    @staticmethod
    def _extract_result_list(payload: Any) -> list[Any]:
        if not isinstance(payload, dict):
            return []
        result = payload.get("result", [])
        return result if isinstance(result, list) else []

    @classmethod
    def _normalize_mapping(cls, value: dict[str, Any]) -> dict[str, Any]:
        return {str(key): cls._normalize_value(item) for key, item in value.items()}

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.lower() in {"", "null", "none", "n/a"}:
                return None
            return stripped
        if isinstance(value, dict):
            return cls._normalize_mapping(value)
        if isinstance(value, list):
            return [cls._normalize_value(item) for item in value]
        return value

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
