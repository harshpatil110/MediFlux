# Task Spec: Task 2 — Supabase Project and Database Schema

---

## 1. Objective
Establish the relational data foundations for MediFlux, creating PostgreSQL migrations defining all 10 supply-chain architectural layers, custom enumerations, pgvector embeddings, performance indexes, and atomic PL/pgSQL inventory mutation routines.

---

## 2. Inputs & Context
- **Dependencies**: Task 1 repository scaffold, `.env.example`, Supabase credentials configuration.
- **Reference Docs**: `AGENTS.md`, `tasks.md`, `docs/schema.md`.
- **System Constraints**:
  - No Redis (In-memory caching and Supabase `inventory`/`events` tables for state).
  - No Kafka/Redpanda (Supabase `events` table serves as append-only source of truth).
  - Row-level locking for inventory mutations (`FOR UPDATE`).

---

## 3. Architecture & Design Decisions
- **Migrations Structure**:
  - `supabase/migrations/20260101000001_initial_schema.sql`: Extensions (`uuid-ossp`, `vector`), 10 custom enumerations, and 25 core domain tables.
  - `supabase/migrations/20260101000002_atomic_functions.sql`: PL/pgSQL atomic concurrency routines (`apply_sale`, `apply_return`, `apply_expiry`).
  - `supabase/migrations/20260101000003_indexes.sql`: B-Tree indexes on correlation IDs and timestamps, plus HNSW cosine vector search indexes.
- **Vector Search**:
  - `demand_signals.embedding`: 1536-dimensional vector for AI-predicted demand patterns.
  - `reg_notifications.embedding`: 1536-dimensional vector for RAG retrieval over CDSCO drug notices.

---

## 4. Outputs & Deliverables
- **Migration Scripts**:
  - `supabase/migrations/20260101000001_initial_schema.sql`
  - `supabase/migrations/20260101000002_atomic_functions.sql`
  - `supabase/migrations/20260101000003_indexes.sql`
- **Documentation**:
  - `docs/schema.md`
  - `docs/specs/task-2-spec.md`
  - `docs/HOW_AI_BUILT_THIS.md` updated with Task 2 audit entry.

---

## 5. Edge Cases & Error Handling
- **Concurrency Collisions**: Solved via `FOR UPDATE` locking inside `apply_sale`. Overselling is blocked by returning `{"oversold": true, "success": false}` without reducing quantity below zero.
- **Missing Inventory Records**: Handled gracefully in `apply_sale` with defensive error JSON return.
- **Negative Input Quantities**: Validated and rejected at function boundary.
- **Batch Expiry Depletion**: `apply_expiry` checks network-wide remaining stock before automatically updating `batches.status = 'expired'`.

---

## 6. Acceptance Criteria Checklist
- [x] Migration files created in `supabase/migrations/` (initial schema, atomic functions, indexes).
- [x] All 25 tables defined with appropriate UUID primary keys, foreign key constraints, and default values.
- [x] pgvector extension enabled with 1536-dim vector columns on `demand_signals` and `reg_notifications`.
- [x] Idempotency constraint (`UNIQUE (event_id)`) on `events` table.
- [x] Atomic functions (`apply_sale`, `apply_return`, `apply_expiry`) created with PL/pgSQL.
- [x] Performance B-Tree indexes and HNSW vector cosine indexes defined in migration 3.
- [x] Detailed documentation created in `docs/schema.md`.
- [x] Audit log updated in `docs/HOW_AI_BUILT_THIS.md`.

