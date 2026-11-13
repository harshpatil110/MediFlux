# Task 28 Specification: Desktop Application Packaging & Runtime Integration

## Overview
Task 28 implements the complete desktop application packaging, runtime bridge, dynamic backend configuration, native OS notifications, and developer launcher suite for **MediFlux**, delivering native operational capabilities to pharmaceutical supply chain operators:

1. **Dual-Runtime Desktop Packaging Strategy**:
   - **Tauri Rust Toolchain (`desktop/src-tauri/`)**: Complete configuration specification with `tauri.conf.json` (bundle identifier `in.mediflux.desktop`, 1440x900 window, distDir `../../frontend/dist`), `Cargo.toml`, `build.rs`, and `src/main.rs`.
   - **Electron Wrapper & Active Packaging (`desktop/`)**: Production Electron shell with `package.json`, `main.cjs`, and `preload.cjs`, serving as the primary packaging runtime on environments without Rust/Cargo.
   - Programmatically generated custom icons in `desktop/icons/` and `desktop/src-tauri/icons/` including multi-resolution `icon.ico` (256x256 base, 128x128, 64x64, 48x48, 32x32, 24x24, 16x16) and `icon.png` (512x512).

2. **Frontend Desktop Compatibility & Relative Base Path**:
   - `frontend/vite.config.ts`: Configured with `base: "./"` ensuring all asset references (`./assets/...`) resolve seamlessly when loaded over `file://` or custom desktop protocols (`app://`, `tauri://`).
   - `frontend/src/App.tsx`: Dynamic router selection: utilizes `HashRouter` when running under `file://` or desktop wrappers, and `BrowserRouter` when hosted on standard web servers.
   - Desktop bridge listener handling system tray and native application menu route dispatches (`medifluxDesktop.onNavigate`).

3. **Runtime-Configurable Backend API Base URL**:
   - `frontend/src/config/env.ts` & `frontend/src/lib/api.ts`: Dynamic store reading from `localStorage.getItem("mediflux_backend_url")` (default: `http://localhost:8000`).
   - Dispatches custom event `mediflux:backend-url-changed` on mutation, prompting instant TanStack Query cache invalidation and Server-Sent Events (SSE) auto-reconnection.
   - Warm Editorial Minimalism settings modal (`BackendSettingsModal.tsx`):
     - Live asynchronous round-trip probe to `GET /health` measuring latency in milliseconds.
     - One-click presets (`Localhost:8000`, `Local Network IP`, `Custom Port`).
     - Native desktop environment detection badge (`Desktop App (ELECTRON Shell)` vs `Standard Web Browser`).
     - Integrated in top header bar of `AppShell.tsx` and the access portal of `LoginPage.tsx`.

4. **Native Desktop OS Notifications**:
   - `frontend/src/hooks/useDesktopNotifications.ts`: Bi-modal notification engine prioritizing `window.medifluxDesktop.showNotification` bridge and falling back to the Web Notification API.
   - Auto-triggers native notification alerts for critical supply chain events:
     - **HITL Approvals**: Alerts when high-risk orders require pharmacist/admin verification (routes to `/approvals`).
     - **Cold-Chain Quarantines**: Alerts when temperature excursions trigger automatic batch isolation (routes to `/cold-chain`).
   - One-click notification test buttons in the Backend Settings modal.
   - User notification mute toggle persisted in local storage.

5. **Desktop Shell Integration (`desktop/main.cjs`)**:
   - **Single-Instance Lock**: `app.requestSingleInstanceLock()` prevents duplicate processes and restores/focuses existing windows.
   - **System Tray**: Persistent tray icon with context menu linking directly to Cascade, HITL Approvals, Regulatory Lab, and Cold-Chain monitors.
   - **Native Application Menu**: Platform-standard menu with Operations shortcuts, Settings trigger, and DevTools toggle.

6. **Backend Permissive Desktop CORS & Health Probes**:
   - `backend/app/core/config.py`: Enriched `CORS_ORIGINS` to permit `tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost`, `app://.`, `app://localhost`, `file://`, and `null`.
   - `backend/app/main.py`: `CORSMiddleware` configured with desktop origins and regex matching custom schemes; `/health` endpoint enriched with `"desktop_cors_enabled": True`.

7. **Convenience Launchers & Developer Tooling**:
   - `scripts/start-all.bat`: Windows batch script for dual backend and frontend/desktop startup.
   - `scripts/start-all.ps1`: PowerShell launcher supporting `-Desktop` and `-CheckOnly` switches.
   - `scripts/start_all.py`: Unified Python launcher CLI supporting `--mode (desktop|web|both)`, `--port`, and `--check-only` preflight validation.
   - `docs/DESKTOP_BUILD.md`: Complete packaging, testing, and architecture documentation.

---

## Verification Summary
- **Icon Assets**: Validated presence and resolution of `.ico` and `.png` assets in both `desktop/icons/` and `desktop/src-tauri/icons/`.
- **Tauri & Electron Configs**: Validated schema and package integrity of `tauri.conf.json` and `desktop/package.json`.
- **Frontend Distribution**: Built via `npm --prefix frontend run build` producing relative asset paths in `frontend/dist/index.html`.
- **Backend CORS Preflight**: Verified 200 OK responses with matching `access-control-allow-origin` headers for `tauri://localhost`, `app://.`, and `http://tauri.localhost`.
- **Automated Tests**: Validated via `backend/tests/test_task28_desktop_packaging.py`.

