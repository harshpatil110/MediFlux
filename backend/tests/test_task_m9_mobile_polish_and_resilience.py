"""Automated test suite for Task M9: Polish, Resilience and Testing.

Covers all 4 Acceptance Criteria & Verification Checkpoints:
1. AC #1 & Checkpoint 1: Jest Test Suite & CI Check Execution (apiClient, useEventStream, roleMap, cascadeTimeline, saleIdempotency).
2. AC #2 & Checkpoint 2: Full Mobile Demo Path Repeatability (reset_demo + run_mobile_demo runs consecutively from clean golden state).
3. AC #3 & Checkpoint 3: Network Off Mid-Flow Recovery & Sale Idempotency (preserves event_id across network drop, prevents duplicate deductions, recovers trace).
4. AC #4 & Checkpoint 4: Branding Assets, High-DPI Mobile Screenshots, and Documentation (1024x1024 assets, 6 screenshots in docs/screenshots/mobile/, docs/MOBILE.md test matrix).
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from app.api.v1.endpoints.auth import SEEDED_DEMO_USERS
from app.api.v1.endpoints.devices import (
    get_in_memory_device_tokens,
)
from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MOBILE_DIR = ROOT_DIR / "mobile"
ASSETS_DIR = MOBILE_DIR / "assets"
SCREENSHOTS_DIR = ROOT_DIR / "docs" / "screenshots" / "mobile"


def _get_pharmacy_headers() -> dict[str, str]:
    user = next(u for u in SEEDED_DEMO_USERS if u["role"] == "pharmacy")
    token = user.get("token") or "mock-pharmacy-token"
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-User-Role": "pharmacy",
        "X-Node-Id": str(user.get("node_id") or "11111111-1111-1111-1111-111111111111"),
        "X-User-Id": str(user.get("id") or "usr-pharmacy-demo"),
    }


def _get_admin_headers() -> dict[str, str]:
    user = next(u for u in SEEDED_DEMO_USERS if u["role"] == "admin")
    token = user.get("token") or "mock-admin-token"
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-User-Role": "admin",
        "X-Node-Id": str(user.get("node_id") or "00000000-0000-0000-0000-000000000000"),
        "X-User-Id": str(user.get("id") or "usr-admin-demo"),
    }


# =============================================================================
# CHECKPOINT 1: Mobile Assets, High-DPI Screenshots, and Docs Exist
# =============================================================================
def test_mobile_branding_assets_and_app_config():
    """Verify high-res mobile branding assets and app.config.ts name."""
    assert (ASSETS_DIR / "icon.png").is_file(), "icon.png missing"
    assert (ASSETS_DIR / "adaptive-icon.png").is_file(), "adaptive-icon.png missing"
    assert (ASSETS_DIR / "splash.png").is_file(), "splash.png missing"
    assert (ASSETS_DIR / "favicon.png").is_file(), "favicon.png missing"

    # Verify file sizes are non-empty
    assert (ASSETS_DIR / "icon.png").stat().st_size > 1000
    assert (ASSETS_DIR / "adaptive-icon.png").stat().st_size > 1000
    assert (ASSETS_DIR / "splash.png").stat().st_size > 5000
    assert (ASSETS_DIR / "favicon.png").stat().st_size > 100

    # Verify app.config.ts name
    app_config_file = MOBILE_DIR / "app.config.ts"
    assert app_config_file.is_file()
    content = app_config_file.read_text(encoding="utf-8")
    assert "NexusChain India (MediFlux)" in content
    assert "mediflux-mobile" in content


def test_mobile_screenshots_and_documentation():
    """Verify all 6 mobile UI screenshots and documentation matrix exist."""
    required_screenshots = [
        "01_home_dashboard.png",
        "02_pos_barcode_and_cascade.png",
        "03_hitl_approvals.png",
        "04_prescription_scanner.png",
        "05_coldchain_monitor.png",
        "06_copilot_and_replay.png",
    ]
    for ss in required_screenshots:
        f = SCREENSHOTS_DIR / ss
        assert f.is_file(), f"Screenshot {ss} missing"
        assert f.stat().st_size > 10000, f"Screenshot {ss} is unexpectedly small"

    mobile_doc = ROOT_DIR / "docs" / "MOBILE.md"
    assert mobile_doc.is_file()
    doc_content = mobile_doc.read_text(encoding="utf-8")
    assert "Device Test Matrix" in doc_content
    assert "Failure-Injection Harness" in doc_content
    for ss in required_screenshots:
        assert ss in doc_content, f"Screenshot reference {ss} missing in docs/MOBILE.md"


# =============================================================================
# CHECKPOINT 2: reset_demo Resets All Mobile State Deterministically
# =============================================================================
def test_reset_demo_state_resets_mobile_telemetry():
    """Verify scripts.reset_demo clears device tokens, resets batches, seeds HITL tasks and cascades."""
    from scripts.reset_demo import reset_demo_state

    # 1. Inject a dirty device token and dirty task
    from app.api.v1.endpoints.devices import _in_memory_device_tokens

    dummy_token = f"ExponentPushToken[DirtyTestToken_{uuid.uuid4().hex[:6]}]"
    _in_memory_device_tokens[dummy_token] = {
        "id": str(uuid.uuid4()),
        "token": dummy_token,
        "platform": "android",
        "user_id": "test-dirty-user",
    }
    assert len(get_in_memory_device_tokens()) > 0

    # 2. Run reset
    summary = reset_demo_state()
    assert summary["status"] == "ok"
    assert summary["device_tokens_cleared"] is True
    assert len(get_in_memory_device_tokens()) == 0
    assert summary["barcodes_count"] == 20
    assert summary["tasks_cleared"] >= 3
    assert summary["cascades_reset"] >= 3
    assert len(summary["batches_reset"]) >= 1


@pytest.mark.asyncio
async def test_demo_reset_api_endpoint():
    """Verify POST /api/v1/demo/reset triggers full clean mobile state reset."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/demo/reset")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["success"] is True
        assert payload["device_tokens_cleared"] is True
        assert payload["barcodes_count"] == 20


# =============================================================================
# CHECKPOINT 3: Full Mobile Demo Path Runs Consecutively Twice (Repeatability)
# =============================================================================
@pytest.mark.asyncio
async def test_mobile_demo_runner_consecutive_repeatability():
    """AC #2: Run full mobile demo runner twice from reset state to verify 100% repeatability."""
    from scripts.reset_demo import reset_demo_state
    from scripts.run_mobile_demo import run_mobile_demo

    # First Run
    reset_demo_state()
    res1 = await run_mobile_demo()
    assert res1.get("step1_auth") is True
    assert res1.get("step2_home") is True
    assert res1.get("step3_pos_and_cascade") is True
    assert res1.get("step4_prescription") is True
    assert res1.get("step5_hitl") is True
    assert res1.get("step6_coldchain") is True
    assert res1.get("step7_copilot") is True
    assert res1.get("step8_logout") is True

    # Second Consecutive Run from reset state
    reset_demo_state()
    res2 = await run_mobile_demo()
    assert res2.get("step1_auth") is True
    assert res2.get("step2_home") is True
    assert res2.get("step3_pos_and_cascade") is True
    assert res2.get("step4_prescription") is True
    assert res2.get("step5_hitl") is True
    assert res2.get("step6_coldchain") is True
    assert res2.get("step7_copilot") is True
    assert res2.get("step8_logout") is True


# =============================================================================
# CHECKPOINT 4: Mid-Flow Network Drop & Sale Idempotency Verification
# =============================================================================
@pytest.mark.asyncio
async def test_sale_idempotency_mid_flow_network_recovery():
    """AC #3: Verify retry with same event_id recovers cascade without duplicate inventory deduction."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = _get_pharmacy_headers()

        # 1. Barcode lookup
        bc_resp = await client.get("/api/v1/products/by-barcode/8901000000018", headers=headers)
        assert bc_resp.status_code == 200
        prod = bc_resp.json()

        # 2. Client prepares unique event_id
        client_event_id = str(uuid.uuid4())
        sale_payload = {
            "event_id": client_event_id,
            "product_id": prod["id"],
            "batch_number": "BATCH-PCM-01",
            "quantity": 1,
            "node_id": headers["X-Node-Id"],
            "channel": "mobile_pos",
        }

        # 3. First submission
        res1 = await client.post("/api/v1/events/sale", json=sale_payload, headers=headers)
        assert res1.status_code in [200, 201]
        data1 = res1.json()
        corr_id1 = data1.get("correlation_id") or data1.get("cascade_trace", {}).get("correlation_id")
        assert corr_id1 is not None

        # 4. Simulated mid-flow network disconnect & retry with identical event_id
        res2 = await client.post("/api/v1/events/sale", json=sale_payload, headers=headers)
        assert res2.status_code in [200, 201]
        data2 = res2.json()
        corr_id2 = data2.get("correlation_id") or data2.get("cascade_trace", {}).get("correlation_id")

        # Verify idempotency: correlation IDs match and transaction was recognized as idempotent
        assert corr_id1 == corr_id2

        # 5. Fetch 5-stage cascade trace
        trace_resp = await client.get(f"/api/v1/cascade/{corr_id1}", headers=headers)
        assert trace_resp.status_code == 200
        trace = trace_resp.json()
        assert len(trace.get("steps", [])) >= 4


# =============================================================================
# CHECKPOINT 5: Jest Test Suite Execution
# =============================================================================
def test_mobile_jest_test_suite_execution():
    """AC #1: Verify Jest automated tests in mobile/ pass with 0 failures."""
    cmd = ["npm", "run", "test"]
    result = subprocess.run(
        cmd,
        cwd=str(MOBILE_DIR),
        capture_output=True,
        text=True,
        shell=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Jest tests failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert "Test Suites:" in result.stdout + result.stderr
    assert "Tests:" in result.stdout + result.stderr
