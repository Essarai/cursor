"""CSCD API 客户端（getApiCode / getPeerReviewers / searchArticles）。"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from typing import Any, Deque

API_CODE_TTL = 9 * 60

_session_api_code: str | None = None
_session_api_code_expires_at: float = 0.0
_api_code_lock = threading.Lock()


class _SlidingWindowRateLimiter:
    def __init__(self, max_calls: int, period: float) -> None:
        self._max_calls = max_calls
        self._period = period
        self._timestamps: Deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self._period
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._max_calls:
                wait = self._timestamps[0] + self._period - now
                if wait > 0:
                    time.sleep(wait)
                now = time.monotonic()
                cutoff = now - self._period
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

            self._timestamps.append(time.monotonic())


class CscdClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = config.get(
            "base_url", "http://sciencechina.cn/cscdboot/CscdService"
        ).rstrip("/")
        self.timeout = int(config.get("timeout", 60))
        self.user = (config.get("user") or "").strip()
        self.password = (config.get("password") or "").strip()
        max_per_sec = int(config.get("search_articles_max_per_sec", 3))
        self._search_limiter = _SlidingWindowRateLimiter(max_per_sec, 1.0)

    def invalidate_api_code(self) -> None:
        global _session_api_code, _session_api_code_expires_at
        with _api_code_lock:
            _session_api_code = None
            _session_api_code_expires_at = 0.0

    @staticmethod
    def _is_app_code_error(message: str | None) -> bool:
        return bool(message and "AppCode" in message)

    @staticmethod
    def normalize_keywords(keywords: str) -> str:
        parts = re.split(r"[;；,，、\n]+", keywords.strip())
        return ";;".join(part.strip() for part in parts if part.strip())

    def _request(self, path: str, params: dict[str, str], api_code: str) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{path}?{query}"
        req = urllib.request.Request(
            url,
            headers={"ApiCode": api_code},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            return {
                "success": False,
                "message": f"HTTP {err.code}: {body[:300]}",
                "code": err.code,
                "result": None,
                "timestamp": 0,
            }
        except urllib.error.URLError as err:
            return {
                "success": False,
                "message": f"网络错误: {err.reason}",
                "code": 500,
                "result": None,
                "timestamp": 0,
            }

    def get_api_code(self, user: str | None = None, password: str | None = None) -> dict[str, Any]:
        """GET /getApiCode?user=...&password=..."""
        username = (user or self.user).strip()
        passwd = (password or self.password).strip()
        if not username or not passwd:
            return {
                "success": False,
                "message": "缺少 user 或 password，请在 config.yaml 的 cscd 段配置",
                "code": 400,
                "result": None,
                "timestamp": 0,
            }

        query = urllib.parse.urlencode({"user": username, "password": passwd})
        url = f"{self.base_url}/getApiCode?{query}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            return {
                "success": False,
                "message": f"HTTP {err.code}: {body[:300]}",
                "code": err.code,
                "result": None,
                "timestamp": 0,
            }
        except urllib.error.URLError as err:
            return {
                "success": False,
                "message": f"网络错误: {err.reason}",
                "code": 500,
                "result": None,
                "timestamp": 0,
            }

        if data.get("success") and data.get("result"):
            self._cache_api_code(str(data["result"]))
        return data

    def _cache_api_code(self, code: str) -> None:
        global _session_api_code, _session_api_code_expires_at
        with _api_code_lock:
            _session_api_code = code
            _session_api_code_expires_at = time.time() + API_CODE_TTL

    def refresh_api_code(self) -> str:
        """使用 config 中的 user/password 强制获取新的 ApiCode。"""
        self.invalidate_api_code()
        if not self.user or not self.password:
            raise ValueError("请在 config.yaml 配置 cscd.user / cscd.password")

        data = self.get_api_code(self.user, self.password)
        if not data.get("success") or not data.get("result"):
            message = data.get("message") or "获取 ApiCode 失败"
            raise ValueError(message)
        return str(data["result"])

    def _resolve_api_code(self, force_refresh: bool = False) -> str:
        global _session_api_code, _session_api_code_expires_at

        with _api_code_lock:
            now = time.time()
            if (
                not force_refresh
                and _session_api_code
                and now < _session_api_code_expires_at
            ):
                return _session_api_code

            if self.user and self.password:
                data = self.get_api_code(self.user, self.password)
                if not data.get("success") or not data.get("result"):
                    message = data.get("message") or "获取 ApiCode 失败"
                    raise ValueError(message)
                return str(data["result"])

            raise ValueError("请在 config.yaml 配置 cscd.user / cscd.password")

    def _request_with_api_code(
        self,
        path: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        code = self._resolve_api_code()
        for attempt in range(2):
            data = self._request(path, params, code)
            if data.get("success"):
                return data
            if self._is_app_code_error(data.get("message")) and attempt == 0:
                self.invalidate_api_code()
                code = self._resolve_api_code(force_refresh=True)
                continue
            return data
        return data

    def get_peer_reviewers(self, keywords: str) -> dict[str, Any]:
        """GET /getPeerReviewers?keywords=...，Header: ApiCode"""
        keyword_str = self.normalize_keywords(keywords)
        if not keyword_str:
            return {
                "success": False,
                "message": "请至少输入一个关键词",
                "code": 400,
                "result": None,
                "timestamp": 0,
            }
        return self._request_with_api_code(
            "/getPeerReviewers",
            {"keywords": keyword_str},
        )

    def search_articles(
        self,
        author: str,
        org: str | None = None,
        page: int = 1,
        limit: int = 20,
        pub_year: str | None = None,
    ) -> dict[str, Any]:
        """GET /searchArticles，Header: ApiCode"""
        if not author.strip():
            return {
                "success": False,
                "message": "缺少 author",
                "code": 400,
                "result": None,
                "timestamp": 0,
            }

        params: dict[str, str] = {
            "author": author.strip(),
            "page": str(page),
            "limit": str(min(limit, 50)),
        }
        if org and org.strip():
            params["institute"] = org.strip()
        if pub_year and pub_year.strip():
            params["pubYear"] = pub_year.strip()

        self._search_limiter.acquire()
        return self._request_with_api_code("/searchArticles", params)
