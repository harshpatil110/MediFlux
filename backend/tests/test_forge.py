"""Automated test suite for Task 17 Adapter Forge and Marketplace API."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.events.service import clear_service_state, get_in_memory_stock, set_in_memory_stock
from app.graphs.forge import (
    clear_adapter_store,
    get_adapter,
    run_forge,
)
from app.main import app
from app.modules_runtime.guard import ASTGuard, GuardViolationError
from app.modules_runtime.registry import module_registry


def _load_fixture(name: str) -> str:
    """Resolve fixture file whether running from repo root or backend/."""
    candidates = [
        Path("fixtures/legacy") / name,
        Path("backend/fixtures/legacy") / name,
        Path("../fixtures/legacy") / name,
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Fixture {name} not found in candidate paths.")


@pytest.fixture(autouse=True)
def clean_environment():
    """Ensure clean stores between test runs."""
    clear_adapter_store()
    clear_service_state()
    module_registry.clear()
    with patch.object(settings, "SUPABASE_URL", ""):
        yield
    clear_adapter_store()
    clear_service_state()
    module_registry.clear()


# -----------------------------------------------------------------------------
# 1. Format Auto-Translation Tests (CSV, XML, Nested JSON)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_csv_auto_translation():
    """Verify Forge autonomously translates pharmacy billing CSV into valid SaleEvent adapter."""
    csv_raw = _load_fixture("pharmacy_billing_sample.csv")
    csv_expected = json.loads(_load_fixture("pharmacy_billing_expected.json"))

    state = await run_forge(
        name="pharmacy_csv_adapter",
        raw_sample=csv_raw,
        expected_output=csv_expected,
        target_schema="SaleEvent",
    )

    assert state.get("status") == "succeeded"
    assert state.get("adapter_id") is not None
    assert state.get("version") == 1

    adapter = get_adapter("pharmacy_csv_adapter")
    assert adapter is not None
    assert adapter["status"] == "active"
    assert adapter["test_results"]["passed"] is True
    assert adapter["test_results"]["actual_output"] == csv_expected


@pytest.mark.asyncio
async def test_xml_auto_translation():
    """Verify Forge autonomously translates manufacturer ERP XML into valid BatchUpdate adapter."""
    xml_raw = _load_fixture("manufacturer_erp_sample.xml")
    xml_expected = json.loads(_load_fixture("manufacturer_erp_expected.json"))

    state = await run_forge(
        name="manufacturer_erp_adapter",
        raw_sample=xml_raw,
        expected_output=xml_expected,
        target_schema="BatchUpdate",
    )

    assert state.get("status") == "succeeded"
    assert state.get("adapter_id") is not None

    adapter = get_adapter("manufacturer_erp_adapter")
    assert adapter is not None
    assert adapter["status"] == "active"
    assert adapter["test_results"]["passed"] is True
    assert adapter["test_results"]["actual_output"] == xml_expected


@pytest.mark.asyncio
async def test_nested_json_auto_translation():
    """Verify Forge autonomously translates nested legacy POS JSON into valid SaleEvent adapter."""
    json_raw = json.loads(_load_fixture("nested_legacy_pos_sample.json"))
    json_expected = json.loads(_load_fixture("nested_legacy_pos_expected.json"))

    state = await run_forge(
        name="nested_pos_json_adapter",
        raw_sample=json_raw,
        expected_output=json_expected,
        target_schema="SaleEvent",
    )

    assert state.get("status") == "succeeded"
    assert state.get("adapter_id") is not None

    adapter = get_adapter("nested_pos_json_adapter")
    assert adapter is not None
    assert adapter["status"] == "active"
    assert adapter["test_results"]["passed"] is True
    assert adapter["test_results"]["actual_output"] == json_expected


# -----------------------------------------------------------------------------
# 2. Guard Violation & Fix-Loop Self-Healing Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_guard_violation_and_self_healing():
    """Verify that malicious/forbidden code triggers guard violation, enters fix loop, and self-heals."""
    csv_raw = _load_fixture("pharmacy_billing_sample.csv")
    csv_expected = json.loads(_load_fixture("pharmacy_billing_expected.json"))

    bad_initial_code = """import os
def run(input_data):
    return {}
"""
    # Verify the bad code itself violates the AST guard
    with pytest.raises(GuardViolationError):
        ASTGuard.validate_code(bad_initial_code)

    state = await run_forge(
        name="self_healing_adapter",
        raw_sample=csv_raw,
        expected_output=csv_expected,
        target_schema="SaleEvent",
        injected_bad_code=bad_initial_code,
    )

    assert state.get("status") == "succeeded"
    # Check that error was logged during attempt 0
    assert len(state.get("error_logs", [])) >= 1
    assert any("Guard violation" in err for err in state["error_logs"])

    # Check that fix_loop emitted fixing event
    events = state.get("events", [])
    steps = [e.get("step") for e in events]
    assert "fixing" in steps
    assert "registered" in steps

    # Final adapter is active and functional
    adapter = get_adapter("self_healing_adapter")
    assert adapter is not None
    assert adapter["status"] == "active"


# -----------------------------------------------------------------------------
# 3. Max Attempts Exhaustion / Failure Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_max_attempts_exhaustion_marks_failed():
    """Verify that an adapter that consistently fails is cleanly marked failed after max_attempts."""
    # We patch synthesize_guard_compliant_adapter to always return code that raises an error
    unfixable_code = """def run(input_data):
    raise RuntimeError("Permanent hardware decoding failure")
"""
    with patch("app.graphs.forge.synthesize_guard_compliant_adapter", return_value=unfixable_code):
        state = await run_forge(
            name="failing_adapter",
            raw_sample="CORRUPTED_RAW_STREAM",
            expected_output={"pharmacy_id": "P1"},
            target_schema="SaleEvent",
            max_attempts=2,
        )

    assert state.get("status") == "failed"
    adapter = get_adapter("failing_adapter")
    assert adapter is not None
    assert adapter["status"] == "failed"
    assert adapter["is_active"] is False


# -----------------------------------------------------------------------------
# 4. Live Legacy Ingestion Endpoint Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_live_legacy_ingestion_cascade():
    """Verify POST /api/v1/ingest/{adapter_id} executes adapter in guard and cascades into inventory."""
    csv_raw = _load_fixture("pharmacy_billing_sample.csv")
    csv_expected = json.loads(_load_fixture("pharmacy_billing_expected.json"))

    # 1. Generate active adapter
    state = await run_forge(
        name="pos_csv_ingest_adapter",
        raw_sample=csv_raw,
        expected_output=csv_expected,
        target_schema="SaleEvent",
    )
    adapter_id = state.get("adapter_id")
    assert adapter_id is not None

    # 2. Seed in-memory stock for the dispensing pharmacy
    pharmacy_id = csv_expected["pharmacy_id"]
    product_id = csv_expected["product_id"]
    batch_id = csv_expected["batch_id"]
    set_in_memory_stock(pharmacy_id, product_id, batch_id, 50)
    assert get_in_memory_stock(pharmacy_id, product_id, batch_id) == 50

    # 3. Post legacy CSV directly to the ingest endpoint
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/ingest/{adapter_id}",
            content=csv_raw,
            headers={"Content-Type": "text/csv", "X-Correlation-ID": "test-corr-csv-001"},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["event_type"] == "pos.sales"
    assert data["canonical_event"]["pharmacy_id"] == pharmacy_id
    assert data["canonical_event"]["quantity"] == 2

    # Verify inventory was decremented from 50 to 48
    assert get_in_memory_stock(pharmacy_id, product_id, batch_id) == 48


# -----------------------------------------------------------------------------
# 5. Marketplace Generation & SSE Streaming Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_marketplace_generation_and_sse_streaming():
    """Verify POST /api/v1/adapters/generate and GET /api/v1/adapters/jobs/{id}/stream."""
    csv_raw = _load_fixture("pharmacy_billing_sample.csv")
    csv_expected = json.loads(_load_fixture("pharmacy_billing_expected.json"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Generate
        gen_res = await client.post(
            "/api/v1/adapters/generate",
            json={
                "name": "stream_test_adapter",
                "sample_payload": csv_raw,
                "expected_output": csv_expected,
                "target_schema": "SaleEvent",
            },
        )
        assert gen_res.status_code == 202
        gen_data = gen_res.json()
        job_id = gen_data["job_id"]
        assert gen_data["status"] == "succeeded"

        # Poll JSON job status
        poll_res = await client.get(f"/api/v1/adapters/jobs/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        assert poll_data["status"] == "succeeded"
        assert len(poll_data["events"]) >= 3

        # Stream SSE progress
        stream_res = await client.get(
            f"/api/v1/adapters/jobs/{job_id}/stream",
            headers={"Accept": "text/event-stream"},
        )
        assert stream_res.status_code == 200
        stream_text = stream_res.text
        assert "event: inspecting" in stream_text or "event: coding" in stream_text
        assert "event: done" in stream_text


# -----------------------------------------------------------------------------
# 6. Adapter Catalog & Hot-Swap Version Rollback Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_adapter_catalog_and_version_rollback():
    """Verify listing, details lookup, and atomic hot-swap rollback to prior versions."""
    raw_sample = {"outlet_ref": "STORE-1", "sku": "DRUG-1", "lot": "LOT-1", "qty": 1}
    exp_output = {"pharmacy_id": "STORE-1", "product_id": "DRUG-1", "batch_id": "LOT-1", "quantity": 1, "source": "pos"}

    # Version 1
    state_v1 = await run_forge(
        name="rollback_demo_adapter",
        raw_sample=raw_sample,
        expected_output=exp_output,
        description="Version 1 Initial",
    )
    assert state_v1.get("version") == 1

    # Version 2
    state_v2 = await run_forge(
        name="rollback_demo_adapter",
        raw_sample=raw_sample,
        expected_output=exp_output,
        description="Version 2 Updated",
    )
    assert state_v2.get("version") == 2

    # Verify active is v2
    active_ad = get_adapter("rollback_demo_adapter")
    assert active_ad["version"] == 2

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Catalog list
        list_res = await client.get("/api/v1/adapters")
        assert list_res.status_code == 200
        adapters = list_res.json()
        assert any(a["name"] == "rollback_demo_adapter" for a in adapters)

        # Adapter details
        det_res = await client.get("/api/v1/adapters/rollback_demo_adapter")
        assert det_res.status_code == 200
        det_data = det_res.json()
        assert det_data["adapter"]["version"] == 2
        assert len(det_data["versions"]) == 2

        # Rollback via API
        rb_res = await client.post(
            "/api/v1/adapters/rollback_demo_adapter/rollback",
            json={"target_version": 1},
        )
        assert rb_res.status_code == 200
        rb_data = rb_res.json()
        assert rb_data["status"] == "rolled_back"
        assert rb_data["active_version"] == 1

    # Verify current active in storage is now v1
    rolled_back = get_adapter("rollback_demo_adapter")
    assert rolled_back["version"] == 1
    assert rolled_back["status"] == "active"
