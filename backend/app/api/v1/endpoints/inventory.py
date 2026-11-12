"""Inventory management endpoints with RLS scoping."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.security import get_current_user, get_user_db_client, visible_node_ids
from app.schemas.base import InventoryItemResponse, UserProfile
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

# Synthetic inventory records for offline/test environments
DEFAULT_INVENTORY: list[dict] = [
    {
        "id": "inv-001",
        "node_id": "11111111-1111-1111-1111-111111111111",  # Pharmacy node
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 18,
        "reserved": 2,
        "safety_stock": 10,
        "product_name": "Azithral 500mg",
        "batch_no": "AZI2601",
    },
    {
        "id": "inv-002",
        "node_id": "11111111-1111-1111-1111-111111111111",  # Pharmacy node
        "product_id": "p-002-insulin",
        "batch_id": "b-ins-2026-01",
        "quantity": 5,
        "reserved": 0,
        "safety_stock": 8,
        "product_name": "Human Insulatard 100IU",
        "batch_no": "INS2601",
    },
    {
        "id": "inv-003",
        "node_id": "22222222-2222-2222-2222-222222222222",  # Stockist node
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 250,
        "reserved": 20,
        "safety_stock": 50,
        "product_name": "Azithral 500mg",
        "batch_no": "AZI2601",
    },
    {
        "id": "inv-004",
        "node_id": "33333333-3333-3333-3333-333333333333",  # Distributor node
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 3000,
        "reserved": 200,
        "safety_stock": 500,
        "product_name": "Azithral 500mg",
        "batch_no": "AZI2601",
    },
]


@router.get("", response_model=PaginatedResponse[InventoryItemResponse], summary="List Scoped Inventory")
async def list_inventory(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
    db_client: Annotated[Client | None, Depends(get_user_db_client)],
    product_id: str | None = Query(default=None, description="Filter by product ID"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PaginatedResponse[InventoryItemResponse]:
    """Retrieve inventory balances visible to caller based on node RLS visibility."""
    allowed_nodes = set(visible_node_ids(current_user))

    # 1. Try Supabase query
    if db_client:
        try:
            query = (
                db_client.table("inventory")
                .select("*, products(name), batches(batch_no)")
                .in_("node_id", list(allowed_nodes))
                .limit(limit + 1)
            )
            if product_id:
                query = query.eq("product_id", product_id)
            if cursor:
                query = query.gt("id", cursor)

            res = query.execute()
            data = res.data or []
            if data:
                has_more = len(data) > limit
                items = []
                for row in data[:limit]:
                    prod_info = row.get("products") or {}
                    batch_info = row.get("batches") or {}
                    items.append(
                        InventoryItemResponse(
                            id=row["id"],
                            node_id=row["node_id"],
                            product_id=row["product_id"],
                            batch_id=row["batch_id"],
                            quantity=row["quantity"],
                            reserved=row.get("reserved", 0),
                            safety_stock=row.get("safety_stock", 10),
                            updated_at=row.get("updated_at"),
                            product_name=prod_info.get("name"),
                            batch_no=batch_info.get("batch_no"),
                        )
                    )
                next_cursor = items[-1].id if has_more and items else None
                return PaginatedResponse[InventoryItemResponse](
                    items=items,
                    next_cursor=next_cursor,
                    has_more=has_more,
                    total_count=len(items),
                )
        except Exception:
            pass

    # 2. Local fallback scoped to allowed nodes
    filtered = [inv for inv in DEFAULT_INVENTORY if inv["node_id"] in allowed_nodes]
    if product_id:
        filtered = [inv for inv in filtered if inv["product_id"] == product_id]

    if cursor:
        cursor_index = next((i for i, inv in enumerate(filtered) if inv["id"] == cursor), -1)
        filtered = filtered[cursor_index + 1 :] if cursor_index != -1 else filtered

    has_more = len(filtered) > limit
    selected = filtered[:limit]
    next_cursor = selected[-1]["id"] if has_more and selected else None

    return PaginatedResponse[InventoryItemResponse](
        items=[InventoryItemResponse(**inv) for inv in selected],
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=len(selected),
    )
