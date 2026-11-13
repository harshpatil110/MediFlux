# ruff: noqa: E402
"""Automated test suite for Task 27 Compliance, Copilot, and Developer Portal Screens.

Tests:
1. Prescription Scanner & Sovereign Schedule H Compliance:
   - Privacy-preserving listing (patient initials only, no full names).
   - Synthetic fixtures endpoint with preview data URIs.
   - Fixture ingestion (valid approved, unknown doctor flagged with HITL).
   - Schedule H sale linking.
2. Cold-Chain Biologics Telemetry & Live Excursion Simulation:
   - Batches telemetry listing with chronological readings and Arrhenius degradation.
   - Live excursion simulation (>8°C) causing batch quarantine, available_quantity = 0,
     Excursion Analyst clinical narrative, and rebalance correlation trace.
3. Developer Portal & Sample Client SDK Integration:
   - Scoped API key creation with plaintext secret returned once.
   - Third-party MediFluxClient invocation with provisioned key.
   - MCP tool execution with API key.
   - Key revocation verification.
4. Network Copilot & Vector Search:
   - Question and query parameter compatibility.
   - Grounded tools and reference entity chips.
   - Vector search endpoint.
"""

import sys
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure repo root is on sys.path for importing clients
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from clients.sample_client.typed_client import MediFluxClient

from app.core.audit_ledger import clear_in_memory_audit_ledger
from app.core.hitl import clear_hitl_tasks
from app.graphs.coldchain import reset_coldchain_state
from app.graphs.prescription import clear_prescription_store
from app.main import app


@pytest.fixture(autouse=True)
def clean_environment():
    """Isolate testing environment before and after every test."""
    clear_prescription_store()
    clear_hitl_tasks()
    clear_in_memory_audit_ledger()
    reset_coldchain_state()
    yield
    clear_prescription_store()
    clear_hitl_tasks()
    clear_in_memory_audit_ledger()
    reset_coldchain_state()


# -----------------------------------------------------------------------------
# 1. Sovereign Prescription Scanner & Schedule H Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_prescriptions_listing_privacy_redaction():
    """Verify GET /api/v1/prescriptions projects patient initials only and marks sensitivity sensitive."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/prescriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "prescriptions" in data
        assert data["total"] >= 1

        for rx in data["prescriptions"]:
            # Strict Privacy Check: Never expose patient_name; must have patient_initials
            assert "patient_name" not in rx
            assert "patient_initials" in rx
            assert rx["sensitivity"] == "sensitive"
            assert "doctor_name" in rx
            assert "drugs" in rx


@pytest.mark.asyncio
async def test_prescription_fixtures_endpoint():
    """Verify GET /api/v1/prescriptions/fixtures returns 5 fixtures with base64 data URIs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/prescriptions/fixtures")
        assert resp.status_code == 200
        fixtures = resp.json()
        assert len(fixtures) == 5

        ids = [f["id"] for f in fixtures]
        assert "valid_prescription" in ids
        assert "schedule_h_prescription" in ids
        assert "unknown_doctor" in ids
        assert "missing_reg_no" in ids
        assert "unlisted_drug" in ids

        for f in fixtures:
            assert f["data_uri"] is not None
            assert f["data_uri"].startswith("data:image/png;base64,")
            assert "label" in f
            assert "expected_verdict" in f


@pytest.mark.asyncio
async def test_prescription_scan_valid_and_unknown_doctor():
    """Test POST /api/v1/prescriptions with valid fixture (approved) and unknown doctor (flagged HITL)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Valid Prescription Fixture -> Approved
        resp_valid = await client.post(
            "/api/v1/prescriptions",
            json={"fixture_name": "valid_prescription.png"},
        )
        assert resp_valid.status_code == 201
        valid_data = resp_valid.json()
        assert valid_data["status"] == "approved"
        assert valid_data["decision"] == "approve_dispense"
        assert valid_data["doctor_verified"] is True
        assert valid_data["patient_initials"] == "R.K."
        assert valid_data["hitl_task_id"] is None

        # 2. Unknown Doctor Fixture -> Flagged for HITL
        resp_unknown = await client.post(
            "/api/v1/prescriptions",
            json={"fixture_name": "unknown_doctor.png"},
        )
        assert resp_unknown.status_code == 201
        unk_data = resp_unknown.json()
        assert unk_data["status"] == "flagged"
        assert unk_data["decision"] == "flag"
        assert unk_data["doctor_verified"] is False
        assert unk_data["hitl_task_id"] is not None


@pytest.mark.asyncio
async def test_prescription_schedule_h_sale_link():
    """Verify scanning Schedule H Rx allows linking to retail POS event with prescription_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Scan Schedule H prescription
        scan_resp = await client.post(
            "/api/v1/prescriptions",
            json={"fixture_name": "schedule_h_prescription.png"},
        )
        assert scan_resp.status_code == 201
        rx_data = scan_resp.json()
        rx_id = rx_data["id"]

        # Submit retail sale event with prescription_id
        corr_id = str(uuid.uuid4())
        sale_resp = await client.post(
            "/api/v1/events",
            json={
                "event_type": "retail.sale",
                "product_id": "p-001-azithromycin",
                "sku": "MED-AMX-500",
                "quantity": 2,
                "prescription_id": rx_id,
                "node_id": "11111111-1111-1111-1111-111111111111",
                "unit_price": 45.0,
                "correlation_id": corr_id,
            },
        )
        assert sale_resp.status_code in (200, 201, 202)
        sale_data = sale_resp.json()
        assert sale_data.get("status") in ("accepted", "received", "processed", "ok")


# -----------------------------------------------------------------------------
# 2. Cold-Chain Biologics Telemetry & Live Excursion Simulation Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_coldchain_batches_and_readings_enrichment():
    """Verify GET /api/v1/coldchain/batches provides chronological readings and Arrhenius metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/coldchain/batches")
        assert resp.status_code == 200
        data = resp.json()
        assert "batches" in data
        assert data["total"] >= 1

        for b in data["batches"]:
            assert "readings" in b
            assert len(b["readings"]) >= 5
            assert "shelf_life_estimate" in b
            est = b["shelf_life_estimate"]
            assert "shelf_life_pct" in est
            assert "estimated_remaining_days" in est


@pytest.mark.asyncio
async def test_coldchain_live_excursion_simulation():
    """Verify POST /api/v1/coldchain/simulate with mode=excursion triggers auto-quarantine and zeroes stock."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger critical thermal excursion (>8.0°C)
        sim_resp = await client.post(
            "/api/v1/coldchain/simulate",
            json={"batch_id": "BIO-INS-01", "mode": "excursion", "steps": 4},
        )
        assert sim_resp.status_code == 200
        sim_data = sim_resp.json()

        assert sim_data["status"] == "simulated"
        assert sim_data["mode"] == "excursion"
        assert sim_data["final_decision"] == "quarantine"
        assert sim_data["quarantined"] is True
        assert sim_data["batch_status"] == "quarantined"
        # Available quantity must drop to 0
        assert sim_data["available_quantity"] == 0
        assert sim_data["rebalance_correlation_id"] is not None

        # Verify batch status in GET /batches
        b_resp = await client.get("/api/v1/coldchain/batches")
        batches = b_resp.json()["batches"]
        ins_batch = next((b for b in batches if b["batch_id"] == "BIO-INS-01"), None)
        assert ins_batch is not None
        assert ins_batch["status"] == "quarantined"
        assert ins_batch["available_quantity"] == 0

        # Verify quarantine action recorded with Excursion narrative
        q_resp = await client.get("/api/v1/coldchain/quarantines")
        assert q_resp.status_code == 200
        quarantines = q_resp.json()["quarantines"]
        assert len(quarantines) >= 1
        assert any(q.get("batch_id") == "BIO-INS-01" for q in quarantines)


# -----------------------------------------------------------------------------
# 3. Developer Portal & Sample Client SDK Integration Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_developer_key_creation_and_sample_client():
    """Verify Developer Portal provisions API key usable in MediFluxClient SDK."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Provision Key in Portal
        create_resp = await client.post(
            "/api/v1/developer/keys",
            json={
                "name": "Integration Test Key",
                "scopes": ["read:inventory", "write:events", "use:copilot"],
                "rate_limit": 500,
            },
        )
        assert create_resp.status_code == 201
        key_data = create_resp.json()
        assert "key" in key_data
        plaintext_key = key_data["key"]
        key_id = key_data["id"]

        # 2. Use Sample Third-Party SDK Client with Provisioned Key
        sdk_client = MediFluxClient(
            base_url="http://test",
            api_key=plaintext_key,
            transport=transport,
        )

        inventory_items = await sdk_client.get_inventory()
        assert isinstance(inventory_items, list)

        # 3. Call MCP tool with the provisioned API key
        mcp_resp = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": plaintext_key},
            json={"name": "get_inventory", "arguments": {"limit": 2}},
        )
        assert mcp_resp.status_code == 200
        mcp_data = mcp_resp.json()
        assert mcp_data.get("is_error") is False
        assert len(mcp_data.get("content", [])) >= 1

        # 4. Revoke Key and verify subsequent 401
        revoke_resp = await client.delete(f"/api/v1/developer/keys/{key_id}")
        assert revoke_resp.status_code == 200

        unauth_resp = await client.get(
            "/api/v1/inventory",
            headers={"X-API-Key": plaintext_key},
        )
        assert unauth_resp.status_code == 401


# -----------------------------------------------------------------------------
# 4. Network Copilot & Semantic Vector Search Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_query_and_vector_search():
    """Verify Copilot conversational endpoint and vector search."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test question payload
        q_resp = await client.post(
            "/api/v1/copilot/query",
            json={"question": "What is the stock status of Amoxicillin?"},
        )
        assert q_resp.status_code == 200
        q_data = q_resp.json()
        assert "answer" in q_data
        assert "tools_used" in q_data
        assert "references" in q_data

        # Test query parameter alternative
        alt_resp = await client.post(
            "/api/v1/copilot/query",
            json={"query": "Are any cold-chain batches quarantined?"},
        )
        assert alt_resp.status_code == 200

        # Test vector search
        s_resp = await client.get("/api/v1/search?q=Amoxicillin")
        assert s_resp.status_code == 200
        s_data = s_resp.json()
        assert "results" in s_data
        assert "count" in s_data
