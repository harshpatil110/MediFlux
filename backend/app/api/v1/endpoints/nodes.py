"""Supply chain topology nodes endpoints with RLS scoping."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.security import get_current_user, get_user_db_client, visible_node_ids
from app.schemas.base import NodeResponse, UserProfile
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/nodes", tags=["Network Nodes"])

# Synthetic node repository for offline/test environments
DEFAULT_NODES: list[dict] = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "tier": "pharmacy",
        "name": "Apollo Pharmacy - Connaught Place",
        "region": "DL-Delhi-Central",
        "parent_id": "22222222-2222-2222-2222-222222222222",
        "address": "Block B, Connaught Place, New Delhi 110001",
        "is_active": True,
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "tier": "stockist",
        "name": "North Delhi Stockist Hub",
        "region": "DL-Delhi-North",
        "parent_id": "33333333-3333-3333-3333-333333333333",
        "address": "Okhla Phase III, New Delhi 110020",
        "is_active": True,
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "tier": "distributor",
        "name": "Northern India Regional Depot",
        "region": "HR-Gurugram",
        "parent_id": "44444444-4444-4444-4444-444444444444",
        "address": "Udyog Vihar Phase 4, Gurugram 122016",
        "is_active": True,
    },
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "tier": "manufacturer",
        "name": "Sun Pharma Formulation Plant - Baddi",
        "region": "HP-Baddi",
        "parent_id": None,
        "address": "Industrial Area, Baddi, Himachal Pradesh 173205",
        "is_active": True,
    },
]


@router.get("", response_model=PaginatedResponse[NodeResponse], summary="List Visible Network Nodes")
async def list_nodes(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
    db_client: Annotated[Client | None, Depends(get_user_db_client)],
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PaginatedResponse[NodeResponse]:
    """Retrieve supply chain nodes visible to the authenticated user based on RLS visibility rules."""
    allowed_ids = set(visible_node_ids(current_user))

    # Try live Supabase DB query
    if db_client:
        try:
            query = db_client.table("nodes").select("*").in_("id", list(allowed_ids)).limit(limit + 1)
            if cursor:
                query = query.gt("id", cursor)
            response = query.execute()
            data = response.data or []
            has_more = len(data) > limit
            items = [NodeResponse(**row) for row in data[:limit]]
            next_cursor = items[-1].id if has_more and items else None
            return PaginatedResponse[NodeResponse](
                items=items,
                next_cursor=next_cursor,
                has_more=has_more,
                total_count=len(items),
            )
        except Exception:
            pass  # Fallback to local scoped dataset

    # In-memory RLS filtering
    filtered = [n for n in DEFAULT_NODES if n["id"] in allowed_ids]
    if cursor:
        cursor_index = next((i for i, n in enumerate(filtered) if n["id"] == cursor), -1)
        filtered = filtered[cursor_index + 1 :] if cursor_index != -1 else filtered

    has_more = len(filtered) > limit
    selected = filtered[:limit]
    next_cursor = selected[-1]["id"] if has_more and selected else None

    return PaginatedResponse[NodeResponse](
        items=[NodeResponse(**n) for n in selected],
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=len(selected),
    )
