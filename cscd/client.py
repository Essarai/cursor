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
_session_api_code_source: str | None = None  # "env" | "credentials"
_api_code_lock = threading.Lock()
# 静态 CSCD_API_CODE 已判定过期（AppCode 错误 / 强制刷新）后，改走账号密码
_prefer_credentials: bool = False
# getApiCode「申请失败」后冷却，避免冷启动/并发反复打爆限流
_api_code_fail_until: float = 0.0
API_CODE_FAIL_COOLDOWN = float(os.getenv("CSCD_API_CODE_FAIL_COOLDOWN", "45"))


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
    """清空全局 ApiCode；标记静态码已过期，下次优先用账号密码刷新。"""
    global _session_api_code, _session_api_code_expires_at
    global _prefer_credentials, _session_api_code_source
    with _api_code_lock:
        _session_api_code = None
        _session_api_code_expires_at = 0.0
        _session_api_code_source = None
        _prefer_credentials = True


def _is_app_code_error(message: Optional[str]) -> bool:
    return bool(message and "AppCode" in message)


def fetch_api_code(user: str, password: str) -> str:
    """GET /getApiCode?user=...&password=... 获取 ApiCode。"""
    query = urllib.parse.urlencode({"user": user, "password": password})
    url = f"{BASE_URL}/getApiCode?{query}"
    last_message = "获取 ApiCode 失败"
    # CSCD 对频繁 getApiCode / 非白名单出口易返回「申请失败」；拉长退避少打爆
    delays = (0.0, 5.0, 12.0, 25.0)
    for attempt, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("success") and data.get("result"):
            return str(data["result"])

        last_message = str(data.get("message") or last_message)
        if "申请失败" in last_message and attempt < len(delays) - 1:
            continue
        break

    raise ValueError(last_message)


def _has_cscd_credentials() -> bool:
    return bool(
        os.getenv("CSCD_USER", "").strip() and os.getenv("CSCD_PASSWORD", "").strip()
    )


def _static_api_code_from_env() -> str:
    return os.getenv("CSCD_API_CODE", "").strip()


def _fetch_api_code_from_credentials() -> str:
    user = os.getenv("CSCD_USER", "").strip()
    password = os.getenv("CSCD_PASSWORD", "").strip()
    if not user or not password:
        raise ValueError(
            "缺少 CSCD ApiCode，请设置 CSCD_USER / CSCD_PASSWORD 或 CSCD_API_CODE"
        )
    return fetch_api_code(user, password)


def init_api_code(force_refresh: bool = False) -> str:
    """初始化全局 ApiCode。

    优先读环境变量 CSCD_API_CODE；未配置或已过期（force_refresh /
    AppCode 错误后）再用 CSCD_USER/PASSWORD 调 getApiCode。
    """
    global _session_api_code, _session_api_code_expires_at, _session_api_code_source
    global _api_code_fail_until, _prefer_credentials

    with _api_code_lock:
        now = time.time()
        if (
            not force_refresh
            and _session_api_code
            and now < _session_api_code_expires_at
        ):
            return _session_api_code

        static = _static_api_code_from_env()
        # 内存 TTL 到期且上次是静态码 → 视为过期，改走密码
        ttl_expired_static = (
            bool(_session_api_code)
            and now >= _session_api_code_expires_at
            and _session_api_code_source == "env"
        )
        # 有静态码且尚未判定过期 → 直接用，避免无谓打 getApiCode
        use_static = (
            bool(static)
            and not force_refresh
            and not _prefer_credentials
            and not ttl_expired_static
        )
        clear_fail_cooldown = True
        source = "env"

        if use_static:
            code = static
            source = "env"
        elif _has_cscd_credentials():
            if now < _api_code_fail_until and not force_refresh:
                wait = int(_api_code_fail_until - now)
                raise ValueError(
                    f"CSCD ApiCode 获取失败：申请失败（冷却中，约 {wait}s 后再试）。"
                    "常见原因：出口 IP 未进白名单，或 getApiCode 被限流。"
                    "请打开 /api/v1/cscd/status 核对 egress_ip 与申请结果。"
                )
            try:
                code = _fetch_api_code_from_credentials()
                source = "credentials"
            except ValueError as exc:
                _api_code_fail_until = time.time() + API_CODE_FAIL_COOLDOWN
                clear_fail_cooldown = False
                # 密码申请失败时，若仍有静态码可作最后兜底（可能也已过期）
                if static:
                    code = static
                    source = "env"
                else:
                    raise ValueError(
                        f"CSCD ApiCode 获取失败：{exc}。"
                        "请确认 CSCD_USER/CSCD_PASSWORD、出口 IP 白名单，"
                        "或更新 CSCD_API_CODE。"
                        "可访问 /api/v1/cscd/status 查看 egress_ip。"
                    ) from exc
        elif static:
            # 无账号密码，只能继续用环境变量
            code = static
            source = "env"
        else:
            raise ValueError(
                "CSCD ApiCode 获取失败：请配置 CSCD_API_CODE，"
                "或 CSCD_USER / CSCD_PASSWORD。"
            )

        _session_api_code = code
        _session_api_code_expires_at = now + API_CODE_TTL
        _session_api_code_source = source
        if clear_fail_cooldown:
            _api_code_fail_until = 0.0
        # 成功用密码刷到新码后，允许后续再优先读（可能已更新的）静态码
        if source == "credentials":
            _prefer_credentials = False
        return _session_api_code


def probe_egress_ip(timeout: float = 8.0) -> str | None:
    """探测本服务访问外网时的出口 IP（用于 CSCD 白名单核对）。"""
    for url in (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "http://ip.sb",
    ):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ip = resp.read().decode("utf-8", errors="replace").strip()
            if ip and re.match(r"^[\d.]+$", ip):
                return ip
        except Exception:  # noqa: BLE001
            continue
    return None


def diagnose_cscd() -> Dict[str, Any]:
    """线上排查：凭证是否配置、出口 IP、当前鉴权策略（不返回码本身）。"""
    has_user = bool(os.getenv("CSCD_USER", "").strip())
    has_password = bool(os.getenv("CSCD_PASSWORD", "").strip())
    has_static = bool(_static_api_code_from_env())
    egress_ip = probe_egress_ip()

    get_api_code_ok = False
    get_api_code_message = ""
    used_cached = False
    source = ""
    if _session_api_code and time.time() < _session_api_code_expires_at:
        get_api_code_ok = True
        get_api_code_message = "使用内存缓存中的有效 ApiCode"
        used_cached = True
        source = "cache"
    else:
        try:
            # 与线上一致：优先静态码，过期/强制时再走密码
            init_api_code(force_refresh=_prefer_credentials)
            get_api_code_ok = True
            if has_static and not _prefer_credentials:
                source = "env"
                get_api_code_message = "使用环境变量 CSCD_API_CODE"
            elif has_user and has_password:
                source = "credentials"
                get_api_code_message = "通过 CSCD_USER/PASSWORD 申请成功"
            else:
                source = "env"
                get_api_code_message = "使用环境变量 CSCD_API_CODE"
        except ValueError as exc:
            get_api_code_message = str(exc)

    return {
        "base_url": BASE_URL,
        "has_cscd_user": has_user,
        "has_cscd_password": has_password,
        "has_static_api_code": has_static,
        "prefer_credentials": _prefer_credentials,
        "api_code_source": source,
        "egress_ip": egress_ip,
        "get_api_code_ok": get_api_code_ok,
        "get_api_code_message": get_api_code_message,
        "used_cached_api_code": used_cached,
        "hint": (
            "优先 CSCD_API_CODE；缺失或 AppCode 过期后再用账号密码 getApiCode。"
            "若申请失败，请把 egress_ip 加入 CSCD 白名单（Railway 需固定出口 IP）。"
        ),
    }

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
                # 静态码过期后强制用账号密码重新申请
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
