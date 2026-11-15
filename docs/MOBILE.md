# MediFlux Mobile Application Guide (`docs/MOBILE.md`)

This document outlines the architecture, setup, networking configuration, and runtime procedures for the **MediFlux React Native (Expo + TypeScript) Mobile Application** (`mobile/`).

---

## 1. Monorepo Organization & Packages

```text
MediFlux/
├── backend/                  # FastAPI + LangGraph + Supabase + SSE backend
├── frontend/                 # React 18 + Vite + Tailwind desktop/web admin portal
├── desktop/                  # Tauri / Electron desktop application wrapper
├── mobile/                   # React Native (Expo 51 + Expo Router + TypeScript) mobile app
│   ├── app/
│   │   ├── _layout.tsx       # Root layout with SafeAreaProvider, ThemeProvider, ConnectionBanner
│   │   ├── index.tsx         # Gateway / session verification & redirect
│   │   ├── (auth)/
│   │   │   ├── _layout.tsx
│   │   │   ├── login.tsx     # Sign In with 7 seeded demo roles & server reachability badge
│   │   │   └── settings.tsx  # Dynamic Backend URL editor & 1-tap presets (Local, Emulator, LAN)
│   │   └── (tabs)/
│   │       ├── _layout.tsx   # 6 operational tabs styling (Warm Editorial Minimalism)
│   │       ├── index.tsx     # Home (Node summary, live metrics, topology)
│   │       ├── sell.tsx      # Sell (Counter POS & single-unit cascade replay)
│   │       ├── approvals.tsx # Approvals (Field HITL queue with Approve / Reject)
│   │       ├── scan-rx.tsx   # Scan Rx (Prescription camera capture & Schedule H compliance)
│   │       ├── cold-chain.tsx# Cold Chain (Biologics IoT sensor telemetry & quarantine alerts)
│   │       └── copilot.tsx   # Copilot (Natural-language AI supply assistant)
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts     # Resilient HTTP client with auth headers and ApiError parser
│   │   │   ├── generated.ts  # Auto-generated OpenAPI client and types
│   │   │   └── hooks.ts      # React query/mutation hooks
│   │   ├── components/       # Card, Badge, Timeline, EmptyState, ErrorState, ConnectionBanner
│   │   ├── features/         # Domain modules (pos, approvals, prescriptions, coldchain, copilot, cascade)
│   │   ├── hooks/            # useNetworkStatus, useEventStream (SSE)
│   │   ├── lib/              # config (backend URL & health probe), storage, format
│   │   └── theme/            # tokens.ts (Warm Editorial Minimalism), ThemeContext.tsx
│   ├── app.config.ts         # Expo project configuration
│   └── package.json          # Mobile dependencies & scripts
├── packages/
│   └── shared/               # Shared TypeScript types, enums, error contracts, generated-api
├── scripts/
│   ├── gen_api.py            # One-command OpenAPI TypeScript generator
│   ├── start_all.py          # Unified launcher with --lan support
│   ├── start-all.bat         # Windows batch launcher
│   └── start-all.ps1         # Windows PowerShell launcher
└── docs/
    └── openapi.json          # Exported FastAPI OpenAPI 3.1 schema
```

---

## 2. Design System Alignment (`design.md`)

The mobile application strictly conforms to the **Warm Editorial Minimalism** design system:
- **Canvas**: Warm Ivory (`#E8E4D3`, `#DFDBCA`), Surface (`#FFFFFF`), Elevated (`#F4F1E6`).
- **Typography**: Ink Black (`#031211`) for headings, Charcoal (`#5C584E`) for body and subtitles.
- **Accent**: Electric Teal (`#00AEBB`) used sparingly as an intentional active highlight.
- **Status Colors**: Emerald (`#10B981`) for nominal states, Amber (`#F59E0B`) for warnings/HITL, Coral (`#EF4444`) for critical quarantine.
- **Borders & Radii**: Crisp 1px structural borders (`#D8D3C3`) with tight 2px–4px radii (`rounded-sm`/`rounded-md`). Pill-shaped buttons (`rounded-full`) are strictly forbidden.

---

## 3. Development & Testing Run Options

### Option A: Expo Web (Fastest & Zero Setup on PC)
You can run and test the complete mobile application directly in your PC browser with a responsive mobile viewport:

```powershell
cd mobile
npm run web
```
- Open `http://localhost:8081` in Chrome or Edge.
- Press `F12` and toggle the device toolbar (`Ctrl+Shift+M`) to view as iPhone 14 or Pixel 7.
- Default backend URL: `http://localhost:8000`.

### Option B: Android Emulator (Android Studio / AVD)
When running an Android Virtual Device (AVD):

```powershell
cd mobile
npm run android
```
- Android Emulator routes `10.0.2.2` to the host machine's `localhost`.
- Backend URL: `http://10.0.2.2:8000`.
- In the mobile app's Settings screen, tap the **Android Emulator** 1-tap preset.

### Option C: Physical Mobile Phone (Expo Go via LAN)
To test on a physical iOS or Android phone on the same Wi-Fi network:

1. **Start the backend in LAN mode:**
   ```powershell
   python scripts\start_all.py --lan
   # or
   .\scripts\start-all.ps1 -Lan
   ```
   This automatically detects your laptop's Wi-Fi IPv4 address (e.g. `http://192.168.1.15:8000` or `http://172.20.10.4:8000`), binds FastAPI to `0.0.0.0:8000`, and writes the address to `mobile/.env.local`.

2. **Start the Expo development server:**
   ```powershell
   cd mobile
   npx expo start
   ```

3. **Open in Expo Go:**
   - Scan the terminal QR code with your phone camera (iOS) or Expo Go app (Android).
   - In the mobile app, tap the top `ConnectionBanner` or open Settings to verify that the auto-detected LAN URL is active and `/health` probe passes.

---

## 4. Windows Firewall Configuration (for Port 8000)

If your physical phone reports "Connection refused" or "Network request failed" when connecting to your laptop's LAN IP:

1. Open PowerShell as Administrator.
2. Allow incoming TCP traffic on port 8000:
   ```powershell
   New-NetFirewallRule -DisplayName "MediFlux FastAPI Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```
3. Ensure both your PC and phone are connected to the same Wi-Fi network.

---

## 5. Automated OpenAPI Client Synchronization

Whenever backend endpoints or Pydantic models change:

```powershell
# From repo root:
python scripts\gen_api.py

# Or from mobile/:
npm run gen:api
```

This synchronizes strongly typed interfaces and endpoint registries to:
- `packages/shared/src/generated-api.ts`
- `mobile/src/api/generated.ts`
- `frontend/src/types/generated-api.ts`
