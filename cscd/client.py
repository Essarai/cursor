"""CSCD API 客户端（getApiCode / getPeerReviewers / searchArticles）。"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from typing import Any, Deque, Dict, Optional

BASE_URL = os.getenv(
    "CSCD_BASE_URL", "http://sciencechina.cn/cscdboot/CscdService"
)
TIMEOUT = int(os.getenv("CSCD_TIMEOUT", "60"))
API_CODE_TTL = 9 * 60  # ApiCode 约 10 分钟有效，提前 1 分钟刷新

# 会话级全局 ApiCode，阶段一/二共用
_session_api_code: str | None = None
_session_api_code_expires_at: float = 0.0
_api_code_lock = threading.Lock()


class _SlidingWindowRateLimiter:
    """滑动窗口限流，默认 searchArticles 每秒最多 3 次。"""

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


_search_articles_limiter = _SlidingWindowRateLimiter(
    max_calls=int(os.getenv("CSCD_SEARCH_ARTICLES_MAX_PER_SEC", "3")),
    period=1.0,
)


def invalidate_api_code() -> None:
    """清空全局 ApiCode，下次调用 init_api_code 会重新获取。"""
    global _session_api_code, _session_api_code_expires_at
    with _api_code_lock:
        _session_api_code = None
        _session_api_code_expires_at = 0.0


def _is_app_code_error(message: Optional[str]) -> bool:
    return bool(message and "AppCode" in message)


def fetch_api_code(user: str, password: str) -> str:
    """GET /getApiCode?user=...&password=... 获取 ApiCode。"""
    query = urllib.parse.urlencode({"user": user, "password": password})
    url = f"{BASE_URL}/getApiCode?{query}"
    last_message = "获取 ApiCode 失败"
    # CSCD 对频繁 getApiCode 易返回「申请失败」，少重试、拉长间隔
    for attempt in range(2):
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("success") and data.get("result"):
            return str(data["result"])

        last_message = str(data.get("message") or last_message)
        if "申请失败" in last_message and attempt == 0:
            time.sleep(3.0)
            continue
        break

    raise ValueError(last_message)


def _has_cscd_credentials() -> bool:
    return bool(
        os.getenv("CSCD_USER", "").strip() and os.getenv("CSCD_PASSWORD", "").strip()
    )


def _fetch_api_code_from_credentials() -> str:
    user = os.getenv("CSCD_USER", "").strip()
    password = os.getenv("CSCD_PASSWORD", "").strip()
    if not user or not password:
        raise ValueError(
            "缺少 CSCD ApiCode，请设置 CSCD_USER / CSCD_PASSWORD 或 CSCD_API_CODE"
        )
    return fetch_api_code(user, password)


def _fetch_api_code_from_env() -> str:
    direct = os.getenv("CSCD_API_CODE", "").strip()
    if direct:
        return direct
    raise ValueError("请配置 CSCD_API_CODE 或 CSCD_USER / CSCD_PASSWORD")


def init_api_code(force_refresh: bool = False) -> str:
    """初始化全局 ApiCode。

    有 CSCD_USER/PASSWORD 时只走 getApiCode，禁止回退 CSCD_API_CODE
    （静态码约 10 分钟失效，回退极易导致 AppCode错误）。
    仅未配置账号密码时，才使用 CSCD_API_CODE。
    """
    global _session_api_code, _session_api_code_expires_at

    with _api_code_lock:
        now = time.time()
        if (
            not force_refresh
            and _session_api_code
            and now < _session_api_code_expires_at
        ):
            return _session_api_code

        if _has_cscd_credentials():
            try:
                code = _fetch_api_code_from_credentials()
            except ValueError as exc:
                raise ValueError(
                    f"CSCD ApiCode 获取失败：{exc}。"
                    "已配置 CSCD_USER/CSCD_PASSWORD，不会回退 CSCD_API_CODE；"
                    "请确认账号密码正确，或稍后再试（接口可能限流）。"
                ) from exc
        else:
            try:
                code = _fetch_api_code_from_env()
            except ValueError as exc:
                raise ValueError(
                    f"CSCD ApiCode 获取失败：{exc}。"
                    "请配置 CSCD_USER/CSCD_PASSWORD（推荐），或更新 CSCD_API_CODE。"
                ) from exc

        _session_api_code = code
        _session_api_code_expires_at = now + API_CODE_TTL
        return _session_api_code


def get_api_code() -> str:
    """读取全局 ApiCode；未初始化或已过期则自动 init。"""
    if (
        _session_api_code
        and time.time() < _session_api_code_expires_at
    ):
        return _session_api_code
    return init_api_code()


def obtain_api_code(explicit: str | None = None, force_refresh: bool = False) -> str:
    """兼容旧接口：显式传入 > 全局 ApiCode。"""
    code = (explicit or "").strip()
    if code:
        return code
    return init_api_code(force_refresh=force_refresh)


def _request(
    path: str,
    params: Dict[str, str],
    api_code: str,
) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={"ApiCode": api_code},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
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


def _request_with_session_api_code(
    path: str,
    params: Dict[str, str],
    api_code: str,
) -> Dict[str, Any]:
    """使用传入的 ApiCode 请求；过期时刷新全局并重试一次。"""
    code = api_code.strip() or get_api_code()
    for attempt in range(2):
        data = _request(path, params, code)
        if data.get("success"):
            global _session_api_code, _session_api_code_expires_at
            with _api_code_lock:
                _session_api_code = code
                _session_api_code_expires_at = time.time() + API_CODE_TTL
            return data
        if _is_app_code_error(data.get("message")) and attempt == 0:
            invalidate_api_code()
            try:
                # 强制重新申请；有账号密码时不会再用静态 CSCD_API_CODE
                code = init_api_code(force_refresh=True)
            except ValueError:
                return data
            continue
        return data
    return data


def normalize_keywords(keywords: str) -> str:
    parts = re.split(r"[;；,，、\n]+", keywords.strip())
    return ";;".join(p.strip() for p in parts if p.strip())


def get_peer_reviewers(api_code: str, keywords: str) -> Dict[str, Any]:
    keyword_str = normalize_keywords(keywords)
    if not keyword_str:
        return {
            "success": False,
            "message": "请至少输入一个关键词",
            "code": 400,
            "result": None,
            "timestamp": 0,
        }
    code = api_code.strip() or get_api_code()
    return _request_with_session_api_code(
        "/getPeerReviewers",
        {"keywords": keyword_str},
        code,
    )


def search_articles(
    api_code: str,
    author: str,
    org: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    pub_year: Optional[str] = None,
) -> Dict[str, Any]:
    if not author.strip():
        return {
            "success": False,
            "message": "缺少 author",
            "code": 400,
            "result": None,
            "timestamp": 0,
        }

    params: Dict[str, str] = {
        "author": author.strip(),
        "page": str(page),
        "limit": str(min(limit, 50)),
    }
    if org and org.strip():
        params["institute"] = org.strip()
    if pub_year and pub_year.strip():
        params["pubYear"] = pub_year.strip()

    _search_articles_limiter.acquire()
    code = api_code.strip() or get_api_code()
    return _request_with_session_api_code("/searchArticles", params, code)
