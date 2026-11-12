# Task 15 Specification: Human-in-the-Loop (HITL) Approval System

## 1. Overview & Scope

Task 15 establishes the **Human-in-the-Loop (HITL) Approval System** (RFP 3.5) for the MediFlux pharmaceutical supply chain ecosystem.
When autonomous agents attempt high-risk or regulatory-sensitive operations—such as modifying an active in-progress manufacturing batch, authorizing cross-border freight dispatches, overriding Schedule H prescription verification, or deploying dynamic pricing/compliance modules—the system must:

1. **Pause execution** using LangGraph native `interrupt` primitives and state flags (`status = "waiting_hitl"`).
2. **Persist pending approval tasks** in the `hitl_tasks` table and in-memory test store with calculated expiration deadlines.
3. **Record immutable audit events** in `audit_ledger` with SHA-256 hash chaining (`HITL_TASK_CREATED`).
4. **Emit real-time SSE notifications** (`hitl_pending`, `hitl_resolved`, `hitl_expired`) on the `hitl` event stream.
5. **Provide management REST endpoints** under `/api/v1/hitl/` allowing authorized operators to inspect pending tasks and submit decisions (`approve` or `reject`) with strict Role-Based Access Control (RBAC).
6. **Resume checkpointed execution workflows** dynamically upon approval or roll back / halt safely upon rejection.
7. **Automatically expire overdue tasks** via the asynchronous `HITLExpiryWorker` background job.

---

## 2. Policy Configuration (`config/hitl_policies.yaml`) & Parser (`app/core/hitl_policy.py`)

### 2.1 Policy Rules

Defined in `config/hitl_policies.yaml`:
```yaml
policies:
  in_progress_batch_change:
    enabled: true
    required_roles: ["manufacturer_admin", "compliance_officer", "admin"]
    expiry_hours: 24
    description: "Modifying or reprioritizing a production batch currently in status in_progress."

  cross_border_shipment:
    enabled: true
    required_roles: ["logistics_manager", "compliance_officer", "admin"]
    expiry_hours: 12
    description: "Dispatching shipments crossing regional or international borders."

  schedule_h_override:
    enabled: true
    required_roles: ["pharmacist_in_charge", "compliance_officer", "admin"]
    expiry_hours: 6
    description: "Fulfilling Schedule H medication orders without automated doctor prescription verification."

  module_activation:
    enabled: true
    required_roles: ["system_admin", "compliance_officer", "admin"]
    expiry_hours: 48
    description: "Activating a new WASM or python policy module version."

  reorder_approval:
    enabled: true
    required_roles: ["pharmacist_in_charge", "stockist_admin", "admin"]
    expiry_hours: 24
    description: "Approval for bulk inventory replenishment reorders."
```

### 2.2 Policy Parser API (`app/core/hitl_policy.py`)

- `load_hitl_policies(policy_file_path: str = "config/hitl_policies.yaml") -> dict`: Discovers and parses YAML policies with automatic fallback to built-in defaults.
- `get_hitl_policy(task_type: str) -> dict`: Retrieves policy metadata (normalizing underscores/hyphens and prefixes like `approve_`).
- `is_hitl_required(task_type: str) -> bool`: Evaluates if human intervention is enabled for this action.
- `get_required_roles(task_type: str) -> list[str]`: Returns authorized roles for RBAC verification.
- `get_expiry_hours(task_type: str) -> int`: Returns policy expiry window in hours.

---

## 3. Core Approval Primitives (`app/core/hitl.py`)

- `request_human_approval(...)`:
  - Consults policy via `is_hitl_required(task_type)`. If `False`, returns `{"status": "bypassed", "approved": True}`.
  - If `True`, calculates `expires_at = now() + expiry_hours`.
  - Persists record in `hitl_tasks` table and `_in_memory_hitl_tasks`.
  - Writes immutable `HITL_TASK_CREATED` to `audit_ledger`.
  - Emits SSE event `hitl_pending` to EventBus topic `hitl`.
  - In checkpointed workflows, executes LangGraph native `interrupt(...)`; for cascade orchestration, sets `status = "waiting_hitl"`.
- `create_hitl_task(...)`: Helper for directly persisting pending tasks from tier agent scheduler loops.
- `register_resumable_graph(thread_id, graph, config)` & `resume_graph_thread(thread_id, payload)`: In-memory registry enabling asynchronous thread resumption across background processes.
- `record_audit_log(action_type, payload, node_id)`: SHA-256 chained ledger logging.

---

## 4. API Endpoints (`app/api/v1/endpoints/hitl.py`)

Mounted at `/api/v1/hitl` and tagged with `"HITL"`:

1. `GET /api/v1/hitl/tasks`
   - **Query Parameters**: `status` (`pending`, `approved`, `rejected`, `expired`, `all`), `task_type`, `limit` (1-100).
   - **Security**: `Depends(get_current_user)`.
   - **Response**: List of task definitions from Supabase `hitl_tasks` table with in-memory fallback.
2. `GET /api/v1/hitl/tasks/{task_id}`
   - **Security**: `Depends(get_current_user)`.
   - **Response**: Single task record or 404 Not Found error.
3. `POST /api/v1/hitl/tasks/{task_id}/decision`
   - **Security**: `Depends(get_current_user)`.
   - **Request Body**:
     ```json
     {
       "decision": "approve",
       "note": "Verified regulatory license and batch formulation parameters."
     }
     ```
   - **Validation & RBAC Workflow**:
     1. Verifies task exists (404) and is in `pending` status (400 if already decided/expired).
     2. Enforces RBAC: verifies `current_user.role` against policy `required_roles`. Returns 403 Forbidden if unauthorized.
     3. Updates task status to `approved` or `rejected`, stores `decided_by`, `decided_at`, and `decision_note`.
     4. Appends `HITL_DECISION_SUBMITTED` entry to `audit_ledger`.
     5. Emits `hitl_resolved` SSE event on topic `hitl`.
     6. Resumes paused LangGraph thread if checkpoint exists.
     7. Returns `HITLDecisionResponse` with resolution metadata and execution outcome.

---

## 5. Expiry Background Worker (`app/workers/hitl_expiry_worker.py`)

- `process_expired_hitl_tasks()`:
  - Scans `hitl_tasks` for tasks where `status == 'pending'` and `expires_at < NOW()`.
  - Auto-updates task `status = 'rejected'`, `decision_note = 'Auto-rejected: Task expired without human intervention.'`.
  - Records `HITL_TASK_AUTO_EXPIRED` in `audit_ledger`.
  - Emits `hitl_expired` SSE event to notify operator dashboards.
  - Resumes paused LangGraph thread with rejection fallback `{"approved": False, "reason": "expired"}`.
- `HITLExpiryWorker`: Asynchronous background task running periodic scans every 30 seconds, integrated into FastAPI lifespan in `app/main.py`.

---

## 6. Cascade Graph Multi-Tier Interruption Gates (`app/graphs/cascade.py`)

1. **Pharmacy Node**: Schedule H antibiotics lacking valid doctor prescription trigger `schedule_h_override`. Order replenishment is paused until a `pharmacist_in_charge` signs off.
2. **Distributor Node**: Freight shipments crossing state or national boundaries trigger `cross_border_shipment`. Dispatch is paused until a `logistics_manager` approves.
3. **Manufacturer Node**: Demands requiring alteration of active manufacturing lines trigger `in_progress_batch_change`. Production line updates are paused until a `compliance_officer` approves.
4. **Conditional Routing**: Edges route to `END` whenever any node returns `status == "waiting_hitl"`, gracefully preserving intermediate state.

---

## 7. Verification & Automated Test Suite (`tests/test_hitl_system.py`)

- `test_task_pause_and_creation`: Verifies cross-border shipment and in-progress batch modifications halt cascade execution with `waiting_hitl` and create pending tasks with correct expiry hours.
- `test_approve_and_resume`: Verifies submitting approval via API updates task status, writes audit log, emits SSE event, and resumes cascade workflow to completion.
- `test_reject_and_safe_fallback`: Verifies rejection via API cancels gated actions and records decision in audit ledger.
- `test_rbac_authorization_denied`: Confirms unauthorized user roles receive HTTP 403 Forbidden.
- `test_server_restart_persistence`: Validates that pending tasks and graph state checkpoints survive backend process restarts and resume cleanly from disk.
- `test_hitl_expiry_worker`: Verifies the background worker identifies expired tasks, auto-rejects them, emits `hitl_expired` SSE events, and writes audit records.
