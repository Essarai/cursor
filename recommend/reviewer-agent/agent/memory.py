"""工具调用结果的 SQLite 长期记忆。"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from cscd.client import normalize_keywords

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "tool_memory.db"

_store: Optional["LongTermMemory"] = None
_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LongTermMemory:
    """持久化缓存 get_recommend_reviewers / get_author_info 的 API 响应。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_memory (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tool_memory_namespace
                ON tool_memory(namespace)
                """
            )

    @staticmethod
    def _hash(parts: str) -> str:
        return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:32]

    def reviewers_key(self, keywords: str) -> str:
        normalized = normalize_keywords(keywords)
        return self._hash(f"reviewers:{normalized}")

    def author_info_key(
        self,
        author: str,
        org: str,
        pub_year: str,
        page: int,
        limit: int,
        author_id: str = "",
    ) -> str:
        raw = (
            f"id:{author_id.strip()}|author:{author.strip()}|org:{org.strip()}|"
            f"year:{pub_year.strip()}|p:{page}|l:{limit}"
        )
        return self._hash(raw)

    def get(self, namespace: str, cache_key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM tool_memory
                WHERE namespace = ? AND cache_key = ?
                """,
                (namespace, cache_key),
            ).fetchone()
            if not row:
                return None

            conn.execute(
                """
                UPDATE tool_memory
                SET hit_count = hit_count + 1, updated_at = ?
                WHERE namespace = ? AND cache_key = ?
                """,
                (_utc_now(), namespace, cache_key),
            )
        return json.loads(row["payload"])

    def put(
        self,
        namespace: str,
        cache_key: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_memory (
                    namespace, cache_key, payload, metadata, created_at, updated_at, hit_count
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(namespace, cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    namespace,
                    cache_key,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )


def get_memory_store() -> LongTermMemory:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                db_path = Path(os.getenv("MEMORY_DB_PATH", str(DEFAULT_DB_PATH)))
                _store = LongTermMemory(db_path)
    return _store
