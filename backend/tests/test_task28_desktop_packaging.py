"""Task 28: Desktop Application Packaging & Runtime Verification Tests.

Validates:
1. Programmatically generated multi-resolution desktop icons (ICO, PNG).
2. Complete Tauri configuration (tauri.conf.json, Cargo.toml, build.rs, main.rs).
3. Electron active desktop wrapper (package.json, main.cjs, preload.cjs).
4. Frontend desktop compatibility (base: "./", HashRouter support, dynamic backend URL store).
5. FastAPI CORS permissive desktop origins (tauri://localhost, app://., file://, null) and /health telemetry.
6. Unified launcher CLI (scripts/start_all.py --check-only).
7. Desktop architecture and runtime documentation (docs/DESKTOP_BUILD.md).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DESKTOP_DIR = ROOT_DIR / "desktop"
FRONTEND_DIR = ROOT_DIR / "frontend"
SCRIPTS_DIR = ROOT_DIR / "scripts"
DOCS_DIR = ROOT_DIR / "docs"


class TestDesktopPackagingTask28:
    """Automated test suite verifying full compliance of Task 28."""

    def test_desktop_assets_and_icons_exist(self) -> None:
        """Verify presence and validity of desktop application icon sets."""
        ico_file = DESKTOP_DIR / "icons" / "icon.ico"
        png_512 = DESKTOP_DIR / "icons" / "icon.png"
        png_mirror = DESKTOP_DIR / "icons" / "512x512.png"
        tauri_ico = DESKTOP_DIR / "src-tauri" / "icons" / "icon.ico"
        tauri_png = DESKTOP_DIR / "src-tauri" / "icons" / "icon.png"

        assert ico_file.is_file(), "desktop/icons/icon.ico must exist"
        assert png_512.is_file(), "desktop/icons/icon.png must exist"
        assert png_mirror.is_file(), "desktop/icons/512x512.png must exist"
        assert tauri_ico.is_file(), "desktop/src-tauri/icons/icon.ico must exist"
        assert tauri_png.is_file(), "desktop/src-tauri/icons/icon.png must exist"

        # Check non-trivial icon size
        assert ico_file.stat().st_size > 1000, "icon.ico should contain multi-resolution icon frames"
        assert png_512.stat().st_size > 1000, "icon.png should be high resolution"

    def test_tauri_configuration_integrity(self) -> None:
        """Verify Tauri desktop configuration and Rust crate structure."""
        tauri_conf_path = DESKTOP_DIR / "src-tauri" / "tauri.conf.json"
        cargo_path = DESKTOP_DIR / "src-tauri" / "Cargo.toml"
        main_rs = DESKTOP_DIR / "src-tauri" / "src" / "main.rs"
        build_rs = DESKTOP_DIR / "src-tauri" / "build.rs"

        assert tauri_conf_path.is_file(), "tauri.conf.json must exist"
        assert cargo_path.is_file(), "desktop/src-tauri/Cargo.toml must exist"
        assert main_rs.is_file(), "desktop/src-tauri/src/main.rs must exist"
        assert build_rs.is_file(), "desktop/src-tauri/build.rs must exist"

        with open(tauri_conf_path, encoding="utf-8") as f:
            tauri_conf = json.load(f)

        assert tauri_conf.get("package", {}).get("productName") in ("MediFlux", "MediFlux Control Tower")
        assert tauri_conf.get("tauri", {}).get("bundle", {}).get("identifier") == "in.mediflux.desktop"
        assert tauri_conf.get("build", {}).get("distDir") == "../../frontend/dist"

        cargo_text = cargo_path.read_text(encoding="utf-8")
        assert "tauri =" in cargo_text

    def test_electron_configuration_integrity(self) -> None:
        """Verify Electron active desktop wrapper and IPC preload bridge."""
        pkg_path = DESKTOP_DIR / "package.json"
        main_cjs = DESKTOP_DIR / "main.cjs"
        preload_cjs = DESKTOP_DIR / "preload.cjs"

        assert pkg_path.is_file(), "desktop/package.json must exist"
        assert main_cjs.is_file(), "desktop/main.cjs must exist"
        assert preload_cjs.is_file(), "desktop/preload.cjs must exist"

        with open(pkg_path, encoding="utf-8") as f:
            pkg = json.load(f)

        assert pkg.get("name") == "mediflux-desktop"
        assert "desktop:dev" in pkg.get("scripts", {})
        assert "desktop:pack" in pkg.get("scripts", {})
        assert "desktop:build" in pkg.get("scripts", {})

        main_text = main_cjs.read_text(encoding="utf-8")
        assert "requestSingleInstanceLock" in main_text, "Single-instance lock must be enforced"
        assert "Tray" in main_text, "System tray must be initialized"
        assert "ipcMain" in main_text, "IPC communication must be configured"

        preload_text = preload_cjs.read_text(encoding="utf-8")
        assert "medifluxDesktop" in preload_text, "Context bridge must expose medifluxDesktop"
        assert "showNotification" in preload_text
        assert "onNavigate" in preload_text

    def test_frontend_desktop_compatibility(self) -> None:
        """Verify frontend Vite relative base path and dynamic backend settings."""
        vite_conf = (FRONTEND_DIR / "vite.config.ts").read_text(encoding="utf-8")
        assert 'base: "./"' in vite_conf, "Vite base path must be './' for file:// and webview desktop shells"

        env_ts = (FRONTEND_DIR / "src" / "config" / "env.ts").read_text(encoding="utf-8")
        assert "getApiBaseUrl" in env_ts
        assert "setApiBaseUrl" in env_ts
        assert "mediflux_backend_url" in env_ts
        assert "mediflux:backend-url-changed" in env_ts

        app_tsx = (FRONTEND_DIR / "src" / "App.tsx").read_text(encoding="utf-8")
        assert "HashRouter" in app_tsx, "App.tsx must include HashRouter fallback for desktop/file: mode"
        assert "DesktopBridgeListener" in app_tsx

        modal_tsx = (FRONTEND_DIR / "src" / "components" / "layout" / "BackendSettingsModal.tsx").read_text(encoding="utf-8")
        assert "BackendSettingsModal" in modal_tsx
        assert "testNotification" in modal_tsx

        # Verify built distribution
        dist_html = FRONTEND_DIR / "dist" / "index.html"
        assert dist_html.is_file(), "frontend/dist/index.html must exist after build"
        html_content = dist_html.read_text(encoding="utf-8")
        assert "./assets/" in html_content, "dist/index.html must reference relative asset paths"

    @pytest.mark.asyncio
    async def test_fastapi_cors_desktop_origins_and_health(self) -> None:
        """Verify FastAPI permits desktop preflight and GET requests from custom origins."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Health probe with tauri://localhost origin
            res = await client.get("/health", headers={"Origin": "tauri://localhost"})
            assert res.status_code == 200
            data = res.json()
            assert data.get("status") == "ok"
            assert data.get("desktop_cors_enabled") is True
            assert res.headers.get("access-control-allow-origin") == "tauri://localhost"

            # 2. CORS Preflight OPTIONS with app://. origin
            preflight = await client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "app://.",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type,authorization",
                },
            )
            assert preflight.status_code == 200
            assert preflight.headers.get("access-control-allow-origin") == "app://."

            # 3. CORS Preflight OPTIONS with http://tauri.localhost
            preflight_tauri = await client.options(
                "/health",
                headers={
                    "Origin": "http://tauri.localhost",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert preflight_tauri.status_code == 200
            assert preflight_tauri.headers.get("access-control-allow-origin") == "http://tauri.localhost"

    def test_start_all_script_check_only(self) -> None:
        """Verify the unified full-stack launcher executes --check-only cleanly."""
        start_all_py = SCRIPTS_DIR / "start_all.py"
        assert start_all_py.is_file(), "scripts/start_all.py must exist"

        result = subprocess.run(
            [sys.executable, str(start_all_py), "--check-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"start_all.py --check-only failed: {result.stderr or result.stdout}"
        assert "[SUCCESS]" in result.stdout

    def test_desktop_build_documentation(self) -> None:
        """Verify comprehensive documentation exists for desktop packaging."""
        doc_file = DOCS_DIR / "DESKTOP_BUILD.md"
        assert doc_file.is_file(), "docs/DESKTOP_BUILD.md must exist"

        content = doc_file.read_text(encoding="utf-8")
        assert "Tauri" in content
        assert "Electron" in content
        assert "Dynamic Backend URL" in content
        assert "start-all" in content
