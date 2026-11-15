# Task M4 Specification: Pharmacy POS Lite, Barcode Scan, FEFO Sale & Live Cascade Timeline

## 1. Overview
Task M4 delivers the field-ready mobile Point-of-Sale (POS Lite) module for pharmacists, enabling optical/manual barcode scanning of all 20 catalog products with GS1 India standard EAN-13 barcodes, automatic First-Expiry-First-Out (FEFO) batch recommendation, strict quarantine lockout prevention (409 BATCH_QUARANTINED), Schedule H/H1 prescription compliance validation, and client-side UUID idempotency. Dispensing 1 retail strip triggers the complete 5-stage upstream demand cascade (`supervisor -> pharmacy -> stockist -> distributor -> manufacturer`) with real-time timeline visualization.

## 2. Technical Architecture & Endpoints

### 2.1 Barcode Assets & Printable Manifest
- **Generator**: `scripts/make_barcodes.py` using Pillow to render individual 480x280 barcode cards with GS1 EAN-13 bars, human-readable numbers, product name, schedule badge, and cold-chain tags.
- **Composite Sheets**:
  - `fixtures/barcodes/printable_barcode_sheet.png` (4 columns x 5 rows 300 DPI composite grid).
  - `fixtures/barcodes/printable_barcode_sheet.pdf` (Printable A4 sheet for physical camera testing).
  - `fixtures/barcodes/barcodes_manifest.json` (Structured JSON catalog with 20 items).
- **Execution Wrappers**: `scripts/make-barcodes.bat` and `scripts/make-barcodes.ps1`.

### 2.2 Backend Endpoints
- `GET /api/v1/products/by-barcode/{code}`:
  - Scans catalog by EAN-13 barcode or SKU fallback.
  - Returns product information, price, schedule class, storage requirements.
  - Returns batches sorted strictly by `expiry_date ASC` (FEFO).
  - Flags batches with `days_to_expiry`, `is_near_expiry` (<= 60 days), `is_quarantined`, and `quarantine_reason`.
- `GET /api/v1/products?q={query}`:
  - Autocomplete search matching name, generic name, SKU, and barcode.
- `POST /api/v1/events/sale` (and alias `/api/v1/events/pos`):
  - Ingests `MobileSaleRequest`: `event_id`, `product_id`, `barcode`, `batch_id` / `batch_number`, `node_id`, `quantity`, `prescription_id`, `channel: "mobile_pos"`.
  - **Idempotency Guard**: Replaying with the same `event_id` returns cached result with `idempotent_replay: true` without double decrement.
  - **Quarantine Lockout**: Rejects quarantined or thermal-excursion batches with `409 BATCH_QUARANTINED`.
  - **Schedule H Check**: Flags missing prescription with `compliance_hold: true` and triggers HITL review warning.
  - **5-Stage Cascade Trace**: Emits ordered trace (`supervisor -> pharmacy -> stockist -> distributor -> manufacturer`) cached in `_in_memory_cascade_traces[correlation_id]`.
- `GET /api/v1/cascade/{correlation_id}`:
  - Returns full 5-stage trace with structured outputs, token telemetry, durations, and approval status.

### 2.3 Mobile Components (`mobile/src/features/pos/` & `mobile/src/features/cascade/`)
- `BarcodeScannerView.tsx`:
  - `expo-camera` optical barcode scanner with reticle frame & Electric Teal laser line.
  - 1-Tap Sample Barcode Chips Picker (Paracetamol, Amoxicillin, Human Insulatard, Azithral, Quarantine Test) for web and emulator environments.
  - 2500ms scan debouncing & haptic feedback (`expo-haptics`).
  - Autocomplete search bar querying `GET /api/v1/products?q=...`.
- `BatchSelector.tsx`:
  - FEFO-ordered batch cards with auto-selection of earliest active non-quarantined batch.
  - Amber badge for near-expiry (<= 60 days).
  - Prominent red lockout banner (`QUARANTINED — DO NOT DISPENSE`) with disabled interaction.
- `CascadeTimeline.tsx`:
  - Visualizes all 5 pipeline stages with icons and state badges (`completed`, `waiting_approval`, `running`, `skipped`, `failed`).
  - Actionable Human-in-the-Loop review link navigating to `/(tabs)/approvals`.
  - Formatted output grid & expandable raw telemetry JSON.
- `mobile/app/(tabs)/sell.tsx`:
  - Assembles end-to-end POS workflow: barcode scan -> FEFO batch pick -> quantity stepper -> Schedule H check -> idempotent checkout (`pendingEventIdRef`) -> live cascade trace.

## 3. Verification & Definition of Done
- **Backend Tests**: `backend/tests/test_task_m4_pos_lite_and_cascade.py` (9 tests, 100% pass).
- **All Mobile Tests**: 28 passed across M2, M3, and M4 in 18.26s.
- **Code Quality**: `ruff check` passes with 0 warnings/errors.
- **TypeScript**: `npm run typecheck` passes with 0 errors.
- **Web Export**: `npx expo export --platform web` bundles cleanly.
