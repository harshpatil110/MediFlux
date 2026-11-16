"""Automated test suite for Task M8: Network Copilot and Cascade History (Lite).

Covers all 3 Acceptance Criteria:
1. AC #1: Stockout Risk Copilot Question & Tappable References (grounded answer, tools_used, activity_steps, references).
2. AC #2: Strict Pharmacy RLS Isolation in Copilot (Pharmacy A queries never leak Pharmacy B rows or references).
3. AC #3: Cascade Listing Endpoint (GET /api/v1/cascade) & 5-Stage Replay Trace (GET /api/v1/cascade/{correlation_id}).
And friendly LLM error code mapping (429, 503, 403).
"""

from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from app.api.v1.endpoints.auth import SEEDED_DEMO_USERS
from app.api.v1.endpoints.cascade import _seed_initial_cascades_if_empty
from app.main import app

# Test users
ADMIN_USER = next(u for u in SEEDED_DEMO_USERS if u["role"] == "admin")
PHARMACY_A_USER = next(u for u in SEEDED_DEMO_USERS if u["role"] == "pharmacy")

PHARMACY_A_NODE_ID = "11111111-1111-1111-1111-111111111111"
PHARMACY_B_NODE_ID = "11111111-1111-1111-1111-111111111121"


def _get_headers_for(user_dict: dict[str, Any]) -> dict[str, str]:
    role = str(user_dict.get("role", "user"))
    token = str(user_dict.get("token") or f"mock-{role}-token")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _get_pharmacy_b_headers() -> dict[str, str]:
    return {
        "X-User-Role": "pharmacy",
        "X-Node-Id": PHARMACY_B_NODE_ID,
        "X-User-Id": "usr-pharmacy-b-demo",
        "Content-Type": "application/json",
    }


@pytest.fixture(autouse=True)
def _reset_cascades():
    """Ensure baseline cascades are seeded before every test."""
    _seed_initial_cascades_if_empty()
    yield


# -----------------------------------------------------------------------------
# AC #3: Cascade Listing (GET /api/v1/cascade) & 5-Stage Trace Replay
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cascade_listing_endpoint_baseline_and_schema():
    """AC #3: Verify GET /api/v1/cascade returns populated list with required schema."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/cascade?limit=25", headers=_get_headers_for(ADMIN_USER))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3, "Must have at least 3 baseline seeded cascades"

        for item in data:
            assert "correlation_id" in item
            assert "product_name" in item
            assert "pharmacy_name" in item
            assert "created_at" in item
            assert "outcome" in item
            assert item["outcome"] in ("complete", "partial", "waiting_approval")
            assert "steps_completed" in item
            assert "total_steps" in item
            assert "total_duration_ms" in item
            assert "total_tokens" in item
            assert "summary" in item


@pytest.mark.asyncio
async def test_cascade_history_rls_filtering():
    """AC #3: Pharmacy A caller sees only its cascades; Pharmacy B sees only its cascades."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Pharmacy A query
        resp_a = await client.get("/api/v1/cascade?limit=25", headers=_get_headers_for(PHARMACY_A_USER))
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        cids_a = {item["correlation_id"] for item in data_a}
        assert "casc-seed-01" in cids_a
        assert "casc-seed-02" in cids_a
        assert "casc-seed-03" not in cids_a, "Pharmacy A must not see Pharmacy B's cascade (casc-seed-03)"

        # 2. Pharmacy B query
        resp_b = await client.get("/api/v1/cascade?limit=25", headers=_get_pharmacy_b_headers())
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        cids_b = {item["correlation_id"] for item in data_b}
        assert "casc-seed-03" in cids_b
        assert "casc-seed-01" not in cids_b, "Pharmacy B must not see Pharmacy A's cascade"
        assert "casc-seed-02" not in cids_b, "Pharmacy B must not see Pharmacy A's cascade"

        # 3. Admin query sees all
        resp_admin = await client.get("/api/v1/cascade?limit=25", headers=_get_headers_for(ADMIN_USER))
        assert resp_admin.status_code == 200
        data_admin = resp_admin.json()
        cids_admin = {item["correlation_id"] for item in data_admin}
        assert "casc-seed-01" in cids_admin
        assert "casc-seed-02" in cids_admin
        assert "casc-seed-03" in cids_admin


@pytest.mark.asyncio
async def test_cascade_outcome_filtering():
    """AC #3: Verify outcome query parameter correctly filters cascades."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/cascade?outcome=waiting_approval", headers=_get_headers_for(ADMIN_USER))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert item["outcome"] == "waiting_approval"


@pytest.mark.asyncio
async def test_cascade_trace_full_5_stages_replay():
    """AC #3: Verify GET /api/v1/cascade/{correlation_id} returns all 5 stages for replay."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for cid in ["casc-seed-01", "casc-seed-02", "casc-seed-03"]:
            resp = await client.get(f"/api/v1/cascade/{cid}", headers=_get_headers_for(ADMIN_USER))
            assert resp.status_code == 200, f"Failed for {cid}: {resp.text}"
            data = resp.json()
            assert data["correlation_id"] == cid
            assert "steps" in data
            steps = data["steps"]
            assert len(steps) == 5, f"Expected 5 stages, got {len(steps)} for {cid}"

            # Verify order of 5 stages
            expected_stages = ["supervisor", "pharmacy", "stockist", "distributor", "manufacturer"]
            for idx, stage_name in enumerate(expected_stages):
                step = steps[idx]
                assert step["stage"] == stage_name, f"Step {idx} expected {stage_name}, got {step['stage']}"
                assert "tier" in step
                assert "node_id" in step
                assert "reasoning" in step


# -----------------------------------------------------------------------------
# AC #1: Stockout Risk Copilot Question & Tappable References
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_stockout_risk_question_and_references():
    """AC #1: POST /api/v1/copilot/query returns grounded answer, activity_steps, and references."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"question": "Which pharmacies are at risk of running out of Paracetamol 500mg?"}
        resp = await client.post("/api/v1/copilot/query", json=payload, headers=_get_headers_for(ADMIN_USER))
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "answer" in data and len(data["answer"]) > 10
        assert "trace_id" in data
        assert "tools_used" in data
        assert "get_stockout_risk" in data["tools_used"]
        assert "activity_steps" in data
        assert len(data["activity_steps"]) >= 2

        # Check references contract
        assert "references" in data
        refs = data["references"]
        assert len(refs) > 0, "Stockout risk query must return structured references"

        first_ref = refs[0]
        assert "id" in first_ref
        assert "type" in first_ref
        assert first_ref["type"] in ("inventory", "batch", "approval", "cascade", "node")
        assert "label" in first_ref
        assert "node_id" in first_ref
        assert "deep_link" in first_ref
        assert "/(tabs)/sell" in first_ref["deep_link"] or "/" in first_ref["deep_link"]


# -----------------------------------------------------------------------------
# AC #2: Strict Pharmacy RLS Isolation in Copilot
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_strict_pharmacy_rls_isolation():
    """AC #2: Pharmacy A query strictly isolates data; zero rows/references for Pharmacy B."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Pharmacy A asks about Pharmacy B explicitly
        payload = {
            "question": f"Show me the inventory and stockout risk of Pharmacy B ({PHARMACY_B_NODE_ID})",
            "node_id": PHARMACY_B_NODE_ID,  # Pharmacy trying to override node_id
        }
        resp = await client.post("/api/v1/copilot/query", json=payload, headers=_get_headers_for(PHARMACY_A_USER))
        assert resp.status_code == 200
        data = resp.json()

        # 1. Zero references belonging to Pharmacy B
        refs = data.get("references", [])
        for ref in refs:
            assert ref.get("node_id") != PHARMACY_B_NODE_ID, "Must not leak references for Pharmacy B"

        # 2. Answer must explicitly state RLS isolation notice
        answer = data.get("answer", "")
        assert "restricted" in answer.lower() or "isolation" in answer.lower(), (
            f"Expected RLS isolation notice in answer: {answer}"
        )


# -----------------------------------------------------------------------------
# Friendly Error Handling (Task M8.3)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_error_mapping_429_provider_busy():
    """Task M8.3: Verify 429 returns standard LLM_PROVIDER_BUSY payload with retryable=True."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = dict(_get_headers_for(ADMIN_USER), **{"X-Test-Error": "429"})
        resp = await client.post("/api/v1/copilot/query", json={"question": "Test error"}, headers=headers)
        assert resp.status_code == 429
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "LLM_PROVIDER_BUSY"
        assert data["error"]["details"]["retryable"] is True


@pytest.mark.asyncio
async def test_copilot_error_mapping_503_local_offline():
    """Task M8.3: Verify 503 returns SOVEREIGN_LOCAL_MODEL_OFFLINE."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = dict(_get_headers_for(ADMIN_USER), **{"X-Test-Error": "503"})
        resp = await client.post("/api/v1/copilot/query", json={"question": "Test offline"}, headers=headers)
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "SOVEREIGN_LOCAL_MODEL_OFFLINE"


@pytest.mark.asyncio
async def test_copilot_error_mapping_403_forbidden_scope():
    """Task M8.3: Verify 403 returns COPILOT_FORBIDDEN_SCOPE."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = dict(_get_headers_for(ADMIN_USER), **{"X-Test-Error": "403"})
        resp = await client.post("/api/v1/copilot/query", json={"question": "Test forbidden"}, headers=headers)
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "COPILOT_FORBIDDEN_SCOPE"
        assert data["error"]["details"]["retryable"] is False
