"""Product catalog and barcode lookup endpoints."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from supabase import Client

from app.core.exceptions import AppException
from app.core.security import CurrentUser, get_current_user_optional, get_service_db_client
from app.schemas.base import ProductResponse
from app.schemas.common import PaginatedResponse

logger = logging.getLogger("mediflux.api.products")

router = APIRouter(prefix="/products", tags=["Product Catalog"])


def _load_all_catalog_products() -> list[dict[str, Any]]:
    """Load all 20 curated products with barcodes from fixtures."""
    root_fixture = Path(__file__).resolve().parents[5] / "fixtures" / "drug_schedules.json"
    candidates = [
        root_fixture,
        Path("fixtures/drug_schedules.json"),
        Path("backend/fixtures/drug_schedules.json"),
        Path(__file__).resolve().parents[4] / "fixtures" / "drug_schedules.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                with open(p, encoding="utf-8") as f:
                    raw = json.load(f)
                catalog = []
                for idx, item in enumerate(raw, 1):
                    sku = item.get("sku", f"SKU-{idx:03d}")
                    barcode = item.get("barcode", f"8901000{idx:05d}")
                    sched_type = item.get("schedule_type", "OTC")
                    sched_class = "OTC" if "otc" in sched_type.lower() else ("SCHEDULE_H1" if "h1" in sched_type.lower() else ("SCHEDULE_X" if "narcotic" in sched_type.lower() else "SCHEDULE_H"))
                    ceiling = float(item.get("neml_ceiling_price", 25.0))
                    price = round(ceiling * 0.92, 2)
                    catalog.append({
                        "id": f"p-{idx:03d}-{sku.lower()}",
                        "name": item.get("product_name"),
                        "generic_name": item.get("product_name").split(" ")[0],
                        "sku": sku,
                        "barcode": barcode,
                        "schedule_class": sched_class,
                        "requires_prescription": bool(
                            item.get("requires_prescription")
                            or sched_class in ("SCHEDULE_H", "SCHEDULE_H1", "SCHEDULE_X")
                        ),
                        "is_cold_chain": bool(item.get("is_cold_chain", False)),
                        "storage_min_c": item.get("min_temp_celsius", 15.0),
                        "storage_max_c": item.get("max_temp_celsius", 25.0),
                        "is_lifesaving": bool(item.get("is_cold_chain") or "h1" in sched_type.lower()),
                        "unit": "vial" if item.get("is_cold_chain") else "strip",
                        "price_per_unit": price,
                    })
                if catalog:
                    return catalog
            except Exception as exc:
                logger.debug("Fixture load error: %s", exc)

    # Hardcoded minimum fallback
    return [
        {
            "id": "p-001-med-amx-500",
            "name": "Amoxicillin 500mg Capsules",
            "generic_name": "Amoxicillin",
            "sku": "MED-AMX-500",
            "barcode": "8901000000025",
            "schedule_class": "SCHEDULE_H",
            "requires_prescription": True,
            "is_cold_chain": False,
            "storage_min_c": 15.0,
            "storage_max_c": 25.0,
            "is_lifesaving": False,
            "unit": "strip",
            "price_per_unit": 6.90,
        },
        {
            "id": "p-004-med-pcm-650",
            "name": "Paracetamol 650mg Tablets",
            "generic_name": "Paracetamol",
            "sku": "MED-PCM-650",
            "barcode": "8901000000018",
            "schedule_class": "OTC",
            "requires_prescription": False,
            "is_cold_chain": False,
            "storage_min_c": 15.0,
            "storage_max_c": 30.0,
            "is_lifesaving": False,
            "unit": "strip",
            "price_per_unit": 1.89,
        },
        {
            "id": "p-010-med-ins-reg",
            "name": "Human Regular Insulin 100IU/ml",
            "generic_name": "Human Regular Insulin",
            "sku": "MED-INS-REG",
            "barcode": "8901000000056",
            "schedule_class": "SCHEDULE_H",
            "requires_prescription": True,
            "is_cold_chain": True,
            "storage_min_c": 2.0,
            "storage_max_c": 8.0,
            "is_lifesaving": True,
            "unit": "vial",
            "price_per_unit": 138.00,
        },
    ]


DEFAULT_PRODUCTS: list[dict[str, Any]] = _load_all_catalog_products()


class ProductBatchDetail(BaseModel):
    batch_id: str
    batch_no: str
    batch_number: str
    expiry_date: str
    days_to_expiry: int
    is_near_expiry: bool = False
    status: str = "active"
    is_quarantined: bool = False
    quarantine_reason: str | None = None
    available_quantity: int
    reserved_quantity: int = 0
    safety_stock: int = 20
    node_id: str | None = None


class ProductBarcodeLookupResponse(BaseModel):
    id: str
    name: str
    generic_name: str
    sku: str
    barcode: str
    schedule_class: str
    requires_prescription: bool
    is_lifesaving: bool
    is_cold_chain: bool
    storage_min_c: float | None = None
    storage_max_c: float | None = None
    unit_price: float
    batches: list[ProductBatchDetail] = Field(default_factory=list)


def _generate_mock_batches_for_product(prod: dict[str, Any], node_id: str | None = None) -> list[ProductBatchDetail]:
    """Generate realistic FEFO-sorted batches for a product."""
    # Batch 1: Near expiry (45 days) - active
    b1_date = "2027-01-15"
    # Batch 2: Normal expiry (320 days) - active
    b2_date = "2027-09-30"
    # Batch 3: Quarantined batch (excursion)
    b3_date = "2027-05-15"

    b1_no = f"B-{prod.get('sku', 'SKU')}-26A"
    b2_no = f"B-{prod.get('sku', 'SKU')}-26B"
    b3_no = f"B-{prod.get('sku', 'SKU')}-EXCUR"

    batches = [
        ProductBatchDetail(
            batch_id=f"btch-{prod.get('sku', 'sku').lower()}-01",
            batch_no=b1_no,
            batch_number=b1_no,
            expiry_date=b1_date,
            days_to_expiry=45,
            is_near_expiry=True,
            status="active",
            is_quarantined=False,
            available_quantity=24,
            reserved_quantity=0,
            safety_stock=20,
            node_id=node_id or "11111111-1111-1111-1111-111111111111",
        ),
        ProductBatchDetail(
            batch_id=f"btch-{prod.get('sku', 'sku').lower()}-02",
            batch_no=b2_no,
            batch_number=b2_no,
            expiry_date=b2_date,
            days_to_expiry=320,
            is_near_expiry=False,
            status="active",
            is_quarantined=False,
            available_quantity=150,
            reserved_quantity=5,
            safety_stock=20,
            node_id=node_id or "11111111-1111-1111-1111-111111111111",
        ),
        ProductBatchDetail(
            batch_id=f"btch-{prod.get('sku', 'sku').lower()}-03-q",
            batch_no=b3_no,
            batch_number=b3_no,
            expiry_date=b3_date,
            days_to_expiry=180,
            is_near_expiry=False,
            status="quarantined",
            is_quarantined=True,
            quarantine_reason="Thermal excursion flagged during hub transit",
            available_quantity=40,
            reserved_quantity=0,
            safety_stock=20,
            node_id=node_id or "11111111-1111-1111-1111-111111111111",
        ),
    ]

    # Sort strictly by expiry_date ASC (FEFO)
    batches.sort(key=lambda b: b.expiry_date)
    return batches


@router.get(
    "/by-barcode/{code}",
    response_model=ProductBarcodeLookupResponse,
    summary="Lookup Product by Barcode or SKU",
    description="Retrieve product details and FEFO-sorted batches for scanning at retail pharmacy counter.",
)
async def get_product_by_barcode(
    code: str,
    db_client: Annotated[Client | None, Depends(get_service_db_client)],
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> ProductBarcodeLookupResponse:
    """Find product matching barcode or SKU, returning FEFO-sorted batches."""
    clean_code = code.strip()
    matched_prod: dict[str, Any] | None = None

    # 1. Try Supabase query
    if db_client:
        try:
            res = db_client.table("products").select("*").or_(
                f"barcode.eq.{clean_code},sku.eq.{clean_code}"
            ).execute()
            if res.data and len(res.data) > 0:
                matched_prod = res.data[0]
        except Exception as exc:
            logger.debug("Database barcode lookup skipped: %s", exc)

    # 2. Local catalog matching
    if not matched_prod:
        for p in DEFAULT_PRODUCTS:
            if (
                p.get("barcode") == clean_code
                or p.get("sku", "").lower() == clean_code.lower()
                or clean_code in p.get("barcode", "")
            ):
                matched_prod = p
                break

    if not matched_prod:
        raise AppException(
            message=f"No product matches barcode or SKU '{clean_code}'.",
            code="PRODUCT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 3. Resolve batches for product
    node_id = current_user.node_id if current_user else "11111111-1111-1111-1111-111111111111"
    batches: list[ProductBatchDetail] = []

    if db_client and matched_prod.get("id"):
        try:
            q = db_client.table("batches").select("*").eq("product_id", matched_prod["id"])
            b_res = q.execute()
            if b_res.data:
                now_d = datetime.now(UTC).date()
                for b in b_res.data:
                    exp_str = b.get("expiry_date", "2027-01-01")
                    try:
                        exp_d = datetime.fromisoformat(exp_str).date()
                        days = (exp_d - now_d).days
                    except Exception:
                        days = 180
                    batches.append(
                        ProductBatchDetail(
                            batch_id=str(b.get("id", b.get("batch_id"))),
                            batch_no=b.get("batch_no", "BATCH-01"),
                            expiry_date=exp_str,
                            days_to_expiry=days,
                            is_near_expiry=days <= 60,
                            status=b.get("status", "active"),
                            available_quantity=b.get("quantity", b.get("initial_quantity", 50)),
                            reserved_quantity=b.get("reserved", 0),
                            safety_stock=20,
                            node_id=node_id,
                        )
                    )
        except Exception as exc:
            logger.debug("Batches db query failed: %s", exc)

    if not batches:
        batches = _generate_mock_batches_for_product(matched_prod, node_id)

    # Sort by FEFO (expiry_date ASC)
    batches.sort(key=lambda b: b.expiry_date)

    sched_raw = matched_prod.get("schedule_class", "OTC")
    sched_class = "H" if "H" in sched_raw else ("H1" if "H1" in sched_raw else ("X" if "X" in sched_raw else "OTC"))

    return ProductBarcodeLookupResponse(
        id=str(matched_prod.get("id")),
        name=matched_prod.get("name", "Medicine"),
        generic_name=matched_prod.get("generic_name", matched_prod.get("name", "")),
        sku=matched_prod.get("sku", "SKU-001"),
        barcode=matched_prod.get("barcode", clean_code),
        schedule_class=sched_class,
        requires_prescription=bool(
            matched_prod.get("requires_prescription")
            or sched_class in ("SCHEDULE_H", "SCHEDULE_H1", "SCHEDULE_X", "H", "H1", "X")
        ),
        is_lifesaving=bool(matched_prod.get("is_lifesaving", False)),
        is_cold_chain=bool(matched_prod.get("is_cold_chain", False)),
        storage_min_c=matched_prod.get("storage_min_c"),
        storage_max_c=matched_prod.get("storage_max_c"),
        unit_price=float(matched_prod.get("price_per_unit", 45.0)),
        batches=batches,
    )


@router.get("", response_model=PaginatedResponse[ProductResponse], summary="List Products")
async def list_products(
    db_client: Annotated[Client | None, Depends(get_service_db_client)],
    search: str | None = Query(default=None, description="Search by name or generic name"),
    q: str | None = Query(default=None, description="Search query alias (name, generic, sku, barcode)"),
    schedule_class: str | None = Query(default=None, description="Filter by CDSCO schedule class"),
    is_cold_chain: bool | None = Query(default=None, description="Filter cold-chain items"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PaginatedResponse[ProductResponse]:
    """Retrieve catalog products with optional filtering by schedule class, query, or cold-chain."""
    search_query = q or search

    # 1. Try Supabase query
    if db_client:
        try:
            query = db_client.table("products").select("*").limit(limit + 1)
            if search_query:
                query = query.or_(
                    f"name.ilike.%{search_query}%,generic_name.ilike.%{search_query}%,sku.ilike.%{search_query}%,barcode.ilike.%{search_query}%"
                )
            if schedule_class:
                query = query.eq("schedule_class", schedule_class)
            if is_cold_chain is not None:
                query = query.eq("is_cold_chain", is_cold_chain)
            if cursor:
                query = query.gt("id", cursor)

            res = query.execute()
            data = res.data or []
            if data:
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
    # Demo seeding also registers UUID aliases for catalog products. Show each
    # formulation once while preserving those aliases for inventory lookups.
    canonical_names = {
        product["name"].strip().casefold() for product in DEFAULT_PRODUCTS if product.get("sku")
    }
    filtered = [
        product for product in DEFAULT_PRODUCTS
        if product.get("sku") or product["name"].strip().casefold() not in canonical_names
    ]
    if search_query:
        s = search_query.lower()
        filtered = [
            p
            for p in filtered
            if s in p.get("name", "").lower()
            or s in p.get("generic_name", "").lower()
            or s in p.get("sku", "").lower()
            or s in p.get("barcode", "").lower()
        ]
    if schedule_class:
        filtered = [p for p in filtered if p.get("schedule_class") == schedule_class]
    if is_cold_chain is not None:
        filtered = [p for p in filtered if p.get("is_cold_chain") == is_cold_chain]

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
