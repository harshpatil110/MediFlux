# Task 17 Specification: Adapter Forge (Self-Evolving API Translators)

## 1. Overview & Objective

Task 17 implements the **Adapter Forge** for MediFlux (RFP Phase 4), enabling autonomous coding agents to inspect legacy, heterogeneous pharmacy and manufacturer payloads (CSV, XML, and deeply nested JSON), write custom Python translation adapters, test them inside the Task 8 Restricted Execution Guard sandbox, self-heal via an automated fix loop, register passing adapters into the dynamic module registry, and expose live ingestion and marketplace APIs.

---

## 2. Core Architecture & Workflow

```
[Legacy Payload: CSV / XML / JSON]
                  │
                  ▼
      ┌─────────────────────────┐
      │   schema_inspector      │ Auto-detects format, field inventory, data types,
      └───────────┬─────────────┘ mapping rules to SaleEvent / BatchUpdate
                  │
                  ▼
      ┌─────────────────────────┐
      │      adapter_coder      │ Generates guard-compliant def run(input_data) -> dict
      └───────────┬─────────────┘ (AST/structural synthesizer fallback for test reliability)
                  │
                  ▼
      ┌─────────────────────────┐
      │     adapter_tester      │ 1. ASTGuard static check (blocks forbidden imports)
      └───────────┬─────────────┘ 2. SubprocessRunner isolated sandboxed execution
                  │               3. Pydantic validation (SaleEvent / BatchUpdate)
                  │               4. Expected output field equivalence
                  ├──────────────────────────────┐
            [Tests Passed]                 [Tests Failed]
                  │                              │
                  ▼                              ▼
      ┌─────────────────────────┐        ┌───────────────┐
      │    register_adapter     │        │ Check Attempt │
      │  (modules + adapters)   │        └───────┬───────┘
      └─────────────────────────┘                │
                                       ┌─────────┴─────────┐
                       [attempt < max_attempts]    [attempt >= max_attempts]
                                       │                           │
                                       ▼                           ▼
                               ┌───────────────┐           ┌───────────────┐
                               │   fix_loop    │           │  mark_failed  │
                               │  (retry code) │           │(status=failed)│
                               └───────┬───────┘           └───────────────┘
                                       │
                                       └─► (back to adapter_coder)
```

---

## 3. Component Details

### 3.1 Legacy Fixtures (`fixtures/legacy/` and `backend/fixtures/legacy/`)
Three paired sets of synthetic legacy payloads and their canonical outputs:
1. **Pharmacy Billing CSV**: `pharmacy_billing_sample.csv` + `pharmacy_billing_expected.json`
   - Headers: `BILL_NO,STORE_CODE,DRUG_SKU,BATCH_NUM,QTY_SOLD,UNIT_MRP,TXN_DATE`
   - Maps to canonical `SaleEvent` (`pharmacy_id`, `product_id`, `batch_id`, `quantity`, `source="pos"`).
2. **Manufacturer ERP XML**: `manufacturer_erp_sample.xml` + `manufacturer_erp_expected.json`
   - Tags: `<ERPDispatch><Header><PlantCode>...</PlantCode>...</Header><BatchDetails><ItemCode>...</ItemCode><LotNumber>...</LotNumber><MfgDate>YYYYMMDD</MfgDate><ExpDate>YYYYMMDD</ExpDate><Quantity>...</Quantity></BatchDetails></ERPDispatch>`
   - Maps to canonical `BatchUpdate` (`node_id`, `product_id`, `batch_number`, `quantity`, `mfg_date`, `exp_date`, `status="released"`).
3. **Nested Legacy POS JSON**: `nested_legacy_pos_sample.json` + `nested_legacy_pos_expected.json`
   - Nested structure: `{"txn_meta": {"outlet_ref": "...", ...}, "basket": {"line_items": [{"sku_code": "...", "lot_ref": "...", "count": ...}]}}`
   - Maps to canonical `SaleEvent`.

### 3.2 Forge LangGraph (`backend/app/graphs/forge.py`)
- **ForgeState**: Tracks `job_id`, `adapter_name`, `description`, `raw_sample`, `expected_output`, `target_schema`, `inspection_report`, `generated_code`, `test_results`, `error_logs`, `attempt_count`, `max_attempts`, `status`, `adapter_id`, `module_id`, `version`, `events`, and test injection hooks.
- **Node 1: Schema Inspector Agent (`schema_inspector_node`)**: Analyzes structure, detects format, infers canonical target schema, generates field inventory. Emits SSE event.
- **Node 2: Adapter Coder Agent (`adapter_coder_node`)**: Generates self-contained, guard-compliant Python code with signature `def run(input_data: Any) -> dict:`. Incorporates deterministic AST structural synthesizers for CSV, XML, and nested JSON.
- **Node 3: Adapter Tester Agent (`adapter_tester_node`)**:
  - Enforces `ASTGuard.validate_code(...)` to block forbidden imports (`os`, `sys`, `eval`, `exec`, `open`, etc.).
  - Runs code in `SubprocessRunner.execute_module(...)` with isolated environment variables.
  - Validates output dictionary with `SaleEvent.model_validate` or `BatchUpdate.model_validate` and checks equivalence with `expected_output`.
- **Fix Loop & Self-Healing**: On test failure, increments `attempt_count`, appends failure reason to `error_logs`, emits `step="fixing"` SSE event, and loops back to `adapter_coder_node`. After `max_attempts` (default 4), routes to `mark_failed_node`.
- **Node 4: Registration Node (`register_adapter_node`)**:
  - Registers active adapter in `module_registry` / `public.modules` with `kind='adapter'`, `version=next_ver`, `status='active'`.
  - Persists adapter metadata and test results in `public.adapters` and memory cache.
- **Node 5: Mark Failed Node (`mark_failed_node`)**:
  - Persists failed adapter in `public.adapters` with `status='failed'`, `is_active=False`, and detailed `error_logs`.

### 3.3 Live Legacy Ingestion Endpoint (`backend/app/api/v1/endpoints/ingest.py`)
- `POST /api/v1/ingest/{adapter_id}`:
  - Accepts raw text/csv, xml, or json payloads.
  - Resolves active adapter by UUID or name.
  - Runs `SubprocessRunner.execute_module(adapter.source_code, raw_input)` inside the Task 8 sandbox.
  - If `BatchUpdate`: validates schema and broadcasts `type="batch.update"` to `in_process_event_bus`.
  - If `SaleEvent`: atomically decrements stock via `apply_sale(event, correlation_id)` and broadcasts `type="pos.sales"` to `in_process_event_bus`.
  - Returns canonical event, ingestion status, inventory decrement status, and correlation ID.

### 3.4 Adapter Marketplace API (`backend/app/api/v1/endpoints/adapters.py`)
- `POST /api/v1/adapters/generate`: Submits adapter generation job, runs the Forge Graph, returns job ID and adapter ID.
- `GET /api/v1/adapters/jobs/{job_id}`: Returns JSON status or streams SSE events based on `Accept` header.
- `GET /api/v1/adapters/jobs/{job_id}/stream`: Real-time SSE event stream (`step="inspecting"`, `"coding"`, `"testing"`, `"fixing"`, `"registered"`, `"done"`).
- `GET /api/v1/adapters`: Lists all registered active adapters.
- `GET /api/v1/adapters/{identifier}`: Returns full details, source code, test results, and all historical versions.
- `POST /api/v1/adapters/{identifier}/rollback`: Reverts adapter to a prior version (or `active_version - 1`) and synchronizes `module_registry`.

---

## 4. Verification Checkpoints

1. **Legacy Fixtures**: Verified in `fixtures/legacy/` and `backend/fixtures/legacy/` with CSV, XML, and nested JSON.
2. **Auto-Translation Test**: Verified that CSV, XML, and JSON fixtures all produce functional, passing adapters.
3. **Guard Violation & Fix-Loop**: Verified that code with forbidden `import os` triggers AST guard violation, routes to fix loop, and self-heals into a passing adapter.
4. **Max Attempts Failure**: Verified that unfixable failures are marked `status='failed'` after exhausting retry attempts.
5. **Live Ingestion Cascade**: Verified that raw legacy CSV posted to `POST /api/v1/ingest/{adapter_id}` decrements stock and publishes `pos.sales` to `in_process_event_bus`.
6. **Marketplace & Rollback**: Verified generation, SSE streaming, catalog query, and version rollback to v1.
7. **Quality Gates**: All 124 backend tests pass with 0 failures; `ruff check backend` reports 0 warnings/errors; `npm run build` succeeds cleanly.
