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
    tier: int = Field(..., description="Tier level: 5 (Supervisor) -> 4 (Pharmacy) -> 3 (Stockist) -> 2 (Distributor) -> 1 (Manufacturer)")
    tier_label: str
    stage: str | None = None
    agent_name: str
    node_id: str
    node_name: str
    status: str = "succeeded"
    state: str | None = "done"
    reasoning: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    skip_reason: str | None = None
    hitl_task_id: str | None = None
    model: str = "meta/llama-3.1-70b-instruct"
    provider: str = "groq"
    prompt_tokens: int = 140
    completion_tokens: int = 60
    total_tokens: int = 200
    duration_ms: float = 25.0
    timestamp: str = ""
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
    product_id: str = "11111111-2222-3333-4444-555555555555"
    product_name: str
    sku: str = "MED-PARA-500"
    pharmacy_node_id: str = "11111111-1111-1111-1111-111111111111"
    pharmacy_name: str
    created_at: str
    timestamp: str | None = None
    outcome: str = "complete"  # complete | partial | waiting_approval
    status: str = "completed"
    steps_completed: int = 5
    total_steps: int = 5
    tiers_completed: str = "5/5"
    quantity: int = 1
    total_duration_ms: float
    total_tokens: int
    summary: str = ""
    trigger_summary: str = ""


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
            tier_num = 5
        else:
            tier_num = 4 - (idx % 4)

    tier_labels = {
        5: "Supervisor Orchestrator",
        4: "Pharmacy Edge Node",
        3: "Stockist Regional Hub",
        2: "Logistics Distributor",
        1: "Formulation Plant",
    }
    label = tier_label or tier_labels.get(tier_num, "Supply Tier")

    stage = s.get("stage") or ("supervisor" if tier_num == 5 else ("pharmacy" if tier_num == 4 else ("stockist" if tier_num == 3 else ("distributor" if tier_num == 2 else "manufacturer"))))
    state = s.get("state") or ("done" if s.get("status") == "succeeded" else s.get("status", "done"))
    structured_output = s.get("structured_output") or s.get("output") or {}

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
        stage=stage,
        state=state,
        structured_output=structured_output,
        skip_reason=s.get("skip_reason"),
        hitl_task_id=s.get("hitl_task_id"),
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
    """Ensure baseline seeded historical cascade traces exist with 5 stages across tiers."""
    # Seed 1: Complete 5-stage cascade for Apollo Pharmacy (Connaught Place)
    cid1 = "casc-seed-01"
    steps1 = [
        CascadeStepDetail(
            tier=5,
            tier_label="Supervisor Orchestrator",
            stage="supervisor",
            state="done",
            agent_name="supervisor_orchestrator",
            node_id="00000000-0000-0000-0000-000000000000",
            node_name="MediFlux Network Orchestrator",
            status="succeeded",
            reasoning="Retail demand trigger received from Apollo Pharmacy POS. Verified cryptographic signature and dispatched cascade workflow across tiers.",
            input={"trigger": "retail_pos_sale", "pharmacy_node_id": "11111111-1111-1111-1111-111111111111"},
            output={"workflow_id": "wf-seed-01", "dispatched_agents": 4},
            model="meta/llama-3.1-70b-instruct",
            provider="groq",
            prompt_tokens=90,
            completion_tokens=42,
            total_tokens=132,
            duration_ms=45.0,
            timestamp="2026-11-16T10:15:00Z",
            entities_created={"workflow_run_id": "wf-seed-01"},
        ),
        CascadeStepDetail(
            tier=4,
            tier_label="Pharmacy Edge Node",
            stage="pharmacy",
            state="done",
            agent_name="pharmacy_node_agent",
            node_id="11111111-1111-1111-1111-111111111111",
            node_name="Apollo Pharmacy - Connaught Place",
            status="succeeded",
            reasoning="Retail POS dispense deducted 1 strip of Paracetamol 500mg. Stock dropped to 8 units (safety buffer 25). Auto-replenishment trigger fired.",
            input={"pharmacy_id": "11111111-1111-1111-1111-111111111111", "product": "Paracetamol 500mg", "qty": 1},
            output={"dispensed": 1, "remaining_stock": 8, "reorder_needed": True, "target_stockist": "Fortis Central Stockist Hub"},
            model="meta/llama-3.1-70b-instruct",
            provider="groq",
            prompt_tokens=142,
            completion_tokens=68,
            total_tokens=210,
            duration_ms=115.4,
            timestamp="2026-11-16T10:15:01Z",
            entities_created={"pos_transaction_id": "pos-init-001", "product": "Paracetamol 500mg"},
        ),
        CascadeStepDetail(
            tier=3,
            tier_label="Stockist Hub",
            stage="stockist",
            state="done",
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
            timestamp="2026-11-16T10:15:02Z",
            entities_created={"order_id": "ord-init-101", "stockist_order": True},
        ),
        CascadeStepDetail(
            tier=2,
            tier_label="Distributor Layer",
            stage="distributor",
            state="done",
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
            timestamp="2026-11-16T10:15:03Z",
            entities_created={"shipment_id": "shp-init-202", "vehicle": "MH-04-RF-8821"},
        ),
        CascadeStepDetail(
            tier=1,
            tier_label="Manufacturer Plant",
            stage="manufacturer",
            state="done",
            agent_name="manufacturer_production_agent",
            node_id="44444444-4444-4444-4444-444444444444",
            node_name="Sun Pharma Formulation Plant - Baddi",
            status="succeeded",
            reasoning="Active ingredient inventory (API Paracetamol) confirmed in store (450 kg available). Scheduled production line Line-A2 slot. Cryptographic block sealed in audit ledger.",
            input={"plant_id": "44444444-4444-4444-4444-444444444444", "product": "Paracetamol 500mg"},
            output={"batch_id": "BAT-PAR-2026-09", "production_line": "Line-A2", "audit_sealed": True},
            model="meta/llama-3.1-70b-instruct",
            provider="groq",
            prompt_tokens=260,
            completion_tokens=110,
            total_tokens=370,
            duration_ms=177.4,
            timestamp="2026-11-16T10:15:04Z",
            entities_created={"production_batch_id": "BAT-PAR-2026-09", "audit_hash": "sha256-sealed-init"},
        ),
    ]

    trace1 = {
        "correlation_id": cid1,
        "product_id": "11111111-2222-3333-4444-555555555555",
        "product_name": "Paracetamol 500mg Strip",
        "sku": "MED-PARA-500",
        "pharmacy_node_id": "11111111-1111-1111-1111-111111111111",
        "pharmacy_name": "Apollo Pharmacy - Connaught Place",
        "created_at": "2026-11-16T10:15:00Z",
        "started_at": "2026-11-16T10:15:00Z",
        "completed_at": "2026-11-16T10:15:04Z",
        "outcome": "complete",
        "status": "completed",
        "steps_completed": 5,
        "total_steps": 5,
        "total_duration_ms": 640.0,
        "total_tokens": 1284,
        "summary": "1 strip sold at Apollo Pharmacy -> Stockist order -> Distributor dispatch -> Manufacturer batch",
        "trigger_event": {
            "product_id": "11111111-2222-3333-4444-555555555555",
            "product_name": "Paracetamol 500mg Strip",
            "sku": "MED-PARA-500",
            "pharmacy_node_id": "11111111-1111-1111-1111-111111111111",
            "pharmacy_name": "Apollo Pharmacy - Connaught Place",
            "quantity": 1,
            "timestamp": "2026-11-16T10:15:00Z",
        },
        "steps": [s.model_dump() for s in steps1],
    }

    _in_memory_cascade_traces[cid1] = trace1
    # Backward compatibility alias
    _in_memory_cascade_traces["casc-init-seed-01"] = dict(trace1, correlation_id="casc-init-seed-01")

    # Seed 2: Waiting Approval (HITL) cascade for Apollo Pharmacy
    cid2 = "casc-seed-02"
    steps2 = [
        CascadeStepDetail(
            tier=5,
            tier_label="Supervisor Orchestrator",
            stage="supervisor",
            state="done",
            agent_name="supervisor_orchestrator",
            node_id="00000000-0000-0000-0000-000000000000",
            node_name="MediFlux Network Orchestrator",
            status="succeeded",
            reasoning="Antibiotic surge detection trigger received. Evaluated regional consumption velocity.",
            duration_ms=40.0,
            total_tokens=120,
            timestamp="2026-11-16T09:40:00Z",
        ),
        CascadeStepDetail(
            tier=4,
            tier_label="Pharmacy Edge Node",
            stage="pharmacy",
            state="done",
            agent_name="pharmacy_node_agent",
            node_id="11111111-1111-1111-1111-111111111111",
            node_name="Apollo Pharmacy - Connaught Place",
            status="succeeded",
            reasoning="Schedule H antibiotic prescription scanned. Stock depleted below critical safety threshold.",
            duration_ms=95.0,
            total_tokens=180,
            timestamp="2026-11-16T09:40:01Z",
        ),
        CascadeStepDetail(
            tier=3,
            tier_label="Stockist Hub",
            stage="stockist",
            state="waiting_approval",
            agent_name="dynamic_balancing_agent",
            node_id="22222222-2222-2222-2222-222222222222",
            node_name="Fortis Central Stockist Hub - Delhi",
            status="waiting_approval",
            hitl_task_id="hitl-seed-02",
            reasoning="Schedule H antibiotic volume exceeds standard autonomous threshold. Pharmacist approval required.",
            duration_ms=185.0,
            total_tokens=280,
            timestamp="2026-11-16T09:40:02Z",
        ),
        CascadeStepDetail(
            tier=2,
            tier_label="Distributor Layer",
            stage="distributor",
            state="pending",
            agent_name="distributor_logistics_agent",
            node_id="33333333-3333-3333-3333-333333333333",
            node_name="MedPlus Regional Depot - West",
            status="pending",
            reasoning="Awaiting upstream stockist HITL approval before dispatch scheduling.",
            duration_ms=0.0,
            total_tokens=0,
            timestamp="2026-11-16T09:40:02Z",
        ),
        CascadeStepDetail(
            tier=1,
            tier_label="Manufacturer Plant",
            stage="manufacturer",
            state="pending",
            agent_name="manufacturer_production_agent",
            node_id="44444444-4444-4444-4444-444444444444",
            node_name="Sun Pharma Formulation Plant - Baddi",
            status="pending",
            reasoning="Awaiting upstream distributor fulfillment.",
            duration_ms=0.0,
            total_tokens=0,
            timestamp="2026-11-16T09:40:02Z",
        ),
    ]

    _in_memory_cascade_traces[cid2] = {
        "correlation_id": cid2,
        "product_id": "22222222-3333-4444-5555-666666666666",
        "product_name": "Amoxicillin 500mg Capsule",
        "sku": "MED-AMOX-500",
        "pharmacy_node_id": "11111111-1111-1111-1111-111111111111",
        "pharmacy_name": "Apollo Pharmacy - Connaught Place",
        "created_at": "2026-11-16T09:40:00Z",
        "started_at": "2026-11-16T09:40:00Z",
        "completed_at": "2026-11-16T09:40:02Z",
        "outcome": "waiting_approval",
        "status": "waiting_approval",
        "steps_completed": 2,
        "total_steps": 5,
        "total_duration_ms": 320.0,
        "total_tokens": 580,
        "summary": "Antibiotic surge detected -> Schedule H compliance approval pending review",
        "trigger_event": {
            "product_id": "22222222-3333-4444-5555-666666666666",
            "product_name": "Amoxicillin 500mg Capsule",
            "sku": "MED-AMOX-500",
            "pharmacy_node_id": "11111111-1111-1111-1111-111111111111",
            "pharmacy_name": "Apollo Pharmacy - Connaught Place",
            "quantity": 2,
            "timestamp": "2026-11-16T09:40:00Z",
        },
        "steps": [s.model_dump() for s in steps2],
    }

    # Seed 3: Partial / lateral rebalance cascade for Wellness Forever (Bandra West - Mumbai)
    cid3 = "casc-seed-03"
    steps3 = [
        CascadeStepDetail(
            tier=5,
            tier_label="Supervisor Orchestrator",
            stage="supervisor",
            state="done",
            agent_name="supervisor_orchestrator",
            node_id="00000000-0000-0000-0000-000000000000",
            node_name="MediFlux Network Orchestrator",
            status="succeeded",
            reasoning="Retail trigger received for Mumbai regional node. Route optimized for lateral stock rebalance.",
            duration_ms=38.0,
            total_tokens=110,
            timestamp="2026-11-16T08:20:00Z",
        ),
        CascadeStepDetail(
            tier=4,
            tier_label="Pharmacy Edge Node",
            stage="pharmacy",
            state="done",
            agent_name="pharmacy_node_agent",
            node_id="11111111-1111-1111-1111-111111111121",
            node_name="Wellness Forever - Bandra West",
            status="succeeded",
            reasoning="Retail POS sale completed. Reorder threshold breached; initiated replenishment request.",
            duration_ms=102.0,
            total_tokens=195,
            timestamp="2026-11-16T08:20:01Z",
        ),
        CascadeStepDetail(
            tier=3,
            tier_label="Stockist Hub",
            stage="stockist",
            state="done",
            agent_name="dynamic_balancing_agent",
            node_id="22222222-2222-2222-2222-222222222231",
            node_name="Mumbai Central Stockist Hub",
            status="succeeded",
            reasoning="Executed lateral rebalance from Andheri depot. No manufacturer order required.",
            duration_ms=155.0,
            total_tokens=290,
            timestamp="2026-11-16T08:20:02Z",
        ),
        CascadeStepDetail(
            tier=2,
            tier_label="Distributor Layer",
            stage="distributor",
            state="done",
            agent_name="distributor_logistics_agent",
            node_id="33333333-3333-3333-3333-333333333341",
            node_name="Western Corridor Logistics Hub",
            status="succeeded",
            reasoning="Dispatched regional transfer cargo van MH-02-AB-1234.",
            duration_ms=145.0,
            total_tokens=240,
            timestamp="2026-11-16T08:20:03Z",
        ),
        CascadeStepDetail(
            tier=1,
            tier_label="Manufacturer Plant",
            stage="manufacturer",
            state="skipped",
            agent_name="manufacturer_production_agent",
            node_id="44444444-4444-4444-4444-444444444444",
            node_name="Sun Pharma Formulation Plant - Baddi",
            status="skipped",
            skip_reason="Lateral stockist rebalance satisfied demand; production run skipped.",
            reasoning="Demand satisfied via lateral transfer; production run scheduled buffer intact.",
            duration_ms=70.0,
            total_tokens=55,
            timestamp="2026-11-16T08:20:04Z",
        ),
    ]

    _in_memory_cascade_traces[cid3] = {
        "correlation_id": cid3,
        "product_id": "33333333-4444-5555-6666-777777777777",
        "product_name": "Azithromycin 500mg Strip",
        "sku": "MED-AZI-500",
        "pharmacy_node_id": "11111111-1111-1111-1111-111111111121",
        "pharmacy_name": "Wellness Forever - Bandra West",
        "created_at": "2026-11-16T08:20:00Z",
        "started_at": "2026-11-16T08:20:00Z",
        "completed_at": "2026-11-16T08:20:04Z",
        "outcome": "partial",
        "status": "partial",
        "steps_completed": 4,
        "total_steps": 5,
        "total_duration_ms": 510.0,
        "total_tokens": 890,
        "summary": "Lateral transfer rebalanced across West region stockists",
        "trigger_event": {
            "product_id": "33333333-4444-5555-6666-777777777777",
            "product_name": "Azithromycin 500mg Strip",
            "sku": "MED-AZI-500",
            "pharmacy_node_id": "11111111-1111-1111-1111-111111111121",
            "pharmacy_name": "Wellness Forever - Bandra West",
            "quantity": 1,
            "timestamp": "2026-11-16T08:20:00Z",
        },
        "steps": [s.model_dump() for s in steps3],
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
    limit: int = Query(25, ge=1, le=100),
    outcome: str | None = Query(default=None, description="Optional outcome filter (complete, partial, waiting_approval)"),
) -> list[CascadeSummaryItem]:
    """List recent demand cascades with summary details for replay selector."""
    _seed_initial_cascades_if_empty()

    summaries: list[CascadeSummaryItem] = []
    # Read from in-memory cascade traces
    for cid, record in reversed(list(_in_memory_cascade_traces.items())):
        trig = record.get("trigger_event") or {}
        prod_id = str(record.get("product_id") or trig.get("product_id") or "11111111-2222-3333-4444-555555555555")
        prod = str(record.get("product_name") or trig.get("product_name") or trig.get("product") or "Paracetamol 500mg Strip")
        sku = str(record.get("sku") or trig.get("sku") or "MED-PARA-500")
        pharm_id = str(record.get("pharmacy_node_id") or trig.get("pharmacy_node_id") or "11111111-1111-1111-1111-111111111111")
        pharm = str(record.get("pharmacy_name") or trig.get("pharmacy_name") or "Apollo Pharmacy - Connaught Place")
        qty = int(trig.get("quantity") or record.get("quantity") or 1)
        steps = record.get("steps") or []
        tot_tok = int(record.get("total_tokens") or sum(s.get("total_tokens", 0) for s in steps))
        tot_dur = float(record.get("total_duration_ms") or sum(s.get("duration_ms", 0.0) for s in steps))

        # Outcome normalization
        raw_outcome = str(record.get("outcome") or record.get("status") or "complete").lower()
        if raw_outcome in ("completed", "succeeded", "complete"):
            norm_outcome = "complete"
        elif "approval" in raw_outcome or raw_outcome == "pending":
            norm_outcome = "waiting_approval"
        elif "partial" in raw_outcome:
            norm_outcome = "partial"
        else:
            norm_outcome = raw_outcome

        # Strict RLS scoping: pharmacy users only see cascades originating from or involving their node
        if current_user.role == "pharmacy" and current_user.node_id:
            user_node = str(current_user.node_id)
            involved_node_ids = {pharm_id}
            for s in steps:
                if isinstance(s, dict) and s.get("node_id"):
                    involved_node_ids.add(str(s["node_id"]))
                elif hasattr(s, "node_id") and s.node_id:
                    involved_node_ids.add(str(s.node_id))
            if user_node not in involved_node_ids:
                continue

        # Filter by outcome if requested
        if outcome:
            o_clean = outcome.strip().lower()
            if norm_outcome != o_clean and raw_outcome != o_clean:
                continue

        created_ts = str(record.get("created_at") or record.get("started_at") or record.get("completed_at") or datetime.now(UTC).isoformat())
        summary_text = str(record.get("summary") or f"{qty} strip sold at {pharm} -> Multi-tier cascade")

        steps_done = int(record.get("steps_completed") or len([s for s in steps if (s.get("state") if isinstance(s, dict) else getattr(s, "state", None)) in ("done", "completed", "succeeded")]) or len(steps))
        total_steps_cnt = int(record.get("total_steps") or len(steps) or 5)

        summaries.append(
            CascadeSummaryItem(
                correlation_id=cid,
                product_id=prod_id,
                product_name=prod,
                sku=sku,
                pharmacy_node_id=pharm_id,
                pharmacy_name=pharm,
                created_at=created_ts,
                timestamp=created_ts,
                outcome=norm_outcome,
                status=str(record.get("status") or "completed"),
                steps_completed=steps_done,
                total_steps=total_steps_cnt,
                tiers_completed=f"{steps_done}/{total_steps_cnt}",
                quantity=qty,
                total_duration_ms=round(tot_dur, 1),
                total_tokens=tot_tok,
                summary=summary_text,
                trigger_summary=f"{qty} Strip {prod} @ {pharm}",
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
