# Task Spec: Task 6 — Event Bus, Event Persistence, and SSE Stream

---

## 1. Objective
Build the ultra-fast, zero-LLM event ingestion path and real-time streaming backbone for MediFlux:
1. Event model definitions (`EventEnvelope`, `SaleEvent`, `ReturnEvent`, `ExpiryEvent`, `SensorReadingEvent`).
2. Abstract `EventBus` interface and `InProcessEventBus` implementation backed by `asyncio.Queue` and database persistence.
3. Stored procedure `apply_sale` for atomic, idempotent inventory decrements and audit ledgering (`supabase/migrations/004_events_and_inventory_rpc.sql`).
4. High-performance REST endpoints (`POST /api/v1/events/sale`, `POST /api/v1/events/sale/batch`).
5. Server-Sent Events (SSE) streaming endpoint (`GET /api/v1/stream`) with `Last-Event-ID` replay support, heartbeat keepalives, and multi-tenant RLS node isolation.

---

## 2. Inputs & Context
- **Dependencies**: Tasks 1–5, `sse-starlette`, FastAPI, Supabase database schema.
- **Constraints & Rules**:
  - Zero LLM calls on the POS ingestion path (critical for POS counter throughput < 1s).
  - Strictly no Apache Kafka or Redpanda in the MVP; in-process event bus with pluggable interface.
  - Idempotent event ingestion: duplicate `event_id` submissions must not double-decrement inventory.
  - Multi-tenant node isolation: pharmacy users must not receive events originating from other retail pharmacies.

---

## 3. Architecture & Design Decisions
- **Domain Event Models (`app/events/models.py`)**:
  - `EventEnvelope`: Standard envelope containing `event_id`, `type`, `node_id`, `correlation_id`, `timestamp`, `payload`.
  - Typed payloads: `SaleEvent`, `ReturnEvent`, `ExpiryEvent`, `SensorReadingEvent`.
  - Backward compatibility: aliased `DomainEvent = EventEnvelope` and preserved simulator payload classes.
- **Event Bus Backbone (`app/events/bus.py`)**:
  - `EventBus` abstract base class defining `publish` and `subscribe`.
  - `InProcessEventBus` managing topic queues (`pos.sales`, `cascade.updates`, `agent.activity`, `hitl`, `coldchain`, `regulatory`, `webhooks`) via `asyncio.Queue`.
  - Automatic persistence hook upserting events into Supabase `events` table with `on_conflict="event_id"`.
  - In-memory event history with `get_events_after` for reconnection replay.
- **Atomic Database Procedure (`supabase/migrations/004_events_and_inventory_rpc.sql` & `app/events/service.py`)**:
  - Stored procedure `apply_sale`:
    1. Checks if `event_id` exists in `events`; if duplicate, returns `{ "status": "duplicate", "applied": false }`.
    2. Inserts new record into `events`.
    3. Decrements `inventory.quantity` atomically ensuring non-negative balance (`GREATEST(quantity - p_quantity, 0)`).
    4. Computes rolling cryptographic hash and records immutable entry in `audit_ledger`.
    5. Returns `{ "status": "success", "applied": true, "remaining_quantity": ... }`.
  - Python fallback in `events/service.py` ensures sub-millisecond execution during unit tests or database failover.
- **Ingestion Endpoints (`app/api/v1/endpoints/events.py`)**:
  - `POST /api/v1/events/sale`: Ingests single POS dispense, runs `apply_sale`, broadcasts to `pos.sales` topic, returns 202 Accepted.
  - `POST /api/v1/events/sale/batch`: Bulk ingestion of sales for simulators and benchmark load tests.
- **SSE Streaming Endpoint (`app/api/v1/endpoints/stream.py` & `app/events/sse.py`)**:
  - `GET /api/v1/stream`:
    - Secured with `get_current_user` dependency.
    - Filters events against caller's `visible_node_ids()` (pharmacy only sees own events; stockist sees child nodes; admin sees all).
    - Checks `Last-Event-ID` header/query and replays missed events before streaming live events.
    - Emits 15-second heartbeat ping comments to keep connections alive through proxies and firewalls.
    - Automatically cleans up subscription queues upon client disconnection.

---

## 4. Outputs & Deliverables
- **Database Migrations**:
  - `supabase/migrations/004_events_and_inventory_rpc.sql`: Stored function `apply_sale`.
- **Backend Modules**:
  - `backend/app/events/models.py`: Pydantic event models.
  - `backend/app/events/bus.py`: `EventBus` and `InProcessEventBus`.
  - `backend/app/events/service.py`: `apply_sale` orchestration and state manager.
  - `backend/app/events/sse.py`: Generator for SSE streaming and replay.
  - `backend/app/api/v1/endpoints/events.py`: POS sale ingestion endpoints.
  - `backend/app/api/v1/endpoints/stream.py`: SSE real-time stream endpoint.
  - `backend/app/events/__init__.py`: Package exports.
- **Test Suite**:
  - `backend/tests/test_events_and_sse.py`: 7 integration tests.

---

## 5. Automated Verification & Results
- **Pytest**:
  ```powershell
  cd backend; .\venv\Scripts\pytest
  # Result: 42 passed in 4.79s (7/7 test_events_and_sse.py passed)
  ```
- **Linter**:
  ```powershell
  cd backend; .\venv\Scripts\ruff check .
  # Result: All checks passed! (0 warnings, 0 errors)
  ```
- **Test Coverage**:
  1. `test_sale_event_ingestion_and_latency`: Sub-second latency (< 1s) from POST to broadcast.
  2. `test_duplicate_sale_event_idempotency`: Duplicate `event_id` causes exactly 1 inventory deduction.
  3. `test_batch_sale_ingestion`: Batch POS processing handles multiple sales atomically.
  4. `test_sse_replay_mechanism_with_last_event_id`: Missing events replayed sequentially.
  5. `test_node_isolation_filtering`: Cross-node event isolation enforced.
  6. `test_stream_endpoint_requires_auth`: 401 Unauthorized without credentials.
  7. `test_apply_sale_rpc_invocation_path`: Verified Supabase client RPC execution.

