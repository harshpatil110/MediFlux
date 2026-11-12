"""FastAPI endpoints for Cold-Chain Telemetry, Batch Monitoring, and Quarantine Actions (Task 20)."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import get_service_db_client
from app.events.models import SensorReadingEvent
from app.graphs.coldchain import (
    get_in_memory_coldchain_batches,
    get_in_memory_quarantine_actions,
    run_coldchain_pipeline,
)

logger = logging.getLogger("mediflux.api.coldchain")

router = APIRouter(prefix="/coldchain", tags=["Cold Chain Telemetry"])


# -----------------------------------------------------------------------------
# GET /api/v1/coldchain/batches
# -----------------------------------------------------------------------------
@router.get(
    "/batches",
    summary="List Cold-Chain Batches with Telemetry & Shelf-Life Estimates",
    description="Returns all cold-chain batches enriched with real-time shelf life, last sensor reading, and quarantine status.",
    status_code=status.HTTP_200_OK,
)
async def list_coldchain_batches() -> JSONResponse:
    """Retrieve cold-chain batches enriched with sensor readings and shelf-life estimates."""
    enriched_batches: list[dict[str, Any]] = []

    # 1. Fetch from database if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("batches")
                    .select("*, products(name, sku, is_cold_chain, storage_min_c, storage_max_c)")
                    .execute()
                )
                if res.data:
                    for row in res.data:
                        prod = row.get("products") or {}
                        if prod.get("is_cold_chain", False) or row.get("last_reading_temp") is not None:
                            # Check available quantity in inventory
                            inv_res = client.table("inventory").select("quantity").eq("batch_id", row["id"]).execute()
                            avail_qty = sum(i.get("quantity", 0) for i in (inv_res.data or []))
                            if row.get("status") == "quarantined":
                                avail_qty = 0

                            batch_entry = {
                                "batch_id": row["id"],
                                "batch_no": row["batch_no"],
                                "product_id": row["product_id"],
                                "product_name": prod.get("name", "Biologic"),
                                "sku": prod.get("sku", "MED-COLD"),
                                "storage_min_c": float(prod.get("storage_min_c", 2.0)),
                                "storage_max_c": float(prod.get("storage_max_c", 8.0)),
                                "status": row.get("status", "active"),
                                "available_quantity": avail_qty,
                                "last_reading": {
                                    "temperature_c": row.get("last_reading_temp"),
                                    "shock_g": row.get("last_reading_shock"),
                                    "ts": row.get("last_reading_ts"),
                                } if row.get("last_reading_temp") is not None else None,
                                "shelf_life_estimate": {
                                    "nominal_remaining_days": 180.0,
                                    "estimated_remaining_days": row.get("estimated_remaining_days", 180.0),
                                    "shelf_life_pct": row.get("shelf_life_pct", 100.0),
                                    "degradation_days": max(0.0, 180.0 - float(row.get("estimated_remaining_days") or 180.0)),
                                    "formula_model": "Simplified Arrhenius Degree-Hour & Mechanical Shock Model",
                                    "decision": row.get("last_telemetry_status", "ok"),
                                },
                            }
                            enriched_batches.append(batch_entry)
        except Exception as exc:
            logger.debug("DB batches query failed (%s); serving from in-memory cache", exc)

    # 2. Merge with in-memory batches cache
    cached = get_in_memory_coldchain_batches()
    existing_ids = {b["batch_id"] for b in enriched_batches}

    for b in cached:
        b_id = b.get("batch_id") or b.get("id")
        if b_id not in existing_ids:
            # Build standardized shelf-life estimate payload
            nominal_days = float(b.get("estimated_remaining_days") or 180.0)
            est_days = float(b.get("estimated_remaining_days") or 180.0)
            shelf_pct = float(b.get("shelf_life_pct") or 100.0)

            enriched_batches.append({
                "batch_id": b_id,
                "batch_no": b.get("batch_no", f"B26-{b_id}"),
                "product_id": b.get("product_id", "p-008-insulin"),
                "product_name": b.get("product_name", "Cold-Chain Biologic"),
                "sku": b.get("sku", "MED-COLD"),
                "storage_min_c": float(b.get("storage_min_c", 2.0)),
                "storage_max_c": float(b.get("storage_max_c", 8.0)),
                "status": b.get("status", "active"),
                "available_quantity": 0 if b.get("status") == "quarantined" else int(b.get("available_quantity", 1000)),
                "last_reading": b.get("last_reading"),
                "shelf_life_estimate": {
                    "nominal_remaining_days": nominal_days,
                    "estimated_remaining_days": est_days,
                    "shelf_life_pct": shelf_pct,
                    "degradation_days": max(0.0, nominal_days - est_days),
                    "formula_model": "Simplified Arrhenius Degree-Hour & Mechanical Shock Model",
                    "decision": b.get("last_telemetry_status", "ok"),
                },
            })

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "batches": enriched_batches,
            "total": len(enriched_batches),
        },
    )


# -----------------------------------------------------------------------------
# GET /api/v1/coldchain/quarantines
# -----------------------------------------------------------------------------
@router.get(
    "/quarantines",
    summary="List Cold-Chain Quarantine Actions",
    description="Returns all quarantine action records enriched with clinical excursion reasons and rebalancing status.",
    status_code=status.HTTP_200_OK,
)
async def list_quarantine_actions() -> JSONResponse:
    """Retrieve quarantine actions from Supabase and in-memory fallback store."""
    quarantines: list[dict[str, Any]] = []

    # 1. Fetch from Supabase if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("quarantine_actions").select("*").order("created_at", desc=True).execute()
                if res.data:
                    quarantines.extend(res.data)
        except Exception as exc:
            logger.debug("DB quarantine_actions query failed: %s", exc)

    # 2. Merge in-memory quarantine actions
    cached_quarantines = get_in_memory_quarantine_actions()
    existing_ids = {q.get("id") for q in quarantines}
    for q in cached_quarantines:
        if q.get("id") not in existing_ids:
            quarantines.append(q)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "quarantines": quarantines,
            "total": len(quarantines),
        },
    )


# -----------------------------------------------------------------------------
# POST /api/v1/coldchain/sensor (Alias for direct coldchain sensor ingestion)
# -----------------------------------------------------------------------------
@router.post(
    "/sensor",
    summary="Direct Cold-Chain Sensor Telemetry Ingestion",
    description="Ingest sensor telemetry directly to coldchain engine and return evaluation.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_coldchain_sensor(
    reading: SensorReadingEvent | dict[str, Any],
    request: Request,
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> JSONResponse:
    """Evaluate sensor reading directly through the Cold-Chain Telemetry Graph."""
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    payload = reading.model_dump(mode="json") if hasattr(reading, "model_dump") else dict(reading)

    batch_id = payload.get("batch_id", "BIO-INS-01")
    node_id = payload.get("node_id", "22222222-2222-2222-2222-222222222222")
    shipment_id = payload.get("shipment_id")

    eval_result = await run_coldchain_pipeline(
        batch_id=batch_id,
        readings=payload,
        node_id=node_id,
        shipment_id=shipment_id,
        correlation_id=correlation_id,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "evaluated",
            "batch_id": batch_id,
            "decision": eval_result.get("decision"),
            "shelf_life_estimate": eval_result.get("shelf_life_estimate"),
            "explanation": eval_result.get("explanation"),
            "quarantined": eval_result.get("quarantined", False),
            "quarantine_action_id": eval_result.get("quarantine_action_id"),
            "rebalance_result": eval_result.get("rebalance_result"),
            "correlation_id": correlation_id,
        },
    )
