# Task M5 Specification: Mobile HITL Approvals (Human-in-the-Loop)

## 1. Overview
Task M5 enables authorized supply-chain operators to inspect, approve, or reject high-risk autonomous agent decisions from their mobile devices (`mobile/app/(tabs)/approvals.tsx` and `mobile/app/approvals/[id].tsx`), backed by `config/hitl_policies.yaml`, `GET /api/v1/hitl/tasks`, `POST /api/v1/hitl/tasks/{id}/decision`, and live Server-Sent Events (`hitl` topic). It features 4 type-specific payload renderers (`cross_border_shipment`, `batch_modification`, `regulatory_activation`, `doctor_verification` / `schedule_h_override`) plus a generic JSON fallback, optional biometric confirmation (`expo-local-authentication`), strict non-optimistic server verification, role-based restriction enforcement (HTTP 403 `HITL_FORBIDDEN_ROLE`), and graceful handling of expired or already-finalized tasks.

## 2. Technical Architecture & Endpoints

### 2.1 Policy Alignment (`config/hitl_policies.yaml` & `backend/app/core/hitl_policy.py`)
- Defines explicit role permissions (`allowed_roles`), `risk_level`, `timeout_minutes`, and `description` for all 5 canonical task types:
  1. `cross_border_shipment`:
     - `allowed_roles`: `["admin", "distributor", "stockist", "regulator", "logistics_manager", "compliance_officer"]`
     - `risk_level`: `"high"`
     - `timeout_minutes`: 720 (12 hours)
  2. `batch_modification`:
     - `allowed_roles`: `["admin", "manufacturer", "manufacturer_admin", "compliance_officer"]`
     - `risk_level`: `"high"`
     - `timeout_minutes`: 1440 (24 hours)
  3. `regulatory_activation` (alias `regulatory_hot_swap`, `regulatory_module_activation`):
     - `allowed_roles`: `["admin", "regulator", "compliance_officer", "system_admin"]`
     - `risk_level`: `"critical"`
     - `timeout_minutes`: 2880 (48 hours)
  4. `doctor_verification` (alias `prescription_doctor_verification`, `prescription_unknown_drug`):
     - `allowed_roles`: `["admin", "regulator", "stockist", "pharmacist_in_charge", "compliance_officer"]`
     - `risk_level`: `"medium"`
     - `timeout_minutes`: 720 (12 hours)
  5. `schedule_h_override` (alias `compliance_hold`):
     - `allowed_roles`: `["admin", "regulator", "stockist", "compliance_officer"]`
     - `risk_level`: `"high"`
     - `timeout_minutes`: 360 (6 hours)
- Exposes policy map via `GET /api/v1/hitl/policies`.

### 2.2 Backend Endpoints (`backend/app/api/v1/endpoints/hitl.py`)
- `GET /api/v1/hitl/tasks` (and `/hitl`, `/hitl/tasks/{task_id}`):
  - Runs automatic expiry sweep transitioning overdue pending tasks (`expires_at <= now()`) to `"expired"`.
  - Supports query filters: `?status=pending|decided|approved|rejected|expired|all&task_type=&risk_level=&limit=50`.
  - Enriches every task for the calling user: `allowed_roles`, `can_current_user_decide` (bool), `cannot_decide_reason` (string), and `expires_at`.
- `POST /api/v1/hitl/tasks/{task_id}/decision`:
  - **RBAC Policy Enforcement**: Returns `403 Forbidden` (`code: "HITL_FORBIDDEN_ROLE"`) when caller's role is not authorized.
  - **Graceful Already-Finalized Handling**: When a task is already `approved`, `rejected`, or `expired`, returns `200 OK` with `already_finalized: true`, `status: task.status`, and `outcome: task.status`.
  - **Graph Resumption**: Upon approval, resumes the paused graph, transitions paused step in `_in_memory_cascade_traces[correlation_id]` to `succeeded` / `done`, advances downstream stages to `done`, marks cascade `completed`, writes cryptographic audit entry to `public.audit_ledger`, and emits SSE events on `hitl` (`hitl.decided`) and `cascade.updates`.
- `POST /api/v1/hitl/tasks/trigger`:
  - Simulator trigger for dev testing of rich payloads (notably `cross_border_shipment`), setting up paused cascade and emitting SSE events.

### 2.3 Mobile Screens & Components (`mobile/src/features/approvals/` & `mobile/app/`)
- `renderers.tsx`:
  - `CrossBorderShipmentRenderer`: Route card (origin -> checkpoint -> destination, km), products manifest with INR currency formatting, compliance/risk flags, and priority badges.
  - `BatchModificationRenderer`: Batch identity, parameter comparison (previous -> proposed with strikethrough), reason, and API raw material stock impact with buffer breach warning.
  - `RegulatoryActivationRenderer`: Version transition pill, change summary, staging test & AST guard metrics, and collapsible simplified diff.
  - `PrescriptionOverrideRenderer`: Sovereign local data privacy banner, patient initials, prescribing doctor NMC credentials, audit status, and schedule class pills.
  - `GenericJsonRenderer`: Key-value summary rows and collapsible formatted JSON tree.
  - `TaskPayloadRenderer`: Dynamic dispatcher based on task type.
- `mobile/app/(tabs)/approvals.tsx`:
  - Segmented filter tabs: `Pending (N)` and `Decided (M)`.
  - Role policy banner explaining view-only mode for unauthorized roles like pharmacy.
  - Quick demo trigger button: `⚡ Simulate Cross-Border Shipment Hold`.
  - Live ticking countdown timer for pending tasks and real-time SSE refresh.
- `mobile/app/approvals/[id].tsx`:
  - Detailed task inspection with agent reasoning, type-specific renderer, and related cascade deep-link (`/cascade/${task.correlation_id}`).
  - Biometric authentication confirmation modal (`expo-local-authentication`).
  - Strict non-optimistic server outcome presentation (Approved, Rejected, Expired, Already Finalized).
- `mobile/app/(tabs)/_layout.tsx`:
  - Live numeric `tabBarBadge` on Approvals tab, synchronized with SSE events on `hitl`.

## 3. Verification & Definition of Done
- **Automated Pytest Suite**: `backend/tests/test_task_m5_mobile_approvals.py` (5 tests, 100% pass across all 4 acceptance criteria).
- **Comprehensive Backend Regression**: 20/20 HITL-related tests pass.
- **Linter**: `ruff check` passes with 0 warnings/errors.
- **TypeScript**: `npm run typecheck` in `mobile/` passes with 0 errors.
- **Web Export**: `npx expo export --platform web` bundles cleanly.
