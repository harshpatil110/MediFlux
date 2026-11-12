"""Automated test suite for Task 18 Regulatory Pipeline and Zero-Downtime Hot-Swap."""

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.audit_ledger import get_in_memory_audit_ledger
from app.core.config import settings
from app.core.hitl import clear_hitl_tasks
from app.graphs.regulatory import (
    activate_regulatory_run,
    clear_regulatory_store,
    crawl_regulatory_notice,
    ensure_baseline_regulatory_modules,
    run_regulatory_pipeline,
)
from app.main import app
from app.modules_runtime.registry import module_registry


def _load_reg_fixture(name: str) -> str:
    """Resolve regulatory fixture from repo root or backend/."""
    candidates = [
        Path("fixtures/regulatory") / name,
        Path("backend/fixtures/regulatory") / name,
        Path("../fixtures/regulatory") / name,
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Regulatory fixture '{name}' not found.")


@pytest.fixture(autouse=True)
def clean_regulatory_env():
    """Ensure clean module registry and regulatory state between tests."""
    clear_regulatory_store()
    clear_hitl_tasks()
    module_registry.clear()
    with patch.object(settings, "SUPABASE_URL", ""):
        ensure_baseline_regulatory_modules()
        yield
    clear_regulatory_store()
    clear_hitl_tasks()
    module_registry.clear()


# -----------------------------------------------------------------------------
# 1. Price Ceiling Notice Ingestion to Staging
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_price_ceiling_notice_to_staging():
    """Verify NPPA price ceiling notice generates v2 code, tests in guard, and pauses in staging."""
    notice_text = _load_reg_fixture("nppa_price_ceiling_notice.txt")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/regulatory/notifications",
            json={"text": notice_text, "source": "nppa", "title": "DPCO Paracetamol Ceiling"},
        )
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "awaiting_approval"
        assert data["staged_version"] == 2
        assert data["active_version"] == 1
        assert data["hitl_task_id"] is not None

        # Verify diff was generated
        diff = data["diff"]
        assert "---" in diff and "+++" in diff
        assert "12.5" in diff

        # Verify tests passed
        test_results = data["test_results"]
        assert test_results["passed"] is True
        assert test_results["guard_passed"] is True

        # Active version in module registry MUST still be v1 before approval
        active_mod = module_registry.get_active("pricing_engine")
        assert active_mod is not None
        assert active_mod.version == 1


# -----------------------------------------------------------------------------
# 2. Zero-Downtime Hot-Swap Verification
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_zero_downtime_hot_swap():
    """Verify live pricing calculation uses v1 before approval, v2 price cap after approval, and writes audit ledger."""
    notice_text = _load_reg_fixture("nppa_price_ceiling_notice.txt")
    notice = crawl_regulatory_notice(text=notice_text, source="nppa", title="DPCO Notice")
    run_state = await run_regulatory_pipeline(
        notification_id=notice["id"],
        notification_text=notice["full_text"],
    )
    run_id = run_state["id"]
    assert run_state["status"] == "awaiting_approval"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Before approval: price check with unit_price = 25.0 must NOT be capped
        before_res = await client.post(
            "/api/v1/regulatory/price-check",
            json={"sku": "PARA-500", "unit_price": 25.0, "quantity": 2},
        )
        assert before_res.status_code == 200
        before_data = before_res.json()
        assert before_data["active_version"] == 1
        assert before_data["result"]["effective_price"] == 25.0
        assert before_data["result"]["total_amount"] == 50.0
        assert before_data["result"]["price_capped"] is False

        # 2. Approve the regulatory run
        app_res = await client.post(
            f"/api/v1/regulatory/runs/{run_id}/approve?approver=human:compliance_head",
        )
        assert app_res.status_code == 200
        assert app_res.json()["status"] == "deployed"
        assert app_res.json()["active_version"] == 2

        # 3. Immediately after approval: price check MUST enforce new 12.50 ceiling without server restart!
        after_res = await client.post(
            "/api/v1/regulatory/price-check",
            json={"sku": "PARA-500", "unit_price": 25.0, "quantity": 2},
        )
        assert after_res.status_code == 200
        after_data = after_res.json()
        assert after_data["active_version"] == 2
        assert after_data["result"]["effective_price"] == 12.50
        assert after_data["result"]["total_amount"] == 25.0
        assert after_data["result"]["price_capped"] is True
        assert after_data["result"]["ceiling_applied"] == 12.50

    # 4. Verify audit ledger entry was written
    audit_entries = get_in_memory_audit_ledger()
    hot_swap_entry = next((e for e in audit_entries if e.get("action") == "REGULATORY_HOT_SWAP_DEPLOYED"), None)
    assert hot_swap_entry is not None
    assert hot_swap_entry["actor"] == "human:compliance_head"
    assert hot_swap_entry["entity_id"] == "pricing_engine"


# -----------------------------------------------------------------------------
# 3. Instant Rollback Verification
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_instant_rollback():
    """Verify rollback reverts active module pointer and restores v1 pricing immediately."""
    notice_text = _load_reg_fixture("nppa_price_ceiling_notice.txt")
    notice = crawl_regulatory_notice(text=notice_text, source="nppa")
    run_state = await run_regulatory_pipeline(notice["id"], notice["full_text"])
    run_id = run_state["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Deploy v2
        await client.post(f"/api/v1/regulatory/runs/{run_id}/approve")
        assert module_registry.get_active("pricing_engine").version == 2

        # Trigger rollback via API
        rb_res = await client.post(f"/api/v1/regulatory/runs/{run_id}/rollback")
        assert rb_res.status_code == 200
        assert rb_res.json()["status"] == "rolled_back"
        assert rb_res.json()["active_version"] == 1

        # Live pricing must immediately reflect restored v1 behavior
        check_res = await client.post(
            "/api/v1/regulatory/price-check",
            json={"sku": "PARA-500", "unit_price": 25.0, "quantity": 2},
        )
        assert check_res.status_code == 200
        check_data = check_res.json()
        assert check_data["active_version"] == 1
        assert check_data["result"]["effective_price"] == 25.0
        assert check_data["result"]["total_amount"] == 50.0

    # Verify audit ledger rollback record
    audit_entries = get_in_memory_audit_ledger()
    rb_entry = next((e for e in audit_entries if e.get("action") == "REGULATORY_HOT_SWAP_ROLLED_BACK"), None)
    assert rb_entry is not None


# -----------------------------------------------------------------------------
# 4. Guard Rejection & Max Attempts Failure Safety
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_guard_rejection_and_max_attempts_safety():
    """Verify that code violating the Restricted Guard triggers retry loop, fails, and NEVER activates."""
    bad_code = """import os
def run(input_data):
    os.system("echo breach")
    return {}
"""
    notice_text = _load_reg_fixture("nppa_price_ceiling_notice.txt")
    notice = crawl_regulatory_notice(text=notice_text, source="nppa")

    # Inject bad code and set max_attempts=2
    run_res = await run_regulatory_pipeline(
        notification_id=notice["id"],
        notification_text=notice["full_text"],
        max_attempts=2,
        injected_bad_code=bad_code,
    )

    # When injected code violates guard on every attempt, it marks failed
    assert run_res["status"] == "failed"

    # Active module MUST still be v1
    active_mod = module_registry.get_active("pricing_engine")
    assert active_mod.version == 1


# -----------------------------------------------------------------------------
# 5. Low-Confidence Ambiguous Notice Gate
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_low_confidence_gate_to_hitl():
    """Verify that corrupt or ambiguous notices pause at awaiting_hitl_clarification without code mutation."""
    corrupt_text = _load_reg_fixture("corrupt_or_untestable_notice.txt")
    notice = crawl_regulatory_notice(text=corrupt_text, source="unknown")

    run_res = await run_regulatory_pipeline(
        notification_id=notice["id"],
        notification_text=notice["full_text"],
    )

    assert run_res["status"] == "awaiting_hitl_clarification"
    assert run_res["confidence"] < 0.70
    assert run_res["hitl_task_id"] is not None

    # Staged version was NOT generated
    assert run_res.get("diff") == ""


# -----------------------------------------------------------------------------
# 6. CDSCO Track-and-Trace Compliance Mutation
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_track_and_trace_compliance_mutation():
    """Verify CDSCO notice mutates compliance_validator to enforce GTIN barcode."""
    cdsco_text = _load_reg_fixture("cdsco_track_and_trace_notice.txt")
    notice = crawl_regulatory_notice(text=cdsco_text, source="cdsco", title="Track and Trace Directive")

    run_res = await run_regulatory_pipeline(
        notification_id=notice["id"],
        notification_text=notice["full_text"],
    )

    assert run_res["status"] == "awaiting_approval"
    assert run_res["target_module_name"] == "compliance_validator"
    assert run_res["staged_version"] == 2
    assert run_res["test_results"]["passed"] is True

    # Activate and test compliance validator v2
    await activate_regulatory_run(run_res["id"])
    active_mod = module_registry.get_active("compliance_validator")
    assert active_mod.version == 2

    # Compliant with GTIN and batch_no
    out_valid = module_registry.run_module("compliance_validator", {
        "schedule_h": False,
        "gtin_barcode": "GTIN-88991122",
        "batch_no": "B-9912",
    })
    assert out_valid["compliant"] is True

    # Non-compliant without barcode
    out_invalid = module_registry.run_module("compliance_validator", {
        "schedule_h": False,
        "gtin_barcode": None,
        "batch_no": "B-9912",
    })
    assert out_invalid["compliant"] is False


# -----------------------------------------------------------------------------
# 7. Check-Now Endpoint
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_manual_check_now_endpoint():
    """Verify POST /api/v1/regulatory/check-now crawls configured sources and executes pipeline."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/regulatory/check-now")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 2
        sources = {item["source"] for item in data}
        assert "nppa" in sources
        assert "cdsco" in sources


# -----------------------------------------------------------------------------
# 8. Notifications and Runs Catalog Query Endpoints
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_notifications_and_runs_catalog_queries():
    """Verify GET /api/v1/regulatory/notifications and GET /api/v1/regulatory/runs/{id}."""
    notice_text = _load_reg_fixture("nppa_price_ceiling_notice.txt")
    notice = crawl_regulatory_notice(text=notice_text, source="nppa", title="Catalog DPCO Test")
    run_res = await run_regulatory_pipeline(notice["id"], notice["full_text"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # List notifications
        list_res = await client.get("/api/v1/regulatory/notifications")
        assert list_res.status_code == 200
        notifications = list_res.json()
        assert any(n["content_hash"] == notice["content_hash"] for n in notifications)

        # Get run details
        run_id = run_res["id"]
        run_detail_res = await client.get(f"/api/v1/regulatory/runs/{run_id}")
        assert run_detail_res.status_code == 200
        detail = run_detail_res.json()
        assert detail["id"] == run_id
        assert detail["target_module_name"] == "pricing_engine"
        assert detail["staged_version"] == 2
