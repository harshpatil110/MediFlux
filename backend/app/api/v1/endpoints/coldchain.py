"""FastAPI endpoints for Cold-Chain Telemetry, Batch Monitoring, and Quarantine Actions (Task 20 & Task 27)."""

import datetime
import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
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


NODE_NAMES: dict[str, str] = {
    "11111111-1111-1111-1111-111111111111": "Apollo Pharmacy - Connaught Place",
    "22222222-2222-2222-2222-222222222222": "North Delhi Stockist Hub",
    "33333333-3333-3333-3333-333333333333": "Northern India Regional Depot",
    "44444444-4444-4444-4444-444444444444": "Sun Pharma Formulation Plant - Baddi",
}


def _normalize_batch_status(raw_status: str | None, telemetry_status: str | None) -> str:
    """Normalize batch and telemetry status to 'ok' | 'warn' | 'quarantined'."""
    s = (raw_status or "").lower()
    t = (telemetry_status or "").lower()
    if s in ("quarantined", "quarantine") or t in ("quarantined", "quarantine"):
        return "quarantined"
    if s in ("warn", "warning") or t in ("warn", "warning"):
        return "warn"
    return "ok"


def _find_quarantine_info(batch_id: str) -> dict[str, Any] | None:
    """Find latest quarantine record for a batch from in-memory or Supabase."""
    all_q = get_in_memory_quarantine_actions()
    for q in reversed(all_q):
        if q.get("batch_id") == batch_id:
            reason_str = q.get("explanation") or q.get("reason") or "Thermal excursion beyond safe envelope"
            return {
                "id": q.get("id"),
                "reason": q.get("reason") or reason_str,
                "explanation": reason_str,
                "correlation_id": q.get("correlation_id"),
                "audit_entry_id": str(q.get("audit_seq") or q.get("audit_entry_id") or ""),
                "rebalance_triggered": True,
                "created_at": q.get("created_at") or q.get("triggered_at"),
            }

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("quarantine_actions")
                    .select("*")
                    .eq("batch_id", batch_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    q = res.data[0]
                    reason_str = q.get("explanation") or q.get("reason") or "Thermal excursion beyond safe envelope"
                    return {
                        "id": q.get("id"),
                        "reason": q.get("reason") or reason_str,
                        "explanation": reason_str,
                        "correlation_id": q.get("correlation_id"),
                        "audit_entry_id": str(q.get("audit_seq") or q.get("audit_entry_id") or ""),
                        "rebalance_triggered": True,
                        "created_at": q.get("created_at") or q.get("triggered_at"),
                    }
        except Exception as exc:
            logger.debug("Supabase lookup for quarantine failed: %s", exc)

    return None


def _build_enriched_batch(row: dict[str, Any]) -> dict[str, Any]:
    """Enrich a batch record with complete sensor readings, shelf life, and quarantine details."""
    b_id = row.get("batch_id") or row.get("id") or "BIO-INS-01"
    raw_status = row.get("status")
    telemetry_status = row.get("last_telemetry_status") or row.get("decision")
    norm_status = _normalize_batch_status(raw_status, telemetry_status)

    is_quarantined = (norm_status == "quarantined")
    avail_qty = 0 if is_quarantined else int(row.get("available_quantity", 1000))

    readings = _get_or_seed_batch_readings(b_id)
    last_rd = readings[-1] if readings else None

    nominal_days = float(row.get("nominal_days") or 180.0)
    est_days = float(row.get("estimated_remaining_days") or (0.0 if is_quarantined else nominal_days))
    shelf_pct = float(row.get("shelf_life_pct") or (0.0 if is_quarantined else 100.0))
    thermal_penalty = max(0.0, nominal_days - est_days)

    node_id = str(row.get("node_id") or "22222222-2222-2222-2222-222222222222")
    node_name = row.get("node_name") or NODE_NAMES.get(node_id, "North Delhi Stockist Hub")

    prod = row.get("products") or {} if isinstance(row.get("products"), dict) else {}
    prod_name = row.get("product_name") or prod.get("name") or "Cold-Chain Biologic"
    sku = row.get("sku") or prod.get("sku") or "MED-COLD"
    storage_min = float(row.get("storage_min_c") or prod.get("storage_min_c") or 2.0)
    storage_max = float(row.get("storage_max_c") or prod.get("storage_max_c") or 8.0)

    quarantine_info = _find_quarantine_info(b_id) if is_quarantined else None

    return {
        "batch_id": b_id,
        "id": b_id,
        "batch_no": row.get("batch_no", f"B26-{b_id}"),
        "product_id": row.get("product_id", "p-008-insulin"),
        "product_name": prod_name,
        "sku": sku,
        "node_id": node_id,
        "node_name": node_name,
        "storage_min_c": storage_min,
        "storage_max_c": storage_max,
        "status": norm_status,
        "available_quantity": avail_qty,
        "readings": readings,
        "last_reading": last_rd,
        "shelf_life_estimate": {
            "nominal_remaining_days": nominal_days,
            "estimated_remaining_days": est_days,
            "shelf_life_pct": shelf_pct,
            "thermal_penalty_days": thermal_penalty,
            "shock_penalty_days": 0.0,
            "degradation_days": thermal_penalty,
            "formula_model": "Simplified Arrhenius Degree-Hour & Mechanical Shock Model",
            "decision": norm_status,
        },
        "quarantine": quarantine_info,
    }


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
    seen_ids: set[str] = set()

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
                            row_copy = dict(row)
                            row_copy["available_quantity"] = avail_qty
                            enriched = _build_enriched_batch(row_copy)
                            enriched_batches.append(enriched)
                            seen_ids.add(enriched["batch_id"])
        except Exception as exc:
            logger.debug("DB batches query failed (%s); serving from in-memory cache", exc)

    # 2. Merge with in-memory batches cache
    cached = get_in_memory_coldchain_batches()
    for b in cached:
        b_id = b.get("batch_id") or b.get("id")
        if b_id and b_id not in seen_ids:
            enriched = _build_enriched_batch(b)
            enriched_batches.append(enriched)
            seen_ids.add(b_id)

    # 3. Fallback to default coldchain batches if empty
    if not enriched_batches:
        for _b_id, b_data in DEFAULT_COLDCHAIN_BATCHES.items():
            enriched = _build_enriched_batch(b_data)
            enriched_batches.append(enriched)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "batches": enriched_batches,
            "total": len(enriched_batches),
        },
    )


# -----------------------------------------------------------------------------
# GET /api/v1/coldchain/batches/{batch_id}
# -----------------------------------------------------------------------------
@router.get(
    "/batches/{batch_id}",
    summary="Get Cold-Chain Batch Details & Telemetry",
    description="Returns detailed telemetry, Arrhenius shelf-life estimates, recent readings, and quarantine records for a batch.",
    status_code=status.HTTP_200_OK,
)
async def get_coldchain_batch(batch_id: str) -> JSONResponse:
    """Retrieve detailed cold-chain telemetry, readings, and quarantine records for a batch."""
    batch_data: dict[str, Any] | None = None

    # 1. Search in DB
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("batches")
                    .select("*, products(name, sku, is_cold_chain, storage_min_c, storage_max_c)")
                    .or_(f"id.eq.{batch_id},batch_no.eq.{batch_id}")
                    .execute()
                )
                if res.data:
                    batch_data = dict(res.data[0])
                    inv_res = client.table("inventory").select("quantity").eq("batch_id", batch_data["id"]).execute()
                    avail_qty = sum(i.get("quantity", 0) for i in (inv_res.data or []))
                    if batch_data.get("status") == "quarantined":
                        avail_qty = 0
                    batch_data["available_quantity"] = avail_qty
        except Exception as exc:
            logger.debug("DB batch lookup failed: %s", exc)

    # 2. Search in-memory cache
    if not batch_data:
        cached = get_in_memory_coldchain_batches()
        for b in cached:
            if b.get("batch_id") == batch_id or b.get("id") == batch_id or b.get("batch_no") == batch_id:
                batch_data = dict(b)
                break

    # 3. Fallback to default batches
    if not batch_data and batch_id in DEFAULT_COLDCHAIN_BATCHES:
        batch_data = dict(DEFAULT_COLDCHAIN_BATCHES[batch_id])

    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cold-chain batch '{batch_id}' not found.",
        )

    enriched = _build_enriched_batch(batch_data)
    return JSONResponse(status_code=status.HTTP_200_OK, content=enriched)



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
