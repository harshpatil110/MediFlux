"""Task M1: Expo Mobile Foundation & Shared OpenAPI Package Verification Tests.

Validates:
1. Complete mobile/ and packages/shared/ file layout and configuration.
2. One-command OpenAPI generator (scripts/gen_api.py) synchronizing types across packages.
3. Shared API package enums, errors, events, and types.
4. Backend /health reachability probe and standard error response format {error: {code, message, details}, detail}.
5. Backend CORS permissive LAN origin matching.
6. scripts/start_all.py --lan LAN IP detection and mobile/.env.local generation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MOBILE_DIR = ROOT_DIR / "mobile"
SHARED_DIR = ROOT_DIR / "packages" / "shared"
SCRIPTS_DIR = ROOT_DIR / "scripts"
DOCS_DIR = ROOT_DIR / "docs"


class TestMobileFoundationTaskM1:
    """Automated test suite verifying full compliance of Task M1."""

    def test_mobile_and_shared_file_structure(self) -> None:
        """Verify presence of all required mobile, shared, and documentation files."""
        required_paths = [
            SHARED_DIR / "package.json",
            SHARED_DIR / "tsconfig.json",
            SHARED_DIR / "src" / "index.ts",
            SHARED_DIR / "src" / "enums.ts",
            SHARED_DIR / "src" / "errors.ts",
            SHARED_DIR / "src" / "events.ts",
            SHARED_DIR / "src" / "types.ts",
            SHARED_DIR / "src" / "generated-api.ts",
            MOBILE_DIR / "package.json",
            MOBILE_DIR / "app.config.ts",
            MOBILE_DIR / "tsconfig.json",
            MOBILE_DIR / ".eslintrc.js",
            MOBILE_DIR / "README.md",
            MOBILE_DIR / "src" / "theme" / "tokens.ts",
            MOBILE_DIR / "src" / "theme" / "ThemeContext.tsx",
            MOBILE_DIR / "src" / "lib" / "config.ts",
            MOBILE_DIR / "src" / "lib" / "storage.ts",
            MOBILE_DIR / "src" / "lib" / "format.ts",
            MOBILE_DIR / "src" / "api" / "client.ts",
            MOBILE_DIR / "src" / "api" / "generated.ts",
            MOBILE_DIR / "src" / "api" / "hooks.ts",
            MOBILE_DIR / "src" / "components" / "Card.tsx",
            MOBILE_DIR / "src" / "components" / "Badge.tsx",
            MOBILE_DIR / "src" / "components" / "Timeline.tsx",
            MOBILE_DIR / "src" / "components" / "EmptyState.tsx",
            MOBILE_DIR / "src" / "components" / "ErrorState.tsx",
            MOBILE_DIR / "src" / "components" / "ConnectionBanner.tsx",
            MOBILE_DIR / "app" / "_layout.tsx",
            MOBILE_DIR / "app" / "index.tsx",
            MOBILE_DIR / "app" / "(auth)" / "_layout.tsx",
            MOBILE_DIR / "app" / "(auth)" / "login.tsx",
            MOBILE_DIR / "app" / "(auth)" / "settings.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "_layout.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "index.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "sell.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "approvals.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "scan-rx.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "cold-chain.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "copilot.tsx",
            SCRIPTS_DIR / "gen_api.py",
            SCRIPTS_DIR / "gen-api.bat",
            SCRIPTS_DIR / "gen-api.ps1",
            DOCS_DIR / "MOBILE.md",
        ]

        missing = [str(p.relative_to(ROOT_DIR)) for p in required_paths if not p.exists()]
        assert not missing, f"Missing required Task M1 paths: {missing}"

    def test_gen_api_script_execution(self) -> None:
        """Verify python scripts/gen_api.py runs successfully and generates valid files."""
        res = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "gen_api.py")],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"gen_api.py failed:\n{res.stderr}\n{res.stdout}"

        shared_gen = SHARED_DIR / "src" / "generated-api.ts"
        mobile_gen = MOBILE_DIR / "src" / "api" / "generated.ts"

        assert shared_gen.is_file() and shared_gen.stat().st_size > 5000
        assert mobile_gen.is_file() and mobile_gen.stat().st_size > 5000

        content = shared_gen.read_text(encoding="utf-8")
        assert "export interface ApiOperations" in content
        assert "export interface ApiClientContract" in content

    def test_shared_package_contents(self) -> None:
        """Verify packages/shared exports critical enums and error definitions."""
        enums_txt = (SHARED_DIR / "src" / "enums.ts").read_text(encoding="utf-8")
        assert "UserRole" in enums_txt
        assert "SupplyTier" in enums_txt
        assert "HitlStatus" in enums_txt
        assert "EventType" in enums_txt

        errors_txt = (SHARED_DIR / "src" / "errors.ts").read_text(encoding="utf-8")
        assert "StandardErrorPayload" in errors_txt
        assert "class ApiError" in errors_txt

    def test_start_all_lan_preflight(self) -> None:
        """Verify scripts/start_all.py with --lan --check-only."""
        res = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "start_all.py"), "--lan", "--check-only"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"start_all.py --lan --check-only failed:\n{res.stderr}\n{res.stdout}"
        assert "LAN Mode" in res.stdout
        assert "Android Emulator URL" in res.stdout

        env_local = MOBILE_DIR / ".env.local"
        assert env_local.is_file(), "mobile/.env.local must be created by --lan flag"
        env_content = env_local.read_text(encoding="utf-8")
        assert "EXPO_PUBLIC_LAN_API_URL=" in env_content

    @pytest.mark.asyncio
    async def test_backend_health_probe(self) -> None:
        """Verify /health endpoint returns HTTP 200 with operational status."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "version" in data
            assert "environment" in data

    @pytest.mark.asyncio
    async def test_backend_standard_error_format(self) -> None:
        """Verify backend error responses conform to {error: {code, message, details}, detail}."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Query a non-existent path to trigger 404
            resp = await client.get("/api/v1/nonexistent/resource")
            assert resp.status_code == 404
            data = resp.json()

            # Ensure both standard structure and legacy detail exist
            assert "error" in data, "Error response must include 'error' object"
            assert "code" in data["error"]
            assert "message" in data["error"]
            assert "details" in data["error"]
            assert "detail" in data, "Error response must retain 'detail' for backwards compatibility"

    @pytest.mark.asyncio
    async def test_backend_cors_lan_origin(self) -> None:
        """Verify CORS middleware allows requests from LAN IPs."""
        transport = ASGITransport(app=app)
        headers = {
            "Origin": "http://192.168.1.100:8081",
            "Access-Control-Request-Method": "GET",
        }
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.options("/health", headers=headers)
            assert resp.status_code == 200
            allow_origin = resp.headers.get("access-control-allow-origin")
            assert allow_origin == "http://192.168.1.100:8081" or allow_origin == "*"
