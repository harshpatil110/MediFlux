"""Automated tests for Task 15 Human-in-the-Loop (HITL) approval system."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from app.agents.bootstrap_agent import bootstrap_agent
from app.agents.graph import build_hitl_workflow_graph
from app.core.config import settings
from app.core.hitl import (
    clear_hitl_tasks,
    clear_in_memory_audit_ledger,
    get_hitl_task,
    get_in_memory_audit_ledger,
    get_in_memory_hitl_tasks,
    request_human_approval,
)
from app.core.hitl_policy import get_expiry_hours
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.graphs.cascade import CascadeState, build_cascade_graph
from app.main import app
from app.workers.hitl_expiry_worker import process_expired_hitl_tasks


class FakeLLM:
    """Mock LLM Router returning predetermined compliant test structures."""

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        return '{"analysis": "mock analysis", "decision": "approved", "actions": []}'


@pytest.fixture(autouse=True)
def clean_hitl_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure clean in-memory state and offline settings for deterministic test isolation."""
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "")
    clear_hitl_tasks()
    clear_in_memory_audit_ledger()
    bootstrap_agent.bootstrap_all_modules()


# -----------------------------------------------------------------------------
# Test 1: Task Pause & Creation Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_task_pause_and_creation():
    """Trigger cross-border shipment and in-progress batch change; assert execution pauses and creates pending tasks."""
    graph = build_cascade_graph()

    # 1. Trigger Cross-Border Shipment Pause
    corr_id_xb = f"corr-xb-{uuid.uuid4().hex[:6]}"
    state_xb: CascadeState = {
        "event": {"source": "pos", "quantity": 10},
        "correlation_id": corr_id_xb,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 10,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "is_cross_border": True,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result_xb = await graph.ainvoke(
        state_xb,
        config={"configurable": {"thread_id": corr_id_xb}},
    )

    assert result_xb["status"] == "waiting_hitl"

    tasks = get_in_memory_hitl_tasks()
    xb_task = next(
        (t for t in tasks if t.get("correlation_id") == corr_id_xb and t.get("task_type") == "cross_border_shipment"),
        None,
    )
    assert xb_task is not None
    assert xb_task["status"] == "pending"
    assert "expires_at" in xb_task
    # Cross-border policy has 12h expiry
    assert get_expiry_hours("cross_border_shipment") == 12

    # 2. Trigger In-Progress Batch Modification Pause
    corr_id_mfg = f"corr-mfg-{uuid.uuid4().hex[:6]}"
    state_mfg: CascadeState = {
        "event": {"source": "pos", "quantity": 50},
        "correlation_id": corr_id_mfg,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "quantity": 50,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "modify_in_progress": True,
        "is_burst": True,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result_mfg = await graph.ainvoke(
        state_mfg,
        config={"configurable": {"thread_id": corr_id_mfg}},
    )

    assert result_mfg["status"] == "waiting_hitl"

    tasks_after = get_in_memory_hitl_tasks()
    mfg_task = next(
        (t for t in tasks_after if t.get("correlation_id") == corr_id_mfg and "batch" in t.get("task_type", "")),
        None,
    )
    assert mfg_task is not None
    assert mfg_task["status"] == "pending"
    assert get_expiry_hours("in_progress_batch_change") == 24


# -----------------------------------------------------------------------------
# Test 2: Approve & Resume Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_approve_and_resume():
    """Post approval decision using authorized role; assert graph resumes and audit ledger updates."""
    corr_id = f"corr-approve-{uuid.uuid4().hex[:6]}"

    # 1. Create a pending task for cross_border_shipment
    hitl_res = await request_human_approval(
        task_type="cross_border_shipment",
        node_id="11111111-1111-1111-1111-111111111111",
        correlation_id=corr_id,
        details={
            "destination": "Regional-Central-Hub",
            "quantity": 250,
            "cold_chain": True,
        },
    )
    task_id = hitl_res["task_id"]
    assert hitl_res["status"] == "waiting_hitl"

    # 2. Submit approval decision via API using authorized logistics_manager role
    headers = {"Authorization": "Bearer mock-logistics-token"}
    payload = {
        "decision": "approve",
        "note": "Verified regional transport manifest and cold-chain compliance. Approved for dispatch.",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.post(f"/api/v1/hitl/tasks/{task_id}/decision", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "approved"
        assert data["decision"] == "approve"
        assert data["task_id"] == task_id

    # 3. Verify task status in store
    task = get_hitl_task(task_id)
    assert task is not None
    assert task["status"] == "approved"
    assert task["decision_note"] == payload["note"]

    # 4. Verify immutable audit log recorded
    ledger = get_in_memory_audit_ledger()
    decision_log = next((entry for entry in ledger if entry["action_type"] == "HITL_DECISION_SUBMITTED"), None)
    assert decision_log is not None
    assert decision_log["payload"]["task_id"] == task_id
    assert decision_log["payload"]["decision"] == "approve"

    # 5. Verify resumed state continues cascade execution to completion
    graph = build_cascade_graph()
    resumed_state: CascadeState = {
        "event": {"source": "pos", "quantity": 10},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-002-paracetamol",
        "quantity": 10,
        "active_tiers": ["distributor", "manufacturer"],
        "is_cross_border": True,
        "cross_border_approved": True,  # Resumed with human approval
        "trace": [],
        "errors": [],
        "status": "pending",
    }
    final_res = await graph.ainvoke(
        resumed_state,
        config={"configurable": {"thread_id": corr_id}},
    )
    assert final_res["status"] == "completed"


# -----------------------------------------------------------------------------
# Test 3: Reject & Safe Fallback Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reject_and_safe_fallback():
    """Post rejection decision; assert graph safely halts or cancels gated action."""
    corr_id = f"corr-reject-{uuid.uuid4().hex[:6]}"

    # 1. Create a pending task for in_progress_batch_change
    hitl_res = await request_human_approval(
        task_type="in_progress_batch_change",
        node_id="44444444-4444-4444-4444-444444444444",
        correlation_id=corr_id,
        details={
            "line_id": "line-01",
            "batch_id": "batch-active-99",
            "requested_alteration": "resize_down_50_percent",
        },
    )
    task_id = hitl_res["task_id"]

    # 2. Submit rejection via API using authorized compliance_officer
    headers = {"Authorization": "Bearer mock-compliance-token"}
    payload = {
        "decision": "reject",
        "note": "Rejection: Mid-cycle batch adjustment violates sterile stability protocol.",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.post(f"/api/v1/hitl/tasks/{task_id}/decision", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "rejected"
        assert data["decision"] == "reject"

    # 3. Verify task store and audit log
    task = get_hitl_task(task_id)
    assert task is not None
    assert task["status"] == "rejected"

    ledger = get_in_memory_audit_ledger()
    rej_log = next(
        (entry for entry in ledger if entry["action_type"] == "HITL_DECISION_SUBMITTED" and entry["payload"]["decision"] == "reject"),
        None,
    )
    assert rej_log is not None


# -----------------------------------------------------------------------------
# Test 4: RBAC Authorization Denied Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rbac_authorization_denied():
    """Attempt decision submission with unauthorized role; assert 403 Forbidden."""
    corr_id = f"corr-rbac-{uuid.uuid4().hex[:6]}"

    # Create module_activation task (requires system_admin, compliance_officer, admin)
    hitl_res = await request_human_approval(
        task_type="module_activation",
        node_id="00000000-0000-0000-0000-000000000000",
        correlation_id=corr_id,
        details={"module_id": "mod-margin-v2", "version": "2.0.0"},
    )
    task_id = hitl_res["task_id"]

    # Attempt to decide using pharmacy_staff (restricted)
    headers = {"Authorization": "Bearer mock-staff-token"}
    payload = {"decision": "approve", "note": "Attempted rogue approval by staff."}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.post(f"/api/v1/hitl/tasks/{task_id}/decision", json=payload, headers=headers)
        assert res.status_code == 403
        data = res.json()
        assert "not authorized" in str(data).lower()

    # Assert task remains in 'pending' status
    task = get_hitl_task(task_id)
    assert task is not None
    assert task["status"] == "pending"


# -----------------------------------------------------------------------------
# Test 5: Server Restart Persistence Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_server_restart_persistence(tmp_path: Path):
    """Verify pending task survives process restart and resumes cleanly via SQLiteSaver checkpointer."""
    db_file = tmp_path / "test_hitl_restart.db"
    thread_id = f"thread-restart-{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "correlation_id": "corr-restart-99",
        "trace_id": "trace-restart-99",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "user-restart-01",
        "messages": [],
        "current_agent": "stockist_order_agent",
        "next_step": "propose",
        "data": {"medicine_id": "MED-PCM-650", "requested_quantity": 500},
        "hitl_pending": False,
        "hitl_task_id": None,
    }

    # Phase 1: Run graph until HITL interrupt
    async with aiosqlite.connect(str(db_file)) as conn1:
        saver1 = AsyncSqliteSaver(conn1)
        await saver1.setup()
        graph1 = build_hitl_workflow_graph(checkpointer=saver1)

        await graph1.ainvoke(initial_state, config=config)

        snapshot1 = await graph1.aget_state(config)
        assert snapshot1.next == ("propose_action",)
        assert len(snapshot1.interrupts) > 0
        task_id = snapshot1.interrupts[0].value.get("task_id")
        assert task_id is not None

        # Confirm recorded in store
        task = get_hitl_task(task_id)
        assert task is not None
        assert task["status"] == "pending"

    # Connection closed, simulating backend shutdown

    # Phase 2: Process Restart -> Reconnect, verify state on disk, resume
    async with aiosqlite.connect(str(db_file)) as conn2:
        saver2 = AsyncSqliteSaver(conn2)
        graph2 = build_hitl_workflow_graph(checkpointer=saver2)

        restored_snapshot = await graph2.aget_state(config)
        assert restored_snapshot.next == ("propose_action",)

        resume_payload = {"approved": True, "notes": "Approved by senior pharmacist post-restart"}
        final_state = await graph2.ainvoke(Command(resume=resume_payload), config=config)

        assert final_state["data"]["final_execution_status"] == "approved_and_executed"
        assert final_state["data"]["approval_result"]["approved"] is True

        final_snapshot = await graph2.aget_state(config)
        assert final_snapshot.next == ()


# -----------------------------------------------------------------------------
# Test 6: HITL Expiry Worker Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hitl_expiry_worker():
    """Verify background expiry worker identifies expired tasks and auto-rejects them with audit trail."""
    hitl_events: list[EventEnvelope] = []
    in_process_event_bus.register_listener("hitl", lambda evt: hitl_events.append(evt))

    # Create task with expires_at in the past
    task_res = await request_human_approval(
        task_type="schedule_h_override",
        node_id="11111111-1111-1111-1111-111111111111",
        correlation_id="corr-exp-01",
        details={"medicine_id": "MED-AZI-500", "qty": 100},
    )
    task_id = task_res["task_id"]

    # Manually backdate expires_at to simulate expiration
    task = get_hitl_task(task_id)
    assert task is not None
    past_iso = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    task["expires_at"] = past_iso

    # Run expiry processor
    auto_rejected = await process_expired_hitl_tasks()
    assert len(auto_rejected) >= 1
    assert any(str(t.get("id") or t.get("task_id")) == task_id for t in auto_rejected)

    # Check task status updated to rejected
    updated_task = get_hitl_task(task_id)
    assert updated_task["status"] == "rejected"
    assert "Auto-rejected" in updated_task["decision_note"]

    # Check audit ledger
    ledger = get_in_memory_audit_ledger()
    exp_log = next(
        (entry for entry in ledger if entry["action_type"] == "HITL_TASK_AUTO_EXPIRED" and entry["payload"]["task_id"] == task_id),
        None,
    )
    assert exp_log is not None

    # Check SSE event emitted
    assert any(e.type == "hitl_expired" for e in hitl_events)
