"""Thread-safe SQLite persistent response cache for deterministic replays and offline execution."""

import hashlib
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.core.config import settings
from app.llm.schemas import LLMCacheMissError, LLMResponse

logger = logging.getLogger("mediflux.llm.cache")


class SQLiteLLMCache:
    """Thread-safe SQLite caching layer supporting off, record, and replay modes."""

    def __init__(self, db_path: str | None = None, mode: str | None = None) -> None:
        self.db_path = db_path or settings.LLM_CACHE_DB_PATH
        self.mode = mode or settings.LLM_CACHE_MODE
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with autocommit isolation."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize the cache schema if it does not exist."""
        # Ensure parent directory exists
        db_file = Path(self.db_path)
        if db_file.parent and str(db_file.parent) != ".":
            db_file.parent.mkdir(parents=True, exist_ok=True)

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    latency_ms REAL DEFAULT 0.0,
                    data_json TEXT NOT NULL,
                    raw_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    @staticmethod
    def compute_cache_key(
        agent: str,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
    ) -> str:
        """Compute a deterministic SHA-256 hash across agent name, messages, and model schema."""
        if hasattr(response_model, "model_json_schema"):
            schema_json = json.dumps(response_model.model_json_schema(), sort_keys=True)
        else:
            from pydantic import TypeAdapter

            schema_json = json.dumps(TypeAdapter(response_model).json_schema(), sort_keys=True)
        messages_json = json.dumps(messages, sort_keys=True)
        combined = f"{agent}:{messages_json}:{schema_json}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(
        self,
        cache_key: str,
        response_model: type[BaseModel],
    ) -> LLMResponse[Any] | None:
        """Retrieve a cached LLMResponse from SQLite.

        Raises:
            LLMCacheMissError: When mode is 'replay' and key is not found.
        """
        if self.mode == "off":
            return None

        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT provider, model, prompt_tokens, completion_tokens, total_tokens, latency_ms, data_json, raw_content
                FROM llm_cache
                WHERE cache_key = ?
                """,
                (cache_key,),
            )
            row = cursor.fetchone()

        if row:
            logger.debug("Cache HIT for key %s", cache_key[:12])
            if hasattr(response_model, "model_validate_json"):
                parsed_data = response_model.model_validate_json(row["data_json"])
            else:
                from pydantic import TypeAdapter

                parsed_data = TypeAdapter(response_model).validate_json(row["data_json"])
            return LLMResponse(
                data=parsed_data,
                provider=row["provider"],
                model=row["model"],
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
                latency_ms=row["latency_ms"],
                cached=True,
                raw_content=row["raw_content"],
            )

        if self.mode == "replay":
            raise LLMCacheMissError(
                f"Cache miss in replay mode for key {cache_key[:12]}. Network calls are disabled."
            )

        return None

    def set(
        self,
        cache_key: str,
        agent: str,
        response: LLMResponse[Any],
    ) -> None:
        """Store validated response and metadata in SQLite if mode is 'record'."""
        if self.mode != "record":
            return

        data_json = (
            response.data.model_dump_json()
            if isinstance(response.data, BaseModel)
            else json.dumps(response.data)
        )

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (
                    cache_key, agent, provider, model, prompt_tokens,
                    completion_tokens, total_tokens, latency_ms, data_json, raw_content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    agent,
                    response.provider,
                    response.model,
                    response.prompt_tokens,
                    response.completion_tokens,
                    response.total_tokens,
                    response.latency_ms,
                    data_json,
                    response.raw_content,
                ),
            )
            conn.commit()

        logger.debug("Cache RECORDED for key %s (agent: %s)", cache_key[:12], agent)

    def clear(self) -> None:
        """Wipe all cached entries."""
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM llm_cache")
            conn.commit()


llm_cache = SQLiteLLMCache()
