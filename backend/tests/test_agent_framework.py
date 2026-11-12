"""Unit and integration tests for Task 7: Agent Framework, Tool Registry, Traces, and HITL."""

import uuid
from pathlib import Path

import pytest
from langgraph.types import Command

from app.agents.base import (
    BaseAgent,
    FinalAnswerAction,
    ToolCallAction,
    clear_agent_runs,
    get_in_memory_agent_runs,
)
from app.agents.graph import build_hitl_workflow_graph, build_single_agent_graph
from app.agents.hitl import clear_hitl_tasks, get_hitl_task
from app.agents.testing import FakeLLM
from app.agents.tools.registry import get_agent_tools
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope


@pytest.fixture(autouse=True)
def clean_test_environment() -> None:
    """Reset traces, events, and HITL tasks before and after each test."""
    from unittest.mock import patch

    from app.core.config import settings

    clear_agent_runs()
    clear_hitl_tasks()
    in_process_event_bus.clear()
    with patch.object(settings, "SUPABASE_URL", ""):
        yield
    clear_agent_runs()
    clear_hitl_tasks()
    in_process_event_bus.clear()


# -----------------------------------------------------------------------------
# 1. Tool Calling Agent Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tool_calling_agent_execution_and_telemetry() -> None:
    """Verify agent executes tool_call, feeds result back, emits final_answer, and writes agent_runs."""
    node_id = "11111111-1111-1111-1111-111111111111"
    correlation_id = str(uuid.uuid4())

    # Pre-script FakeLLM decisions:
    # 1. Call tool get_inventory
    # 2. Return final answer using tool result
    fake_llm = FakeLLM([
        ToolCallAction(
            action_type="tool_call",
            tool_name="get_inventory",
            tool_args={"node_id": node_id},
        ),
        FinalAnswerAction(
            action_type="final_answer",
            content={"status": "stock_verified", "available_stock": 100},
        ),
    ])

    agent = BaseAgent(
        name="inventory_agent",
        allowed_tools=["get_inventory"],
        max_steps=5,
        router=fake_llm,
    )

    state = {
        "correlation_id": correlation_id,
        "node_id": node_id,
        "messages": [{"role": "user", "content": "Check stock balance for Delhi node"}],
    }

    # Listen on agent.activity topic
    activity_events: list[EventEnvelope] = []
    in_process_event_bus.register_listener("agent.activity", lambda evt: activity_events.append(evt))

    result = await agent.run(state)

    assert result["status"] == "success"
    assert result["output"]["status"] == "stock_verified"
    assert result["output"]["available_stock"] == 100
    assert result["steps"] == 2

    # Verify agent_runs record was written
    recorded_runs = get_in_memory_agent_runs()
    assert len(recorded_runs) == 1
    run = recorded_runs[0]
    assert run["agent_name"] == "inventory_agent"
    assert run["status"] == "success"
    assert run["correlation_id"] == correlation_id
    assert run["tokens_in"] > 0
    assert run["tokens_out"] > 0
    assert run["duration_ms"] >= 0

    # Verify event bus received agent.activity event
    assert len(activity_events) == 1
    assert activity_events[0].type == "agent.activity"
    assert activity_events[0].correlation_id == correlation_id
    assert activity_events[0].payload["agent_name"] == "inventory_agent"


# -----------------------------------------------------------------------------
# 2. Max Steps Enforcement Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_max_steps_halts_infinite_loop() -> None:
    """Verify that when an agent gets stuck calling tools indefinitely, max_steps halts execution."""
    # Pre-script FakeLLM with continuous tool calls
    infinite_tool_calls = [
        ToolCallAction(
            action_type="tool_call",
            tool_name="get_inventory",
            tool_args={"node_id": "11111111-1111-1111-1111-111111111111"},
        )
        for _ in range(10)
    ]
    fake_llm = FakeLLM(infinite_tool_calls)

    max_steps = 2
    agent = BaseAgent(
        name="looping_agent",
        allowed_tools=["get_inventory"],
        max_steps=max_steps,
        router=fake_llm,
    )

    state = {
        "correlation_id": "test-loop-corr",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "messages": [{"role": "user", "content": "Keep checking"}],
    }

    result = await agent.run(state)

    # Agent should halt precisely at max_steps (2 steps)
    assert result["steps"] == max_steps
    assert "max_steps (2) exceeded" in str(result["output"].get("warning", ""))

    recorded_runs = get_in_memory_agent_runs()
    assert len(recorded_runs) == 1
    assert recorded_runs[0]["agent_name"] == "looping_agent"


# -----------------------------------------------------------------------------
# 3. Tool Scoping & Unauthorized Tool Call Rejection
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_tool_call_is_rejected() -> None:
    """Verify that attempting to call a tool not in allowed_tools is rejected."""
    fake_llm = FakeLLM([
        ToolCallAction(
            action_type="tool_call",
            tool_name="unauthorized_secret_tool",
            tool_args={},
        ),
        FinalAnswerAction(
            action_type="final_answer",
            content={"status": "handled_rejection"},
        ),
    ])

    agent = BaseAgent(
        name="scoped_agent",
        allowed_tools=["get_inventory"],  # "unauthorized_secret_tool" not allowed
        max_steps=3,
        router=fake_llm,
    )

    result = await agent.run({
        "correlation_id": "corr-scoping",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "messages": [{"role": "user", "content": "Try unauthorized tool"}],
    })

    assert result["status"] == "success"
    # Agent should have handled rejection and completed in 2 steps
    assert result["steps"] == 2


def test_tool_metadata_scoping() -> None:
    """Verify get_agent_tools returns only permitted tools."""
    schemas = get_agent_tools(["get_inventory", "get_node"])
    names = [s["name"] for s in schemas]
    assert "get_inventory" in names
    assert "get_node" in names
    assert "run_module" not in names


# -----------------------------------------------------------------------------
# 4. LangGraph SQLite Checkpointer & HITL Interrupt / Resume Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hitl_interrupt_and_resume_across_process_restart(tmp_path: Path) -> None:
    """Verify graph execution pauses at request_human_approval and resumes after process restart."""
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    db_file = tmp_path / "test_checkpoints.db"
    thread_id = f"thread-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    hitl_events: list[EventEnvelope] = []
    in_process_event_bus.register_listener("hitl", lambda evt: hitl_events.append(evt))

    initial_state = {
        "correlation_id": "corr-hitl-01",
        "trace_id": "trace-01",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "user-01",
        "messages": [],
        "current_agent": "stockist_order_agent",
        "next_step": "propose",
        "data": {"medicine_id": "MED-AZI-500", "requested_quantity": 250},
        "hitl_pending": False,
        "hitl_task_id": None,
    }

    # Phase 1: Initial Run -> Triggers HITL interrupt and pauses
    async with aiosqlite.connect(str(db_file)) as conn1:
        saver1 = AsyncSqliteSaver(conn1)
        await saver1.setup()
        graph1 = build_hitl_workflow_graph(checkpointer=saver1)

        # Execute graph until interrupt
        await graph1.ainvoke(initial_state, config=config)

        # Verify graph is paused at 'propose_action'
        snapshot1 = await graph1.aget_state(config)
        assert snapshot1.next == ("propose_action",)
        assert len(snapshot1.interrupts) > 0
        interrupt_val = snapshot1.interrupts[0].value
        assert interrupt_val.get("hitl_pending") is True

        # Verify HITL task was recorded and event broadcast
        task_id = interrupt_val.get("task_id")
        assert task_id is not None
        recorded_task = get_hitl_task(task_id)
        assert recorded_task is not None
        assert recorded_task["step_name"] == "reorder_approval"
        assert recorded_task["task_data"]["risk_level"] == "high"

        assert len(hitl_events) == 1
        assert hitl_events[0].type == "hitl"
        assert hitl_events[0].payload["task_id"] == task_id

    # Connection conn1 is closed (process exit)

    # -------------------------------------------------------------------------
    # Phase 2: Process Restart -> Reload state from SQLite and resume execution
    # -------------------------------------------------------------------------
    async with aiosqlite.connect(str(db_file)) as conn2:
        saver2 = AsyncSqliteSaver(conn2)
        graph2 = build_hitl_workflow_graph(checkpointer=saver2)

        # Verify snapshot restored from disk
        restored_snapshot = await graph2.aget_state(config)
        assert restored_snapshot.next == ("propose_action",)

        # Resume graph with human approval decision
        resume_payload = {"approved": True, "notes": "Approved by senior pharmacist"}
        final_state = await graph2.ainvoke(Command(resume=resume_payload), config=config)

        # Verify execution finished successfully
        assert final_state["data"]["final_execution_status"] == "approved_and_executed"
        assert final_state["data"]["approval_result"]["approved"] is True

        # Verify snapshot now completed (no next steps)
        final_snapshot = await graph2.aget_state(config)
        assert final_snapshot.next == ()


# -----------------------------------------------------------------------------
# 5. Single Agent Graph Compilation & Execution
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_agent_graph_compilation() -> None:
    """Verify build_single_agent_graph integrates BaseAgent and compiles cleanly."""
    fake_llm = FakeLLM([
        FinalAnswerAction(
            action_type="final_answer",
            content={"analysis": "All pharmacy inventory levels healthy"},
        )
    ])

    agent = BaseAgent(name="health_check_agent", router=fake_llm)
    graph = build_single_agent_graph(agent)

    state = {
        "correlation_id": "corr-single-graph",
        "trace_id": "trace-single-graph",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "u-01",
        "messages": [{"role": "user", "content": "Analyze node"}],
        "current_agent": "health_check_agent",
        "next_step": "init",
        "data": {},
        "hitl_pending": False,
        "hitl_task_id": None,
    }

    result = await graph.ainvoke(state)
    assert result["next_step"] == "completed"
    assert result["data"]["analysis"] == "All pharmacy inventory levels healthy"
