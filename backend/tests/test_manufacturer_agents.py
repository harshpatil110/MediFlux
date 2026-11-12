"""Unit and integration tests for Manufacturer Tier agents (DemandSynthesisAgent, JITSchedulerAgent).

Covers:
1. Burst simulation producing sustained_surge trend, higher forecast_qty, and schedule changes.
2. Isolated single-store spike classified as one_off_spike noise (is_noise=True, 0 actions).
3. API inventory deficit handling and batch rejection / capping.
4. Active in-progress batch modification triggering HITL pause and task creation without unapproved commit.
5. End-to-end demand cascade execution through manufacturer tier.
6. Cascade execution pausing with status="waiting_hitl" upon in-progress batch modification.
"""

import uuid
from unittest.mock import patch

import pytest

from app.agents.demand_synthesis_agent import DemandSignal, DemandSynthesisAgent
from app.agents.hitl import clear_hitl_tasks, get_in_memory_hitl_tasks
from app.agents.scheduler_agent import JITSchedulerAgent, ScheduleChange
from app.core.config import settings
from app.graphs.cascade import CascadeState, build_cascade_graph
from app.tools.manufacturer_tools import (
    clear_in_memory_demand_signals,
    clear_in_memory_production_batches,
    clear_mock_api_inventory,
    clear_mock_events_window,
    clear_mock_production_schedule,
    get_in_memory_production_batches,
    set_mock_api_inventory,
    set_mock_events_window,
    set_mock_production_schedule,
)


@pytest.fixture(autouse=True)
def setup_manufacturer_environment():
    """Ensure tests run purely offline in isolated test fixtures."""
    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "NVIDIA_API_KEY", None), \
         patch.object(settings, "OPENROUTER_API_KEY", None), \
         patch.object(settings, "OLLAMA_BASE_URL", ""):
        clear_in_memory_demand_signals()
        clear_in_memory_production_batches()
        clear_mock_events_window()
        clear_mock_production_schedule()
        clear_mock_api_inventory()
        clear_hitl_tasks()
        yield
        clear_in_memory_demand_signals()
        clear_in_memory_production_batches()
        clear_mock_events_window()
        clear_mock_production_schedule()
        clear_mock_api_inventory()
        clear_hitl_tasks()


@pytest.mark.asyncio
async def test_burst_demand_synthesis():
    """Verify high-volume demand across multiple stockists synthesizes a sustained_surge signal and schedules batches."""
    product_id = "p-001-azithromycin"

    # Simulate multi-node demand surge across 3 distinct nodes
    events = [
        {"node_id": "pharmacy-01", "product_id": product_id, "quantity": 15, "baseline_rate": 2.0},
        {"node_id": "pharmacy-02", "product_id": product_id, "quantity": 25, "baseline_rate": 2.0},
        {"node_id": "pharmacy-03", "product_id": product_id, "quantity": 30, "baseline_rate": 2.0},
    ]
    set_mock_events_window(events)
    set_mock_api_inventory(product_id, {"available_kg": 200.0, "safety_threshold_kg": 5.0})

    synthesis_agent = DemandSynthesisAgent()
    state = {
        "product_id": product_id,
        "region": "north-delhi-ncr",
        "is_burst": True,
        "correlation_id": "corr-burst-001",
    }

    signal: DemandSignal = await synthesis_agent.evaluate_demand(state)
    assert signal.trend == "sustained_surge"
    assert signal.is_noise is False
    assert signal.forecast_qty >= 1000
    assert signal.confidence > 0.85

    # Run scheduler with this signal
    scheduler_agent = JITSchedulerAgent()
    schedule_state = {
        "product_id": product_id,
        "demand_signal": signal.model_dump(),
        "correlation_id": "corr-burst-001",
    }
    change: ScheduleChange = await scheduler_agent.evaluate_schedule(schedule_state)
    assert len(change.actions) >= 1
    assert change.actions[0].action_type == "add_batch"
    assert change.actions[0].quantity == signal.forecast_qty
    assert change.modifies_in_progress is False
    assert change.requires_hitl is False

    # Verify atomic DB persistence
    batches = get_in_memory_production_batches()
    assert len(batches) == 1
    assert batches[0]["quantity"] == signal.forecast_qty


@pytest.mark.asyncio
async def test_one_off_spike_noise_classification():
    """Verify an isolated single-store demand spike is classified as noise and yields 0 scheduler actions."""
    product_id = "p-001-azithromycin"

    # Single isolated node spike
    events = [
        {"node_id": "pharmacy-isolated-01", "product_id": product_id, "quantity": 50, "baseline_rate": 1.0},
    ]
    set_mock_events_window(events)

    synthesis_agent = DemandSynthesisAgent()
    state = {
        "product_id": product_id,
        "region": "north-delhi-ncr",
        "is_isolated_spike": True,
        "correlation_id": "corr-spike-noise-001",
    }

    signal: DemandSignal = await synthesis_agent.evaluate_demand(state)
    assert signal.trend == "one_off_spike"
    assert signal.is_noise is True
    assert signal.forecast_qty == 0

    # Scheduler must discard noise and perform 0 production actions
    scheduler_agent = JITSchedulerAgent()
    schedule_state = {
        "product_id": product_id,
        "demand_signal": signal.model_dump(),
        "correlation_id": "corr-spike-noise-001",
    }
    change: ScheduleChange = await scheduler_agent.evaluate_schedule(schedule_state)
    assert len(change.actions) == 0
    assert "noise" in change.reasoning.lower()
    assert change.modifies_in_progress is False


@pytest.mark.asyncio
async def test_api_inventory_exceeded_rejection():
    """Verify formulation change is rejected when required API raw stock exceeds available inventory."""
    product_id = "p-paracetamol-deficit"

    # Set API inventory to 5.0 kg (insufficient for 1000 units requiring 20 kg API @ 0.02 kg/unit)
    set_mock_api_inventory(
        product_id,
        {
            "available_kg": 5.0,
            "safety_threshold_kg": 5.0,
            "api_name": "Paracetamol-API",
        },
    )

    scheduler_agent = JITSchedulerAgent()
    schedule_state = {
        "product_id": product_id,
        "forecast_qty": 1000,
        "demand_signal": {
            "product_id": product_id,
            "trend": "sustained_surge",
            "forecast_qty": 1000,
            "is_noise": False,
        },
        "correlation_id": "corr-api-deficit-001",
    }

    change: ScheduleChange = await scheduler_agent.evaluate_schedule(schedule_state)
    assert len(change.actions) == 0
    assert "API inventory deficit" in change.reasoning
    assert change.requires_hitl is True

    # Confirm no batch was committed
    batches = get_in_memory_production_batches()
    assert len(batches) == 0


@pytest.mark.asyncio
async def test_in_progress_batch_modification_hitl_guard():
    """Verify that modifying an active 'in_progress' batch creates a HITL task and halts unapproved DB commit."""
    product_id = "p-epinephrine"
    corr_id = "corr-hitl-in-progress-001"

    # Set up production schedule with an active 'in_progress' batch
    active_batch = {
        "id": "batch-active-prog-101",
        "line_id": "line-sterile-01",
        "product_id": product_id,
        "batch_number": "BATCH-EPI-001",
        "quantity": 500,
        "status": "in_progress",
    }
    set_mock_production_schedule([active_batch])
    set_mock_api_inventory(product_id, {"available_kg": 100.0, "safety_threshold_kg": 5.0})

    scheduler_agent = JITSchedulerAgent()
    schedule_state = {
        "product_id": product_id,
        "modify_in_progress": True,
        "forecast_qty": 1500,
        "demand_signal": {
            "product_id": product_id,
            "trend": "sustained_surge",
            "forecast_qty": 1500,
            "is_noise": False,
        },
        "correlation_id": corr_id,
    }

    change: ScheduleChange = await scheduler_agent.evaluate_schedule(schedule_state)
    assert change.modifies_in_progress is True
    assert change.requires_hitl is True
    assert len(change.actions) == 1
    assert change.actions[0].is_in_progress is True
    assert change.actions[0].action_type == "resize_batch"

    # Verify a HITL task was recorded in hitl_tasks
    hitl_tasks = get_in_memory_hitl_tasks()
    assert len(hitl_tasks) >= 1
    matching_task = next(t for t in hitl_tasks if t.get("correlation_id") == corr_id)
    assert matching_task["action_type"] == "approve_in_progress_batch_change"
    assert matching_task["status"] == "pending"

    # Confirm batch was NOT committed to production_batches pending approval
    batches = get_in_memory_production_batches()
    assert len(batches) == 0


@pytest.mark.asyncio
async def test_cascade_manufacturer_integration():
    """Verify full 4-tier demand cascade execution reaches manufacturer node and populates demand_signal."""
    graph = build_cascade_graph()
    corr_id = f"test-corr-mfg-cascade-{uuid.uuid4().hex[:6]}"
    product_id = "p-001-azithromycin"

    set_mock_api_inventory(product_id, {"available_kg": 500.0, "safety_threshold_kg": 5.0})

    initial_state: CascadeState = {
        "event": {"source": "pos", "quantity": 10},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": product_id,
        "batch_id": "b-azi-2026-01",
        "quantity": 10,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "pharmacy_result": None,
        "stockist_result": None,
        "settlement_result": None,
        "distributor_result": None,
        "demand_signal": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    assert result["status"] == "completed"
    assert result["demand_signal"] is not None
    assert "trend" in result["demand_signal"]
    assert result["manufacturer_result"] is not None
    assert "actions" in result["manufacturer_result"]


@pytest.mark.asyncio
async def test_cascade_manufacturer_hitl_pause():
    """Verify cascade execution pauses with status='waiting_hitl' when an in-progress batch modification occurs."""
    graph = build_cascade_graph()
    corr_id = f"test-corr-mfg-hitl-{uuid.uuid4().hex[:6]}"
    product_id = "p-insulin-in-progress"

    set_mock_api_inventory(product_id, {"available_kg": 200.0, "safety_threshold_kg": 5.0})
    set_mock_production_schedule([{
        "id": "batch-prog-active-01",
        "line_id": "line-cold-01",
        "product_id": product_id,
        "status": "in_progress",
    }])

    initial_state: CascadeState = {
        "event": {"source": "pos", "quantity": 25},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": product_id,
        "batch_id": "b-ins-2026-01",
        "quantity": 25,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "modify_in_progress": True,
        "is_burst": True,
        "pharmacy_result": None,
        "stockist_result": None,
        "settlement_result": None,
        "distributor_result": None,
        "demand_signal": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    # Must yield back status 'waiting_hitl'
    assert result["status"] == "waiting_hitl"
    assert result["manufacturer_result"]["modifies_in_progress"] is True
    assert result["manufacturer_result"]["requires_hitl"] is True
