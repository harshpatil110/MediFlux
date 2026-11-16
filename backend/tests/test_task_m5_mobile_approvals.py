"""Tests for Task M5: Mobile HITL Approvals.

Covers:
1. All 5 task types defined in config/hitl_policies.yaml and endpoints exposed.
2. Acceptance Criterion #1: Trigger live cross-border shipment task with paused cascade and SSE emission.
3. Acceptance Criterion #2: Approving pending task resumes paused graph and advances cascade to completed.
4. Acceptance Criterion #3: Unauthorized role (e.g. pharmacy) receives can_current_user_decide=False and 403 Forbidden on decision.
5. Acceptance Criterion #4: Expired tasks transition to expired cleanly without 500; already-decided tasks return already_finalized=True with 200 OK.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.hitl import _in_memory_hitl_tasks, clear_hitl_tasks
from app.core.hitl_policy import (
    clear_policy_cache,
    get_all_policies,
    get_allowed_roles,
    get_hitl_policy,
)
from app.graphs.cascade import clear_cascade_traces
from app.main import app


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_policy_cache()
    clear_hitl_tasks()
    clear_cascade_traces()
    yield
    clear_policy_cache()
    clear_hitl_tasks()
    clear_cascade_traces()


@pytest.mark.asyncio
async def test_hitl_policies_alignment():
    """Verify config/hitl_policies.yaml defines all 5 task types and roles."""
    policies = get_all_policies()

    task_types = [
        "cross_border_shipment",
        "batch_modification",
        "regulatory_activation",
        "doctor_verification",
        "schedule_h_override",
    ]

    for tt in task_types:
        assert tt in policies, f"Task type {tt} missing from policies"
        policy = get_hitl_policy(tt)
        assert policy.get("enabled") is True
        allowed = get_allowed_roles(tt)
        assert isinstance(allowed, list) and len(allowed) > 0
        assert "admin" in allowed

    # Verify pharmacy is restricted from cross_border_shipment and batch_modification
    assert "pharmacy" not in get_allowed_roles("cross_border_shipment")
    assert "pharmacy" not in get_allowed_roles("batch_modification")
    assert "manufacturer" in get_allowed_roles("batch_modification")
    assert "regulator" in get_allowed_roles("regulatory_activation")


@pytest.mark.asyncio
async def test_acceptance_criterion_1_live_cross_border_shipment():
    """AC #1: Trigger live cross-border shipment task and verify payload, countdown, and pending queue."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Trigger cross_border_shipment
        trigger_res = await client.post(
            "/api/v1/hitl/tasks/trigger",
            json={"task_type": "cross_border_shipment"},
            headers=admin_headers,
        )
        assert trigger_res.status_code == 200
        data = trigger_res.json()

        task_id = data["id"]
        corr_id = data["correlation_id"]
        assert data["task_type"] == "cross_border_shipment"
        assert data["status"] == "pending"
        assert data["can_current_user_decide"] is True
        assert "route" in data["details"]
        assert "products" in data["details"]
        assert "flags" in data["details"]
        assert data["details"]["route"]["border_checkpoint"] == "Raxaul ICP"

        # Verify task is returned in pending list
        list_res = await client.get("/api/v1/hitl/tasks?status=pending", headers=admin_headers)
        assert list_res.status_code == 200
        items = list_res.json()
        assert any(item["id"] == task_id for item in items)

        # Verify paused cascade trace exists
        cascade_res = await client.get(f"/api/v1/cascade/{corr_id}", headers=admin_headers)
        assert cascade_res.status_code == 200
        cascade_data = cascade_res.json()
        assert cascade_data["status"] == "waiting_approval"
        distributor_step = next(
            s for s in cascade_data["steps"] if s["tier"] == 2 or s["stage"] == "distributor"
        )
        assert distributor_step["status"] == "waiting_approval"


@pytest.mark.asyncio
async def test_acceptance_criterion_2_graph_resumption_on_approval():
    """AC #2: Approving pending task resumes paused graph and advances cascade trace to completed."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Trigger task with paused cascade
        trigger_res = await client.post(
            "/api/v1/hitl/tasks/trigger",
            json={"task_type": "cross_border_shipment"},
            headers=admin_headers,
        )
        task_data = trigger_res.json()
        task_id = task_data["id"]
        corr_id = task_data["correlation_id"]

        # Submit approval decision
        dec_res = await client.post(
            f"/api/v1/hitl/tasks/{task_id}/decision",
            json={"decision": "approved", "note": "Cleared customs transit permit at Raxaul."},
            headers=admin_headers,
        )
        assert dec_res.status_code == 200
        res_data = dec_res.json()
        assert res_data["status"] == "approved"
        assert res_data["outcome"] == "resumed_graph"
        assert res_data["already_finalized"] is False
        assert res_data["resumed_cascade_correlation_id"] == corr_id

        # Verify cascade trace is now completed and distributor step is done
        cascade_res = await client.get(f"/api/v1/cascade/{corr_id}", headers=admin_headers)
        assert cascade_res.status_code == 200
        cascade_trace = cascade_res.json()
        assert cascade_trace["status"] == "completed"

        dist_step = next(s for s in cascade_trace["steps"] if s["tier"] == 2 or s["stage"] == "distributor")
        assert dist_step["status"] == "succeeded"
        assert dist_step["state"] == "done"
        assert "Cleared customs transit permit" in dist_step["reasoning"]


@pytest.mark.asyncio
async def test_acceptance_criterion_3_unauthorized_role_forbidden():
    """AC #3: Role without approver rights receives can_current_user_decide=False and 403 Forbidden on decide."""
    pharmacy_headers = {"Authorization": "Bearer mock-pharmacy-token"}
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Trigger a batch_modification task (allowed: admin, manufacturer)
        trigger_res = await client.post(
            "/api/v1/hitl/tasks/trigger",
            json={"task_type": "batch_modification"},
            headers=admin_headers,
        )
        task_id = trigger_res.json()["id"]

        # Inspect task as pharmacy user
        get_res = await client.get(f"/api/v1/hitl/tasks/{task_id}", headers=pharmacy_headers)
        assert get_res.status_code == 200
        pharmacy_task = get_res.json()
        assert pharmacy_task["can_current_user_decide"] is False
        assert "does not have approver rights" in pharmacy_task["cannot_decide_reason"]

        # Attempt decision as pharmacy user -> 403 Forbidden
        dec_res = await client.post(
            f"/api/v1/hitl/tasks/{task_id}/decision",
            json={"decision": "approved", "note": "Unauthorized attempt."},
            headers=pharmacy_headers,
        )
        assert dec_res.status_code == 403
        err_body = dec_res.json()
        assert "HITL_FORBIDDEN_ROLE" in str(err_body)


@pytest.mark.asyncio
async def test_acceptance_criterion_4_expired_and_already_decided_handling():
    """AC #4: Overdue tasks transition to expired cleanly; already-decided tasks return already_finalized=True."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    now_utc = datetime.now(UTC)
    past_iso = (now_utc - timedelta(hours=2)).isoformat()

    # 1. Test Expired Task
    expired_task_id = f"task-expired-{uuid.uuid4().hex[:6]}"
    _in_memory_hitl_tasks[expired_task_id] = {
        "id": expired_task_id,
        "task_id": expired_task_id,
        "task_type": "schedule_h_override",
        "title": "Expired Test Task",
        "summary": "Should expire automatically.",
        "status": "pending",
        "created_at": past_iso,
        "expires_at": (now_utc - timedelta(minutes=10)).isoformat(),
        "details": {},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Fetching task runs sweep and transitions to expired
        get_res = await client.get(f"/api/v1/hitl/tasks/{expired_task_id}", headers=admin_headers)
        assert get_res.status_code == 200
        assert get_res.json()["status"] == "expired"

        # Attempting decision returns already_finalized=True with 200 OK (not 500)
        dec_res = await client.post(
            f"/api/v1/hitl/tasks/{expired_task_id}/decision",
            json={"decision": "approved", "note": "Late attempt."},
            headers=admin_headers,
        )
        assert dec_res.status_code == 200
        body = dec_res.json()
        assert body["already_finalized"] is True
        assert body["status"] == "expired"

        # 2. Test Already Decided Task
        approved_task_id = f"task-approved-{uuid.uuid4().hex[:6]}"
        _in_memory_hitl_tasks[approved_task_id] = {
            "id": approved_task_id,
            "task_id": approved_task_id,
            "task_type": "regulatory_activation",
            "title": "Already Approved Task",
            "summary": "Already decided by compliance.",
            "status": "approved",
            "created_at": past_iso,
            "expires_at": (now_utc + timedelta(hours=10)).isoformat(),
            "decided_by": "compliance_lead@mediflux.io",
            "decided_at": past_iso,
            "decision_note": "Signed off.",
            "details": {},
        }

        dec_again = await client.post(
            f"/api/v1/hitl/tasks/{approved_task_id}/decision",
            json={"decision": "reject", "note": "Secondary decision."},
            headers=admin_headers,
        )
        assert dec_again.status_code == 200
        dec_body = dec_again.json()
        assert dec_body["already_finalized"] is True
        assert dec_body["status"] == "approved"
        assert dec_body["decided_by"] == "compliance_lead@mediflux.io"


@pytest.mark.asyncio
async def test_hitl_policies_api_endpoint():
    """Verify GET /api/v1/hitl/policies returns all 5 task types with allowed_roles and risk_level."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/hitl/policies", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert "policies" in data
        policies = data["policies"]

        task_types = [
            "cross_border_shipment",
            "batch_modification",
            "regulatory_activation",
            "doctor_verification",
            "schedule_h_override",
        ]
        for tt in task_types:
            assert tt in policies, f"Expected {tt} in policies response"
            p = policies[tt]
            assert "allowed_roles" in p or "required_roles" in p
            roles = p.get("allowed_roles") or p.get("required_roles")
            assert isinstance(roles, list) and len(roles) > 0


@pytest.mark.asyncio
async def test_all_five_task_type_payloads_and_renderers():
    """Verify triggering all 5 task types produces rich structured payloads for mobile renderers."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. cross_border_shipment
        res1 = await client.post("/api/v1/hitl/tasks/trigger", json={"task_type": "cross_border_shipment"}, headers=admin_headers)
        assert res1.status_code == 200
        p1 = res1.json()["details"]
        assert "route" in p1 and p1["route"]["border_checkpoint"] == "Raxaul ICP"
        assert len(p1["products"]) >= 1
        assert "COLD_CHAIN_2_8C" in p1["flags"]

        # 2. batch_modification
        res2 = await client.post("/api/v1/hitl/tasks/trigger", json={"task_type": "batch_modification"}, headers=admin_headers)
        assert res2.status_code == 200
        p2 = res2.json()["details"]
        assert "batch" in p2 and "MFG-AMOX" in p2["batch"]["batch_no"]
        assert "change" in p2 and p2["change"]["field"] == "batch_size_units"
        assert "api_stock_impact" in p2 and p2["api_stock_impact"]["below_safety_buffer"] is True

        # 3. regulatory_activation
        res3 = await client.post("/api/v1/hitl/tasks/trigger", json={"task_type": "regulatory_activation"}, headers=admin_headers)
        assert res3.status_code == 200
        p3 = res3.json()["details"]
        assert p3["module_name"] == "pricing_engine"
        assert "v1 → v2" in p3["version_transition"]
        assert p3["test_results"]["regression_suite"] == "PASS"
        assert "MAX_UNIT_PRICE" in p3["simplified_diff"]

        # 4. doctor_verification
        res4 = await client.post("/api/v1/hitl/tasks/trigger", json={"task_type": "doctor_verification"}, headers=admin_headers)
        assert res4.status_code == 200
        p4 = res4.json()["details"]
        assert p4["doctor_registration_no"] == "MCI-UNVERIFIED-9901"
        assert p4["verification_status"] == "not_found_in_nmc_registry"
        assert len(p4["drugs"]) >= 1

        # 5. schedule_h_override
        res5 = await client.post("/api/v1/hitl/tasks/trigger", json={"task_type": "schedule_h_override"}, headers=admin_headers)
        assert res5.status_code == 200
        p5 = res5.json()["details"]
        assert "drugs" in p5
        assert any(d.get("schedule_class") == "H" for d in p5["drugs"])


@pytest.mark.asyncio
async def test_pharmacy_cannot_decide_cross_border_shipment():
    """Explicitly verify pharmacy role cannot decide cross_border_shipment (AC #3)."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}
    pharmacy_headers = {"Authorization": "Bearer mock-pharmacy-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Trigger cross_border_shipment
        trigger_res = await client.post(
            "/api/v1/hitl/tasks/trigger",
            json={"task_type": "cross_border_shipment"},
            headers=admin_headers,
        )
        assert trigger_res.status_code == 200
        task_id = trigger_res.json()["id"]

        # Inspect as pharmacy
        get_res = await client.get(f"/api/v1/hitl/tasks/{task_id}", headers=pharmacy_headers)
        assert get_res.status_code == 200
        task_data = get_res.json()
        assert task_data["can_current_user_decide"] is False
        assert "PHARMACY" in task_data["cannot_decide_reason"]

        # Attempt decision as pharmacy -> 403 Forbidden
        dec_res = await client.post(
            f"/api/v1/hitl/tasks/{task_id}/decision",
            json={"decision": "approved", "note": "Pharmacy trying to approve cross-border."},
            headers=pharmacy_headers,
        )
        assert dec_res.status_code == 403
        err = dec_res.json()
        assert "HITL_FORBIDDEN_ROLE" in str(err)


@pytest.mark.asyncio
async def test_rejection_decision_outcome_and_audit():
    """Verify rejecting a HITL task returns outcome=rejected, records audit, and aborts action."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        trigger_res = await client.post(
            "/api/v1/hitl/tasks/trigger",
            json={"task_type": "cross_border_shipment"},
            headers=admin_headers,
        )
        task_id = trigger_res.json()["id"]

        # Submit rejection
        dec_res = await client.post(
            f"/api/v1/hitl/tasks/{task_id}/decision",
            json={"decision": "rejected", "note": "Customs permit expired. Shipment blocked."},
            headers=admin_headers,
        )
        assert dec_res.status_code == 200
        data = dec_res.json()
        assert data["status"] == "rejected"
        assert data["outcome"] == "rejected"
        assert data["already_finalized"] is False
        assert data["audit_entry_id"] is not None


@pytest.mark.asyncio
async def test_hitl_tasks_decided_filter():
    """Verify GET /api/v1/hitl/tasks?status=decided returns approved, rejected, and expired tasks."""
    admin_headers = {"Authorization": "Bearer mock-admin-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Trigger 2 tasks
        t1 = (await client.post("/api/v1/hitl/tasks/trigger", json={"task_type": "batch_modification"}, headers=admin_headers)).json()
        t2 = (await client.post("/api/v1/hitl/tasks/trigger", json={"task_type": "cross_border_shipment"}, headers=admin_headers)).json()

        # Approve t1
        await client.post(f"/api/v1/hitl/tasks/{t1['id']}/decision", json={"decision": "approved", "note": "Approved"}, headers=admin_headers)

        # Query status=decided
        decided_res = await client.get("/api/v1/hitl/tasks?status=decided", headers=admin_headers)
        assert decided_res.status_code == 200
        decided_items = decided_res.json()

        # t1 should be in decided items
        assert any(item["id"] == t1["id"] for item in decided_items)
        # t2 (pending) should NOT be in decided items
        assert not any(item["id"] == t2["id"] for item in decided_items)

