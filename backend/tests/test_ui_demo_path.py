"""Automated verification suite for Task 29: UI Demo Path & Error Handling Integration.

Verifies:
1. Built bundle integrity (frontend/dist/index.html & assets).
2. Domain error normalization specifications (frontend/src/lib/errorMessages.ts).
3. UI Demo controls & Error Banner presence (AppShell, BackendSettingsModal, LlmErrorBanner).
4. Frontend API client demo contract (frontend/src/lib/api.ts).
5. Live FastAPI demo reset & status endpoints (/api/v1/demo/status, /api/v1/demo/reset).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def test_frontend_dist_bundle_integrity() -> None:
    """Verify that frontend/dist was generated, index.html exists, and contains valid entry markup."""
    dist_dir = FRONTEND_DIR / "dist"
    index_html = dist_dir / "index.html"
    assert index_html.exists(), "frontend/dist/index.html must exist (built bundle required)"

    content = index_html.read_text(encoding="utf-8")
    assert '<div id="root"></div>' in content
    # Ensure bundled JS script tag is present
    assert re.search(r'<script[^>]+src="[^"]*assets/[^"]+\.js"', content) is not None


def test_error_messages_definitions() -> None:
    """Verify that errorMessages.ts covers all required failure modes and codes."""
    err_file = FRONTEND_DIR / "src" / "lib" / "errorMessages.ts"
    assert err_file.exists(), "frontend/src/lib/errorMessages.ts must exist"

    content = err_file.read_text(encoding="utf-8")
    required_codes = [
        "PROVIDER_RATE_LIMITED_429",
        "LLM_INVALID_JSON_OUTPUT",
        "SOVEREIGN_LOCAL_MODEL_OFFLINE",
        "HITL_TASK_EXPIRED",
        "PARTIAL_CASCADE_FAILURE",
        "NETWORK_OFFLINE",
    ]
    for code in required_codes:
        assert code in content, f"errorMessages.ts must handle domain error code {code}"

    assert "normalizeLlmError" in content


def test_ui_components_presence() -> None:
    """Verify Warm Editorial Minimalism error banner and AppShell demo reset controls."""
    # 1. Error Banner component
    banner_file = FRONTEND_DIR / "src" / "components" / "shared" / "LlmErrorBanner.tsx"
    assert banner_file.exists(), "LlmErrorBanner.tsx must exist"
    banner_content = banner_file.read_text(encoding="utf-8")
    assert "normalizeErrorMessage" in banner_content or "normalizeLlmError" in banner_content
    assert "onRetry" in banner_content

    # 2. AppShell header controls
    app_shell_file = FRONTEND_DIR / "src" / "components" / "layout" / "AppShell.tsx"
    assert app_shell_file.exists()
    app_shell_content = app_shell_file.read_text(encoding="utf-8")
    assert "Reset Demo" in app_shell_content
    assert "DEMO REPLAY" in app_shell_content or "REPLAY" in app_shell_content

    # 3. BackendSettingsModal controls
    modal_file = FRONTEND_DIR / "src" / "components" / "layout" / "BackendSettingsModal.tsx"
    assert modal_file.exists()
    modal_content = modal_file.read_text(encoding="utf-8")
    assert "Demo Environment State" in modal_content or "Reset Demo" in modal_content

    # 4. API client exports demo methods
    api_file = FRONTEND_DIR / "src" / "lib" / "api.ts"
    assert api_file.exists()
    api_content = api_file.read_text(encoding="utf-8")
    assert "demo:" in api_content
    assert "reset:" in api_content
    assert "getStatus:" in api_content


@pytest.mark.asyncio
async def test_demo_api_endpoints() -> None:
    """Verify backend FastAPI demo status and demo reset endpoints respond cleanly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # GET /api/v1/demo/status
        status_res = await client.get("/api/v1/demo/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "demo_mode" in status_data
        assert "cache_mode" in status_data
        assert "cache_entries" in status_data

        # POST /api/v1/demo/reset
        reset_res = await client.post("/api/v1/demo/reset")
        assert reset_res.status_code == 200
        reset_data = reset_res.json()
        assert reset_data["success"] is True
        assert "Demo state reset" in reset_data["message"]
