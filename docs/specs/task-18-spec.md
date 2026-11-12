# Task 18 Specification: Regulatory Pipeline (Crawler, Analyst, DevOps Coding Agent, Hot-Swap)

## 1. Overview & Objective

Task 18 implements the **Autonomous Regulatory Pipeline** for MediFlux (RFP Phase 4). The system monitors authoritative regulatory bodies across the Indian pharmaceutical landscape (Ministry of Health & Family Welfare — MoHFW, Central Drugs Standard Control Organisation — CDSCO, and National Pharmaceutical Pricing Authority — NPPA / Gazette of India) for price ceiling mandates, track-and-trace serialization directives, and clinical notices.

Upon detection of a regulatory notice:
1. Ingests, normalizes, and deduplicates notification text via SHA-256 content hashing.
2. Extracts structured `RegChange` directives using a multi-agent analyst with confidence scoring. Low-confidence (<0.70) or corrupt notices pause to Human-in-the-Loop (`regulatory_clarification`).
3. Dispatches a DevOps Coding Agent to fetch active v1 module code and synthesize guard-compliant v2 mutations (e.g. DPCO ceiling price enforcement or 2D barcode serialization).
4. Generates regulatory assertions while guaranteeing 100% regression coverage of baseline v1 tests.
5. Executes sandboxed static AST inspection (`ASTGuard`) and subprocess verification (`SubprocessRunner`) with an automated fix loop up to `max_attempts`.
6. Gates deployment via HITL approval (`regulatory_hot_swap`) whenever `REG_AUTO_DEPLOY=False` or the affected module is pricing/compliance.
7. Executes zero-downtime hot-swap upon approval by atomically repointing the active module pointer in `module_registry` without server restart and logging to `public.audit_ledger`.
8. Supports instant rollback restoring previous behavior and recording to the immutable audit ledger.

---

## 2. Core Architecture & Workflow

```
[Official Notice: MoHFW / CDSCO / NPPA / Gazette]
                       │
                       ▼
           ┌────────────────────────┐
           │ crawl_regulatory_notice│ Ingestion, SHA-256 deduplication,
           └───────────┬────────────┘ and persistence in reg_notifications
                       │
                       ▼
           ┌────────────────────────┐
           │      analyst_node      │ Extracts structured RegChange
           └───────────┬────────────┘ Confidence score calculation
                       │
        ┌──────────────┴──────────────┐
  [confidence < 0.70]          [confidence >= 0.70]
        │                             │
        ▼                             ▼
┌──────────────────┐      ┌────────────────────────┐
│  HITL Clarify    │      │    devops_coder_node   │ Fetches v1 code & tests
│ (status=awaiting │      └───────────┬────────────┘ Mutates code & generates unified diff
│_clarification)   │                  │
└──────────────────┘                  ▼
                          ┌────────────────────────┐
                          │  test_generator_node   │ Generates new regulatory tests
                          └───────────┬────────────┘ Preserves 100% regression suite
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │staging_test_runner_node│ 1. ASTGuard static check
                          └───────────┬────────────┘ 2. Subprocess sandboxed tests
                                      │
                       ┌──────────────┴──────────────┐
                 [Tests Passed]                [Tests Failed]
                       │                             │
                       ▼                             ▼
           ┌───────────────────────┐         ┌───────────────┐
           │   deploy_gate_node    │         │ Check Attempt │
           └───────────┬───────────┘         └───────┬───────┘
                       │                             │
           ┌───────────┴───────────┐         ┌───────┴───────┐
     [must_gate = True]     [Auto-Deploy] [attempt < max] [attempt >= max]
           │                       │         │               │
           ▼                       ▼         ▼               ▼
   ┌───────────────┐       ┌──────────────┐┌───────────┐ ┌───────────┐
   │  HITL Task    │       │   Hot-Swap   ││ fix_loop  │ │mark_failed│
   │ (awaiting_    │       │ (status=     ││  (retry)  │ │ (failed)  │
   │  approval)    │       │   deployed)  │└─────┬─────┘ └───────────┘
   └───────┬───────┘       └──────────────┘      │
           │                                     └──► (to devops_coder)
   [Approved via API]
           │
           ▼
   ┌───────────────┐
   │Zero-Downtime  │ Atomically repoint module_registry
   │   Hot-Swap    │ Write REGULATORY_HOT_SWAP_DEPLOYED to audit_ledger
   └───────┬───────┘
           │
     [Rollback API]
           │
           ▼
   ┌───────────────┐
   │Instant Rollback Restore prior module version
   │               │ Write REGULATORY_HOT_SWAP_ROLLED_BACK to audit_ledger
   └───────────────┘
```

---

## 3. Data Contracts & Schemas

### 3.1 `RegChange`
```python
class RegChange(BaseModel):
    topic: str
    effective_date: str = "immediate"
    affected_module_kind: Literal["pricing", "compliance"]
    target_module_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    summary: str
    confidence: float = 1.0
```

### 3.2 `RegulatoryState`
```python
class RegulatoryState(TypedDict, total=False):
    run_id: str
    notification_id: str
    notification_text: str
    source: str
    title: str
    content_hash: str
    correlation_id: str
    reg_change: dict[str, Any]
    confidence: float
    v_current_code: str
    v_current_tests: str
    v_current_version: int
    v_new_code: str
    v_new_tests: str
    diff: str
    staged_version: int
    active_version: int
    test_results: dict[str, Any]
    attempt_count: int
    max_attempts: int
    error_logs: list[str]
    status: str
    hitl_task_id: str | None
    events: list[dict[str, Any]]
```

---

## 4. API Endpoints (`/api/v1/regulatory`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/notifications` | Ingest raw regulatory notice text, compute SHA-256 hash, and execute pipeline. Returns run state with status (e.g. `awaiting_approval`). |
| `GET` | `/runs/{run_id}` | Retrieve pipeline execution status, parsed `RegChange`, unified diff, test results, and associated `hitl_task_id`. |
| `POST` | `/check-now` | Trigger on-demand crawler check across configured MoHFW, CDSCO, and NPPA sources. |
| `POST` | `/runs/{run_id}/approve` | Approve HITL staging task, resolve pending approval, execute zero-downtime hot-swap, and write to audit ledger. |
| `POST` | `/runs/{run_id}/rollback` | Instantly roll back an active regulatory deployment to the previous version and record to audit ledger. |
| `POST` | `/price-check` | Execute live pricing calculation against the active `pricing_engine` module to verify immediate hot-swap behavior without server restart. |
| `GET` | `/notifications` | List parsed and ingested regulatory notices. |
| `GET` | `/runs` | List history of regulatory pipeline runs. |

---

## 5. Security & Isolation

- **AST Guard Enforcement**: All synthesized Python module code and generated test code must pass static inspection by `ASTGuard` (blocking `import os`, `subprocess`, `sys`, socket, and filesystem tampering).
- **Subprocess Isolation**: Test suites are executed via `SubprocessRunner` with strict execution timeouts (default 10s).
- **Immutable Audit Logging**: Every hot-swap activation and rollback writes a cryptographically linked SHA-256 entry to `public.audit_ledger` with actor, timestamp, version pointers, and unified diff payload.
- **Architectural Rules (AGENTS.md)**: Zero Redis, Zero Docker, Zero WASM, Zero Kafka. All state is persisted in Supabase tables (`reg_notifications`, `regulatory_runs`, `modules`, `hitl_tasks`, `audit_ledger`) with in-memory fallbacks for offline test isolation.
