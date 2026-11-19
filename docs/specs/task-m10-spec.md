# Task M10 Specification: Mobile Distribution, Documentation, and Demo Integration

## 1. Overview
Task M10 completes the final phase of the MediFlux / NexusChain React Native mobile application (`mobile/`), establishing seamless evaluation run paths, comprehensive system documentation, demo walkthroughs, and monorepo release packaging:
1. **Run Paths & EAS Build Configuration (`M10.1`)**:
   - Configured **Path A** (Expo Go on physical phone via LAN IP auto-detection in `scripts/start-all.py --lan`).
   - Configured **Path B** (Standalone Android APK distribution via `mobile/eas.json` with `preview` profile).
   - Added cleartext HTTP support for local development in `mobile/app.config.ts` via `expo-build-properties` (`usesCleartextTraffic: true`).
2. **Comprehensive Documentation Suite (`M10.2`)**:
   - Authored `docs/MOBILE.md` covering architecture, screen-to-endpoint mappings, setup instructions, troubleshooting, device matrix, failure injection, and known limitations.
   - Updated root `README.md` with dedicated Mobile Application showcase section and visual screenshot gallery.
   - Updated `docs/ARCHITECTURE.md` adding the decoupled client layer (Web, Desktop, Mobile) and data flow diagrams.
   - Updated `docs/API_GUIDE.md` adding Section 7 documenting the 5 new mobile REST endpoints.
   - Appended mobile implementation log to `docs/HOW_AI_BUILT_THIS.md`.
3. **Demo Script & Narrator Walkthrough (`M10.3`)**:
   - Updated `docs/DEMO_SCRIPT.md` with a dedicated 5-step Mobile App Walkthrough segment `[9:30 - 12:45]`.
   - Highlighted the core architectural talking point: *"The mobile app is a thin client built strictly over our public OpenAPI REST endpoints and Server-Sent Events stream, proving that external developers can build custom clients over our public API."*
4. **Verification, Secrets Check, and Release Tagging (`M10.4`)**:
   - Re-exported FastAPI OpenAPI 3.1 schema to `docs/openapi.json` (95 total paths including all mobile routes).
   - Verified zero leaked credentials via `python -m scripts.check_secrets`.
   - Verified `.env.example` and `mobile/.env.example` templates.
   - Verified consecutive demo reset and mobile demo repeatability (`scripts.reset_demo` + `scripts.run_mobile_demo`).

---

## 2. Technical Deliverables & Configuration

### 2.1 EAS Build Profile (`mobile/eas.json`)
```json
{
  "cli": { "version": ">= 12.0.0" },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "production": {
      "channel": "production"
    }
  },
  "submit": { "production": {} }
}
```

### 2.2 Cleartext HTTP Plugin Configuration (`mobile/app.config.ts`)
```typescript
plugins: [
  'expo-router',
  [
    'expo-build-properties',
    {
      android: {
        usesCleartextTraffic: true,
      },
    },
  ],
],
```

### 2.3 Mobile REST Endpoints Documented in `docs/API_GUIDE.md`
1. `POST /api/v1/devices` & `DELETE /api/v1/devices/{token}` — Device Push Token registration and unregistration.
2. `GET /api/v1/mobile/summary` — High-performance single-call RLS-scoped operational KPI summary.
3. `GET /api/v1/products/by-barcode/{code}` — EAN-13 barcode lookup with FEFO-sorted batch list.
4. `GET /api/v1/events/recent` — Low-latency polling fallback event feed.
5. `GET /api/v1/cascade` & `GET /api/v1/cascade/{correlation_id}` — Historical cascade list and 5-stage replay progression.

---

## 3. Verification & Acceptance Criteria

- [x] **AC1 — Fresh Clone Run Paths**: Both Path A (Expo Go on physical phone via `--lan`) and Path B (standalone APK via `eas.json`) are fully configured and documented in `docs/MOBILE.md` and `README.md`.
- [x] **AC2 — Decoupled Architecture Documentation**: `docs/ARCHITECTURE.md`, `docs/MOBILE.md`, and `README.md` articulate the thin-client decoupling model and provide exact screen-to-endpoint mappings.
- [x] **AC3 — Demo Walkthrough Integration**: `docs/DEMO_SCRIPT.md` includes the 5-step mobile walkthrough with narrator talking points and backup video notes.
- [x] **AC4 — OpenAPI Schema Synchronization**: `docs/openapi.json` exported with 95 paths including all mobile routes, and verified in `docs/API_GUIDE.md`.
- [x] **AC5 — Clean Secrets & Demo Repeatability**: `python -m scripts.check_secrets` confirms 0 leaked secrets; `python -m scripts.reset_demo && python -m scripts.run_mobile_demo` passes consecutively back-to-back.
- [x] **AC6 — Full Test Suite Pass Rate**: All 85 mobile pytest backend tests pass (100%), ruff check passes with 0 warnings, mobile `npm run check` passes with 23/23 Jest tests, and Expo web export bundles cleanly.

