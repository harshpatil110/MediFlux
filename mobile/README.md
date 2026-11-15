# MediFlux / NexusChain — Mobile Client (`mobile/`)

React Native (Expo + TypeScript + Expo Router) operational mobile application for the **MediFlux** Autonomous Pharmaceutical Supply Chain Network.

Built to run cross-platform on **Web (Desktop / Mobile Viewport)**, **Android Emulator (AVD / 10.0.2.2)**, and **Physical Mobile Devices via Expo Go (LAN)**.

---

## 1. Architecture & Design Principles

- **Design System**: Strictly conforms to **Warm Editorial Minimalism** (`design.md`):
  - Canvas: Warm Ivory (`#E8E4D3`, `#DFDBCA`, `#FFFFFF`)
  - Typography: Ink Black (`#031211`), Charcoal (`#5C584E`)
  - Accent: Electric Teal (`#00AEBB`)
  - Structural: Crisp 1px borders (`#D8D3C3`), no pill-shaped buttons
- **Navigation**: File-based routing via `expo-router`:
  - `(auth)`: Login screen with 7 seeded demo roles, runtime Backend URL editor & `/health` reachability probe.
  - `(tabs)`: 6 operational tabs:
    1. **Home**: Operational node summary, live topology, inventory metrics.
    2. **Sell**: Counter POS terminal with instant single-unit demand cascade propagation.
    3. **Approvals**: Field HITL decisions queue with Approve / Reject workflows.
    4. **Scan Rx**: Sovereign prescription camera capture, doctor registry verification, and Schedule H compliance.
    5. **Cold Chain**: Biologics IoT sensors, Arrhenius kinetic shelf-life degradation, and quarantine alerts.
    6. **Copilot**: Grounded natural-language conversational supply assistant.

---

## 2. Quick Start Commands

```bash
# Install dependencies
cd mobile
npm install

# Run on Web (Browser Mobile Viewport)
npm run web

# Run on Android Emulator
npm run android

# Regenerate TypeScript OpenAPI client from docs/openapi.json
npm run gen:api

# Run TypeScript check
npm run typecheck

# Run Linter
npm run lint
```

---

## 3. Connecting to the FastAPI Backend

The mobile client features dynamic backend URL configuration with `/health` reachability checks:

| Target Environment | Backend URL | Setup Notes |
| :--- | :--- | :--- |
| **Expo Web (Browser)** | `http://localhost:8000` | Works automatically |
| **Android Emulator** | `http://10.0.2.2:8000` | Loopback alias to development host machine |
| **Physical Phone / Expo Go** | `http://<LAN_IP>:8000` | Start backend with `python -m scripts.start_all --lan` |

The `ConnectionBanner` at the top of the mobile application displays real-time reachability status and latency, allowing instant tap-to-configure switching between presets.

