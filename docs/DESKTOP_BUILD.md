# MediFlux Desktop Application Packaging & Runtime Guide

## 1. Executive Summary & Architecture

MediFlux delivers a unified user experience across web browsers and desktop operating systems (Windows, macOS, Linux). The desktop shell packages the React 18 frontend into an isolated desktop window with native OS integration (system tray, window management, single-instance locking, and system notifications) while communicating asynchronously with the FastAPI backend.

```
+-----------------------------------------------------------------------+
|                       MediFlux Desktop Shell                          |
|                                                                       |
|  +---------------------------+       +-----------------------------+  |
|  |     Main Process          |       |     Renderer Process        |  |
|  |  (Electron / Tauri Rust)  |       |  (React 18 / Vite / TS)     |  |
|  |                           |       |                             |  |
|  | - Single Instance Lock    |  IPC  | - HashRouter / BrowserRouter|  |
|  | - System Tray Menu        |<----->| - Dynamic Backend URL Store |  |
|  | - Native App Menu         | Bridge| - Live Latency Probe        |  |
|  | - OS Notifications        |       | - Auto-Trigger Notifications|  |
|  +---------------------------+       +--------------+--------------+  |
+-----------------------------------------------------|-----------------+
                                                      |
                                                      | HTTP / SSE
                                                      v
                                       +-----------------------------+
                                       |      FastAPI Backend        |
                                       |                             |
                                       | - Permissive Desktop CORS   |
                                       | - Liveness Probe (/health)  |
                                       | - Multi-tier Agent Cascade  |
                                       +-----------------------------+
```

---

## 2. Dual-Engine Strategy: Tauri + Electron

MediFlux maintains first-class support for both modern desktop runtimes:

1. **Tauri Rust Toolchain (`desktop/src-tauri/`)**:
   - Configuration: `tauri.conf.json` configured with bundle identifier `in.mediflux.desktop`, 1440x900 initial window, distDir `../../frontend/dist`, and system tray.
   - Cargo Specification: `Cargo.toml` with `tauri 1.8`, `serde`, and `serde_json`.
   - Windows build requires `cargo` and `rustc`.

2. **Electron Active Packaging Target (`desktop/`)**:
   - Serves as the zero-dependency fallback and active packaging target on environments without Rust/Cargo.
   - Uses `electron` and `electron-builder` (`desktop/package.json`).
   - Secure IPC Preload bridge (`desktop/preload.cjs`) isolating Node.js APIs from the web renderer.

---

## 3. Key Desktop Capabilities

### A. Dynamic Backend URL Configuration
- Web deployments connect to `http://localhost:8000` by default.
- Packaged desktop users can point the app to any local, on-premise, or cloud MediFlux FastAPI server without rebuilding the desktop wrapper.
- Settings are saved to `localStorage.getItem("mediflux_backend_url")`.
- When updated, a custom event `mediflux:backend-url-changed` is dispatched, prompting:
  - All TanStack Query caches to invalidate.
  - Active Server-Sent Events (SSE) streams to cleanly close and reconnect to the new host.
- Accessible via the **Backend** pill in the top header and **Server Settings** on the login screen.

### B. Live Health Probe & Latency Measurement
- The Backend Settings modal initiates an asynchronous round-trip probe against `GET /health`.
- Displays real-time latency in milliseconds (e.g. `ONLINE (14ms)`).
- Validates CORS header compatibility and reports version and environment details.

### C. Native Desktop Notifications
- Automatically triggers native OS banners with action routes:
  - **HITL Approval Tasks**: Alerts operator when high-risk orders require review; clicking opens `/approvals`.
  - **Cold-Chain Batch Quarantine**: Alerts on temperature excursions; clicking opens `/cold-chain`.
- Features single-click test buttons in the Backend Settings modal.
- Respects user mute toggle persisted in local storage.

### D. Single-Instance Lock & System Tray
- `desktop/main.cjs` requests a single-instance lock (`app.requestSingleInstanceLock()`). Subsequent invocations restore and focus the primary window.
- The system tray icon provides quick access to:
  - Open MediFlux
  - Operations (Cascade, HITL Approvals, Regulatory Lab, Cold-Chain Telemetry)
  - Connection Settings
  - Quit

---

## 4. Development & Build Commands

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+ with backend virtual environment
- Operating System: Windows 10/11, macOS 12+, or modern Linux (Ubuntu 22.04+)

### One-Command Full Stack Launcher
```powershell
# Windows PowerShell (Backend + Frontend Web + Electron Desktop)
.\scripts\start-all.ps1 -Desktop

# Windows Command Prompt
.\scripts\start-all.bat --desktop

# Cross-Platform Python CLI
python scripts/start_all.py --mode desktop
python scripts/start_all.py --check-only
```

### Manual Development Workflow
```powershell
# 1. Start FastAPI Backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 2. Build or start Frontend
cd frontend
npm run build

# 3. Launch Desktop Wrapper
cd desktop
npm run desktop:dev
```

### Packaging Production Executables
```powershell
# Build frontend dist
cd frontend
npm run build

# Pack unpackaged desktop executable directory (fast verification)
cd desktop
npm run desktop:pack

# Generate production Windows installer / standalone exe
cd desktop
npm run desktop:build
```

---

## 5. Verification Checklist

| Checkpoint | Target | Status |
| :--- | :--- | :--- |
| **Desktop Icons** | `desktop/icons/icon.ico`, `desktop/icons/icon.png` (512x512) | Verified |
| **Tauri Specification** | `desktop/src-tauri/tauri.conf.json`, `Cargo.toml` | Verified |
| **Electron Runtime** | `desktop/package.json`, `desktop/main.cjs`, `desktop/preload.cjs` | Verified |
| **Vite Base Path** | `frontend/vite.config.ts` (`base: "./"`) | Verified |
| **Router Fallback** | `frontend/src/App.tsx` (`HashRouter` on `file://` / desktop shell) | Verified |
| **Backend CORS** | `CORSMiddleware` in `backend/app/main.py` permits desktop origins | Verified |
| **Health Probe** | `GET /health` returns `desktop_cors_enabled=True` | Verified |
| **CI Dry-Run Check** | `python scripts/start_all.py --check-only` exits with code 0 | Verified |

