"""Automated test suite for Task 26: Workflow Screens (Approvals Inbox, Audit Ledger Viewer, Adapter Forge, Regulatory Lab).

Tests cover:
1. HITL Approvals Queue Listing, Seeding, and Filtering (GET /api/v1/hitl/tasks)
2. HITL Approval & Graph Resumption with Audit Logging (POST /api/v1/hitl/{task_id}/decide)
3. Cryptographic Audit Ledger Listing & SHA-256 Chain Verification (GET & POST /api/v1/audit/verify)
4. Adapter Forge Fixtures & Synthesized Code Generation (GET /api/v1/adapters/fixtures, POST /api/v1/adapters/generate)
5. Live Adapter Ingestion Sandbox (POST /api/v1/ingest/{adapter_id})
6. Regulatory Gazette Fixtures & Multi-Stage Pipeline Execution (GET /api/v1/regulatory/fixtures, POST /api/v1/regulatory/notifications)
7. Zero-Downtime Hot-Swap Price Capping Verification (Before vs After Approval & Rollback)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADER = {"Authorization": "Bearer mock-admin-token"}


@pytest.mark.asyncio
async def test_hitl_tasks_listing_and_seeding():
    """Verify HITL tasks are seeded with realistic checkpoints and can be filtered."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/hitl/tasks", headers=AUTH_HEADER)
        assert resp.status_code == 200
        tasks = resp.json()
        assert isinstance(tasks, list)
        assert len(tasks) >= 3

        # Verify diverse task types and risk levels
        types = [t.get("task_type") for t in tasks]
        assert "regulatory_hot_swap" in types
        assert "prescription_doctor_verification" in types
        assert "coldchain_high_value" in types

        # Test filtering by status
        resp_pending = await client.get("/api/v1/hitl/tasks?status=pending", headers=AUTH_HEADER)
        assert resp_pending.status_code == 200
        for t in resp_pending.json():
            assert t["status"] == "pending"

        # Test filtering by risk level
        resp_crit = await client.get("/api/v1/hitl/tasks?risk_level=critical", headers=AUTH_HEADER)
        assert resp_crit.status_code == 200
        for t in resp_crit.json():
            assert t["risk_level"] == "critical"


@pytest.mark.asyncio
async def test_hitl_approval_resumes_workflow_and_logs_audit():
    """Verify approving a HITL task resumes paused graph and appends to cryptographic audit ledger."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get tasks
        resp = await client.get("/api/v1/hitl/tasks", headers=AUTH_HEADER)
        tasks = resp.json()
        reg_task = next((t for t in tasks if t.get("task_type") == "regulatory_hot_swap"), tasks[0])
        task_id = reg_task.get("task_id") or reg_task["id"]

        # Approve task
        payload = {
            "decision": "approved",
            "note": "Operator verification of DPCO 2013 Gazette notification for Paracetamol 500mg",
        }
        decide_resp = await client.post(f"/api/v1/hitl/{task_id}/decide", json=payload, headers=AUTH_HEADER)
        assert decide_resp.status_code == 200
        decide_data = decide_resp.json()

        assert decide_data["status"] == "approved"
        assert decide_data["task_id"] == task_id
        assert "resumed_workflow" in decide_data
        assert decide_data["resumed_workflow"].get("status") == "resumed" or "action" in decide_data["resumed_workflow"]

        # Verify audit ledger recorded the human approval
        audit_resp = await client.get("/api/v1/audit?action=HITL_DECISION_SUBMITTED", headers=AUTH_HEADER)
        assert audit_resp.status_code == 200
        raw_audit = audit_resp.json()
        audit_entries = raw_audit.get("items", raw_audit) if isinstance(raw_audit, dict) else raw_audit
        assert len(audit_entries) >= 1
        assert any(e["action"] == "HITL_DECISION_SUBMITTED" for e in audit_entries)


@pytest.mark.asyncio
async def test_audit_ledger_listing_and_cryptographic_verification():
    """Verify SHA-256 recursive cryptographic audit chain validation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Retrieve ledger
        resp = await client.get("/api/v1/audit", headers=AUTH_HEADER)
        assert resp.status_code == 200
        raw_resp = resp.json()
        entries = raw_resp.get("items", raw_resp) if isinstance(raw_resp, dict) else raw_resp
        assert len(entries) >= 1

        # Check genesis entry structure
        first_entry = entries[0]
        assert "entry_hash" in first_entry or "hash" in first_entry
        assert "prev_hash" in first_entry

        # Run cryptographic verification via POST
        verify_post = await client.post("/api/v1/audit/verify", headers=AUTH_HEADER)
        assert verify_post.status_code == 200
        data = verify_post.json()

        assert data["valid"] is True
        assert data["status"] == "verified"
        assert data["verified_entries"] >= 1
        assert len(data["genesis_hash"]) == 64
        assert len(data["head_hash"]) == 64

        # Run verification via GET
        verify_get = await client.get("/api/v1/audit/verify", headers=AUTH_HEADER)
        assert verify_get.status_code == 200
        assert verify_get.json()["valid"] is True


@pytest.mark.asyncio
async def test_adapter_fixtures_and_generation():
    """Verify adapter fixtures endpoint and multi-agent synthesis pipeline."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check fixtures
        fix_resp = await client.get("/api/v1/adapters/fixtures", headers=AUTH_HEADER)
        assert fix_resp.status_code == 200
        fixtures = fix_resp.json()
        assert len(fixtures) >= 3

        formats = [f["format"] for f in fixtures]
        assert "csv" in formats
        assert "xml" in formats
        assert "json" in formats

        # Generate adapter from CSV fixture
        csv_fixture = next(f for f in fixtures if f["format"] == "csv")
        gen_payload = {
            "name": "Marg POS Test Translator",
            "target_schema": "SaleEvent",
            "sample_payload": csv_fixture["sample_payload"],
            "expected_output": csv_fixture.get("expected_output"),
        }
        gen_resp = await client.post("/api/v1/adapters/generate", json=gen_payload, headers=AUTH_HEADER)
        assert gen_resp.status_code in (200, 202)
        gen_data = gen_resp.json()
        assert "job_id" in gen_data
        assert gen_data["status"] in ("completed", "registered", "succeeded")
        assert "adapter_id" in gen_data

        # Inspect job status
        job_id = gen_data["job_id"]
        job_resp = await client.get(f"/api/v1/adapters/jobs/{job_id}", headers=AUTH_HEADER)
        assert job_resp.status_code == 200
        job_data = job_resp.json()
        assert job_data["job_id"] == job_id
        assert len(job_data.get("events", [])) >= 1


@pytest.mark.asyncio
async def test_adapter_live_ingestion():
    """Verify live ingest transforms raw legacy payload into canonical event."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get active adapters
        ad_resp = await client.get("/api/v1/adapters", headers=AUTH_HEADER)
        assert ad_resp.status_code == 200
        adapters = ad_resp.json()
        assert len(adapters) >= 1

        adapter_id = adapters[0]["id"]
        sample_csv = "timestamp,store_code,sku,qty,price\n2026-11-13T10:00:00Z,PHARM-001,PARA-500,5,15.50"

        # Ingest raw payload
        ingest_resp = await client.post(
            f"/api/v1/ingest/{adapter_id}",
            content=sample_csv,
            headers={"Content-Type": "text/plain", **AUTH_HEADER},
        )
        assert ingest_resp.status_code in (200, 202)
        ingest_data = ingest_resp.json()

        assert ingest_data["status"] in ("ingested", "accepted")
        assert "correlation_id" in ingest_data
        assert "canonical_event" in ingest_data
        assert "event_id" in ingest_data.get("canonical_event", {}) or "event_id" in ingest_data


@pytest.mark.asyncio
async def test_regulatory_fixtures_and_notification_pipeline():
    """Verify synthetic regulatory directives and 5-stage hot-swap pipeline."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check fixtures
        fix_resp = await client.get("/api/v1/regulatory/fixtures", headers=AUTH_HEADER)
        assert fix_resp.status_code == 200
        fixtures = fix_resp.json()
        assert len(fixtures) >= 2

        nppa_fix = next(f for f in fixtures if "Ceiling" in f["title"])
        assert "PARA-500" in nppa_fix["raw_text"] or "Paracetamol" in nppa_fix["raw_text"]

        # Ingest notification
        notice_payload = {
            "title": nppa_fix["title"],
            "source": nppa_fix["source"],
            "text": nppa_fix["raw_text"],
        }
        notice_resp = await client.post("/api/v1/regulatory/notifications", json=notice_payload, headers=AUTH_HEADER)
        assert notice_resp.status_code in (200, 202)
        notice_data = notice_resp.json()

        assert "run_id" in notice_data
        assert "notification_id" in notice_data
        assert notice_data["status"] in ("staged", "awaiting_approval")

        # List runs
        runs_resp = await client.get("/api/v1/regulatory/runs", headers=AUTH_HEADER)
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert len(runs) >= 1


@pytest.mark.asyncio
async def test_regulatory_zero_downtime_hot_swap_price_check():
    """Verify live pricing engine enforces DPCO ceiling immediately upon approval with rollback support."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First ensure regulatory run exists
        fix_resp = await client.get("/api/v1/regulatory/fixtures", headers=AUTH_HEADER)
        fixtures = fix_resp.json()
        nppa_fix = fixtures[0]

        notice_resp = await client.post(
            "/api/v1/regulatory/notifications",
            json={
                "title": nppa_fix["title"],
                "source": nppa_fix["source"],
                "text": nppa_fix["raw_text"],
            },
            headers=AUTH_HEADER,
        )
        assert notice_resp.status_code in (200, 202)
        run_id = notice_resp.json()["run_id"]

        price_before = await client.post(
            "/api/v1/regulatory/price-check",
            json={"sku": "PARA-500", "unit_price": 25.0, "quantity": 10},
            headers=AUTH_HEADER,
        )
        assert price_before.status_code == 200
        before_data = price_before.json()
        assert before_data["active_version"] in (1, 2)

        # Approve run to trigger zero-downtime hot-swap!
        approve_resp = await client.post(f"/api/v1/regulatory/runs/{run_id}/approve", headers=AUTH_HEADER)
        assert approve_resp.status_code == 200
        approved_version = approve_resp.json()["active_version"]
        assert approved_version >= 2

        # Check price immediately without server restart: DPCO ceiling ₹12.50 must be strictly enforced!
        price_after = await client.post(
            "/api/v1/regulatory/price-check",
            json={"sku": "PARA-500", "unit_price": 25.0, "quantity": 10},
            headers=AUTH_HEADER,
        )
        assert price_after.status_code == 200
        after_data = price_after.json()
        assert after_data["active_version"] == approved_version
        assert after_data["output"]["price_capped"] is True
        assert after_data["output"]["effective_price"] == 12.50
        assert after_data["output"]["ceiling_applied"] == 12.50
        assert after_data["output"]["total_amount"] == 125.0  # 12.50 * 10

        # Rollback to verify hot-swap rollback capability
        rollback_resp = await client.post(f"/api/v1/regulatory/runs/{run_id}/rollback", headers=AUTH_HEADER)
        assert rollback_resp.status_code == 200
        rolled_back_version = rollback_resp.json()["active_version"]
        assert rolled_back_version < approved_version

        # Check price after rollback: returns rolled back version
        price_rolled_back = await client.post(
            "/api/v1/regulatory/price-check",
            json={"sku": "PARA-500", "unit_price": 25.0, "quantity": 10},
            headers=AUTH_HEADER,
        )
        assert price_rolled_back.status_code == 200
        assert price_rolled_back.json()["active_version"] == rolled_back_version
        assert price_rolled_back.json()["output"]["effective_price"] in (12.50, 25.0)
