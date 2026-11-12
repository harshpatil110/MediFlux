"""Cryptographically hash-chained audit ledger service with monotonic ordering and concurrency locking."""

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client

logger = logging.getLogger("mediflux.core.audit_ledger")

# Single-writer lock for concurrency isolation in local and in-memory environments
_write_lock = asyncio.Lock()

# Global in-memory audit ledger store for offline operation and deterministic tests
_in_memory_audit_ledger: list[dict[str, Any]] = []


def get_in_memory_audit_ledger() -> list[dict[str, Any]]:
    """Retrieve all in-memory audit ledger entries."""
    return list(_in_memory_audit_ledger)


def clear_in_memory_audit_ledger() -> None:
    """Clear all in-memory audit ledger entries."""
    _in_memory_audit_ledger.clear()


def set_in_memory_audit_ledger(entries: list[dict[str, Any]]) -> None:
    """Replace in-memory audit ledger entries in-place (useful for tamper simulation tests)."""
    _in_memory_audit_ledger.clear()
    _in_memory_audit_ledger.extend(entries)


def compute_entry_hash(
    prev_hash: str,
    seq: int,
    ts: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any] | Any,
    explanation: str = "",
) -> str:
    """Computes deterministic SHA-256 hash over canonical representation.

    hash = SHA-256(prev_hash + canonical_json(entry))
    """
    canonical_data = {
        "action": action,
        "actor": actor,
        "entity_id": str(entity_id),
        "entity_type": entity_type,
        "explanation": explanation or "",
        "payload": payload if isinstance(payload, dict) else {"data": payload},
        "seq": seq,
        "ts": ts,
    }
    # Canonical JSON string with sorted keys and no whitespace
    canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
    raw_bytes = (prev_hash + canonical_json).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


async def write_audit_entry(
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any] | None = None,
    explanation: str = "",
    db_client: Any = None,
) -> dict[str, Any]:
    """Acquires write lock, retrieves latest seq & hash, computes new hash, and persists entry."""
    async with _write_lock:
        now_iso = datetime.now(UTC).isoformat()
        actual_payload = dict(payload or {})
        actual_explanation = str(explanation or "")

        latest_seq = 0
        prev_hash = "0" * 64

        # 1. Check Supabase DB for latest entry if configured
        client = db_client
        if client is None and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
            except Exception as exc:
                logger.debug("get_service_db_client lookup failed: %s", exc)

        if client is not None:
            try:
                resp = (
                    client.table("audit_ledger")
                    .select("seq, hash")
                    .order("seq", desc=True)
                    .limit(1)
                    .execute()
                )
                if resp.data:
                    latest_seq = int(resp.data[0]["seq"])
                    prev_hash = str(resp.data[0]["hash"])
            except Exception as exc:
                logger.warning("DB query for latest audit_ledger seq failed (%s); checking memory", exc)

        # 2. Check in-memory store if DB is empty or unavailable
        if not latest_seq and _in_memory_audit_ledger:
            latest_entry = _in_memory_audit_ledger[-1]
            latest_seq = int(latest_entry.get("seq", len(_in_memory_audit_ledger)))
            prev_hash = str(latest_entry.get("hash") or latest_entry.get("current_hash") or ("0" * 64))

        new_seq = latest_seq + 1
        new_hash = compute_entry_hash(
            prev_hash=prev_hash,
            seq=new_seq,
            ts=now_iso,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            payload=actual_payload,
            explanation=actual_explanation,
        )

        entry_record = {
            "seq": new_seq,
            "sequence_id": new_seq,
            "ts": now_iso,
            "timestamp": now_iso,
            "actor": actor,
            "action": action,
            "action_type": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "payload": actual_payload,
            "explanation": actual_explanation,
            "prev_hash": prev_hash,
            "previous_hash": prev_hash,
            "hash": new_hash,
            "current_hash": new_hash,
        }

        # 3. Persist to database if available
        if client is not None:
            try:
                client.table("audit_ledger").insert(entry_record).execute()
                logger.info(
                    "Audit entry seq=%d action=%s hash=%s persisted to Supabase",
                    new_seq,
                    action,
                    new_hash[:8],
                )
            except Exception as exc:
                logger.warning("Supabase insert to audit_ledger failed (%s); saved to in-memory store", exc)

        _in_memory_audit_ledger.append(entry_record)
        return entry_record


def verify_audit_chain(
    records: list[dict[str, Any]] | None = None,
    db_client: Any = None,
) -> dict[str, Any]:
    """Verify cryptographic integrity of the hash chain from seq=1 to the latest record.

    Pinpoints the exact sequence number (broken_at_seq) of any tampered or corrupt entry.
    """
    entries = records
    if entries is None:
        client = db_client
        if client is None and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
            except Exception as exc:
                logger.debug("get_service_db_client lookup failed: %s", exc)

        if client is not None:
            try:
                resp = client.table("audit_ledger").select("*").order("seq", desc=False).execute()
                if resp.data:
                    entries = resp.data
            except Exception as exc:
                logger.warning("DB query for audit_ledger verify failed: %s", exc)

        if entries is None:
            entries = list(_in_memory_audit_ledger)

    if not entries:
        return {
            "valid": True,
            "total_entries": 0,
            "message": "Audit ledger is empty; integrity intact.",
        }

    # Sort entries by seq ascending
    sorted_entries = sorted(entries, key=lambda e: int(e.get("seq", 0)))
    expected_prev_hash = "0" * 64

    for entry in sorted_entries:
        seq = int(entry.get("seq", 0))
        ts = str(entry.get("ts") or entry.get("timestamp") or "")
        actor = str(entry.get("actor") or "")
        action = str(entry.get("action") or entry.get("action_type") or "")
        entity_type = str(entry.get("entity_type") or "general")
        entity_id = str(entry.get("entity_id") or "")
        payload = entry.get("payload") or {}
        explanation = str(entry.get("explanation") or "")
        actual_prev_hash = str(entry.get("prev_hash") or entry.get("previous_hash") or "")
        actual_hash = str(entry.get("hash") or entry.get("current_hash") or "")

        # 1. Verify prev_hash matches expected predecessor hash
        if actual_prev_hash != expected_prev_hash:
            logger.error(
                "Audit chain break at seq=%d: prev_hash mismatch. Expected %s, got %s",
                seq,
                expected_prev_hash,
                actual_prev_hash,
            )
            return {
                "valid": False,
                "total_entries": len(sorted_entries),
                "broken_at_seq": seq,
                "reason": (
                    f"Previous hash mismatch detected at seq {seq}. "
                    f"Expected predecessor hash '{expected_prev_hash}', got '{actual_prev_hash}'."
                ),
            }

        # 2. Recompute current hash and verify against stored hash
        recalculated_hash = compute_entry_hash(
            prev_hash=expected_prev_hash,
            seq=seq,
            ts=ts,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            explanation=explanation,
        )

        if recalculated_hash != actual_hash:
            logger.error(
                "Audit chain break at seq=%d: hash mismatch. Recalculated %s, stored %s",
                seq,
                recalculated_hash,
                actual_hash,
            )
            return {
                "valid": False,
                "total_entries": len(sorted_entries),
                "broken_at_seq": seq,
                "reason": f"Hash mismatch detected at seq {seq}. Database payload or sequence altered.",
            }

        expected_prev_hash = actual_hash

    return {
        "valid": True,
        "total_entries": len(sorted_entries),
        "message": "Audit ledger chain integrity verified successfully.",
    }
