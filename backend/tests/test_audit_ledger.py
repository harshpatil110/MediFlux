"""Automated test suite for Task 16 Tamper-Evident Hash-Chained Audit Ledger and Audit Agent."""

import asyncio
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.audit_agent import audit_agent, generate_explanation
from app.agents.bootstrap_agent import bootstrap_agent
from app.agents.tools import execute_tool
from app.core.audit_ledger import (
    clear_in_memory_audit_ledger,
    get_in_memory_audit_ledger,
    set_in_memory_audit_ledger,
    verify_audit_chain,
    write_audit_entry,
)
from app.core.config import settings
from app.core.hitl import clear_hitl_tasks, request_human_approval
from app.graphs.cascade import CascadeState, build_cascade_graph
from app.main import app


@pytest.fixture(autouse=True)
def clean_audit_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure clean in-memory state and offline settings for deterministic test isolation."""
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "")
    clear_in_memory_audit_ledger()
    clear_hitl_tasks()
    bootstrap_agent.bootstrap_all_modules()


# -----------------------------------------------------------------------------
# Test 1: Sequential Hash Chain Generation Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sequential_hash_chain_generation():
    """Write 5 audit entries; assert monotonic seq, valid prev_hash chaining, and verify endpoint."""
    entries = []
    for i in range(1, 6):
        entry = await write_audit_entry(
            actor="agent:PharmacyAgent",
            action="CREATE_ORDER",
            entity_type="orders",
            entity_id=f"order-{i}",
            payload={"sku": "MED-PCM-650", "quantity": i * 10},
            explanation=f"Routine restocking of batch {i}",
        )
        entries.append(entry)

    # 1. Assert monotonic sequence numbers
    assert [e["seq"] for e in entries] == [1, 2, 3, 4, 5]

    # 2. Assert prev_hash of entry 1 is 64 zeros
    assert entries[0]["prev_hash"] == "0" * 64

    # 3. Assert prev_hash of entry N equals hash of entry N-1
    for i in range(1, 5):
        assert entries[i]["prev_hash"] == entries[i - 1]["hash"]

    # 4. Verify chain integrity function
    verify_res = verify_audit_chain(entries)
    assert verify_res["valid"] is True
    assert verify_res["total_entries"] == 5

    # 5. Call API verify endpoint
    headers = {"Authorization": "Bearer mock-admin-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/audit/verify", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["total_entries"] == 5

        # Query paginated audit entries
        list_res = await client.get("/api/v1/audit?limit=10", headers=headers)
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] == 5
        assert len(list_data["items"]) == 5


test_sequential_hash_chain = test_sequential_hash_chain_generation


# -----------------------------------------------------------------------------
# Test 2: Direct DB Tampering Detection Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_direct_db_tampering_detection():
    """Manually alter payload or hash in row seq=2; assert verify detects break at broken_at_seq=2."""
    for i in range(1, 4):
        await write_audit_entry(
            actor="system",
            action=f"ACTION_{i}",
            entity_type="test",
            entity_id=f"id-{i}",
            payload={"value": i * 100},
        )

    ledger = get_in_memory_audit_ledger()
    assert len(ledger) == 3

    # Tamper with row seq=2 directly (change payload without recalculating cryptographic hash)
    tampered_ledger = [dict(entry) for entry in ledger]
    tampered_ledger[1]["payload"] = {"value": 999999}  # Malicious alteration

    set_in_memory_audit_ledger(tampered_ledger)

    # 1. Verify function detects tampering
    verify_res = verify_audit_chain(tampered_ledger)
    assert verify_res["valid"] is False
    assert verify_res["broken_at_seq"] == 2
    assert "mismatch" in verify_res["reason"].lower()

    # 2. API verify endpoint detects tampering
    headers = {"Authorization": "Bearer mock-admin-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/audit/verify", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert data["broken_at_seq"] == 2


# -----------------------------------------------------------------------------
# Test 3: Concurrent Writes Integrity Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_writes_integrity():
    """Fire 20 concurrent write_audit_entry tasks; assert monotonic sequence, no gaps, and valid chain."""
    num_writes = 20

    async def _write(index: int) -> dict:
        return await write_audit_entry(
            actor=f"worker-{index % 4}",
            action="CONCURRENT_EVENT",
            entity_type="inventory",
            entity_id=f"sku-{index}",
            payload={"index": index, "qty": index * 5},
            explanation="Concurrent test write",
        )

    tasks = [_write(i) for i in range(num_writes)]
    results = await asyncio.gather(*tasks)

    assert len(results) == num_writes

    ledger = get_in_memory_audit_ledger()
    assert len(ledger) == num_writes

    # Assert sequence numbers are exactly 1 through 20 without duplicates or gaps
    seqs = [entry["seq"] for entry in ledger]
    assert seqs == list(range(1, num_writes + 1))

    # Assert cryptographic integrity of entire chain
    verify_res = verify_audit_chain(ledger)
    assert verify_res["valid"] is True
    assert verify_res["total_entries"] == num_writes

    # API verify endpoint
    headers = {"Authorization": "Bearer mock-admin-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/audit/verify", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["total_entries"] == num_writes


# -----------------------------------------------------------------------------
# Test 4: LLM Failure Resilience / Non-Blocking Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_llm_failure_resilience_non_blocking():
    """Mock LLM Router failure and timeout; assert audit write never blocks and completes with explanation=''."""
    # 1. Simulate LLM timeout (>2s)
    async def _mock_slow_llm(*args, **kwargs):
        await asyncio.sleep(5.0)
        return "Slow explanation"

    with patch.object(audit_agent.router, "complete", side_effect=_mock_slow_llm):
        explanation_timeout = await generate_explanation(
            actor="agent:SchedulerAgent",
            action="SCHEDULE_H_OVERRIDE",
            entity_type="hitl_task",
            payload={"risk": "high"},
        )
        assert explanation_timeout == ""

    # 2. Simulate LLM exception/error
    with patch.object(audit_agent.router, "complete", side_effect=RuntimeError("Provider API failure")):
        explanation_error = await generate_explanation(
            actor="agent:SettlementAgent",
            action="SETTLEMENT_APPROVED",
            entity_type="settlements",
            payload={"net_total": 50000},
        )
        assert explanation_error == ""

    # 3. Verify write_audit tool executes cleanly and records valid audit entry even under LLM error
    with patch.object(audit_agent.router, "complete", side_effect=TimeoutError("Network timeout")):
        tool_res = await execute_tool(
            "write_audit",
            {
                "actor_id": "user:pharmacist",
                "action": "SCHEDULE_H_OVERRIDE",
                "details": {"patient_id": "P-100", "approved": True},
            },
        )
        assert tool_res["status"] == "recorded"
        assert "hash" in tool_res
        assert tool_res["seq"] >= 1

    # Verify audit ledger chain remains intact
    ledger = get_in_memory_audit_ledger()
    assert len(ledger) >= 1
    assert verify_audit_chain(ledger)["valid"] is True


test_llm_failure_non_blocking = test_llm_failure_resilience_non_blocking


# -----------------------------------------------------------------------------
# Test 5: Cross-Component Event Coverage Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cross_component_event_coverage():
    """Execute cascade run, HITL decision, and module activation; assert audit records for each appear in ledger."""
    # 1. HITL Request & Decision Event
    hitl_res = await request_human_approval(
        task_type="schedule_h_override",
        node_id="11111111-1111-1111-1111-111111111111",
        correlation_id="corr-cross-01",
        details={"medicine_id": "MED-AZI-500", "qty": 100},
    )
    task_id = hitl_res["task_id"]

    # Submit decision via API
    headers = {"Authorization": "Bearer mock-pic-token"}
    payload = {"decision": "approve", "note": "Verified doctor prescription copy. Approved."}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.post(f"/api/v1/hitl/tasks/{task_id}/decision", json=payload, headers=headers)
        assert res.status_code == 200

    # 2. Module Activation Event
    await write_audit_entry(
        actor="user:system_admin",
        action="MODULE_ACTIVATION",
        entity_type="modules",
        entity_id="margin_rules",
        payload={"module_id": "margin_rules", "version": "2.0.0", "active": True},
        explanation="Upgraded margin rules to v2",
    )

    # 3. Tool Direct Audit Event
    await execute_tool(
        "write_audit",
        {
            "actor_id": "agent:StockistAgent",
            "action": "CREATE_ORDER",
            "details": {"order_id": "ord-stockist-99", "quantity": 100},
            "entity_type": "orders",
            "entity_id": "ord-stockist-99",
        },
    )

    # 4. Cascade Run
    graph = build_cascade_graph()
    corr_id_casc = "corr-casc-audit-01"
    cascade_state: CascadeState = {
        "event": {"source": "pos", "quantity": 5},
        "correlation_id": corr_id_casc,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-002-paracetamol",
        "quantity": 5,
        "active_tiers": ["distributor", "manufacturer"],
        "trace": [],
        "errors": [],
        "status": "pending",
    }
    await graph.ainvoke(
        cascade_state,
        config={"configurable": {"thread_id": corr_id_casc}},
    )

    ledger = get_in_memory_audit_ledger()
    assert len(ledger) >= 3

    # Assert specific actions exist in ledger
    actions = [entry.get("action") or entry.get("action_type") for entry in ledger]
    assert any("HITL" in str(act) for act in actions)
    assert "MODULE_ACTIVATION" in actions
    assert "CREATE_ORDER" in actions

    # Verify overall chain validity
    assert verify_audit_chain(ledger)["valid"] is True


test_cross_component_audit_coverage = test_cross_component_event_coverage
