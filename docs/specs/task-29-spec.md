# Task 29 Specification: Backend Failure Handling, Fault Injection & Core Resilience

## Overview
Task 29 hardens the MediFlux platform against free-tier LLM rate limits (429), malformed model outputs, provider outages, network disconnects, and cascade partial failures with deterministic resilience mechanics:

1. **Sovereign LLM Offline Error (HTTP 503)**:
   - Defined `SovereignLLMOfflineError` in `backend/app/core/errors.py` (and `backend/app/llm/schemas.py`) with `status_code=503` and `code="SOVEREIGN_LOCAL_MODEL_OFFLINE"`.
   - In `backend/app/llm/router.py`: when `sensitivity="sensitive"`, if local Ollama fails or is offline, raises `SovereignLLMOfflineError` (HTTP 503) and strictly forbids external hosted cloud fallback (protecting patient medical records and CDSCO Schedule H audits).
   - Global exception handler registered in `backend/app/main.py` and `backend/app/core/handlers.py` returning HTTP 503 with standardized error payload.

2. **Resilient JSON Parser (`parse_and_repair_llm_json`)**:
   - In `backend/app/llm/parser.py`, implemented `parse_and_repair_llm_json(raw_text, response_model, fallback_factory=None)`.
   - Strips markdown code fences (` ```json ` ... ` ``` ` or raw ` ``` ` blocks).
   - Automatically repairs unbalanced brackets `{` / `}` and `[` / `]`.
   - Strips trailing commas in objects and arrays (`{"a": 1,}`).
   - Converts unquoted (`{key: "value"}`) and single-quoted (`{'key': "value"}`) keys to double-quoted JSON.
   - Parses and validates against Pydantic `response_model`. If validation fails, safely invokes `fallback_factory()` without raising unhandled `json.JSONDecodeError`.

3. **Deterministic Fault Injection Context Manager (`inject_llm_fault`)**:
   - In `backend/app/llm/fault.py`, implemented `inject_llm_fault(provider, error_type)` supporting providers (`"nvidia"`, `"openrouter"`, `"ollama"`) and error types (`"rate_limit_429"`, `"server_error_500"`, `"bad_gateway_502"`, `"service_unavailable_503"`, `"timeout"`, `"connect_error"`, `"kill"`).
   - Integrated into `LLMRouter` (`backend/app/llm/router.py`) with preflight fault checking, triggering automatic failover in < 100ms across the fallback chain without crashing agent nodes.
   - Cleanly exported from `backend/app/llm/__init__.py`.

4. **HITL Task Expiration & HTTP 409 Conflict**:
   - In `backend/app/api/v1/endpoints/hitl.py` (`submit_hitl_decision`) and `backend/app/core/hitl.py`:
   - Inspects `expires_at` against current UTC time. If task is past `expires_at` (or status is `"expired"`), transitions task status to `"expired"`, logs to `audit_ledger` via `write_audit_entry`, and rejects decision attempts with `HTTPException(status_code=409, detail="Task has expired and cannot be approved")`.
   - In `backend/app/workers/hitl_expiry_worker.py`: automatically marks expired tasks with status `"expired"` while retaining compatibility with rejection fallback.

5. **Cascade Partial Failure Handling**:
   - In `backend/app/graphs/cascade.py`:
   - Updated `CascadeState` status literal to include `"partial_failure"`.
   - In `_execute_tier_node`, `stockist_node`, `distributor_node`, `manufacturer_node`, and `finalize_node`: when any downstream tier fails, retains earlier tiers' results, marks status as `"partial_failure"`, creates a high-priority HITL escalation task via `request_human_approval`, and records an audit ledger entry via `write_audit_entry` without crashing or throwing HTTP 500 errors.

6. **Duplicate Event Idempotency**:
   - In `backend/app/api/v1/endpoints/events.py` and `backend/app/events/service.py`: duplicate POS sale events return HTTP 200 with `{"status": "duplicate", "applied": False, "event_id": ...}` without triggering duplicate inventory deductions or double cascades.

---

## Verification Summary
- **Resilience Test Suite**: `backend/tests/test_milestone1_resilience.py` with 17 tests passed (100% pass rate).
- **Regression Test Suites**: `tests/test_cascade.py`, `tests/test_hitl_system.py`, `tests/test_llm_router.py`, `tests/test_events_and_sse.py` all passed (46 passed across 5 test suites).
- **Linter**: `ruff check .` across `backend` passes cleanly with 0 errors/warnings.


---

## Milestone 2 Specification: Deterministic LLM Replay Cache & Demo Reset (Requirement R3)

### Overview
Milestone 2 provides offline reliability tooling for high-stakes demos and local evaluations without dependence on external network connectivity or cloud LLM availability:

1. **Deterministic LLM Replay Cache (`backend/app/llm/cache.py`)**:
   - `LLMReplayCache` stores prompt/schema records in `fixtures/demo_cache/llm_replay_cache.json`.
   - When `LLM_CACHE_MODE="replay"` or `DEMO_MODE=true` (or `settings.DEMO_MODE=True`), serves cached responses with zero external network calls.
   - Any cache miss in replay mode raises `LLMCacheMissError`, guaranteeing that no unexpected external requests leak out.
   - Canonical SHA-256 computation: `SQLiteLLMCache.compute_cache_key(agent, messages, response_model)` across `f"{agent}:{messages_json}:{schema_json}"`.
   - Normalized cache key computation: `compute_normalized_cache_key` invariant to run-time UUIDs and ISO timestamps.
   - Pre-recorded complete 6-act demo cassette in `fixtures/demo_cache/llm_replay_cache.json` covering Acts 1 through 6.

2. **Demo Reset Endpoints (`backend/app/api/v1/endpoints/demo.py`)**:
   - `POST /api/v1/demo/reset`: Restores all dynamic modules to baseline v1 (`ensure_baseline_regulatory_modules`), clears dynamic adapters (`clear_adapter_store`), resets cold-chain batches and clears auto-quarantines (`reset_coldchain_state`), clears transient HITL tasks (`clear_hitl_tasks`), clears transient prescription records (`clear_prescription_store`), resets active inventory stock (`clear_service_state` / `seed_agent.seed_database`), and clears in-memory cryptographic audit ledger.
   - `GET /api/v1/demo/status`: Returns `demo_mode`, `cache_mode`, `cache_entries`, `baseline_module_status`, `quarantine_count`, and `pending_hitl_tasks`.
   - Master router registration in `backend/app/api/v1/router.py`.

3. **Standalone Reset Script (`scripts/reset_demo.py`)**:
   - CLI executable that performs clean baseline reset idempotently across all system components.

4. **Scripted Demo Runner (`scripts/run_demo.py`)**:
   - CLI tool that executes all 6 demo acts end-to-end with `--mode replay` and `--mode ollama`.
   - In `--mode replay`, executes completely offline using the replay cache with zero network calls.

### Verification Summary
- **Unit and Integration Tests**: `backend/tests/test_milestone2_demo_replay.py` with 7 tests passed (100% pass rate).
- **Milestone 1 Remediation & Regression**: `tests/test_milestone1_resilience.py`, `tests/test_llm_router.py`, `tests/test_cascade.py` all passing (41 total tests).
- **Demo Reset CLI**: `python -m scripts.reset_demo` executes idempotently with exit code 0.
- **Offline 6-Act Runner**: `python -m scripts.run_demo --mode replay` executes all 6 acts cleanly with exit code 0.
- **Lint Cleanliness**: `cd backend; ruff check .` passes with 0 warnings/errors.

---

## Milestone 3 Specification: Full Test Suites, UI Error Handling, and Hardened Verification (Task 29 Complete)

### 1. Comprehensive Automated Test Suites
- **Core Unit Tests (`backend/tests/test_unit_core.py`)**:
  - `TestASTGuardSecurity`: Blocks forbidden imports (`os`, `subprocess`, `sys`, `socket`), dangerous builtins (`eval`, `exec`, `open`, `__import__`), and dunder lookups (`__globals__`, `__class__`), while allowing safe transformations (`csv.DictReader`, dict lookups, math).
  - `TestModuleRegistryLifecycle`: Zero-downtime hot-swap and rollback across version history (`create_version`, `activate`, `rollback`).
  - `TestAuditLedgerTamperDetection`: Cryptographic hash chain validation detecting payload alterations and returning `broken_at_seq` and `broken_at_id`.
  - `TestEventBusDeduplication`: In-process asynchronous `InProcessEventBus` verifying deduplication of duplicate event IDs and idempotency guarantees.

- **Deterministic LangGraph FakeLLM Test Suite (`backend/tests/test_graphs_fakellm.py`)**:
  - Validates all 6 multi-agent LangGraph workflows end-to-end without external network calls:
    1. Demand Cascade Graph (`app.graphs.cascade.cascade_graph.ainvoke`)
    2. Adapter Forge Graph (`app.graphs.forge.run_forge`)
    3. Regulatory Pipeline Graph (`app.graphs.regulatory.run_regulatory_pipeline`)
    4. Sovereign Prescription Compliance Graph (`app.graphs.prescription.run_prescription_graph`)
    5. Cold-Chain Telemetry Graph (`app.graphs.coldchain.run_coldchain_pipeline`)
    6. Network Copilot Tool Loop (`app.graphs.copilot.run_copilot`)

- **API Security, RBAC, RLS & Webhooks Suite (`backend/tests/test_api_security_and_webhooks.py`)**:
  - Auth & RBAC: Token rejection (401 Unauthorized), actor role resolution (pharmacist, stockist, admin).
  - RLS Node Isolation: Multi-tier tree boundaries (`visible_node_ids`), pharmacy node boundary isolation.
  - Developer Platform Scoped API Keys: Plaintext key prefix `mfx_live_` shown once, stored as SHA-256 hash, granular scope enforcement (403 on missing `write:events`).
  - In-Memory Token Bucket: Rate limiter returns HTTP 429 upon quota exhaustion with `Retry-After` header.
  - Outbound Webhooks: HMAC-SHA256 signature generation and tampering verification (`verify_webhook_signature`), exponential retry, and auto-disable after repeated failures.

- **UI Demo Path & Error Normalizer Suite (`backend/tests/test_ui_demo_path.py`)**:
  - Built bundle integrity verification (`frontend/dist/index.html` & hashed JS assets).
  - Domain error normalizer (`frontend/src/lib/errorMessages.ts`) covering all 6 domain failure codes.
  - Warm Editorial Minimalism error banner (`frontend/src/components/shared/LlmErrorBanner.tsx`).
  - Header & modal demo reset triggers (`AppShell.tsx`, `BackendSettingsModal.tsx`).
  - Live backend demo endpoints (`/api/v1/demo/status`, `/api/v1/demo/reset`).

- **Master System Verification Suite (`backend/tests/test_task29_reliability_and_demo.py`)**:
  - Fault injection testing all 6 failure modes with transparent router failover.
  - Deterministic replay cache latency (< 50ms) and miss enforcement (`LLMCacheMissError`).
  - Offline demo runner executing all 6 interview presentation acts with returncode 0.
  - Clean demo baseline state restoration.
  - Secrets scanner audit returning 100% clean.

### 2. Secrets & Credential Leakage Scanner (`scripts/check_secrets.py`)
- Audits git-tracked files against regex patterns for NVIDIA NIM, OpenRouter, Google/Gemini, and OpenAI API keys, RSA/EC private keys, and live JWT tokens.
- Asserts `.env` is untracked by git.
- Asserts `.env.example` contains safe placeholders and includes all required keys (`SUPABASE_JWT_SECRET`, etc.).

### 3. Golden Path E2E Script (`scripts/e2e_verify.py`)
- Synchronous and asynchronous 6-step golden path verification:
  - Step 1: Liveness & Desktop CORS
  - Step 2: Single-Unit POS Sale & 4-Tier Demand Cascade
  - Step 3: Self-Evolving Adapter Forge Synthesis
  - Step 4: Autonomous Regulatory Pipeline & Staging Diff
  - Step 5: Cold-Chain Arrhenius Degradation Auto-Quarantine
  - Step 6: Sovereign Vision Prescription Scan & SHA-256 Audit Chain Verification

