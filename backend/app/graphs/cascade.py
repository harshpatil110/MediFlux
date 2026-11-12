"""Demand cascade LangGraph workflow across 4 supply chain tiers.

Architecture:
Supervisor -> Pharmacy -> Stockist -> Distributor -> Manufacturer -> Finalize

Features:
- Full 4-tier demand cascade propagation triggered by retail POS sales.
- Dynamic supervisor routing with conditional edges (active_tiers).
- Dual telemetry event broadcasting (agent.activity and cascade.updates) per node.
- Partial failure isolation ensuring errors never crash graph or worker.
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.base import BaseAgent
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.events.service import get_in_memory_stock
from app.llm.router import llm_router

logger = logging.getLogger("mediflux.graphs.cascade")

# In-memory store for cascade execution traces
_in_memory_cascade_traces: dict[str, dict[str, Any]] = {}


def get_in_memory_cascade_trace(correlation_id: str) -> dict[str, Any] | None:
    """Retrieve recorded cascade execution trace by correlation ID."""
    return _in_memory_cascade_traces.get(correlation_id)


def clear_cascade_traces() -> None:
    """Clear recorded cascade traces."""
    _in_memory_cascade_traces.clear()


class CascadeState(TypedDict):
    """Execution state schema for multi-tier demand cascade orchestration."""

    event: dict[str, Any]
    correlation_id: str
    pharmacy_id: str
    product_id: str
    batch_id: str
    quantity: int
    active_tiers: list[str]  # e.g. ["pharmacy", "stockist", "distributor", "manufacturer"]
    pharmacy_result: dict[str, Any] | None
    stockist_result: dict[str, Any] | None
    distributor_result: dict[str, Any] | None
    manufacturer_result: dict[str, Any] | None
    hitl_status: dict[str, Any] | None
    trace: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    status: Literal["pending", "completed", "partial", "failed"]


async def _publish_telemetry(
    correlation_id: str,
    tier: str,
    agent_name: str,
    action: str,
    status: str,
    summary: str,
    trace_step: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Publish dual observability events (agent.activity & cascade.updates) to EventBus."""
    # 1. agent.activity
    act_env = EventEnvelope(
        type="agent.activity",
        node_id=tier,
        correlation_id=correlation_id,
        payload={
            "correlation_id": correlation_id,
            "agent_name": agent_name,
            "tier": tier,
            "action": action,
            "status": status,
            **(details or {}),
        },
    )
    await in_process_event_bus.publish("agent.activity", act_env)

    # 2. cascade.updates
    casc_env = EventEnvelope(
        type="cascade.updates",
        node_id=tier,
        correlation_id=correlation_id,
        payload={
            "correlation_id": correlation_id,
            "tier": tier,
            "summary": summary,
            "trace_step": trace_step,
            "status": status,
            **(details or {}),
        },
    )
    await in_process_event_bus.publish("cascade.updates", casc_env)


# -----------------------------------------------------------------------------
# 1. Supervisor Node
# -----------------------------------------------------------------------------
async def supervisor_node(state: CascadeState, router: Any = None) -> dict[str, Any]:
    """Analyze sale event and stock context to decide which tiers need to act."""
    corr_id = state.get("correlation_id", str(uuid.uuid4()))
    trace = list(state.get("trace", []))
    errors = list(state.get("errors", []))
    perf_start = time.perf_counter()
    start_time = datetime.now(UTC).isoformat()

    await _publish_telemetry(
        correlation_id=corr_id,
        tier="supervisor",
        agent_name="supervisor_agent",
        action="started",
        status="running",
        summary="Supervisor evaluating demand cascade routing",
        trace_step="enter",
    )

    # Check context
    pharmacy_id = state.get("pharmacy_id", "")
    product_id = state.get("product_id", "")
    batch_id = state.get("batch_id", "")
    quantity = state.get("quantity", 1)
    current_stock = get_in_memory_stock(pharmacy_id, product_id, batch_id)

    supervisor_agent = BaseAgent(
        name="supervisor_agent",
        graph_name="cascade_graph",
        router=router or llm_router,
        system_prompt=(
            "You are the MediFlux Supply Chain Supervisor. Determine which tiers "
            "must activate in response to this POS retail sale event."
        ),
    )

    try:
        agent_res = await supervisor_agent.run(
            input_data={
                "event": state.get("event"),
                "pharmacy_id": pharmacy_id,
                "product_id": product_id,
                "quantity": quantity,
                "current_stock": current_stock,
            },
            correlation_id=corr_id,
        )

        # Check if agent decision overrides active_tiers
        decision_tiers: list[str] | None = None
        if isinstance(agent_res, dict):
            output = agent_res.get("output") or agent_res.get("output_data") or {}
            if isinstance(output, dict) and "active_tiers" in output and isinstance(output["active_tiers"], list):
                decision_tiers = output["active_tiers"]
            elif "active_tiers" in agent_res and isinstance(agent_res["active_tiers"], list):
                decision_tiers = agent_res["active_tiers"]

        if decision_tiers:
            active_tiers = decision_tiers
        elif "active_tiers" in state and state["active_tiers"]:
            active_tiers = list(state["active_tiers"])
        else:
            # Default full cascade propagation
            active_tiers = ["pharmacy", "stockist", "distributor", "manufacturer"]

        latency_ms = round((time.perf_counter() - perf_start) * 1000, 2)
        trace_step = {
            "tier": "supervisor",
            "agent_name": "supervisor_agent",
            "status": "success",
            "summary": f"Supervisor activated tiers: {active_tiers}",
            "start_time": start_time,
            "end_time": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
        }
        trace.append(trace_step)

        await _publish_telemetry(
            correlation_id=corr_id,
            tier="supervisor",
            agent_name="supervisor_agent",
            action="completed",
            status="success",
            summary=f"Supervisor selected tiers: {active_tiers}",
            trace_step="complete",
            details={"active_tiers": active_tiers},
        )

        return {"active_tiers": active_tiers, "trace": trace, "errors": errors}

    except Exception as exc:
        logger.error("Supervisor node error: %s", exc)
        errors.append({"tier": "supervisor", "error": str(exc)})
        active_tiers = ["pharmacy", "stockist", "distributor", "manufacturer"]
        return {"active_tiers": active_tiers, "trace": trace, "errors": errors, "status": "partial"}


# -----------------------------------------------------------------------------
# 2. Tier Nodes (Pharmacy, Stockist, Distributor, Manufacturer)
# -----------------------------------------------------------------------------
async def pharmacy_node(state: CascadeState, router: Any = None) -> dict[str, Any]:
    """Pharmacy Edge Node: Run PharmacyAgent to evaluate inventory telemetry, compliance, and orders."""
    corr_id = state.get("correlation_id", str(uuid.uuid4()))
    trace = list(state.get("trace", []))
    errors = list(state.get("errors", []))
    perf_start = time.perf_counter()
    start_time = datetime.now(UTC).isoformat()

    await _publish_telemetry(
        correlation_id=corr_id,
        tier="pharmacy",
        agent_name="PharmacyAgent",
        action="started",
        status="running",
        summary="Pharmacy telemetry agent evaluating inventory, returns, and compliance",
        trace_step="enter",
    )

    try:
        from app.agents.pharmacy_agent import PharmacyAgent, persist_replenishment_order

        agent = PharmacyAgent(
            name="PharmacyAgent",
            router=router or llm_router,
        )

        agent_result = await agent.run(
            state=state,
            input_data={
                "event": state.get("event"),
                "pharmacy_id": state.get("pharmacy_id"),
                "product_id": state.get("product_id"),
                "quantity": state.get("quantity"),
                "batch_id": state.get("batch_id"),
                "correlation_id": corr_id,
            },
            correlation_id=corr_id,
        )

        signal = agent_result.signal if hasattr(agent_result, "signal") else None
        needed = agent_result.get("needed", False)
        compliance_hold = agent_result.get("compliance_hold", False)
        target_stockist_id = agent_result.get("target_stockist_id")
        reorder_qty = agent_result.get("quantity", 0)
        urgency = agent_result.get("urgency", "low")
        reason = agent_result.get("reason", "Pharmacy telemetry processed")

        # Database Order Persistence when needed=True and compliance_hold=False
        if needed and not compliance_hold:
            await persist_replenishment_order(
                pharmacy_id=state.get("pharmacy_id") or "11111111-1111-1111-1111-111111111111",
                stockist_id=target_stockist_id,
                product_id=state.get("product_id") or "p-001-azithromycin",
                quantity=reorder_qty,
                priority=urgency,
                correlation_id=corr_id,
                reason=reason,
            )

        latency_ms = round((time.perf_counter() - perf_start) * 1000, 2)
        summary = f"Pharmacy telemetry processed: needed={needed}, compliance_hold={compliance_hold}"

        trace.append({
            "tier": "pharmacy",
            "agent_name": "PharmacyAgent",
            "status": "success",
            "summary": summary,
            "start_time": start_time,
            "end_time": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
        })

        await _publish_telemetry(
            correlation_id=corr_id,
            tier="pharmacy",
            agent_name="PharmacyAgent",
            action="completed",
            status="success",
            summary=summary,
            trace_step="complete",
            details={
                "needed": needed,
                "compliance_hold": compliance_hold,
                "quantity": reorder_qty,
            },
        )

        pharmacy_result_dict = (
            signal.model_dump()
            if signal
            else (agent_result.dict() if hasattr(agent_result, "dict") else dict(agent_result))
        )

        return {
            "pharmacy_result": pharmacy_result_dict,
            "trace": trace,
            "errors": errors,
        }

    except Exception as exc:
        logger.error("Pharmacy node execution error: %s", exc)
        latency_ms = round((time.perf_counter() - perf_start) * 1000, 2)
        errors.append({
            "tier": "pharmacy",
            "error": str(exc),
            "timestamp": datetime.now(UTC).isoformat(),
        })
        trace.append({
            "tier": "pharmacy",
            "agent_name": "PharmacyAgent",
            "status": "failed",
            "summary": f"Error in pharmacy: {exc}",
            "start_time": start_time,
            "end_time": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
        })

        await _publish_telemetry(
            correlation_id=corr_id,
            tier="pharmacy",
            agent_name="PharmacyAgent",
            action="failed",
            status="failed",
            summary=f"Pharmacy execution failed: {exc}",
            trace_step="error",
        )

        return {
            "pharmacy_result": {"status": "failed", "error": str(exc)},
            "trace": trace,
            "errors": errors,
        }


async def stockist_node(state: CascadeState, router: Any = None) -> dict[str, Any]:
    """Stockist Hub Node: Aggregate retail demand and issue restocking replenishment."""
    return await _execute_tier_node(
        tier="stockist",
        state=state,
        router=router,
        summary_template="Stockist hub verified inventory levels and initiated replenishment PO",
    )


async def distributor_node(state: CascadeState, router: Any = None) -> dict[str, Any]:
    """Distributor Layer Node: Allocate regional depot inventory and route logistics dispatch."""
    return await _execute_tier_node(
        tier="distributor",
        state=state,
        router=router,
        summary_template="Distributor depot allocated regional stock and routed fleet shipment",
    )


async def manufacturer_node(state: CascadeState, router: Any = None) -> dict[str, Any]:
    """Manufacturer Plant Node: Ingest demand signal and queue formulation production batch."""
    return await _execute_tier_node(
        tier="manufacturer",
        state=state,
        router=router,
        summary_template="Manufacturer plant ingested demand signal and scheduled production batch",
    )


async def _execute_tier_node(
    tier: str,
    state: CascadeState,
    router: Any = None,
    summary_template: str = "",
) -> dict[str, Any]:
    """Execute a single tier agent wrapper with resilient error boundary."""
    corr_id = state.get("correlation_id", str(uuid.uuid4()))
    trace = list(state.get("trace", []))
    errors = list(state.get("errors", []))
    agent_name = f"{tier}_agent"
    perf_start = time.perf_counter()
    start_time = datetime.now(UTC).isoformat()

    await _publish_telemetry(
        correlation_id=corr_id,
        tier=tier,
        agent_name=agent_name,
        action="started",
        status="running",
        summary=f"{tier.title()} cascade node started",
        trace_step="enter",
    )

    try:
        agent = BaseAgent(
            name=agent_name,
            graph_name="cascade_graph",
            router=router or llm_router,
            system_prompt=f"You are the autonomous {tier.title()} supply chain agent in MediFlux.",
        )

        agent_result = await agent.run(
            input_data={
                "tier": tier,
                "event": state.get("event"),
                "pharmacy_id": state.get("pharmacy_id"),
                "product_id": state.get("product_id"),
                "quantity": state.get("quantity"),
                "correlation_id": corr_id,
            },
            correlation_id=corr_id,
        )

        if agent_result.get("status") == "failed":
            raise RuntimeError(agent_result.get("error_message") or f"{tier.title()} agent execution failed")

        latency_ms = round((time.perf_counter() - perf_start) * 1000, 2)
        summary = summary_template or f"{tier.title()} step completed"
        trace.append({
            "tier": tier,
            "agent_name": agent_name,
            "status": "success",
            "summary": summary,
            "start_time": start_time,
            "end_time": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
        })

        await _publish_telemetry(
            correlation_id=corr_id,
            tier=tier,
            agent_name=agent_name,
            action="completed",
            status="success",
            summary=summary,
            trace_step="complete",
        )

        return {
            f"{tier}_result": agent_result,
            "trace": trace,
            "errors": errors,
        }

    except Exception as exc:
        logger.error("Tier [%s] execution error: %s", tier, exc)
        latency_ms = round((time.perf_counter() - perf_start) * 1000, 2)
        errors.append({
            "tier": tier,
            "error": str(exc),
            "timestamp": datetime.now(UTC).isoformat(),
        })
        trace.append({
            "tier": tier,
            "agent_name": agent_name,
            "status": "failed",
            "summary": f"Error in {tier}: {exc}",
            "start_time": start_time,
            "end_time": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
        })

        await _publish_telemetry(
            correlation_id=corr_id,
            tier=tier,
            agent_name=agent_name,
            action="failed",
            status="failed",
            summary=f"{tier.title()} execution failed: {exc}",
            trace_step="error",
            details={"error": str(exc)},
        )

        # Resilient error isolation: do not crash graph
        return {
            f"{tier}_result": {"error": str(exc)},
            "trace": trace,
            "errors": errors,
            "status": "partial",
        }


# -----------------------------------------------------------------------------
# 3. Finalize Node
# -----------------------------------------------------------------------------
async def finalize_node(state: CascadeState) -> dict[str, Any]:
    """Aggregate multi-tier results, record skipped tiers, and finalize cascade trace."""
    corr_id = state.get("correlation_id", str(uuid.uuid4()))
    trace = list(state.get("trace", []))
    errors = list(state.get("errors", []))
    active_tiers = set(state.get("active_tiers", []))

    # Log skipped tiers explicitly in trace
    all_downstream_tiers = ["stockist", "distributor", "manufacturer"]
    for skipped in all_downstream_tiers:
        if skipped not in active_tiers:
            trace.append({
                "tier": skipped,
                "agent_name": f"{skipped}_agent",
                "status": "skipped",
                "summary": "Skipped by supervisor decision",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "latency_ms": 0.0,
            })
            await _publish_telemetry(
                correlation_id=corr_id,
                tier=skipped,
                agent_name=f"{skipped}_agent",
                action="skipped",
                status="skipped",
                summary=f"{skipped.title()} skipped by supervisor",
                trace_step="skip",
            )

    # Determine final cascade status
    if errors or state.get("status") == "partial":
        final_status: Literal["completed", "partial", "failed"] = "partial"
    elif not active_tiers:
        final_status = "failed"
    else:
        final_status = "completed"

    record = {
        "correlation_id": corr_id,
        "status": final_status,
        "event": state.get("event", {}),
        "steps": trace,
        "errors": errors,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    _in_memory_cascade_traces[corr_id] = record

    await _publish_telemetry(
        correlation_id=corr_id,
        tier="finalize",
        agent_name="finalize_node",
        action="completed",
        status=final_status,
        summary=f"Cascade {final_status} for correlation_id={corr_id}",
        trace_step="finalize",
    )

    return {"status": final_status, "trace": trace, "errors": errors}


# -----------------------------------------------------------------------------
# 4. Graph Construction & Conditional Routing
# -----------------------------------------------------------------------------
def build_cascade_graph(
    checkpointer: Any = None,
    supervisor_router: Any = None,
    pharmacy_router: Any = None,
    stockist_router: Any = None,
    distributor_router: Any = None,
    manufacturer_router: Any = None,
) -> CompiledStateGraph:
    """Build and compile the multi-tier cascade StateGraph with conditional supervisor edges."""
    builder = StateGraph(CascadeState)

    # Add Nodes with async wrappers to preserve coroutine awaiting
    async def _sup(s: CascadeState) -> dict[str, Any]:
        return await supervisor_node(s, router=supervisor_router)

    async def _pharm(s: CascadeState) -> dict[str, Any]:
        return await pharmacy_node(s, router=pharmacy_router)

    async def _stk(s: CascadeState) -> dict[str, Any]:
        return await stockist_node(s, router=stockist_router)

    async def _dist(s: CascadeState) -> dict[str, Any]:
        return await distributor_node(s, router=distributor_router)

    async def _mfg(s: CascadeState) -> dict[str, Any]:
        return await manufacturer_node(s, router=manufacturer_router)

    builder.add_node("supervisor", _sup)
    builder.add_node("pharmacy", _pharm)
    builder.add_node("stockist", _stk)
    builder.add_node("distributor", _dist)
    builder.add_node("manufacturer", _mfg)
    builder.add_node("finalize", finalize_node)

    # Entry edge
    builder.set_entry_point("supervisor")
    builder.add_edge("supervisor", "pharmacy")

    # Conditional Routing Edges
    def _route_from_pharmacy(s: CascadeState) -> str:
        return "stockist" if "stockist" in s.get("active_tiers", []) else "finalize"

    def _route_from_stockist(s: CascadeState) -> str:
        return "distributor" if "distributor" in s.get("active_tiers", []) else "finalize"

    def _route_from_distributor(s: CascadeState) -> str:
        return "manufacturer" if "manufacturer" in s.get("active_tiers", []) else "finalize"

    builder.add_conditional_edges("pharmacy", _route_from_pharmacy)
    builder.add_conditional_edges("stockist", _route_from_stockist)
    builder.add_conditional_edges("distributor", _route_from_distributor)
    builder.add_edge("manufacturer", "finalize")
    builder.add_edge("finalize", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


# Singleton compiled cascade graph
cascade_graph = build_cascade_graph()
