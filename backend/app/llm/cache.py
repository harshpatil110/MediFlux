"""Deterministic LLM Record & Replay Cache for offline demos and test reproducibility.

Supports:
- Normalized cache keys invariant to dynamic UUIDs and ISO timestamps.
- JSON file persistence (`fixtures/demo_cache/llm_replay_cache.json`).
- Secondary thread-safe SQLite fallback store.
- 'off', 'record', and 'replay' modes with instant (< 50ms) offline responses.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.core.config import settings
from app.llm.schemas import LLMCacheMissError, LLMResponse

logger = logging.getLogger("mediflux.llm.cache")

UUID_REGEX = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
TIMESTAMP_REGEX = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)
DATE_REGEX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def normalize_prompt_text(text: str) -> str:
    """Strip dynamic UUIDs and timestamps to create deterministic prompt signatures."""
    text = UUID_REGEX.sub("<UUID>", text)
    text = TIMESTAMP_REGEX.sub("<TIMESTAMP>", text)
    text = DATE_REGEX.sub("<DATE>", text)
    return text.strip()


class SQLiteLLMCache:
    """Thread-safe SQLite caching layer supporting off, record, and replay modes."""

    def __init__(self, db_path: str | None = None, mode: str | None = None) -> None:
        self.db_path = db_path or settings.LLM_CACHE_DB_PATH
        self._mode_override = mode
        self._lock = threading.Lock()
        self._init_db()

    @property
    def mode(self) -> str:
        if self._mode_override:
            return self._mode_override
        if getattr(settings, "DEMO_MODE", False) or getattr(settings, "LLM_CACHE_MODE", "") == "replay":
            return "replay"
        return settings.LLM_CACHE_MODE

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with autocommit isolation."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize the cache schema if it does not exist."""
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
        response_model: type[BaseModel] | Any = None,
    ) -> str:
        """Compute a deterministic SHA-256 hash across agent name, messages, and model schema."""
        if response_model is None:
            schema_json = "{}"
        elif hasattr(response_model, "model_json_schema"):
            schema_json = json.dumps(response_model.model_json_schema(), sort_keys=True)
        else:
            from pydantic import TypeAdapter

            schema_json = json.dumps(TypeAdapter(response_model).json_schema(), sort_keys=True)
        messages_json = json.dumps(messages, sort_keys=True)
        combined = f"{agent}:{messages_json}:{schema_json}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(
        self,
        cache_key: str | None = None,
        response_model: type[BaseModel] | Any = None,
        agent: str | None = None,
        messages: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse[Any] | None:
        """Retrieve a cached LLMResponse from SQLite."""
        if self.mode == "off":
            return None

        if cache_key is None and agent and messages:
            cache_key = self.compute_cache_key(agent, messages, response_model)
        if cache_key is None:
            return None
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
            logger.debug("SQLite cache HIT for key %s", cache_key[:12])
            if response_model is None:
                parsed_data = json.loads(row["data_json"])
            elif hasattr(response_model, "model_validate_json"):
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
        **kwargs: Any,
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

    def clear(self) -> None:
        """Wipe all cached SQLite entries."""
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM llm_cache")
            conn.commit()


class LLMReplayCache:
    """Hybrid in-memory JSON & SQLite deterministic replay cache."""

    def __init__(
        self,
        json_path: str | None = None,
        db_path: str | None = None,
        mode: str | None = None,
    ) -> None:
        self.json_path = json_path or settings.LLM_CACHE_PATH
        self._mode_override = mode
        self.sqlite_cache = SQLiteLLMCache(db_path=db_path, mode=mode)
        self._entries: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._resolved_json_path: Path | None = None
        self.load()

    @property
    def mode(self) -> str:
        if self._mode_override:
            return self._mode_override
        if getattr(settings, "DEMO_MODE", False) or getattr(settings, "LLM_CACHE_MODE", "") == "replay":
            return "replay"
        return settings.LLM_CACHE_MODE

    def _find_json_path(self) -> Path:
        """Locate the JSON replay cache file across root, backend, and relative paths."""
        candidates = [
            Path(self.json_path),
            Path("backend") / self.json_path,
            Path(__file__).resolve().parent.parent.parent / self.json_path,
            Path(__file__).resolve().parent.parent.parent.parent / self.json_path,
            Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "demo_cache" / "llm_replay_cache.json",
        ]
        for c in candidates:
            if c.is_file():
                return c
        # Default to root fixtures/demo_cache path if not found
        fallback = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "demo_cache" / "llm_replay_cache.json"
        return fallback

    def load(self, path: str | None = None) -> int:
        """Load entries from the JSON replay cache file into memory."""
        target = Path(path) if path else self._find_json_path()
        self._resolved_json_path = target
        if not target.is_file():
            return 0

        try:
            with open(target, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    with self._lock:
                        self._entries.update(data)
                    logger.info("Loaded %d LLM replay cache entries from %s", len(data), target)
                    return len(data)
        except Exception as exc:
            logger.warning("Failed to load JSON replay cache from %s: %s", target, exc)
        return 0

    def save(self, path: str | None = None) -> None:
        """Persist in-memory replay entries to JSON disk file."""
        target = Path(path) if path else (self._resolved_json_path or self._find_json_path())
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = dict(self._entries)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        logger.info("Saved %d LLM replay cache entries to %s", len(payload), target)

    @classmethod
    def compute_cache_key(
        cls,
        agent: str,
        messages: list[dict[str, str]],
        response_model: type[BaseModel] | Any = None,
    ) -> str:
        """Compute standard SHA-256 hash."""
        return SQLiteLLMCache.compute_cache_key(agent, messages, response_model)

    @classmethod
    def compute_normalized_cache_key(
        cls,
        agent: str,
        messages: list[dict[str, str]],
        response_model: type[BaseModel] | Any = None,
    ) -> str:
        """Compute normalized hash invariant to dynamic run UUIDs and timestamps."""
        norm_messages = []
        for msg in messages:
            norm_messages.append({
                "role": msg.get("role", ""),
                "content": normalize_prompt_text(str(msg.get("content", ""))),
            })
        if response_model is None:
            schema_json = "{}"
        elif hasattr(response_model, "model_json_schema"):
            schema_json = json.dumps(response_model.model_json_schema(), sort_keys=True)
        else:
            from pydantic import TypeAdapter

            schema_json = json.dumps(TypeAdapter(response_model).json_schema(), sort_keys=True)
        messages_json = json.dumps(norm_messages, sort_keys=True)
        combined = f"norm:{agent}:{messages_json}:{schema_json}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(
        self,
        cache_key: str | None = None,
        response_model: type[BaseModel] | Any = None,
        agent: str | None = None,
        messages: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse[Any] | None:
        """Retrieve response from JSON cache, normalized fallback, or SQLite."""
        if self.mode == "off":
            return None

        if cache_key is None:
            if agent and messages:
                cache_key = self.compute_cache_key(agent, messages, response_model)
            elif kwargs.get("prompt"):
                cache_key = f"prompt:{kwargs['prompt']}"
            elif agent:
                cache_key = f"agent:{agent}"
            else:
                cache_key = "default_cache_key"

        # 1. Exact match in JSON cache
        with self._lock:
            entry = self._entries.get(cache_key)

        # 2. Normalized match in JSON cache
        if not entry and agent and messages:
            norm_key = self.compute_normalized_cache_key(agent, messages, response_model)
            with self._lock:
                entry = self._entries.get(norm_key)

        # 3. Fallback match by agent in JSON cache (named demo act cassettes during DEMO_MODE or replay)
        if not entry and agent and (getattr(settings, "DEMO_MODE", False) or self.mode == "replay"):
            with self._lock:
                for k, v in self._entries.items():
                    if k.startswith(f"norm:{agent}:") or v.get("agent") == agent:
                        entry = v
                        break

        if entry:
            logger.debug("LLMReplayCache HIT for key %s", cache_key[:12])
            raw_data = entry.get("data_json", "{}")
            try:
                if response_model is None:
                    parsed_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                elif hasattr(response_model, "model_validate_json"):
                    parsed_data = response_model.model_validate_json(raw_data)
                else:
                    from pydantic import TypeAdapter

                    parsed_data = TypeAdapter(response_model).validate_json(raw_data)

                return LLMResponse(
                    data=parsed_data,
                    provider=entry.get("provider", "cached_replay"),
                    model=entry.get("model", "replay-model"),
                    prompt_tokens=entry.get("prompt_tokens", 50),
                    completion_tokens=entry.get("completion_tokens", 25),
                    total_tokens=entry.get("total_tokens", 75),
                    latency_ms=entry.get("latency_ms", 12.0),
                    cached=True,
                    raw_content=entry.get("raw_content", raw_data),
                )
            except Exception as val_err:
                logger.debug("LLMReplayCache entry schema mismatch: %s", val_err)
                entry = None

        # 3. Check SQLite cache
        try:
            sqlite_resp = self.sqlite_cache.get(cache_key, response_model, **kwargs)
            if sqlite_resp:
                return sqlite_resp
        except LLMCacheMissError:
            pass

        # 4. In replay/demo mode, cache miss is fatal to guarantee no external network calls
        if self.mode == "replay":
            raise LLMCacheMissError(
                f"Replay cache miss for key {cache_key[:12]} (agent: {agent}). Network calls blocked."
            )

        return None

    def set(
        self,
        cache_key: str,
        agent: str,
        response: LLMResponse[Any],
        messages: list[dict[str, str]] | None = None,
        response_model: type[BaseModel] | Any = None,
        **kwargs: Any,
    ) -> None:
        """Record response into JSON store and SQLite cache."""
        if self.mode != "record":
            return

        data_json = (
            response.data.model_dump_json()
            if isinstance(response.data, BaseModel)
            else json.dumps(response.data)
        )

        entry = {
            "agent": agent,
            "provider": response.provider,
            "model": response.model,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
            "latency_ms": response.latency_ms,
            "data_json": data_json,
            "raw_content": response.raw_content,
        }

        with self._lock:
            self._entries[cache_key] = entry
            if messages and response_model:
                norm_key = self.compute_normalized_cache_key(agent, messages, response_model)
                self._entries[norm_key] = entry

        try:
            self.save()
        except Exception as exc:
            logger.warning("Failed to auto-save JSON replay cache: %s", exc)

        self.sqlite_cache.set(cache_key, agent, response)

    def clear(self) -> None:
        """Clear both in-memory entries and SQLite database."""
        with self._lock:
            self._entries.clear()
        self.sqlite_cache.clear()

    def count(self) -> int:
        """Return total number of cached entries."""
        with self._lock:
            return len(self._entries)


# Default global instance
llm_cache = LLMReplayCache()
