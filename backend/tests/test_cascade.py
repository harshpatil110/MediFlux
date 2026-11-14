"""Integration tests for Task 10: Cascade Graph Vertical Slice, Supervisor Routing, and Worker."""

import asyncio
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.base import (
    FinalAnswerAction,
    clear_agent_runs,
    get_in_memory_agent_runs,
)
from app.agents.testing import FakeLLM
from app.core.config import settings
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.graphs.cascade import (
    CascadeState,
    build_cascade_graph,
    cascade_graph,
    clear_cascade_traces,
    get_in_memory_cascade_trace,
)
from app.main import app
from app.workers.cascade_worker import CascadeWorker


@pytest.fixture(autouse=True)
def mock_supabase_offline():
    """Ensure tests run purely offline in test isolation."""
    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "NVIDIA_API_KEY", None), \
         patch.object(settings, "OPENROUTER_API_KEY", None), \
         patch.object(settings, "OLLAMA_BASE_URL", ""):
        clear_agent_runs()
        clear_cascade_traces()
        yield
        clear_agent_runs()
        clear_cascade_traces()


@pytest.mark.asyncio
async def test_full_4_tier_cascade_propagation():
    """Test full 4-tier demand cascade propagation from Pharmacy through Manufacturer."""
    corr_id = "test-corr-4-tier-001"
    initial_state: CascadeState = {
        "event": {"source": "pos", "receipt_id": "REC-001"},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 2,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "pharmacy_result": None,
        "stockist_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await cascade_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    assert result["status"] == "completed"
    assert result["pharmacy_result"] is not None
    assert result["stockist_result"] is not None
    assert result["distributor_result"] is not None
    assert result["manufacturer_result"] is not None

    # Verify execution trace in graph state and in-memory trace
    assert len(result["trace"]) >= 5
    saved_trace = get_in_memory_cascade_trace(corr_id)
    assert saved_trace is not None
    assert saved_trace["status"] == "completed"

    # Verify agent_runs contains traces for all tiers under this correlation_id
    runs = [r for r in get_in_memory_agent_runs() if r.get("correlation_id") == corr_id]
    assert len(runs) >= 4
    agent_names = {r["agent_name"] for r in runs}
    assert "pharmacy_agent" in agent_names
    assert "stockist_agent" in agent_names
    assert "distributor_agent" in agent_names
    assert "manufacturer_agent" in agent_names


@pytest.mark.asyncio
async def test_supervisor_conditional_skipping():
    """Test that Supervisor selecting active_tiers=['pharmacy'] skips downstream tiers with explicit skip reason."""
    corr_id = "test-corr-supervisor-skip-002"

    # Script FakeLLM to make supervisor choose only pharmacy tier
    fake_supervisor = FakeLLM()
    fake_supervisor.queue_response(
        FinalAnswerAction(content={"active_tiers": ["pharmacy"], "reason": "Sufficient buffer stock"})
    )

    custom_graph = build_cascade_graph(supervisor_router=fake_supervisor)

    initial_state: CascadeState = {
        "event": {"source": "pos"},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 1,
        "active_tiers": [],
        "pharmacy_result": None,
        "stockist_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await custom_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    assert result["active_tiers"] == ["pharmacy"]
    assert result["pharmacy_result"] is not None
    assert result["stockist_result"] is None
    assert result["distributor_result"] is None
    assert result["manufacturer_result"] is None

    # Check that skipped tiers are explicitly logged in trace
    skipped_steps = [s for s in result["trace"] if s.get("status") == "skipped"]
    assert len(skipped_steps) == 3
    skipped_tiers = {s["tier"] for s in skipped_steps}
    assert skipped_tiers == {"stockist", "distributor", "manufacturer"}
    for step in skipped_steps:
        assert "Skipped by supervisor" in step["summary"]


@pytest.mark.asyncio
async def test_partial_failure_isolation():
    """Test that a failure in one tier isolates cleanly as status='partial' without crashing the graph."""
    corr_id = "test-corr-partial-failure-003"

    # Script distributor node to fail
    class FailingRouter:
        async def complete(self, *args, **kwargs):
            raise RuntimeError("Regional depot network connectivity timeout")

    custom_graph = build_cascade_graph(distributor_router=FailingRouter())

    initial_state: CascadeState = {
        "event": {"source": "pos"},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 1,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "pharmacy_result": None,
        "stockist_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await custom_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    # Must complete with status 'partial' or 'partial_failure'
    assert result["status"] in ("partial", "partial_failure")
    assert len(result["errors"]) >= 1
    assert result["errors"][0]["tier"] == "distributor"
    assert "Regional depot network" in result["errors"][0]["error"]
    assert result["pharmacy_result"] is not None
    assert result["stockist_result"] is not None

    # Saved trace also records partial / partial_failure status
    saved = get_in_memory_cascade_trace(corr_id)
    assert saved is not None
    assert saved["status"] in ("partial", "partial_failure")


@pytest.mark.asyncio
async def test_sse_stream_sequence_cascade_updates():
    """Verify that chronological cascade update events are broadcast on cascade.updates topic."""
    corr_id = "test-corr-sse-004"
    received_updates: list[EventEnvelope] = []

    def _listener(env: EventEnvelope) -> None:
        if env.correlation_id == corr_id:
            received_updates.append(env)

    in_process_event_bus.register_listener("cascade.updates", _listener)

    initial_state: CascadeState = {
        "event": {"source": "pos"},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 1,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "pharmacy_result": None,
        "stockist_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    await cascade_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    # We expect updates across all tiers
    assert len(received_updates) >= 5
    tiers_received = [u.payload.get("tier") for u in received_updates]
    assert "supervisor" in tiers_received
    assert "pharmacy" in tiers_received
    assert "stockist" in tiers_received
    assert "distributor" in tiers_received
    assert "manufacturer" in tiers_received


@pytest.mark.asyncio
async def test_cascade_worker_per_event_mode():
    """Verify CascadeWorker subscribes to pos.sales and executes cascade graph automatically."""
    worker = CascadeWorker()
    await worker.start()

    corr_id = "test-corr-worker-005"
    sale_envelope = EventEnvelope(
        type="pos.sales",
        node_id="11111111-1111-1111-1111-111111111111",
        correlation_id=corr_id,
        payload={
            "pharmacy_id": "11111111-1111-1111-1111-111111111111",
            "product_id": "p-001-azithromycin",
            "batch_id": "b-azi-2026-01",
            "quantity": 2,
        },
    )

    try:
        await in_process_event_bus.publish("pos.sales", sale_envelope)

        # Allow brief moment for background execution
        for _ in range(20):
            await asyncio.sleep(0.05)
            trace = get_in_memory_cascade_trace(corr_id)
            if trace and trace.get("status") == "completed":
                break

        trace = get_in_memory_cascade_trace(corr_id)
        assert trace is not None
        assert trace["status"] == "completed"
        assert len(trace["steps"]) >= 4
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_cascade_trace_api_endpoint():
    """Verify GET /api/v1/cascade/{correlation_id} returns structured execution trace."""
    corr_id = "test-corr-api-006"

    # Pre-populate cascade execution
    initial_state: CascadeState = {
        "event": {"source": "pos", "units": 5},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 5,
        "active_tiers": ["pharmacy", "stockist"],
        "pharmacy_result": None,
        "stockist_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }
    await cascade_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    headers = {"Authorization": "Bearer mock-pharmacist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Existing trace query
        resp = await client.get(f"/api/v1/cascade/{corr_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["correlation_id"] == corr_id
        assert data["status"] == "completed"
        assert len(data["steps"]) >= 2

        # 2. Non-existent trace query returns 404
        resp_404 = await client.get("/api/v1/cascade/non-existent-uuid-999", headers=headers)
        assert resp_404.status_code == 404
        assert resp_404.json()["error"]["code"] == "NOT_FOUND"

