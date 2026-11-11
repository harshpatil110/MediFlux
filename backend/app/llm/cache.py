"""Deterministic in-memory and disk-based LLM response cache.

Strict constraint: NO Redis. In-process cache with optional local json/file persistence.
"""

import hashlib
import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMCache:
    """In-process deterministic cache for LLM responses."""

    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or settings.LLM_CACHE_MODE
        self._store: dict[str, dict[str, Any]] = {}

    def _generate_key(self, model: str, messages: list[dict[str, Any]], temperature: float) -> str:
        """Generate a deterministic SHA-256 hash for a completion request."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": round(temperature, 4),
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, model: str, messages: list[dict[str, Any]], temperature: float) -> dict[str, Any] | None:
        """Lookup cached response if cache mode permits reading."""
        if self.mode in ("off",):
            return None

        key = self._generate_key(model, messages, temperature)
        result = self._store.get(key)
        if result:
            logger.debug("LLM Cache HIT for key %s", key[:8])
            return result
        return None

    def set(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        response: dict[str, Any],
    ) -> None:
        """Store LLM response if cache mode is 'record'."""
        if self.mode != "record":
            return

        key = self._generate_key(model, messages, temperature)
        self._store[key] = response
        logger.debug("LLM Cache RECORD for key %s", key[:8])

    def clear(self) -> None:
        """Clear the in-memory cache store."""
        self._store.clear()


llm_cache = LLMCache()
