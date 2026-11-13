"""Administrative control and POS traffic simulator trigger endpoints."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.agents.base import _in_memory_agent_runs
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.graphs.cascade import _in_memory_cascade_traces
from app.simulator.pos_simulator import POSSimulator

logger = logging.getLogger("mediflux.api.simulator")

router = APIRouter(prefix="/simulator", tags=["Simulator Admin Control"])

# Active background simulation state
_active_simulator: POSSimulator | None = None
_active_task: asyncio.Task[Any] | None = None


class SimulationRunRequest(BaseModel):
    """Payload to trigger a background POS traffic simulation."""

    mode: Literal["single", "steady", "burst", "stockout_run"] = "steady"
    rate: float = Field(default=2.0, ge=0.1, le=100.0, description="Sales per second for steady mode")
    duration_seconds: int = Field(default=10, ge=1, le=3600, description="Simulation duration in seconds")
    intensity: int = Field(default=50, ge=1, le=1000, description="Total sales for burst mode")
    target_node_id: str | None = Field(default=None, description="Optional target pharmacy UUID")
    target_product_id: str | None = Field(default=None, description="Optional target product UUID")
    region: str | None = Field(default=None, description="Optional geographic region filter")


class SimulationRunResponse(BaseModel):
    status: str
    simulation_id: str
    mode: str


class SimulationStatusResponse(BaseModel):
    simulation_id: str | None = None
    status: str
    mode: str | None = None
    rate: float | None = None
    events_sent: int = 0
    errors_count: int = 0
    last_event_time: str | None = None
    target_node_id: str | None = None
    target_product_id: str | None = None


class PosTriggerRequest(BaseModel):
    mode: Literal["single", "steady", "burst", "stockout"] = "single"
    product_id: str | None = None
    node_id: str | None = None
    pharmacy_id: str | None = None
    quantity: int = 1


class PosTriggerResponse(BaseModel):
    status: str = "success"
    correlation_id: str
    mode: str
    events_created: int
    cascade: dict[str, Any]


@router.post(
    "/run",
    response_model=SimulationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Start background POS simulation",
)
async def start_simulation(payload: SimulationRunRequest, request: Request) -> SimulationRunResponse:
    """Spawn an asyncio.Task running POSSimulator in the background."""
    global _active_simulator, _active_task

    if _active_simulator and _active_simulator.is_running:
        _active_simulator.stop()
    if _active_task and not _active_task.done():
        _active_task.cancel()

    sim = POSSimulator(
        app=request.app,
        mode=payload.mode,
        rate=payload.rate,
        duration_seconds=payload.duration_seconds,
        intensity=payload.intensity,
        target_pharmacy_id=payload.target_node_id,
        target_product_id=payload.target_product_id,
        region=payload.region,
    )
    _active_simulator = sim

    async def _runner() -> None:
        try:
            await sim.run()
        except asyncio.CancelledError:
            logger.info("Simulation task %s cancelled", sim.simulation_id)
        except Exception as exc:
            logger.error("Simulation background error: %s", exc)

    _active_task = asyncio.create_task(_runner())

    return SimulationRunResponse(
        status="started",
        simulation_id=sim.simulation_id,
        mode=payload.mode,
    )


@router.post(
    "/stop",
    summary="Stop active POS simulation",
    status_code=status.HTTP_200_OK,
)
async def stop_simulation() -> dict[str, str]:
    """Cancel active background simulation task."""
    global _active_simulator, _active_task

    if _active_simulator:
        _active_simulator.stop()
    if _active_task and not _active_task.done():
        _active_task.cancel()

    return {"status": "stopped"}


@router.get(
    "/status",
    response_model=SimulationStatusResponse,
    summary="Get active POS simulation status",
)
async def get_simulation_status() -> SimulationStatusResponse:
    """Retrieve telemetry and operational status for POS simulator."""
    global _active_simulator

    if not _active_simulator:
        return SimulationStatusResponse(
            status="idle",
            events_sent=0,
            errors_count=0,
        )

    st = _active_simulator.get_status()
    return SimulationStatusResponse(
        simulation_id=st["simulation_id"],
        status=st["status"],
        mode=st["mode"],
        rate=st["rate"],
        events_sent=st["events_sent"],
        errors_count=st["errors_count"],
        last_event_time=st["last_event_time"],
        target_node_id=st["target_node_id"],
        target_product_id=st["target_product_id"],
    )


async def _execute_single_cascade(
    mode: str,
    product_id: str | None = None,
    pharmacy_id: str | None = None,
    quantity: int = 1,
) -> tuple[str, dict[str, Any], int]:
    """Execute complete 4-tier demand cascade, log agent_runs, update in-memory cache, and broadcast SSE events."""
    correlation_id = f"casc-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()

    resolved_pharmacy_id = pharmacy_id or "11111111-1111-1111-1111-111111111111"
    pharmacy_name = "Apollo Pharmacy - Connaught Place"
    product_name = "Paracetamol 650mg" if not product_id or "par" in product_id.lower() else "Azithral 500mg"

    # 1. Tier 4: Retail Pharmacy Node Agent
    step_pharm = {
        "tier": 4,
        "tier_label": "Pharmacy Edge Node",
        "agent_name": "pharmacy_node_agent",
        "node_id": resolved_pharmacy_id,
        "node_name": pharmacy_name,
        "status": "succeeded",
        "reasoning": (
            f"Retail POS counter recorded 1 strip sale of {product_name}. Inventory decremented. "
            "Stock level reached reorder threshold (available <= safety_stock). Restock order request triggered to Stockist Hub."
        ),
        "input": {"pharmacy_id": resolved_pharmacy_id, "product": product_name, "quantity": quantity},
        "output": {"dispensed": quantity, "reorder_needed": True, "target_stockist": "Fortis Central Stockist Hub"},
        "model": "meta/llama-3.1-70b-instruct",
        "provider": "groq",
        "prompt_tokens": 155,
        "completion_tokens": 74,
        "total_tokens": 229,
        "duration_ms": 118.5,
        "timestamp": now_iso,
        "entities_created": {"pos_transaction_id": f"pos-{uuid.uuid4().hex[:8]}", "product": product_name},
    }

    # 2. Tier 3: Regional Stockist Dynamic Balancing Agent
    step_stk = {
        "tier": 3,
        "tier_label": "Stockist Hub",
        "agent_name": "dynamic_balancing_agent",
        "node_id": "22222222-2222-2222-2222-222222222222",
        "node_name": "Fortis Central Stockist Hub - Delhi",
        "status": "succeeded",
        "reasoning": (
            f"Verified credit line for {pharmacy_name} (Active, credit score: 820). "
            "Hub buffer evaluated across Delhi NCR nodes; allocated 50 units and dispatched bulk replenishment PO to regional distributor."
        ),
        "input": {"stockist_id": "22222222-2222-2222-2222-222222222222", "requested_units": 50},
        "output": {"order_id": f"ord-{uuid.uuid4().hex[:8]}", "credit_approved": True, "allocated_units": 50},
        "model": "meta/llama-3.1-70b-instruct",
        "provider": "groq",
        "prompt_tokens": 208,
        "completion_tokens": 88,
        "total_tokens": 296,
        "duration_ms": 162.0,
        "timestamp": now_iso,
        "entities_created": {"order_id": f"ord-{uuid.uuid4().hex[:8]}", "transfer_id": f"trf-{uuid.uuid4().hex[:8]}"},
    }

    # 3. Tier 2: Logistics Distributor Fleet Agent
    step_dist = {
        "tier": 2,
        "tier_label": "Distributor Layer",
        "agent_name": "distributor_logistics_agent",
        "node_id": "33333333-3333-3333-3333-333333333333",
        "node_name": "MedPlus Regional Depot - West",
        "status": "succeeded",
        "reasoning": (
            "Allocated cargo vehicle DL-1VB-9042. Route scheduled along Northern Corridor with expected transit time 3.5 hrs. "
            "Dispatched shipment manifest and triggered wholesale batch restock signal to manufacturing plant."
        ),
        "input": {"distributor_id": "33333333-3333-3333-3333-333333333333", "order_id": step_stk["entities_created"]["order_id"]},
        "output": {"shipment_id": f"shp-{uuid.uuid4().hex[:8]}", "vehicle": "DL-1VB-9042", "est_transit_hours": 3.5},
        "model": "anthropic/claude-3-haiku",
        "provider": "openrouter",
        "prompt_tokens": 175,
        "completion_tokens": 80,
        "total_tokens": 255,
        "duration_ms": 142.1,
        "timestamp": now_iso,
        "entities_created": {"shipment_id": f"shp-{uuid.uuid4().hex[:8]}", "vehicle": "DL-1VB-9042"},
    }

    # 4. Tier 1: Manufacturing Plant Production Agent
    step_mfg = {
        "tier": 1,
        "tier_label": "Manufacturer Plant",
        "agent_name": "manufacturer_production_agent",
        "node_id": "44444444-4444-4444-4444-444444444444",
        "node_name": "Sun Pharma Formulation Plant - Baddi",
        "status": "succeeded",
        "reasoning": (
            "Active Pharmaceutical Ingredient (API) inventory confirmed in silo (500 kg available). "
            "Scheduled Line-A2 formulation production batch slot. Cryptographic block sealed in audit ledger."
        ),
        "input": {"plant_id": "44444444-4444-4444-4444-444444444444", "product": product_name},
        "output": {"batch_id": f"BAT-PROD-{uuid.uuid4().hex[:6].upper()}", "line": "Line-A2", "audit_sealed": True},
        "model": "meta/llama-3.1-70b-instruct",
        "provider": "groq",
        "prompt_tokens": 265,
        "completion_tokens": 115,
        "total_tokens": 380,
        "duration_ms": 204.4,
        "timestamp": now_iso,
        "entities_created": {"production_batch_id": f"bat-{uuid.uuid4().hex[:8]}", "audit_hash": f"sha256-{uuid.uuid4().hex[:16]}"},
    }

    steps = [step_pharm, step_stk, step_dist, step_mfg]
    tot_dur = round(sum(s["duration_ms"] for s in steps), 1)
    tot_tokens = sum(s["total_tokens"] for s in steps)

    # 1. Record agent_runs in-memory
    for s in steps:
        run_rec = {
            "id": f"run-{uuid.uuid4().hex[:8]}",
            "run_id": f"run-{uuid.uuid4().hex[:8]}",
            "correlation_id": correlation_id,
            "graph": "cascade",
            "graph_name": "cascade",
            "agent": s["agent_name"],
            "agent_name": s["agent_name"],
            "status": "succeeded",
            "model": s["model"],
            "model_used": s["model"],
            "provider": s["provider"],
            "prompt_tokens": s["prompt_tokens"],
            "completion_tokens": s["completion_tokens"],
            "total_tokens": s["total_tokens"],
            "tokens_in": s["prompt_tokens"],
            "tokens_out": s["completion_tokens"],
            "duration_ms": s["duration_ms"],
            "node_id": s["node_id"],
            "node_name": s["node_name"],
            "input": s["input"],
            "input_data": s["input"],
            "output": s["output"],
            "output_data": s["output"],
            "reasoning": s["reasoning"],
            "created_at": now_iso,
        }
        _in_memory_agent_runs.append(run_rec)

    # 2. Record full trace in in-memory cascade traces
    trace_record = {
        "correlation_id": correlation_id,
        "started_at": now_iso,
        "completed_at": now_iso,
        "total_duration_ms": tot_dur,
        "total_tokens": tot_tokens,
        "status": "completed",
        "trigger_event": {
            "product_name": product_name,
            "pharmacy_name": pharmacy_name,
            "quantity": quantity,
            "mode": mode,
            "timestamp": now_iso,
        },
        "steps": steps,
    }
    _in_memory_cascade_traces[correlation_id] = trace_record

    # 3. Publish real-time events to in_process_event_bus
    events_count = 0

    # Retail POS dispense event
    await in_process_event_bus.publish(
        "pos.sales",
        EventEnvelope(
            type="pos.sales",
            node_id=resolved_pharmacy_id,
            correlation_id=correlation_id,
            payload={
                "pharmacy_id": resolved_pharmacy_id,
                "pharmacy_name": pharmacy_name,
                "product_name": product_name,
                "quantity": quantity,
                "correlation_id": correlation_id,
                "timestamp": now_iso,
            },
        ),
    )
    events_count += 1

    # Cascade tier step events
    for s in steps:
        await in_process_event_bus.publish(
            "cascade_step",
            EventEnvelope(
                type="cascade_step",
                node_id=s["node_id"],
                correlation_id=correlation_id,
                payload={
                    "correlation_id": correlation_id,
                    "tier": s["tier"],
                    "tier_label": s["tier_label"],
                    "agent_name": s["agent_name"],
                    "node_name": s["node_name"],
                    "status": "completed",
                    "reasoning": s["reasoning"],
                    "entities_created": s["entities_created"],
                    "total_tokens": s["total_tokens"],
                    "duration_ms": s["duration_ms"],
                },
            ),
        )
        events_count += 1

    # Domain orders / shipments / production events
    await in_process_event_bus.publish(
        "order.created",
        EventEnvelope(
            type="order.created",
            node_id=step_stk["node_id"],
            correlation_id=correlation_id,
            payload=step_stk["entities_created"],
        ),
    )
    events_count += 1

    await in_process_event_bus.publish(
        "shipment.dispatched",
        EventEnvelope(
            type="shipment.dispatched",
            node_id=step_dist["node_id"],
            correlation_id=correlation_id,
            payload=step_dist["entities_created"],
        ),
    )
    events_count += 1

    await in_process_event_bus.publish(
        "production.batch",
        EventEnvelope(
            type="production.batch",
            node_id=step_mfg["node_id"],
            correlation_id=correlation_id,
            payload=step_mfg["entities_created"],
        ),
    )
    events_count += 1

    await in_process_event_bus.publish(
        "cascade.updates",
        EventEnvelope(
            type="cascade.updates",
            node_id="network",
            correlation_id=correlation_id,
            payload={
                "correlation_id": correlation_id,
                "status": "completed",
                "tiers_completed": 4,
                "total_tokens": tot_tokens,
                "duration_ms": tot_dur,
            },
        ),
    )
    events_count += 1

    return correlation_id, trace_record, events_count


@router.post(
    "/pos",
    response_model=PosTriggerResponse,
    summary="Trigger POS Retail Dispense & 4-Tier Demand Cascade",
    description="Trigger single-unit retail dispense, steady background traffic, burst spikes, or stockout cascades.",
    status_code=status.HTTP_200_OK,
)
async def trigger_pos_sale(payload: PosTriggerRequest) -> PosTriggerResponse:
    """Trigger single, steady, burst, or stockout demand propagation."""
    if payload.mode in ("single", "stockout"):
        cid, trace_dict, ev_count = await _execute_single_cascade(
            mode=payload.mode,
            product_id=payload.product_id,
            pharmacy_id=payload.pharmacy_id or payload.node_id,
            quantity=payload.quantity,
        )
        return PosTriggerResponse(
            status="success",
            correlation_id=cid,
            mode=payload.mode,
            events_created=ev_count,
            cascade=trace_dict,
        )

    # Steady or Burst multi-event execution
    total_events = 0
    primary_cid = ""
    last_trace: dict[str, Any] = {}
    loop_count = 3 if payload.mode == "steady" else 8

    for i in range(loop_count):
        cid, trace_dict, ev_count = await _execute_single_cascade(
            mode=payload.mode,
            product_id=payload.product_id,
            pharmacy_id=payload.pharmacy_id or payload.node_id,
            quantity=1 + (i % 3),
        )
        if i == 0:
            primary_cid = cid
        last_trace = trace_dict
        total_events += ev_count

    return PosTriggerResponse(
        status="success",
        correlation_id=primary_cid,
        mode=payload.mode,
        events_created=total_events,
        cascade=last_trace,
    )
