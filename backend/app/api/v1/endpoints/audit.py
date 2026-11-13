"""Cryptographically verified audit ledger endpoints."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.core.audit_ledger import (
    _in_memory_audit_ledger,
    compute_entry_hash,
    get_in_memory_audit_ledger,
    verify_audit_chain,
)
from app.core.config import settings
from app.core.security import get_actor, get_current_user, get_service_db_client
from app.schemas.base import UserProfile

logger = logging.getLogger("mediflux.api.v1.audit")

router = APIRouter(prefix="/audit", tags=["Audit Ledger"])


def _seed_audit_ledger_if_empty() -> None:
    """Ensure at least 3 initial cryptographic audit entries exist if empty."""
    if _in_memory_audit_ledger:
        return

    now_iso = datetime.now(UTC).isoformat()
    prev_0 = "0" * 64

    # Entry 1: Genesis Block
    e1_payload = {"system": "MediFlux", "version": "1.0", "status": "genesis"}
    h1 = compute_entry_hash(
        prev_0, 1, now_iso, "system:genesis", "SYSTEM_GENESIS_INITIALIZED", "system",
        "00000000-0000-0000-0000-000000000000", e1_payload, "MediFlux Network Sovereign Cryptographic Genesis Block initialized."
    )
    _in_memory_audit_ledger.append({
        "id": "aud-0001",
        "seq": 1,
        "ts": now_iso,
        "created_at": now_iso,
        "actor": "system:genesis",
        "action": "SYSTEM_GENESIS_INITIALIZED",
        "entity_type": "system",
        "entity_id": "00000000-0000-0000-0000-000000000000",
        "node_id": "00000000-0000-0000-0000-000000000000",
        "prev_hash": prev_0,
        "hash": h1,
        "entry_hash": h1,
        "explanation": "MediFlux Network Sovereign Cryptographic Genesis Block initialized.",
        "payload": e1_payload,
        "correlation_id": "casc-genesis-001",
    })

    # Entry 2: Regulatory Baseline
    e2_payload = {"module": "pricing_engine", "version": 1, "statute": "DPCO-2013"}
    h2 = compute_entry_hash(
        h1, 2, now_iso, "system:reg_pipeline", "REGULATORY_MODULE_BASELINE_REGISTERED", "modules",
        "pricing_engine", e2_payload, "DPCO-2013 baseline pricing engine registered."
    )
    _in_memory_audit_ledger.append({
        "id": "aud-0002",
        "seq": 2,
        "ts": now_iso,
        "created_at": now_iso,
        "actor": "system:reg_pipeline",
        "action": "REGULATORY_MODULE_BASELINE_REGISTERED",
        "entity_type": "modules",
        "entity_id": "pricing_engine",
        "node_id": "00000000-0000-0000-0000-000000000000",
        "prev_hash": h1,
        "hash": h2,
        "entry_hash": h2,
        "explanation": "DPCO-2013 baseline pricing engine registered.",
        "payload": e2_payload,
        "correlation_id": "casc-genesis-002",
    })

    # Entry 3: Security & RBAC baseline
    e3_payload = {"roles": ["admin", "regulator", "manufacturer", "distributor", "stockist", "pharmacy", "developer"]}
    h3 = compute_entry_hash(
        h2, 3, now_iso, "system:security", "SECURITY_RBAC_POLICY_ESTABLISHED", "policy",
        "rbac_matrix", e3_payload, "Role-based access matrix sealed with 7 sovereign roles."
    )
    _in_memory_audit_ledger.append({
        "id": "aud-0003",
        "seq": 3,
        "ts": now_iso,
        "created_at": now_iso,
        "actor": "system:security",
        "action": "SECURITY_RBAC_POLICY_ESTABLISHED",
        "entity_type": "policy",
        "entity_id": "rbac_matrix",
        "node_id": "00000000-0000-0000-0000-000000000000",
        "prev_hash": h2,
        "hash": h3,
        "entry_hash": h3,
        "explanation": "Role-based access matrix sealed with 7 sovereign roles.",
        "payload": e3_payload,
        "correlation_id": "casc-genesis-003",
    })


@router.get("/ledger", summary="Query and Filter Audit Ledger Entries Alias")
@router.get("", summary="Query and Filter Audit Ledger Entries")
async def get_audit_ledger(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
    entity_type: str | None = Query(default=None, description="Filter by entity type (e.g. orders, hitl_tasks)"),
    entity_id: str | None = Query(default=None, description="Filter by entity UUID"),
    actor: str | None = Query(default=None, description="Filter by actor identifier"),
    action: str | None = Query(default=None, description="Filter by action identifier"),
    node_id: str | None = Query(default=None, description="Filter by node UUID"),
    correlation_id: str | None = Query(default=None, description="Filter by correlation ID"),
    search: str | None = Query(default=None, description="Search across explanation, actor, action, or hashes"),
    start_date: str | None = Query(default=None, description="Start date ISO timestamp"),
    end_date: str | None = Query(default=None, description="End date ISO timestamp"),
    limit: int = Query(default=50, ge=1, le=100, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Retrieve chronologically ordered audit ledger records with multifaceted filtering."""
    _seed_audit_ledger_if_empty()

    if x_api_key:
        actor_obj = await get_actor(x_api_key=x_api_key)
        scopes = actor_obj.scopes
        if "*" not in scopes and "all" not in scopes and "read:audit" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient API key scope. Required: 'read:audit'",
            )

    # 1. Query Supabase database if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("audit_ledger").select("*", count="exact")
                if entity_type:
                    query = query.eq("entity_type", entity_type)
                if entity_id:
                    query = query.eq("entity_id", entity_id)
                if actor:
                    query = query.eq("actor", actor)
                if action:
                    query = query.eq("action", action)
                if node_id:
                    query = query.eq("node_id", node_id)
                if start_date:
                    query = query.gte("ts", start_date)
                if end_date:
                    query = query.lte("ts", end_date)

                query = query.order("seq", desc=False).range(offset, offset + limit - 1)
                resp = query.execute()
                items = resp.data or []
                if items:
                    for item in items:
                        if "entry_hash" not in item:
                            item["entry_hash"] = item.get("hash", "")
                    return {
                        "items": items,
                        "total": resp.count or len(items),
                        "limit": limit,
                        "offset": offset,
                    }
        except Exception as exc:
            logger.warning("DB query for audit_ledger failed (%s); using in-memory store", exc)

    # 2. In-memory store fallback
    all_entries = get_in_memory_audit_ledger()
    filtered: list[dict[str, Any]] = []

    for entry in all_entries:
        if entity_type and entry.get("entity_type") != entity_type:
            continue
        if entity_id and str(entry.get("entity_id")) != str(entity_id):
            continue
        if actor and entry.get("actor") != actor:
            continue
        if action and str(entry.get("action", "")).lower() != action.lower():
            continue
        if node_id and str(entry.get("node_id")) != str(node_id):
            continue
        if correlation_id and str(entry.get("correlation_id")) != str(correlation_id):
            continue

        if search:
            q = search.lower()
            exp = str(entry.get("explanation") or "").lower()
            act = str(entry.get("actor") or "").lower()
            actn = str(entry.get("action") or "").lower()
            h = str(entry.get("hash") or entry.get("entry_hash") or "").lower()
            ph = str(entry.get("prev_hash") or "").lower()
            if q not in exp and q not in act and q not in actn and q not in h and q not in ph:
                continue

        entry_ts = str(entry.get("ts") or entry.get("timestamp") or "")
        if start_date and entry_ts < start_date:
            continue
        if end_date and entry_ts > end_date:
            continue

        item_copy = dict(entry)
        if "entry_hash" not in item_copy:
            item_copy["entry_hash"] = item_copy.get("hash", "")
        filtered.append(item_copy)

    # Sort by seq ascending
    filtered.sort(key=lambda e: int(e.get("seq", 0)))
    total = len(filtered)
    paged = filtered[offset : offset + limit]

    return {
        "items": paged,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/verify", summary="Verify Audit Hash Chain Integrity (POST)")
@router.get("/verify", summary="Verify Audit Hash Chain Integrity (GET)")
async def verify_audit_ledger(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict[str, Any]:
    """Recompute SHA-256 hash chains from seq=1 to present, detecting any database tampering."""
    _seed_audit_ledger_if_empty()
    res = verify_audit_chain()
    is_valid = bool(res.get("valid", True))
    entries = get_in_memory_audit_ledger()
    gen_hash = entries[0]["hash"] if entries else ("0" * 64)
    head_hash = entries[-1]["hash"] if entries else ("0" * 64)

    return {
        "valid": is_valid,
        "status": "verified" if is_valid else "tampered",
        "total_entries": res.get("total_entries", len(entries)),
        "verified_entries": res.get("total_entries", len(entries)),
        "genesis_hash": gen_hash,
        "head_hash": head_hash,
        "broken_at_id": res.get("broken_at_seq"),
        "broken_at_seq": res.get("broken_at_seq"),
        "reason": res.get("reason"),
        "message": res.get("message", "Audit ledger chain integrity verified successfully."),
        "verified_at": datetime.now(UTC).isoformat(),
        "details": [
            {
                "seq": e.get("seq"),
                "hash": e.get("hash") or e.get("entry_hash"),
                "prev_hash": e.get("prev_hash"),
                "action": e.get("action"),
                "actor": e.get("actor"),
            }
            for e in entries[:25]
        ],
    }

