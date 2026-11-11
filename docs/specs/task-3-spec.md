# Task Spec: Task 3 — Authentication, Roles, and Row-Level Security (RLS)

---

## 1. Objective
Enforce per-node data isolation and hierarchical role-based access control across MediFlux using Supabase Auth and PostgreSQL Row-Level Security (RLS) policies, satisfying RFP multi-tenant security requirements.

---

## 2. Inputs & Context
- **Dependencies**: Tasks 1 and 2, Supabase database schema (`nodes`, `profiles`, `inventory`, `batches`, `audit_ledger`, `events`).
- **Key Roles**:
  - `admin`: Global visibility across all nodes.
  - `manufacturer`: Production plant visibility over entire downstream tree.
  - `distributor`: Regional supply chain depot visibility over downstream stockists and pharmacies.
  - `stockist`: Intermediate supplier visibility over child pharmacies.
  - `pharmacy`: End-node retail visibility restricted strictly to own node inventory and transactions.
- **Reference Docs**: `AGENTS.md`, `tasks.md`, `docs/schema.md`.

---

## 3. Architecture & Design Decisions
- **PostgreSQL Recursive Function (`visible_node_ids()`)**:
  - `SECURITY DEFINER` and `SET search_path = public`.
  - Reads caller `auth.uid()`, looks up `node_id` and `role` in `profiles`.
  - For `role = 'admin'`, returns all `nodes.id`.
  - Otherwise, executes a recursive CTE starting at the user's `node_id` and traversing down `nodes.parent_id` to include the user's node and all descendant nodes.
- **Row-Level Security Policies (`supabase/migrations/003_auth_and_rls.sql`)**:
  - `nodes`: SELECT permitted if `id IN (SELECT visible_node_ids())`.
  - `inventory` & `batches`: Scoped to `node_id IN (SELECT visible_node_ids())`.
  - `audit_ledger` & `events`: Immutable. Authenticated role has SELECT and INSERT only. NO UPDATE or DELETE policies exist for the authenticated role, ensuring strict ledger tamper resistance.
- **Backend Security Module (`app/core/security.py`)**:
  - `CurrentUser`: Data structure containing `user_id`, `email`, `role`, `node_id`.
  - `AgentActor`: Background automated agent identity with scopes.
  - `Actor`: Unified caller model supporting both human users and background agents.
  - `get_current_user`: Bearer JWT verification using `SUPABASE_JWT_SECRET`.
  - `get_actor`: Accepts either `Authorization: Bearer <token>` or `X-API-Key` header.
  - `get_user_db_client`: Instantiates Supabase client with caller's JWT token for RLS execution.
  - `get_service_db_client`: Privileged service client for system operations.
- **Demo User Seeding (`scripts/seed_demo_users.py`)**:
  - Idempotently creates 5 demo users in Supabase Auth (admin, manufacturer, distributor, stockist, pharmacy) and links profile records.

---

## 4. Outputs & Deliverables
- **Database Migrations**:
  - `supabase/migrations/003_auth_and_rls.sql`
  - `supabase/migrations/20260101000004_auth_and_rls.sql`
- **Seeding Scripts**:
  - `scripts/seed_demo_users.py`
- **Security Logic**:
  - `backend/app/core/security.py`
- **Automated Tests**:
  - `backend/tests/test_rls_and_auth.py` (7 comprehensive test suites covering isolation, hierarchy, immutability, and token validation)
- **Documentation**:
  - `docs/specs/task-3-spec.md`
  - `docs/HOW_AI_BUILT_THIS.md`

---

## 5. Edge Cases & Error Handling
- **Missing or Invalid Token**: Returns standardized 401 Unauthorized (`UNAUTHORIZED`).
- **Unassigned Node**: Non-admin users without a node assigned receive an empty visible node set (`visible_node_ids()` returns 0 rows).
- **Cross-Node Reads**: Pharmacy querying another pharmacy's inventory receives 0 items under RLS filtering.
- **Audit Tampering**: Attempting UPDATE or DELETE on `audit_ledger` via authenticated user credentials is denied by PostgreSQL RLS.

---

## 6. Acceptance Criteria Checklist
- [x] SQL migration `003_auth_and_rls.sql` exists and contains valid syntax.
- [x] `visible_node_ids()` recursively traverses from parent node down through all descendant nodes.
- [x] RLS enabled on `nodes`, `profiles`, `inventory`, `batches`, `audit_ledger`, and `events`.
- [x] Audit ledger immutability: No UPDATE or DELETE policies exist for authenticated role.
- [x] Demo seed script `scripts/seed_demo_users.py` created and runnable.
- [x] Security dependencies export `CurrentUser`, `get_current_user`, `get_actor`, `get_user_db_client`, `get_service_db_client`.
- [x] Test suite `tests/test_rls_and_auth.py` passes cleanly (`pytest`).
