"""Product catalog endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.security import get_service_db_client
from app.schemas.base import ProductResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/products", tags=["Product Catalog"])

# Master product dataset for offline / bootstrap mode
DEFAULT_PRODUCTS: list[dict] = [
    {
        "id": "p-001-azithromycin",
        "name": "Azithral 500mg",
        "generic_name": "Azithromycin 500mg",
        "schedule_class": "SCHEDULE_H",
        "is_cold_chain": False,
        "storage_min_c": 15.0,
        "storage_max_c": 25.0,
        "is_lifesaving": False,
        "unit": "strip",
        "price_per_unit": 120.00,
    },
    {
        "id": "p-002-insulin",
        "name": "Human Insulatard 100IU",
        "generic_name": "Isophane Insulin IP",
        "schedule_class": "SCHEDULE_H",
        "is_cold_chain": True,
        "storage_min_c": 2.0,
        "storage_max_c": 8.0,
        "is_lifesaving": True,
        "unit": "vial",
        "price_per_unit": 380.00,
    },
    {
        "id": "p-003-paracetamol",
        "name": "Dolo 650mg",
        "generic_name": "Paracetamol 650mg",
        "schedule_class": "OTC",
        "is_cold_chain": False,
        "storage_min_c": 15.0,
        "storage_max_c": 30.0,
        "is_lifesaving": False,
        "unit": "strip",
        "price_per_unit": 30.00,
    },
    {
        "id": "p-004-meropenem",
        "name": "Meronem 1g IV",
        "generic_name": "Meropenem Trihydrate",
        "schedule_class": "SCHEDULE_H1",
        "is_cold_chain": False,
        "storage_min_c": 20.0,
        "storage_max_c": 25.0,
        "is_lifesaving": True,
        "unit": "vial",
        "price_per_unit": 1850.00,
    },
]


@router.get("", response_model=PaginatedResponse[ProductResponse], summary="List Products")
async def list_products(
    db_client: Annotated[Client | None, Depends(get_service_db_client)],
    search: str | None = Query(default=None, description="Search by name or generic name"),
    schedule_class: str | None = Query(default=None, description="Filter by CDSCO schedule class"),
    is_cold_chain: bool | None = Query(default=None, description="Filter cold-chain items"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PaginatedResponse[ProductResponse]:
    """Retrieve catalog products with optional filtering by schedule class or cold-chain requirement."""
    # 1. Try Supabase query
    if db_client:
        try:
            query = db_client.table("products").select("*").limit(limit + 1)
            if search:
                query = query.or_(f"name.ilike.%{search}%,generic_name.ilike.%{search}%")
            if schedule_class:
                query = query.eq("schedule_class", schedule_class)
            if is_cold_chain is not None:
                query = query.eq("is_cold_chain", is_cold_chain)
            if cursor:
                query = query.gt("id", cursor)

            res = query.execute()
            data = res.data or []
            has_more = len(data) > limit
            items = [ProductResponse(**row) for row in data[:limit]]
            next_cursor = items[-1].id if has_more and items else None
            return PaginatedResponse[ProductResponse](
                items=items,
                next_cursor=next_cursor,
                has_more=has_more,
                total_count=len(items),
            )
        except Exception:
            pass

    # 2. Filter local catalog
    filtered = DEFAULT_PRODUCTS
    if search:
        s = search.lower()
        filtered = [p for p in filtered if s in p["name"].lower() or s in p["generic_name"].lower()]
    if schedule_class:
        filtered = [p for p in filtered if p["schedule_class"] == schedule_class]
    if is_cold_chain is not None:
        filtered = [p for p in filtered if p["is_cold_chain"] == is_cold_chain]

    if cursor:
        cursor_index = next((i for i, p in enumerate(filtered) if p["id"] == cursor), -1)
        filtered = filtered[cursor_index + 1 :] if cursor_index != -1 else filtered

    has_more = len(filtered) > limit
    selected = filtered[:limit]
    next_cursor = selected[-1]["id"] if has_more and selected else None

    return PaginatedResponse[ProductResponse](
        items=[ProductResponse(**p) for p in selected],
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=len(selected),
    )
