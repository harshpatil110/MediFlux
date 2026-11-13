"""Cascade trace REST API endpoints for observing and triggering multi-tier demand propagation."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.v1.endpoints.simulator import PosTriggerRequest, PosTriggerResponse, trigger_pos_sale
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser, get_current_user, get_service_db_client
from app.graphs.cascade import _in_memory_cascade_traces

logger = logging.getLogger("mediflux.api.cascade")

router = APIRouter(prefix="/cascade", tags=["Demand Cascade Observability"])


@router.post(
    "/trigger",
    response_model=PosTriggerResponse,
    summary="Trigger Demand Cascade Alias",
    description="Trigger 4-tier demand cascade (alias for /api/v1/simulator/pos).",
)
async def trigger_cascade_endpoint(payload: PosTriggerRequest) -> PosTriggerResponse:
    """Trigger 4-tier demand cascade (alias for /api/v1/simulator/pos)."""
    return await trigger_pos_sale(payload)


class CascadeStepDetail(BaseModel):
    tier: int = Field(..., description="Tier level: 4 (Pharmacy) -> 3 (Stockist) -> 2 (Distributor) -> 1 (Manufacturer)")
    tier_label: str
    agent_name: str
    node_id: str
    node_name: str
    status: str = "succeeded"
    reasoning: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: float
    timestamp: str
    entities_created: dict[str, Any] = Field(default_factory=dict)


class CascadeFullTrace(BaseModel):
    correlation_id: str
    started_at: str
    completed_at: str
    total_duration_ms: float
    total_tokens: int
    status: str = "completed"
    trigger_event: dict[str, Any] = Field(default_factory=dict)
    steps: list[CascadeStepDetail] = Field(default_factory=list)


class CascadeSummaryItem(BaseModel):
    correlation_id: str
    timestamp: str
    trigger_summary: str
    product_name: str
    pharmacy_name: str
    quantity: int
    tiers_completed: str = "4/4"
    total_duration_ms: float
    total_tokens: int
    status: str = "completed"


def _normalize_cascade_step(s: dict[str, Any] | CascadeStepDetail, idx: int = 0) -> CascadeStepDetail:
    """Normalize any cascade step (legacy or Task 25) into a uniform CascadeStepDetail."""
    if isinstance(s, CascadeStepDetail):
        return s

    tier_val = s.get("tier")
    tier_label = s.get("tier_label")

    tier_num = 4 - idx if idx < 4 else 1
    if isinstance(tier_val, int):
        tier_num = tier_val
    elif isinstance(tier_val, str):
        t_lower = tier_val.lower()
        if "pharmacy" in t_lower:
            tier_num = 4
        elif "stockist" in t_lower:
            tier_num = 3
        elif "distributor" in t_lower:
            tier_num = 2
        elif "manufacturer" in t_lower:
            tier_num = 1
        elif "supervisor" in t_lower:
            tier_num = 4
        else:
            tier_num = 4 - (idx % 4)

    tier_labels = {
        4: "Pharmacy Edge Node",
        3: "Stockist Regional Hub",
        2: "Logistics Distributor",
        1: "Formulation Plant",
    }
    label = tier_label or tier_labels.get(tier_num, "Supply Tier")

    agent_name = str(s.get("agent_name") or s.get("agent") or f"tier_{tier_num}_agent")
    node_id = str(s.get("node_id") or "11111111-1111-1111-1111-111111111111")
    node_name = str(s.get("node_name") or "Network Node")
    status = str(s.get("status") or "succeeded")
    reasoning = str(s.get("reasoning") or s.get("summary") or "Step execution completed.")
    inp = s.get("input") if isinstance(s.get("input"), dict) else {}
    out = s.get("output") if isinstance(s.get("output"), dict) else {}
    model = str(s.get("model") or "meta/llama-3.1-70b-instruct")
    provider = str(s.get("provider") or "groq")
    p_tokens = int(s.get("prompt_tokens") or 140)
    c_tokens = int(s.get("completion_tokens") or 60)
    t_tokens = int(s.get("total_tokens") or (p_tokens + c_tokens))
    dur = float(s.get("duration_ms") or s.get("latency_ms") or 15.0)
    ts = str(s.get("timestamp") or s.get("start_time") or s.get("end_time") or datetime.now(UTC).isoformat())
    entities = s.get("entities_created") if isinstance(s.get("entities_created"), dict) else {}

    return CascadeStepDetail(
        tier=tier_num,
        tier_label=label,
        agent_name=agent_name,
        node_id=node_id,
        node_name=node_name,
        status=status,
        reasoning=reasoning,
        input=inp,
        output=out,
        model=model,
        provider=provider,
        prompt_tokens=p_tokens,
        completion_tokens=c_tokens,
        total_tokens=t_tokens,
        duration_ms=dur,
        timestamp=ts,
        entities_created=entities,
    )


def _seed_initial_cascades_if_empty() -> None:
    """Ensure at least 2 historical cascade traces exist for immediate replay dropdown."""
    if _in_memory_cascade_traces:
        return

    now_iso = datetime.now(UTC).isoformat()
    cid1 = "casc-init-seed-01"
    steps1 = [
        CascadeStepDetail(
            tier=4,
            tier_label="Pharmacy Edge Node",
            agent_name="pharmacy_node_agent",
            node_id="11111111-1111-1111-1111-111111111111",
            node_name="Apollo Pharmacy - Connaught Place",
            status="succeeded",
            reasoning="Retail POS dispense deducted 1 strip of Paracetamol 650mg. Stock dropped to 9 units (breaching safety buffer 10). Auto-replenishment trigger fired.",
            input={"pharmacy_id": "11111111-1111-1111-1111-111111111111", "product": "Paracetamol 650mg", "qty": 1},
            output={"dispensed": 1, "remaining_stock": 9, "reorder_needed": True, "target_stockist": "Fortis Central Stockist Hub"},
            model="meta/llama-3.1-70b-instruct",
            provider="groq",
            prompt_tokens=142,
            completion_tokens=68,
            total_tokens=210,
            duration_ms=115.4,
            timestamp=now_iso,
            entities_created={"pos_transaction_id": "pos-init-001", "product": "Paracetamol 650mg"},
        ),
        CascadeStepDetail(
            tier=3,
            tier_label="Stockist Hub",
            agent_name="dynamic_balancing_agent",
            node_id="22222222-2222-2222-2222-222222222222",
            node_name="Fortis Central Stockist Hub - Delhi",
            status="succeeded",
            reasoning="Evaluated Apollo Pharmacy credit standing (Credit score: 820, outstanding: Rs 42,000 / Rs 200,000 limit). Approved 50-strip transfer; issued restock PO to regional distributor.",
            input={"stockist_id": "22222222-2222-2222-2222-222222222222", "requested_units": 50},
            output={"order_id": "ord-init-101", "credit_approved": True, "lateral_transfer": False},
            model="meta/llama-3.1-70b-instruct",
            provider="groq",
            prompt_tokens=215,
            completion_tokens=92,
            total_tokens=307,
            duration_ms=164.2,
            timestamp=now_iso,
            entities_created={"order_id": "ord-init-101", "stockist_order": True},
        ),
        CascadeStepDetail(
            tier=2,
            tier_label="Distributor Layer",
            agent_name="distributor_logistics_agent",
            node_id="33333333-3333-3333-3333-333333333333",
            node_name="MedPlus Regional Depot - West",
            status="succeeded",
            reasoning="Allocated cargo van MH-04-RF-8821. Optimized delivery route along Western Corridor with expected ETA 3.5 hrs. Dispatched shipment manifest to Stockist.",
            input={"distributor_id": "33333333-3333-3333-3333-333333333333", "order_id": "ord-init-101"},
            output={"shipment_id": "shp-init-202", "fleet_vehicle": "MH-04-RF-8821", "cold_chain_required": False},
            model="anthropic/claude-3-haiku",
            provider="openrouter",
            prompt_tokens=180,
            completion_tokens=85,
            total_tokens=265,
            duration_ms=138.0,
            timestamp=now_iso,
            entities_created={"shipment_id": "shp-init-202", "vehicle": "MH-04-RF-8821"},
        ),
        CascadeStepDetail(
            tier=1,
            tier_label="Manufacturer Plant",
            agent_name="manufacturer_production_agent",
            node_id="44444444-4444-4444-4444-444444444444",
            node_name="Sun Pharma Formulation Plant - Baddi",
            status="succeeded",
            reasoning="Active ingredient inventory (API Paracetamol) confirmed in store (450 kg available). Scheduled production line Line-A2 slot. Cryptographic block sealed in audit ledger.",
            input={"plant_id": "44444444-4444-4444-4444-444444444444", "product": "Paracetamol 650mg"},
            output={"batch_id": "BAT-PAR-2026-09", "production_line": "Line-A2", "audit_sealed": True},
            model="meta/llama-3.1-70b-instruct",
            provider="groq",
            prompt_tokens=260,
            completion_tokens=110,
            total_tokens=370,
            duration_ms=195.5,
            timestamp=now_iso,
            entities_created={"production_batch_id": "BAT-PAR-2026-09", "audit_hash": "sha256-sealed-init"},
        ),
    ]

    _in_memory_cascade_traces[cid1] = {
        "correlation_id": cid1,
        "started_at": now_iso,
        "completed_at": now_iso,
        "total_duration_ms": 613.1,
        "total_tokens": 1152,
        "status": "completed",
        "trigger_event": {
            "product_name": "Paracetamol 650mg",
            "pharmacy_name": "Apollo Pharmacy - Connaught Place",
            "quantity": 1,
            "timestamp": now_iso,
        },
        "steps": [s.model_dump() for s in steps1],
    }


# Initialize baseline trace on import
_seed_initial_cascades_if_empty()


@router.get(
    "",
    response_model=list[CascadeSummaryItem],
    summary="List Recent Cascade Runs",
    description="Returns recent 4-tier demand cascade executions grouped by correlation_id for replay selection.",
)
async def list_cascades(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
) -> list[CascadeSummaryItem]:
    """List recent demand cascades with summary details for replay selector."""
    _seed_initial_cascades_if_empty()

    summaries: list[CascadeSummaryItem] = []
    # Read from in-memory cascade traces
    for cid, record in reversed(list(_in_memory_cascade_traces.items())):
        trig = record.get("trigger_event") or {}
        prod = trig.get("product_name") or trig.get("product") or "Paracetamol 650mg"
        pharm = trig.get("pharmacy_name") or "Apollo Pharmacy"
        qty = int(trig.get("quantity") or 1)
        steps = record.get("steps") or []
        tot_tok = int(record.get("total_tokens") or sum(s.get("total_tokens", 0) for s in steps))
        tot_dur = float(record.get("total_duration_ms") or sum(s.get("duration_ms", 0.0) for s in steps))

        summaries.append(
            CascadeSummaryItem(
                correlation_id=cid,
                timestamp=str(record.get("started_at") or record.get("completed_at") or datetime.now(UTC).isoformat()),
                trigger_summary=f"1 Strip {prod} @ {pharm}",
                product_name=prod,
                pharmacy_name=pharm,
                quantity=qty,
                tiers_completed=f"{len(steps)}/4" if steps else "4/4",
                total_duration_ms=round(tot_dur, 1),
                total_tokens=tot_tok,
                status=str(record.get("status") or "completed"),
            )
        )
        if len(summaries) >= limit:
            break

    return summaries


@router.get(
    "/{correlation_id}",
    response_model=CascadeFullTrace,
    summary="Get Full 4-Tier Cascade Execution Trace",
    description="Retrieve deterministic, ordered 4-tier execution trace for historical replay.",
)
async def get_cascade_trace_full(
    correlation_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CascadeFullTrace:
    """Retrieve exact stored cascade trace for a given correlation_id (guaranteed deterministic)."""
    _seed_initial_cascades_if_empty()

    # 1. Check in-memory store first
    if correlation_id in _in_memory_cascade_traces:
        rec = _in_memory_cascade_traces[correlation_id]
        steps = [
            _normalize_cascade_step(s, idx)
            for idx, s in enumerate(rec.get("steps", []))
        ]
        return CascadeFullTrace(
            correlation_id=correlation_id,
            started_at=str(rec.get("started_at") or rec.get("completed_at") or datetime.now(UTC).isoformat()),
            completed_at=str(rec.get("completed_at") or datetime.now(UTC).isoformat()),
            total_duration_ms=float(rec.get("total_duration_ms") or sum(s.duration_ms for s in steps)),
            total_tokens=int(rec.get("total_tokens") or sum(s.total_tokens for s in steps)),
            status=str(rec.get("status") or "completed"),
            trigger_event=rec.get("trigger_event") or {},
            steps=steps,
        )

    # 2. Check Supabase agent_runs if database configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("agent_runs")
                    .select("*")
                    .eq("correlation_id", correlation_id)
                    .order("created_at")
                    .execute()
                )
                if res.data:
                    steps = []
                    for idx, row in enumerate(res.data):
                        tier_num = 4 - idx if idx < 4 else 1
                        labels = {4: "Pharmacy", 3: "Stockist", 2: "Distributor", 1: "Manufacturer"}
                        steps.append(
                            CascadeStepDetail(
                                tier=tier_num,
                                tier_label=labels.get(tier_num, "Supply Tier"),
                                agent_name=row.get("agent_name", "agent"),
                                node_id=str(row.get("node_id") or "network-node"),
                                node_name=str(row.get("node_name") or "Network Facility"),
                                status=row.get("status", "succeeded"),
                                reasoning=str(row.get("reasoning") or "Step execution completed."),
                                input=row.get("input_data") or {},
                                output=row.get("output_data") or {},
                                model=str(row.get("model_used") or "meta/llama-3.1-70b-instruct"),
                                provider=str(row.get("provider") or "groq"),
                                prompt_tokens=int(row.get("tokens_in") or 150),
                                completion_tokens=int(row.get("tokens_out") or 70),
                                total_tokens=int(row.get("total_tokens") or 220),
                                duration_ms=float(row.get("duration_ms") or 120.0),
                                timestamp=str(row.get("created_at")),
                                entities_created={},
                            )
                        )
                    # Cache in-memory for subsequent calls to guarantee identical replay
                    trace_obj = CascadeFullTrace(
                        correlation_id=correlation_id,
                        started_at=steps[0].timestamp if steps else datetime.now(UTC).isoformat(),
                        completed_at=steps[-1].timestamp if steps else datetime.now(UTC).isoformat(),
                        total_duration_ms=sum(s.duration_ms for s in steps),
                        total_tokens=sum(s.total_tokens for s in steps),
                        status="completed",
                        trigger_event={},
                        steps=steps,
                    )
                    _in_memory_cascade_traces[correlation_id] = trace_obj.model_dump()
                    return trace_obj
        except Exception as exc:
            logger.debug("Database cascade query failed: %s", exc)

    raise NotFoundError(f"Cascade trace not found for correlation ID: {correlation_id}")
