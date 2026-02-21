"""
Jan-Seva AI - Research Cache
Persistent SQLite cache for query responses and verified sources.
"""

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.utils.logger import logger


class ResearchCache:
    """SQLite-backed cache for query outputs."""

    def __init__(self):
        settings = get_settings()
        self.enabled = settings.research_cache_enabled
        self.ttl_seconds = max(1, settings.research_cache_ttl_minutes) * 60
        self._lock = threading.Lock()

        db_path = Path(settings.research_cache_path)
        if not db_path.is_absolute():
            backend_root = Path(__file__).resolve().parents[2]
            db_path = backend_root / db_path
        self.db_path = db_path.resolve()

        if self.enabled:
            self._initialize()
            logger.info(f"Research cache enabled at: {self.db_path}")
        else:
            logger.info("Research cache disabled.")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=5.0)

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_cache (
                        cache_key TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        language TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        state_code TEXT,
                        payload_json TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_research_cache_expires ON research_cache(expires_at)"
                )
                conn.commit()

    def _make_key(
        self,
        query: str,
        language: str,
        intent: str,
        state_code: Optional[str],
        profile_fingerprint: Optional[str] = None,
    ) -> str:
        normalized_query = " ".join((query or "").lower().strip().split())
        normalized_lang = (language or "en").lower().strip()
        normalized_intent = (intent or "unknown").strip()
        normalized_state = (state_code or "").upper().strip()
        normalized_profile = (profile_fingerprint or "").strip()
        key_material = (
            f"{normalized_query}|{normalized_lang}|{normalized_intent}|"
            f"{normalized_state}|{normalized_profile}"
        )
        return hashlib.sha256(key_material.encode("utf-8")).hexdigest()

    def get(
        self,
        query: str,
        language: str,
        intent: str,
        state_code: Optional[str],
        profile_fingerprint: Optional[str] = None,
    ) -> Optional[dict]:
        if not self.enabled:
            return None

        cache_key = self._make_key(query, language, intent, state_code, profile_fingerprint)
        now = int(time.time())

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT payload_json, expires_at
                    FROM research_cache
                    WHERE cache_key = ?
                    """,
                    (cache_key,),
                ).fetchone()

                if not row:
                    return None

                payload_json, expires_at = row
                if expires_at < now:
                    conn.execute("DELETE FROM research_cache WHERE cache_key = ?", (cache_key,))
                    conn.commit()
                    return None

        try:
            return json.loads(payload_json)
        except json.JSONDecodeError:
            logger.warning(f"Invalid cache payload detected for key {cache_key}, purging.")
            with self._lock:
                with self._connect() as conn:
                    conn.execute("DELETE FROM research_cache WHERE cache_key = ?", (cache_key,))
                    conn.commit()
            return None

    def put(
        self,
        query: str,
        language: str,
        intent: str,
        state_code: Optional[str],
        payload: dict,
        profile_fingerprint: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return

        cache_key = self._make_key(query, language, intent, state_code, profile_fingerprint)
        now = int(time.time())
        expires_at = now + self.ttl_seconds
        payload_json = json.dumps(payload, ensure_ascii=False)

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO research_cache (
                        cache_key, query, language, intent, state_code,
                        payload_json, created_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        cache_key,
                        query,
                        language,
                        intent,
                        state_code,
                        payload_json,
                        now,
                        expires_at,
                    ),
                )
                conn.commit()

    def purge_expired(self) -> int:
        if not self.enabled:
            return 0
        now = int(time.time())
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM research_cache WHERE expires_at < ?",
                    (now,),
                )
                conn.commit()
                return cursor.rowcount or 0


_research_cache: Optional[ResearchCache] = None


def get_research_cache() -> ResearchCache:
    global _research_cache
    if _research_cache is None:
        _research_cache = ResearchCache()
    return _research_cache
