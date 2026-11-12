"""Cryptographically verified audit ledger endpoints."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.audit_ledger import get_in_memory_audit_ledger, verify_audit_chain
from app.core.config import settings
from app.core.security import get_current_user, get_service_db_client
from app.schemas.base import UserProfile

logger = logging.getLogger("mediflux.api.v1.audit")

router = APIRouter(prefix="/audit", tags=["Audit Ledger"])


@router.get("", summary="Query and Filter Audit Ledger Entries")
async def get_audit_ledger(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
    entity_type: str | None = Query(default=None, description="Filter by entity type (e.g. orders, hitl_tasks)"),
    entity_id: str | None = Query(default=None, description="Filter by entity UUID"),
    actor: str | None = Query(default=None, description="Filter by actor identifier"),
    start_date: str | None = Query(default=None, description="Start date ISO timestamp"),
    end_date: str | None = Query(default=None, description="End date ISO timestamp"),
    limit: int = Query(default=50, ge=1, le=100, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip"),
) -> dict[str, Any]:
    """Retrieve chronologically ordered audit ledger records with multifaceted filtering."""
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
                if start_date:
                    query = query.gte("ts", start_date)
                if end_date:
                    query = query.lte("ts", end_date)

                query = query.order("seq", desc=False).range(offset, offset + limit - 1)
                resp = query.execute()
                return {
                    "items": resp.data or [],
                    "total": resp.count or len(resp.data or []),
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

        entry_ts = str(entry.get("ts") or entry.get("timestamp") or "")
        if start_date and entry_ts < start_date:
            continue
        if end_date and entry_ts > end_date:
            continue

        filtered.append(entry)

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


@router.get("/verify", summary="Cryptographically Verify Audit Hash Chain Integrity")
async def verify_audit_ledger(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict[str, Any]:
    """Recompute SHA-256 hash chains from seq=1 to present, detecting any database tampering."""
    return verify_audit_chain()
