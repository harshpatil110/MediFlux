"""FastAPI endpoints for Cold-Chain Telemetry, Batch Monitoring, and Quarantine Actions (Task 20 & Task 27)."""

import datetime
import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import get_service_db_client
from app.events.models import SensorReadingEvent
from app.graphs.coldchain import (
    DEFAULT_COLDCHAIN_BATCHES,
    get_in_memory_coldchain_batches,
    get_in_memory_quarantine_actions,
    get_in_memory_sensor_readings,
    run_coldchain_pipeline,
)

logger = logging.getLogger("mediflux.api.coldchain")

router = APIRouter(prefix="/coldchain", tags=["Cold Chain Telemetry"])


class ColdChainSimulateRequest(BaseModel):
    """Schema for triggering synthetic IoT telemetry simulation."""

    batch_id: str | None = Field(default=None, description="Target cold-chain batch ID (e.g. BIO-INS-01)")
    mode: Literal["normal", "excursion", "shock"] = Field(
        default="normal",
        description="Simulation telemetry profile: 'normal' (2-8°C), 'excursion' (>8°C), 'shock' (>8g)",
    )
    steps: int = Field(default=4, ge=1, le=10, description="Number of chronological telemetry reading steps")


def _get_or_seed_batch_readings(batch_id: str) -> list[dict[str, Any]]:
    """Retrieve chronological readings for batch or generate 6 baseline historical readings."""
    all_readings = get_in_memory_sensor_readings()
    batch_readings = [r for r in all_readings if r.get("batch_id") == batch_id]

    if len(batch_readings) < 6:
        base_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=6)
        baseline_temps = [4.6, 4.8, 5.1, 4.9, 5.2, 4.7]
        baseline_shocks = [0.2, 0.3, 0.1, 0.4, 0.2, 0.3]
        baseline_humidity = [48.0, 50.2, 49.1, 51.0, 48.5, 49.8]
        generated: list[dict[str, Any]] = []

        for i in range(6):
            t_offset = base_time + datetime.timedelta(hours=i)
            entry = {
                "batch_id": batch_id,
                "temperature_c": baseline_temps[i],
                "humidity": baseline_humidity[i],
                "shock_g": baseline_shocks[i],
                "estimated_remaining_days": 180.0,
                "shelf_life_pct": 100.0,
                "decision": "ok",
                "mode": "normal",
                "ts": t_offset.isoformat(),
            }
            generated.append(entry)
        return generated + batch_readings

    return batch_readings


# -----------------------------------------------------------------------------
# GET /api/v1/coldchain/batches
# -----------------------------------------------------------------------------
@router.get(
    "/batches",
    summary="List Cold-Chain Batches with Telemetry & Shelf-Life Estimates",
    description="Returns all cold-chain batches enriched with real-time shelf life, readings array, and quarantine status.",
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
                            inv_res = client.table("inventory").select("quantity").eq("batch_id", row["id"]).execute()
                            avail_qty = sum(i.get("quantity", 0) for i in (inv_res.data or []))
                            if row.get("status") == "quarantined":
                                avail_qty = 0

                            b_id = row["id"]
                            readings = _get_or_seed_batch_readings(b_id)
                            last_rd = readings[-1] if readings else None

                            nominal_days = 180.0
                            est_days = float(row.get("estimated_remaining_days") or 180.0)
                            shelf_pct = float(row.get("shelf_life_pct") or 100.0)

                            batch_entry = {
                                "batch_id": b_id,
                                "batch_no": row.get("batch_no", f"B26-{b_id}"),
                                "product_id": row.get("product_id"),
                                "product_name": prod.get("name", "Biologic"),
                                "sku": prod.get("sku", "MED-COLD"),
                                "storage_min_c": float(prod.get("storage_min_c", 2.0)),
                                "storage_max_c": float(prod.get("storage_max_c", 8.0)),
                                "status": row.get("status", "active"),
                                "available_quantity": avail_qty,
                                "readings": readings,
                                "last_reading": last_rd,
                                "shelf_life_estimate": {
                                    "nominal_remaining_days": nominal_days,
                                    "estimated_remaining_days": est_days,
                                    "shelf_life_pct": shelf_pct,
                                    "degradation_days": max(0.0, nominal_days - est_days),
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
            nominal_days = float(b.get("estimated_remaining_days") or 180.0)
            est_days = float(b.get("estimated_remaining_days") or 180.0)
            shelf_pct = float(b.get("shelf_life_pct") or 100.0)
            is_quarantined = b.get("status") == "quarantined"

            readings = _get_or_seed_batch_readings(b_id)
            last_rd = readings[-1] if readings else None

            enriched_batches.append({
                "batch_id": b_id,
                "batch_no": b.get("batch_no", f"B26-{b_id}"),
                "product_id": b.get("product_id", "p-008-insulin"),
                "product_name": b.get("product_name", "Cold-Chain Biologic"),
                "sku": b.get("sku", "MED-COLD"),
                "storage_min_c": float(b.get("storage_min_c", 2.0)),
                "storage_max_c": float(b.get("storage_max_c", 8.0)),
                "status": "quarantined" if is_quarantined else b.get("status", "active"),
                "available_quantity": 0 if is_quarantined else int(b.get("available_quantity", 1000)),
                "readings": readings,
                "last_reading": last_rd,
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
# POST /api/v1/coldchain/simulate
# -----------------------------------------------------------------------------
@router.post(
    "/simulate",
    summary="Simulate IoT Cold-Chain Telemetry (Normal, Thermal Excursion, Mechanical Shock)",
    description="Inject synthetic IoT telemetry series; automatically triggers auto-quarantine, stock removal, and rebalancing cascade upon breach.",
    status_code=status.HTTP_200_OK,
)
async def simulate_coldchain_telemetry(
    req: ColdChainSimulateRequest,
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> JSONResponse:
    """Simulate telemetry progression and evaluate through Cold-Chain Graph."""
    corr_id = x_correlation_id or str(uuid.uuid4())
    batch_id = req.batch_id or "BIO-INS-01"

    # Verify batch exists in default or memory
    if batch_id not in DEFAULT_COLDCHAIN_BATCHES and not any(
        (b.get("batch_id") == batch_id or b.get("id") == batch_id) for b in get_in_memory_coldchain_batches()
    ):
        batch_id = "BIO-INS-01"

    now = datetime.datetime.now(datetime.UTC)
    steps = max(1, min(req.steps, 10))
    simulated_readings: list[dict[str, Any]] = []

    if req.mode == "excursion":
        # Temperature escalating from within envelope to critical breach > 8.0°C
        temp_curve = [6.2, 9.4, 13.8, 17.5, 21.0, 24.2, 26.5, 28.0, 29.5, 31.0][:steps]
        shock_curve = [0.3, 0.4, 0.5, 0.4, 0.3, 0.5, 0.4, 0.3, 0.4, 0.5][:steps]
        humidity_curve = [52.0, 56.5, 62.0, 71.0, 75.0, 78.0, 80.0, 81.5, 83.0, 85.0][:steps]
    elif req.mode == "shock":
        # Mechanical shock breach > 8.0g
        temp_curve = [4.8, 5.0, 5.2, 4.9, 5.1, 4.8, 5.0, 5.1, 4.9, 5.0][:steps]
        shock_curve = [0.4, 1.2, 8.9, 0.5, 0.3, 0.4, 0.2, 0.3, 0.4, 0.3][:steps]
        humidity_curve = [49.0, 50.5, 51.0, 49.5, 50.0, 51.5, 50.0, 49.0, 51.0, 50.5][:steps]
    else:
        # Normal safe envelope (2.0°C - 8.0°C)
        temp_curve = [4.5, 4.8, 5.1, 4.7, 5.0, 4.6, 4.9, 5.2, 4.8, 5.0][:steps]
        shock_curve = [0.2, 0.3, 0.2, 0.4, 0.3, 0.2, 0.3, 0.2, 0.4, 0.3][:steps]
        humidity_curve = [48.0, 49.5, 51.0, 48.5, 50.0, 49.0, 50.5, 51.5, 49.0, 50.0][:steps]

    for i in range(steps):
        t_reading = now - datetime.timedelta(minutes=(steps - i) * 15)
        simulated_readings.append({
            "batch_id": batch_id,
            "temperature_c": temp_curve[i],
            "humidity": humidity_curve[i],
            "shock_g": shock_curve[i],
            "ts": t_reading.isoformat(),
            "mode": req.mode,
        })

    eval_result = await run_coldchain_pipeline(
        batch_id=batch_id,
        readings=simulated_readings,
        correlation_id=corr_id,
    )

    # Fetch updated batch info
    cached_batches = get_in_memory_coldchain_batches()
    target_batch = next(
        (b for b in cached_batches if (b.get("batch_id") == batch_id or b.get("id") == batch_id)),
        {},
    )

    quarantine_action: dict[str, Any] | None = None
    if eval_result.get("quarantined"):
        all_q = get_in_memory_quarantine_actions()
        if all_q:
            quarantine_action = all_q[-1]

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "simulated",
            "batch_id": batch_id,
            "mode": req.mode,
            "readings_generated": simulated_readings,
            "final_decision": eval_result.get("decision"),
            "batch_status": target_batch.get("status", "active"),
            "available_quantity": target_batch.get("available_quantity", 0),
            "shelf_life_estimate": eval_result.get("shelf_life_estimate"),
            "explanation": eval_result.get("explanation"),
            "quarantined": eval_result.get("quarantined", False),
            "quarantine_action": quarantine_action,
            "rebalance_correlation_id": corr_id,
            "rebalance_result": eval_result.get("rebalance_result"),
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
