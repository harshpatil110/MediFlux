"""Developer Scoped API Keys, Hashing, Token-Bucket Rate Limiter & Usage Telemetry.

Task 22: Developer Platform Foundation.
Architectural Note:
Per AGENTS.md, Redis is strictly deferred in the MVP.
Rate limiting is maintained in-process using an async-safe Token-Bucket algorithm.
In multi-worker production deployments, this can be swapped to a distributed
Redis Lua script implementation with zero schema changes.
"""

import asyncio
import hashlib
import logging
import math
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client

logger = logging.getLogger("mediflux.services.api_keys")

# Canonical Developer Scopes
CANONICAL_SCOPES = [
    "read:inventory",
    "write:events",
    "read:stream",
    "read:audit",
    "use:copilot",
    "manage:adapters",
    "*",
    "all",
]

# Synchronized in-memory API key store: key_hash -> key_record
_in_memory_api_keys: dict[str, dict[str, Any]] = {}
# Index by ID for fast lookup & revocation: key_id -> key_hash
_id_to_hash_index: dict[str, str] = {}


class TokenBucketRateLimiter:
    """Thread/async-safe in-memory Token-Bucket Rate Limiter per API key."""

    def __init__(self) -> None:
        # key_id -> {"tokens": float, "last_refill": float, "capacity": float, "refill_rate": float}
        self._buckets: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def check_and_consume(
        self, key_id: str, rate_limit: int
    ) -> tuple[bool, int, float, float]:
        """Evaluate token availability and consume 1.0 token if permitted.

        Parameters:
            key_id: Unique identifier of the API key
            rate_limit: Requests permitted per minute (bucket capacity)

        Returns:
            (allowed, retry_after_seconds, remaining_tokens, capacity)
        """
        import time

        now = time.time()
        capacity = max(1.0, float(rate_limit))
        refill_rate = capacity / 60.0  # tokens added per second

        bucket = self._buckets.get(key_id)
        if bucket is None:
            bucket = {
                "tokens": capacity,
                "last_refill": now,
                "capacity": capacity,
                "refill_rate": refill_rate,
            }
            self._buckets[key_id] = bucket
        else:
            bucket["capacity"] = capacity
            bucket["refill_rate"] = refill_rate
            elapsed = max(0.0, now - bucket["last_refill"])
            bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * refill_rate)
            bucket["last_refill"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return (True, 0, bucket["tokens"], capacity)
        else:
            needed = 1.0 - bucket["tokens"]
            retry_after = max(1, math.ceil(needed / refill_rate)) if refill_rate > 0 else 60
            return (False, retry_after, bucket["tokens"], capacity)

    def reset(self, key_id: str | None = None) -> None:
        """Reset rate limiter state for a single key or all keys."""
        if key_id:
            self._buckets.pop(key_id, None)
        else:
            self._buckets.clear()


# Global in-memory rate limiter instance
rate_limiter = TokenBucketRateLimiter()


def hash_api_key(raw_key: str) -> str:
    """Compute 64-character SHA-256 hex digest of plaintext API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_api_key(
    name: str = "Default API Key",
    scopes: list[str] | None = None,
    node_id: str | None = None,
    rate_limit: int = 100,
) -> tuple[dict[str, Any], str]:
    """Generate a new scoped API key, hash it with SHA-256, and persist metadata.

    Returns:
        (persisted_record, plaintext_api_key)
        The plaintext_api_key is returned ONCE AND ONLY ONCE upon creation.
    """
    raw_key = f"mfx_live_{secrets.token_urlsafe(24)}"
    key_prefix = raw_key[:12]
    key_hash = hash_api_key(raw_key)
    key_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()

    valid_scopes = scopes or ["read:inventory", "write:events"]

    record: dict[str, Any] = {
        "id": key_id,
        "name": name,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "scopes": valid_scopes,
        "node_id": node_id,
        "rate_limit": rate_limit,
        "usage_count": 0,
        "last_used_at": None,
        "last_used": None,
        "is_active": True,
        "created_at": now_iso,
    }

    # Store in memory cache
    _in_memory_api_keys[key_hash] = record
    _id_to_hash_index[key_id] = key_hash

    # Sync to Supabase if available
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("api_keys").insert(
                    {
                        "id": key_id,
                        "name": name,
                        "key_prefix": key_prefix,
                        "key_hash": key_hash,
                        "node_id": node_id,
                        "scopes": valid_scopes,
                        "rate_limit": rate_limit,
                        "usage_count": 0,
                        "is_active": True,
                        "created_at": now_iso,
                    }
                ).execute()
        except Exception as exc:
            logger.warning("Supabase api_keys insert skipped/failed: %s", exc)

    logger.info("API key created: id=%s prefix=%s node=%s scopes=%s", key_id, key_prefix, node_id, valid_scopes)
    return record, raw_key


def get_api_key_by_hash(key_hash: str) -> dict[str, Any] | None:
    """Retrieve an active API key record by its SHA-256 hash."""
    # 1. In-memory check
    if key_hash in _in_memory_api_keys:
        return _in_memory_api_keys[key_hash]

    # 2. Database lookup
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("api_keys")
                    .select("*")
                    .eq("key_hash", key_hash)
                    .eq("is_active", True)
                    .execute()
                )
                if res.data:
                    rec = res.data[0]
                    _in_memory_api_keys[key_hash] = rec
                    _id_to_hash_index[rec["id"]] = key_hash
                    return rec
        except Exception as exc:
            logger.warning("Supabase api_keys query failed: %s", exc)

    return None


def get_api_key_by_id(key_id: str) -> dict[str, Any] | None:
    """Retrieve an API key record by ID."""
    key_hash = _id_to_hash_index.get(key_id)
    if key_hash and key_hash in _in_memory_api_keys:
        return _in_memory_api_keys[key_hash]

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("api_keys").select("*").eq("id", key_id).execute()
                if res.data:
                    rec = res.data[0]
                    _in_memory_api_keys[rec["key_hash"]] = rec
                    _id_to_hash_index[rec["id"]] = rec["key_hash"]
                    return rec
        except Exception as exc:
            logger.warning("Supabase api_keys query failed: %s", exc)

    return None


def list_api_keys(node_id: str | None = None, is_admin: bool = False) -> list[dict[str, Any]]:
    """List API keys without exposing key_hash."""
    results: list[dict[str, Any]] = []

    # Read in-memory records
    for rec in _in_memory_api_keys.values():
        if not rec.get("is_active", True):
            continue
        if not is_admin and node_id and rec.get("node_id") != node_id:
            continue
        safe_rec = {
            "id": rec["id"],
            "name": rec.get("name", "API Key"),
            "key_prefix": rec.get("key_prefix", "mfx_live_"),
            "scopes": rec.get("scopes", []),
            "node_id": rec.get("node_id"),
            "rate_limit": rec.get("rate_limit", 100),
            "usage_count": rec.get("usage_count", 0),
            "last_used_at": rec.get("last_used_at") or rec.get("last_used"),
            "is_active": rec.get("is_active", True),
            "created_at": rec.get("created_at"),
        }
        results.append(safe_rec)

    # If database configured, combine and deduplicate
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("api_keys").select(
                    "id, name, key_prefix, scopes, node_id, rate_limit, usage_count, last_used_at, is_active, created_at"
                )
                if not is_admin and node_id:
                    query = query.eq("node_id", node_id)
                res = query.execute()
                existing_ids = {r["id"] for r in results}
                for row in res.data or []:
                    if row["id"] not in existing_ids:
                        results.append(row)
        except Exception as exc:
            logger.warning("Supabase api_keys list failed: %s", exc)

    return results


def revoke_api_key(key_id: str) -> bool:
    """Revoke/deactivate an API key."""
    key_hash = _id_to_hash_index.get(key_id)
    if key_hash and key_hash in _in_memory_api_keys:
        _in_memory_api_keys[key_hash]["is_active"] = False

    rate_limiter.reset(key_id)

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("api_keys").update({"is_active": False}).eq("id", key_id).execute()
        except Exception as exc:
            logger.warning("Supabase api_keys revoke failed: %s", exc)

    logger.info("API key revoked: id=%s", key_id)
    return True


def record_key_usage(key_id: str, key_hash: str) -> None:
    """Increment usage counter and record last_used timestamp."""
    now_iso = datetime.now(UTC).isoformat()
    if key_hash in _in_memory_api_keys:
        rec = _in_memory_api_keys[key_hash]
        rec["usage_count"] = rec.get("usage_count", 0) + 1
        rec["last_used_at"] = now_iso
        rec["last_used"] = now_iso

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("api_keys").update(
                    {
                        "usage_count": _in_memory_api_keys.get(key_hash, {}).get("usage_count", 1),
                        "last_used_at": now_iso,
                    }
                ).eq("id", key_id).execute()
        except Exception as exc:
            logger.debug("Supabase api_keys usage update skipped: %s", exc)


def clear_in_memory_api_keys() -> None:
    """Clear in-memory cache and rate limiter (for test fixtures)."""
    _in_memory_api_keys.clear()
    _id_to_hash_index.clear()
    rate_limiter.reset()
