# NexusChain India MVP: tasks.md

---

# PHASE 1: FOUNDATION

## Task 1: Project setup, repo structure and spec-driven AI-IDE workflow

**Objective:** Create the monorepo, tooling and the AI-IDE rules so every later task can be generated task by task.

**Context:** Solo MVP. Stack: Python + FastAPI backend, React + TypeScript frontend, Supabase (Postgres, pgvector, RLS, Auth), LangGraph for agents, Tauri for desktop. Free models only (NVIDIA-hosted, OpenRouter free, Ollama). Redis, Docker and the WASM sandbox are deferred to after the MVP.

### 1.1 Repo structure
```
nexuschain/
  backend/
    app/
      main.py
      core/            (config.py, logging.py, errors.py, security.py)
      api/v1/          (one router file per resource)
      llm/             (router.py, providers.py, schemas.py, cache.py)
      events/          (bus.py, models.py, sse.py)
      agents/          (base.py, tools/, pharmacy/, stockist/, distributor/, manufacturer/, compliance/, coldchain/, forge/, regulatory/, copilot/)
      graphs/          (cascade.py, prescription.py, coldchain.py, forge.py, regulatory.py, copilot.py)
      modules_runtime/ (registry.py, guard.py, loader.py)
      db/              (client.py, repositories/)
      simulator/       (pos_simulator.py, sensor_simulator.py)
    tests/
    pyproject.toml
  frontend/            (Vite + React + TypeScript)
  desktop/             (Tauri wrapper, added in Task 28)
  supabase/migrations/
  clients/sample_client/
  fixtures/            (legacy payloads, regulatory notices, prescriptions; all synthetic)
  docs/
  scripts/             (start-all, seed, simulate, benchmark)
  AGENTS.md            (AI-IDE rules file, see 1.3)
  .env.example
```

### 1.2 Tooling
- Python 3.11+ virtual environment; dependencies managed via `pyproject.toml` (fastapi, uvicorn, pydantic, pydantic-settings, httpx, langgraph, a LangGraph checkpointer package, supabase client, sse-starlette, tenacity, pytest, pytest-asyncio, ruff).
- Frontend: Vite, React, TypeScript, Tailwind, shadcn/ui, React Router, TanStack Query.
- `scripts/start-all` starts backend and frontend with one command (Windows-friendly: provide `.ps1` and/or cross-platform npm script).
- `.env.example` listing: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL`, `LLM_CACHE_MODE`, `DEMO_MODE`, `CASCADE_MODE`, `REG_AUTO_DEPLOY`.
- Git repository, `.gitignore` (never commit `.env`), conventional commit messages, one commit per task.

### 1.3 Spec-driven AI-coding workflow
- Create `AGENTS.md` (rules file for your AI IDE) containing: project summary, stack, folder map, coding conventions (type hints, Pydantic models, async-first, small functions), the "definition of done" (code + tests + docs), run/test commands, and the list of deferred items (Redis, Docker, WASM, Redpanda) so the AI never adds them.
- Create `docs/specs/` and a short spec file template (Objective, Inputs, Outputs, Edge cases, Acceptance criteria). Each later task gets a spec file generated from this tasks.md before coding.
- Create `docs/HOW_AI_BUILT_THIS.md` and append to it after every task (what the AI generated, what you reviewed or fixed). This feeds the final README.

**Deliverables:** repo scaffold, `AGENTS.md`, `.env.example`, start script, spec template.

**Acceptance criteria:**
- [ ] `scripts/start-all` starts an empty FastAPI app (`/health`) and the Vite app together.
- [ ] `pytest` runs (even with one placeholder test) and `ruff` passes.
- [ ] `AGENTS.md` lists all deferred items explicitly.

**Depends on:** none.

---

## Task 2: Supabase project and database schema

**Objective:** Create all tables, functions and extensions needed by the MVP via versioned SQL migrations.

**Context:** Supabase free tier provides Postgres, pgvector, RLS, Auth and Realtime. Supabase is the control plane only (state, catalog, traces). It is not the high-throughput event path. The supply chain hierarchy is pharmacy → stockist → distributor → manufacturer.

### 2.1 Setup
- Create the Supabase project; enable the `vector` extension; store keys in `.env`.
- Put all SQL in `supabase/migrations/` as numbered files; apply them via Supabase CLI or the SQL editor and keep the files as the source of truth.

### 2.2 Tables
- **Network:** `nodes` (id, tier enum: pharmacy/stockist/distributor/manufacturer, name, region, parent_id, is_active), `profiles` (user_id, role, node_id).
- **Catalog:** `products` (id, name, generic_name, schedule_class, is_cold_chain, storage_min_c, storage_max_c, is_lifesaving, unit), `batches` (id, product_id, manufacturer_id, batch_no, mfg_date, expiry_date, status: active/quarantined/expired).
- **Stock:** `inventory` (node_id, product_id, batch_id, quantity, reserved, safety_stock, updated_at), `api_inventory` (manufacturer_id, ingredient, quantity, unit).
- **Events:** `events` (id, event_id unique, type, node_id, payload jsonb, correlation_id, created_at).
- **Flow:** `orders`, `transfers`, `shipments` (with `is_cross_border`, `priority`, `vehicle_id`, `eta`), `fleet_vehicles` (id, distributor_id, type, is_reefer), `settlements`, `credit_accounts` (node_id, credit_limit, used).
- **Manufacturing:** `production_lines`, `production_batches` (status: planned/in_progress/completed), `demand_signals` (with `embedding vector(N)`).
- **Compliance:** `drug_schedules`, `doctor_registry_mock`, `prescriptions`, `compliance_logs`.
- **Cold chain:** `sensor_readings` (batch_id, node_id, temperature_c, humidity, shock_g, ts), `quarantine_actions`.
- **AI-native:** `agent_runs` (id, correlation_id, graph, agent, status, input, output, error, model, provider, tokens_in, tokens_out, duration_ms, created_at), `modules` (id, name, kind, version, status: staging/active/retired, source_code, tests_source, checksum, created_by, parent_version), `adapters`, `reg_notifications` (with embedding), `hitl_tasks`, `audit_ledger`.
- **Developer platform:** `api_keys` (key_hash, scopes, node_id, rate_limit, last_used), `webhook_subscriptions`, `webhook_deliveries`.
- **Dimension note:** set the pgvector column dimension to match the embedding model you pick in Task 21 (check the model's documented dimension before running the migration; adjust the migration if you change models).

### 2.3 Database functions
- `apply_sale(node_id, product_id, batch_id, qty)`: atomic decrement of inventory (single SQL statement/transaction) that returns new quantity and an `oversold` flag.
- `apply_return(...)`, `apply_expiry(...)` with the same atomic style.
- Idempotency: `events.event_id` unique constraint so duplicate events are ignored.

### 2.4 Indexes
- Indexes on `events(created_at)`, `events(correlation_id)`, `agent_runs(correlation_id)`, `inventory(node_id, product_id)`, and an ivfflat/hnsw index for vector columns if supported on the free tier.

**Deliverables:** migration files, a `docs/schema.md` summary.

**Acceptance criteria:**
- [ ] All migrations apply on a fresh project with no errors.
- [ ] Calling `apply_sale` twice concurrently never produces a wrong quantity.
- [ ] Inserting the same `event_id` twice is rejected or ignored.

**Depends on:** Task 1.

---

## Task 3: Authentication, roles and Row-Level Security

**Objective:** Enforce per-node data isolation with Supabase Auth and RLS (an RFP requirement).

**Context:** Roles: pharmacy, stockist, distributor, manufacturer, admin. Agents write using the service-role key on the server. User-facing reads go through the user's JWT so RLS applies.

### 3.1 Roles and visibility
- Helper SQL function `visible_node_ids()` returning the caller's node and its descendants via `nodes.parent_id` (a stockist sees its child pharmacies; admin sees everything).
- Enable RLS on every table holding node-scoped data; write policies for select/insert/update using `visible_node_ids()`.
- Block UPDATE and DELETE on `audit_ledger` and `events` for all non-service roles.

### 3.2 Demo users
- Seed one demo user per role, each linked to a node via `profiles`.

### 3.3 Backend JWT handling
- FastAPI dependency that verifies the Supabase JWT, loads `profiles`, and returns a `CurrentUser(role, node_id)`.
- A second dependency, `get_actor`, that accepts either `Authorization: Bearer` (JWT) or `X-API-Key` (wired fully in Task 22).
- User-scoped DB client factory (so RLS applies) and a service client factory (agents only).

**Deliverables:** RLS migration, seed script for demo users, `core/security.py`, tests.

**Acceptance criteria:**
- [ ] A pharmacy user cannot read another pharmacy's inventory (verified by a test).
- [ ] A stockist user can read inventory of its child pharmacies only.
- [ ] Attempting to UPDATE `audit_ledger` fails.

**Depends on:** Task 2.

---

## Task 4: FastAPI core skeleton

**Objective:** Build the API foundation that all routers plug into.

**Context:** The public API is a key deliverable ("others can build over it"). FastAPI generates OpenAPI docs automatically, so consistency here pays off later.

### 4.1 App structure
- `main.py` with lifespan hooks (start event bus, cascade workers, schedulers), CORS (allow the Vite dev origin and the Tauri origin), `/health` and `/api/v1` router prefix.
- `core/config.py` using pydantic-settings reading `.env`.
- Structured logging with a correlation ID middleware (every request and event carries a `correlation_id`).

### 4.2 Conventions
- Consistent error format `{error: {code, message, details}}`; custom exception handlers.
- Pydantic request/response models for every endpoint; tags and descriptions so OpenAPI docs are readable.
- Pagination convention (`limit`, `cursor`) and API versioning under `/api/v1`.

### 4.3 First endpoints
- `GET /api/v1/me`, `GET /api/v1/nodes`, `GET /api/v1/products`, `GET /api/v1/inventory` (RLS-scoped).

**Deliverables:** running API with `/docs`, tests with FastAPI TestClient.

**Acceptance criteria:**
- [ ] `/docs` shows grouped, documented endpoints.
- [ ] Authenticated users get only their RLS-scoped inventory.
- [ ] Unhandled errors return the standard error format.

**Depends on:** Tasks 1, 3.

---

# PHASE 2: AGENTIC PLATFORM CORE

## Task 5: LLM Router (NVIDIA, OpenRouter, Ollama)

**Objective:** One abstraction for all model calls, with sensitivity routing, fallback, structured output, caching and token logging.

**Context:** All three providers expose OpenAI-compatible endpoints, so one client class with different base URLs works. Free-tier limits and model IDs change; keep them in config and verify on the provider sites before use. The RFP's "dual routing" is implemented as: sensitive data → local Ollama; analytics/code → hosted free models.

### 5.1 Providers (`llm/providers.py`)
- Config-driven provider list: `nvidia` (base URL from NVIDIA's hosted API catalogue), `openrouter` (free models), `ollama` (`http://localhost:11434/v1`). Keys in `.env`.
- Async client using `httpx` or the OpenAI-compatible Python client.

### 5.2 Routing (`llm/router.py`)
- Single entry point: `await llm.complete(agent, messages, response_model, sensitivity, task_type)`.
- `sensitivity="sensitive"` → Ollama only. **Never fall back to a hosted provider for sensitive calls**; if Ollama is unavailable, fail with a clear error.
- `sensitivity="normal"` → fallback chain from config (e.g., NVIDIA → OpenRouter free → Ollama).
- `config/agent_models.yaml`: maps each agent to a preferred model per provider (strong model for coding agents, small model for simple agents).
- Concurrency limit via `asyncio.Semaphore` per provider; retry with exponential backoff (tenacity) on 429/5xx/timeouts; then move to the next provider.

### 5.3 Structured output
- Every agent call supplies a Pydantic model. Prompt includes the JSON schema; response is parsed and validated.
- Repair loop: on invalid JSON/schema mismatch, send the error back once or twice asking for a corrected object; then fail the call.
- Do not depend on native tool-calling (unreliable on free models). Agents choose actions through structured outputs (Task 7).

### 5.4 Cache (`llm/cache.py`)
- Local SQLite cache keyed by hash(provider-independent request: agent + messages + schema).
- Modes via `LLM_CACHE_MODE`: `off`, `record` (store successful responses), `replay` (serve only from cache; used for demos and tests).

### 5.5 Telemetry
- Every call returns model, provider, tokens in/out (if the API reports it; else estimate), latency; stored via the agent framework into `agent_runs`.

**Deliverables:** `llm/` package, `config/agent_models.yaml`, unit tests with mocked HTTP.

**Acceptance criteria:**
- [ ] A normal call succeeds against at least one live provider and returns a validated Pydantic object.
- [ ] Simulated 429 on the first provider falls through to the next provider.
- [ ] A sensitive call never reaches a hosted provider (test asserts this).
- [ ] `replay` mode returns cached results with the network disabled.

**Depends on:** Task 4.

---

## Task 6: Event bus, event persistence and SSE stream

**Objective:** Build the event-driven backbone for the MVP behind an interface so Redpanda/Kafka can replace it after the MVP.

**Context:** The RFP mandates Kafka/Redpanda. For the MVP, use an in-process async bus plus a persisted `events` table, and document the swap. Ingestion must be instant and contain no LLM call.

### 6.1 Event model (`events/models.py`)
- Pydantic models: `SaleEvent` (event_id, pharmacy_id, product_id, batch_id, quantity (default 1 strip), timestamp, source), `ReturnEvent`, `ExpiryEvent`, `SensorReadingEvent`, plus a generic envelope with `type`, `correlation_id`, `node_id`.

### 6.2 Bus interface (`events/bus.py`)
- Abstract `EventBus` with `publish(topic, event)` and `subscribe(topic) -> async iterator`.
- `InProcessEventBus` implementation using `asyncio.Queue` per subscriber.
- Topics: `pos.sales`, `cascade.updates`, `agent.activity`, `hitl`, `coldchain`, `regulatory`, `webhooks`.
- Persist every ingested event to `events` before publishing (idempotent on `event_id`).

### 6.3 Ingestion path
- `POST /api/v1/events/sale` validates, applies `apply_sale` atomically, persists the event, publishes to `pos.sales`, returns immediately with `correlation_id`.
- `POST /api/v1/events/sale/batch` accepting a list (used by simulator and benchmark).

### 6.4 SSE (`events/sse.py`)
- `GET /api/v1/stream?topics=...` using sse-starlette; supports `Last-Event-ID` replay from the `events`/`agent_runs` tables; filters by the caller's visible nodes.
- Heartbeat comments to keep connections alive; clean disconnect handling.

**Deliverables:** bus, endpoints, tests.

**Acceptance criteria:**
- [ ] Posting a sale decrements inventory and appears on the SSE stream within a second.
- [ ] Posting the same `event_id` twice results in one inventory change.
- [ ] A client reconnecting with `Last-Event-ID` receives missed events.

**Depends on:** Tasks 2, 4.

---

## Task 7: Agent framework (base agent, tools, traces, HITL primitives)

**Objective:** Create the reusable building blocks so every agent and LangGraph graph is built the same way.

**Context:** This is the most important task for AI-nativeness. Agents are LangGraph nodes/subgraphs that call the LLM router for decisions and call Python tools for side effects. Deterministic code is limited to tools (database reads/writes, arithmetic). Decisions come from agents.

### 7.1 BaseAgent (`agents/base.py`)
- Class with: `name`, `graph`, `sensitivity`, system prompt, output Pydantic model, allowed tool list, `max_steps`.
- `run(state)` executes a bounded loop: model outputs either a `tool_call {tool, args}` or a `final` answer (both defined as a Pydantic union); tool results are appended; stops at `max_steps`.
- Every run is wrapped to write an `agent_runs` row (start/end, input, output, errors, provider, model, tokens, duration) and publish an `agent.activity` event.

### 7.2 Tool registry (`agents/tools/`)
- Decorator `@tool(name, description, schema)` registering Python functions; each tool has typed args and returns JSON-serializable data.
- Tools are scoped per agent (an agent only sees tools in its allow-list).
- Initial shared tools: `get_inventory`, `get_recent_sales`, `get_node`, `list_nodes_in_cluster`, `run_module` (Task 8), `write_audit` (Task 16).

### 7.3 LangGraph conventions
- Shared state as Pydantic/TypedDict per graph; every graph includes `correlation_id` and `trace`.
- Checkpointer: use a persistent LangGraph checkpointer (SQLite-based) so paused graphs (HITL) survive restarts. Check the installed LangGraph version's documentation for the exact checkpointer and interrupt/resume API.
- Helper `request_human_approval(state, task_type, payload, risk)` that creates a `hitl_tasks` row, emits an event and pauses the graph using LangGraph's interrupt mechanism (completed in Task 15).

### 7.4 Testing helpers
- A `FakeLLM` that returns scripted outputs, so agents and graphs can be tested deterministically.

**Deliverables:** `agents/base.py`, tool registry, graph helpers, tests.

**Acceptance criteria:**
- [ ] A sample agent with one tool completes a tool call then a final answer, with an `agent_runs` row written.
- [ ] `max_steps` stops a looping agent.
- [ ] A paused graph can be resumed after restarting the process.

**Depends on:** Tasks 5, 6.

---

## Task 8: Generated Module Registry and restricted execution guard

**Objective:** Store business rules and integrations as AI-generated, versioned code modules loaded at runtime. This is the MVP form of the RFP's "zero-code base" and the foundation of the hot-swap.

**Context:** Rules such as margin logic, volume discounts, price ceilings and adapters must not be hardcoded in the repo. They live in the `modules` table, are generated by a coding agent, tested, activated and hot-swapped. The WASM sandbox is deferred; the MVP uses a restricted execution guard and must call it that (not a "sandbox"). The development machine may be Windows, so do not rely on Unix-only `resource` limits.

### 8.1 Module contract
- Each module is Python source exposing `def run(input: dict) -> dict`, with a declared `kind` (e.g., `margin_rules`, `volume_discount`, `price_ceiling`, `traceability_rules`, `adapter`).
- Each module version ships with its own `tests_source` (pytest-style asserts or simple function checks).

### 8.2 Guard (`modules_runtime/guard.py`)
- Static check using Python `ast`: allow a whitelist of imports (`json`, `math`, `datetime`, `decimal`, `re`, `typing`, `statistics`); block `os`, `sys`, `subprocess`, `socket`, `open`, `eval`, `exec`, `compile`, `__import__`, and dunder attribute access.
- Execution in a separate subprocess with a hard timeout, JSON input via stdin and JSON output via stdout, and output size limit. No access to project secrets (pass a minimal environment).
- Clear error types: `GuardViolation`, `ModuleTimeout`, `ModuleError`.

### 8.3 Registry and loader (`modules_runtime/registry.py`)
- Operations: create version (status `staging`), run tests, `activate(name, version)` (atomic pointer switch, previous version becomes `retired` but stays stored), `rollback(name)`.
- In-memory cache of the active version per module name; hot-swap replaces it atomically so in-flight calls finish on the old version.
- `run_module(name, input)` tool used by agents.

### 8.4 Bootstrap generation
- A **Module Bootstrap Agent** (uses the coding model) takes plain-English policies and generates the initial modules plus tests: `margin_rules`, `volume_discount`, `credit_check_rules`, `price_ceiling`. Policies live in `config/bootstrap_policies.md` (written by you, e.g., "volume discount 2% above 100 strips").
- Generated modules go through guard validation, tests and activation automatically on first run.

### 8.5 API
- `GET /api/v1/modules`, `GET /api/v1/modules/{name}/versions`, `POST /api/v1/modules/{name}/rollback` (admin only).

**Deliverables:** guard, registry, bootstrap agent, tests (including malicious-code tests).

**Acceptance criteria:**
- [ ] A module that imports `os` or calls `open` is rejected.
- [ ] An infinite loop is killed by the timeout.
- [ ] Activating a new version changes `run_module` output without restarting the server; rollback restores the old behavior.
- [ ] Bootstrap produces and activates all initial modules from the policies file.

**Depends on:** Tasks 5, 7.

---

## Task 9: Synthetic data agent, seed pipeline and POS simulator

**Objective:** Populate the network with realistic demo data without manual entry, and create the traffic generator for demos.

**Context:** All data is synthetic and must be labeled as such. Medical classification data (schedules) must be verified by you before being used in any demo, because LLM-generated drug data can be wrong.

### 9.1 Synthetic Data Agent
- Generates, as structured JSON validated by Pydantic: a small hierarchy (e.g., 2 manufacturers, 3 distributors, ~5 stockists, ~15 pharmacies across a few regions), 15 to 25 products (mix of normal, Schedule H, cold-chain, lifesaving), batches with expiry dates, safety stock levels, credit accounts, fleet vehicles (some reefer), production lines and API (active ingredient) inventory.
- Writes via repositories; idempotent so it can be re-run (`scripts/seed`).
- `drug_schedules` and `doctor_registry_mock` are seeded from a small curated file you verify (`fixtures/drug_schedules.json`), not freely generated.

### 9.2 POS simulator (`simulator/pos_simulator.py` + `scripts/simulate`)
- Modes: `single` (one strip sold on a chosen pharmacy/product, for the cascade demo), `steady` (random sales at a rate), `burst` (demand spike for a product/region to trigger rebalancing and JIT changes), `stockout_run` (drive a product below safety stock).
- Posts to `/api/v1/events/sale` (or batch endpoint); configurable rate.
- Also expose `POST /api/v1/simulator/run` (admin only) so the UI can start/stop simulations.

### 9.3 Sensor simulator stub
- Create `simulator/sensor_simulator.py` interface (implemented in Task 20).

**Deliverables:** seed agent, curated fixtures, simulator and scripts.

**Acceptance criteria:**
- [ ] Fresh database to fully seeded network with one command.
- [ ] `simulate --mode single` produces one sale event reaching the API.
- [ ] Re-running seed does not duplicate data.

**Depends on:** Tasks 2, 5, 6.

---

# PHASE 3: THE CASCADE (CORE RFP REQUIREMENT)

## Task 10: Cascade graph vertical slice

**Objective:** Get one sale flowing through all four tiers, with a minimal agent at each tier, and visible in the trace. Do this before deepening any tier.

**Context:** The RFP's headline requirement is single-unit demand propagation from pharmacy to manufacturer without human intervention. Ingestion is instant (Task 6); the cascade runs asynchronously from the event bus. Free-model rate limits mean the cascade has two modes (`CASCADE_MODE`): `per_event` (every sale; demos) and `micro_batch` (events grouped by a time window; load runs).

### 10.1 Cascade state and graph (`graphs/cascade.py`)
- `CascadeState`: event, correlation_id, pharmacy_result, stockist_result, distributor_result, manufacturer_result, hitl_status, trace, errors.
- Nodes: `supervisor` → `pharmacy_node` → `stockist_node` → `distributor_node` → `manufacturer_node` → `finalize`.
- **Supervisor Agent:** reads the event and current context, outputs which tiers need to act (e.g., a sale that does not threaten stock may stop after the pharmacy tier). Conditional edges follow its decision and every skip is logged with the reason.
- Each tier node initially wraps one minimal agent (full versions in Tasks 11 to 14).

### 10.2 Workers
- Cascade worker(s) subscribe to `pos.sales`, run the graph with `thread_id = correlation_id`, with a configurable concurrency limit (default 2).
- Failures in one tier are recorded and do not crash the worker; the run is marked partial.

### 10.3 Visibility
- Each node completion publishes `agent.activity` and `cascade.updates` events carrying `correlation_id`, tier, agent, summary.
- `GET /api/v1/cascade/{correlation_id}` returns the full ordered trace from `agent_runs`.

**Deliverables:** graph, worker, trace endpoint, integration test with FakeLLM.

**Acceptance criteria:**
- [ ] `simulate --mode single` creates agent_runs rows for all four tiers (or logged skips) under one correlation_id.
- [ ] The SSE stream shows the activity in order.
- [ ] A tier failure produces a partial result without stopping later events.

**Depends on:** Tasks 6, 7, 8, 9.

---

## Task 11: Pharmacy tier (Inventory Telemetry Agent)

**Objective:** Complete the pharmacy node swarm's inventory intelligence.

**Context:** RFP 3.1: the Inventory Telemetry Agent streams individual item sales, returns and expiry dampening instantly. Atomic stock updates already happen at ingestion; this agent adds reasoning on top.

### 11.1 Agent behavior
- Inputs: the event, current inventory, safety stock, recent sales (via tools).
- Output model `ReplenishmentSignal {needed, quantity, urgency, reason, target_stockist_id, expiry_flags[]}`.
- Handles event types: `sale`, `return` (restock decision, damaged vs sellable), `expiry_alert` (mark for removal; recommend FEFO ordering of batches).
- Schedule H sales: calls a `check_prescription_link` tool (Task 19 provides the data). If a Schedule H product has no verified prescription reference, the agent flags a compliance hold in its output.

### 11.2 Tools
- `get_inventory`, `get_recent_sales(days)`, `get_batches_near_expiry`, `check_prescription_link`.

### 11.3 Persistence
- Writes the signal to the cascade state and creates an `orders` row (status `requested`) from pharmacy to its parent stockist when `needed` is true.

**Deliverables:** agent, prompts, tools, tests with FakeLLM.

**Acceptance criteria:**
- [ ] A sale pushing stock below safety stock yields `needed=true` and an order row.
- [ ] A return and an expiry event are handled with different outputs.
- [ ] A Schedule H sale without a prescription link is flagged.

**Depends on:** Task 10.

---

## Task 12: Stockist tier (Dynamic Balancing Agent)

**Objective:** Decide how replenishment requests are served across the stockist cluster before deficits become acute.

**Context:** RFP 3.2: the Dynamic Balancing Agent manages inventory across localized clusters and shifts allocations between stockists. Lifesaving products take priority.

### 12.1 Agent behavior
- Inputs: the pharmacy's order, inventory of this stockist and its peer stockists (same distributor/region), recent demand, lifesaving/cold-chain flags.
- Output model `BalancingDecision {action: fulfill_local | transfer_from_peer | escalate_to_distributor, transfers[], reasoning, priority}`.
- Creates `transfers` rows (peer-to-peer) or an escalation order to the distributor.
- Proactive mode: when demand spikes in a region (burst simulation), the agent can pre-position stock to peers even without an explicit order.

### 12.2 Tools
- `list_nodes_in_cluster`, `get_cluster_inventory`, `get_demand_trend`, `create_transfer`, `create_order`.

**Deliverables:** agent, tools, tests.

**Acceptance criteria:**
- [ ] With local stock available, the order is fulfilled locally.
- [ ] With local stock short and a peer rich, a transfer is created.
- [ ] With the whole cluster short, an escalation order to the distributor is created.
- [ ] A lifesaving product gets higher priority in the output.

**Depends on:** Task 11.

---

## Task 13: Distributor tier (Settlement Agent and Transit Optimization Agent)

**Objective:** Handle money and logistics for escalated orders.

**Context:** RFP 3.3: the Multi-Tiered Settlement Agent computes credit limits, margins, volume discounts and coordinates trade financing via embedded banking APIs (simulated in the MVP). The Transit Optimization Agent produces dispatch sequences with priority for lifesaving therapeutics. Margin and discount logic must come from generated modules (Task 8), not hardcoded rules.

### 13.1 Settlement Agent
- Inputs: the order, `credit_accounts`, active modules.
- Uses `run_module('credit_check_rules' | 'margin_rules' | 'volume_discount', ...)`; the agent decides how to apply and combine the results and explains it.
- Output `SettlementDecision {approved, price, margin, discount, credit_after, financing_needed, reasoning}`.
- Simulated trade financing: a `mock_bank` tool (clearly labeled simulated) that approves or rejects short-term financing against defined limits.
- Writes `settlements`; updates `credit_accounts`.

### 13.2 Transit Optimization Agent
- Inputs: approved orders, `fleet_vehicles`, shipments in progress, product flags (lifesaving, cold-chain, cross-border).
- Output `DispatchPlan {shipments[ {order_ids, vehicle_id, sequence, priority, eta} ], reasoning}`; cold-chain goods only on reefer vehicles.
- Writes `shipments`. Cross-border shipments trigger HITL approval (Task 15).

### 13.3 Tools
- `get_credit_account`, `run_module`, `mock_bank_finance`, `list_vehicles`, `create_shipment`.

**Deliverables:** two agents, tools, tests.

**Acceptance criteria:**
- [ ] Changing the active `margin_rules` module changes the settlement result without code edits.
- [ ] An order exceeding credit limit uses (simulated) financing or is rejected, with reasoning.
- [ ] A cold-chain order is never assigned to a non-reefer vehicle.
- [ ] Lifesaving shipments are sequenced first.

**Depends on:** Tasks 8, 12.

---

## Task 14: Manufacturer tier (Demand Vector Synthesis and JIT Formulation Scheduler)

**Objective:** Turn sales noise into production decisions.

**Context:** RFP 3.4: the Demand Vector Synthesis Agent converts unstructured demand events into operational signals; the JIT Formulation Scheduler Agent alters manufacturing schedules, handles active-ingredient allocation and machine run-times. Altering an in-progress batch is a high-risk change that requires HITL.

### 14.1 Demand Vector Synthesis Agent
- Aggregates recent events per product and region with statistical tools (moving average, EWMA, simple spike detection).
- The agent interprets the numbers and separates noise from signal (e.g., one-off spike vs sustained trend), outputting `DemandSignal {product_id, region, trend, forecast_qty, confidence, reasoning}`.
- Stores `demand_signals` with an embedding of the textual summary (embedding wired in Task 21; store a null embedding until then).

### 14.2 JIT Formulation Scheduler Agent
- Inputs: demand signals, `production_lines`, `production_batches`, `api_inventory`.
- Output `ScheduleChange {actions[ {type: add_batch | resize_batch | reprioritize | none, batch_id, qty, line_id, start} ], api_allocation, reasoning, modifies_in_progress}`.
- If `modifies_in_progress` is true, request HITL approval and apply only after approval.
- Applies changes by writing `production_batches` and decrementing `api_inventory`; rejects plans that exceed API stock or line capacity.

### 14.3 Tools
- `get_events_window`, `compute_trend`, `get_production_schedule`, `get_api_inventory`, `apply_schedule_change`.

**Deliverables:** agents, tools, tests.

**Acceptance criteria:**
- [ ] A burst simulation produces a `DemandSignal` with higher forecast and a schedule change.
- [ ] A one-off spike is classified as noise (no schedule change) in a FakeLLM-scripted test and in a live run.
- [ ] A plan exceeding API inventory is rejected.
- [ ] Modifying an in-progress batch pauses for approval.

**Depends on:** Tasks 13, 15 (HITL integration can be stubbed until Task 15).

---

## Task 15: Human-in-the-Loop approval system

**Objective:** Pause risky agent actions for human approval and resume graphs after a decision.

**Context:** The RFP requires HITL checkpoints for high-risk structural shifts (batch modifications, cross-border shipments). The MVP also uses HITL for regulatory module activation, doctor-verification failures and Schedule H overrides. Whether these gates are enabled is controlled by config.

### 15.1 Policy config
- `config/hitl_policies.yaml`: which task types require approval, which role can approve, and the expiry time.

### 15.2 Backend
- `request_human_approval(...)` (from Task 7) creates a `hitl_tasks` row (`pending`), writes to the audit ledger, emits a `hitl` event, and pauses the graph with LangGraph's interrupt mechanism.
- `GET /api/v1/hitl/tasks` (filter by status), `GET /api/v1/hitl/tasks/{id}`, `POST /api/v1/hitl/tasks/{id}/decision {decision: approve|reject, note}`.
- On decision: authorize the approver's role, store decision and note, resume the paused graph with the decision, and write the audit entry.
- Expiry job: pending tasks past their expiry are rejected automatically (safe default) and audited.

### 15.3 Graph integration
- Each gated node branches: approved → continue; rejected/expired → record outcome and take the safe alternative path.

**Deliverables:** policies, endpoints, expiry job, tests.

**Acceptance criteria:**
- [ ] A cross-border shipment and an in-progress batch change each pause and create a task.
- [ ] Approve resumes and completes the action; reject cancels it.
- [ ] Unauthorized roles cannot decide.
- [ ] A pending task survives a backend restart and can still be decided.

**Depends on:** Tasks 7, 10.

---

## Task 16: Audit ledger (hash-chained) and Audit Agent

**Objective:** Create a tamper-evident log of every important agent decision and human action, for regulatory audit.

**Context:** RFP 3.1 requires automated digital logs for regulatory audits. The hash chain must be computed by deterministic code; the Audit Agent only adds human-readable explanations.

### 16.1 Ledger service
- `audit_ledger` fields: `seq` (monotonic), `ts`, `actor` (agent/user/system), `action`, `entity_type`, `entity_id`, `payload`, `explanation`, `prev_hash`, `hash`.
- `hash = SHA-256(prev_hash + canonical_json(entry))`; appends serialized with a Postgres advisory lock or single-writer service to keep the chain consistent.
- DB triggers block UPDATE/DELETE (from Task 3).
- `write_audit` tool used by agents and services.

### 16.2 Audit Agent
- For key events (HITL decisions, quarantines, Schedule H decisions, module activations, settlements), generates a short plain-language explanation stored in `explanation`. If the LLM is unavailable, the entry is still written with an empty explanation (the chain must never block on an LLM).

### 16.3 API
- `GET /api/v1/audit` (filters: entity, actor, date), `GET /api/v1/audit/verify` (recomputes the whole chain and reports the first broken link).

**Deliverables:** ledger service, agent, endpoints, tests (including tamper test).

**Acceptance criteria:**
- [ ] Altering a row directly in the database makes `/audit/verify` report the break.
- [ ] Concurrent writes keep the chain valid.
- [ ] Cascade, HITL and module events all produce entries.

**Depends on:** Tasks 3, 7.

---

# PHASE 4: AI-NATIVE ENGINEERING FEATURES

## Task 17: Adapter Forge (self-evolving API translators)

**Objective:** Let agents write, test and register integration adapters for unknown legacy systems.

**Context:** RFP Section 2: a coding agent inspects a legacy billing system or closed ERP payload, writes a custom adapter, tests it and connects, with no human involved. Adapters are stored as `adapter` modules in the registry (Task 8), executed through the restricted guard. Legacy systems are simulated with fixtures.

### 17.1 Fixtures
- `fixtures/legacy/`: at least three synthetic formats: (1) pharmacy billing CSV export, (2) manufacturer ERP XML, (3) a nested JSON with different field names and date formats. Each with an expected canonical output file (canonical = SaleEvent or a production/batch update).

### 17.2 Forge graph (`graphs/forge.py`)
- **Schema Inspector Agent:** analyzes a sample payload and outputs a structured description (fields, types, formats, probable canonical mapping).
- **Adapter Coder Agent:** writes the adapter module (`run(input) -> dict`) mapping to the canonical schema.
- **Adapter Tester Agent:** generates tests from the sample and expected output, and runs them via the guard.
- Fix loop: failures and error output go back to the coder; capped at N attempts (config, default 4); then the adapter is marked `failed` with logs.
- On success: register version in `modules` (kind `adapter`) and `adapters`, then activate.

### 17.3 Live use
- `POST /api/v1/ingest/{adapter_id}` accepts a raw legacy payload, runs the adapter, validates against the canonical model and forwards to the event ingestion path.

### 17.4 Marketplace API
- `POST /api/v1/adapters/generate` (upload sample + optional description, returns job id), `GET /api/v1/adapters/jobs/{id}` (progress), `GET /api/v1/adapters`, `GET /api/v1/adapters/{id}` (versions, source, test results), `POST /api/v1/adapters/{id}/rollback`.
- Progress events stream over SSE so the UI can show each agent step.

**Deliverables:** fixtures, graph, endpoints, tests.

**Acceptance criteria:**
- [ ] All three fixture formats produce a passing adapter without manual code edits (retry loop allowed).
- [ ] A raw legacy payload posted to `/ingest/{adapter_id}` results in a normal sale event and cascade.
- [ ] Generated code violating the guard is rejected and fed back to the coder.
- [ ] Failed generation after N attempts is reported clearly.

**Depends on:** Tasks 6, 8, 16.

---

## Task 18: Regulatory pipeline (Crawler, Analyst, DevOps Coding Agent, hot-swap)

**Objective:** Detect a regulatory change, generate and test a code change, and hot-swap it into the running system.

**Context:** RFP Section 5: a Regulatory Crawler Agent tracks MoHFW, CDSCO and Gazette of India publications; a DevOps Coding Agent generates code mutations and tests in staging, and deploys on full test success via zero-downtime hot-swap. The MVP deploys at module level (Task 8). The RFP says tests passing triggers deployment; the MVP adds a configurable human gate (`REG_AUTO_DEPLOY`, default false) for pricing and compliance modules, because mistakes there carry real risk. Regulatory notices in demos are synthetic fixtures unless a real URL is fetched.

### 18.1 Sources and ingestion
- `config/reg_sources.yaml`: the three source names and their URLs (you fill in and verify the URLs).
- **Crawler Agent:** fetches a configured URL (httpx + HTML-to-text) or accepts pasted/uploaded text; detects new/changed items by content hash; stores in `reg_notifications` (with embedding after Task 21).
- Modes: manual "check now" and optional periodic check (lightweight scheduler such as APScheduler).
- `fixtures/regulatory/`: synthetic notices, e.g., a price-ceiling change for a drug and a track-and-trace requirement change.

### 18.2 Regulatory graph (`graphs/regulatory.py`)
- **Regulatory Analyst Agent:** outputs `RegChange {topic, effective_date, affected_module_kind, parameters, summary, confidence}`; low confidence goes to HITL.
- **DevOps Coding Agent:** reads the current active module source and `RegChange`, generates the new module version.
- **Test Generation Agent:** writes new tests for the change and keeps the previous version's tests as regression tests.
- Run all tests in the guard (staging). Any failure returns to the DevOps agent (capped loop).
- Gate: if `REG_AUTO_DEPLOY=false` or module kind is pricing/compliance, create a HITL task showing the diff and test results.
- On approval (or auto): activate (hot-swap) and write audit entries; previous version retained for rollback.

### 18.3 API
- `POST /api/v1/regulatory/notifications` (text or URL), `GET /api/v1/regulatory/notifications`, `GET /api/v1/regulatory/runs/{id}` (steps, diff, test results), `POST /api/v1/regulatory/check-now`.

**Deliverables:** crawler, graph, fixtures, endpoints, tests.

**Acceptance criteria:**
- [ ] Posting the synthetic price-ceiling notice yields a new module version in staging with passing tests.
- [ ] After approval, a settlement/price check immediately uses the new rule with no restart.
- [ ] Rollback restores the previous behavior.
- [ ] A notice that fails tests never activates.

**Depends on:** Tasks 8, 15, 16.

---

# PHASE 5: COMPLIANCE AND COLD-CHAIN

## Task 19: Prescription and Schedule H compliance graph

**Objective:** Parse a prescription image, check schedule classes, verify the doctor and log the result.

**Context:** RFP 3.1: the Sovereign Prescription & Schedule H Compliance Agent uses local multimodal models to parse scans, cross-verify CDSCO schedule classifications, authenticate doctor credentials via national registries and keep audit logs. The MVP uses a local Ollama vision model if the machine can run one (check what's available), otherwise OCR (Tesseract) plus a local text model. The doctor registry is a simulated table. Prescription data is sensitive, so all calls use `sensitivity="sensitive"` (local only).

### 19.1 Fixtures and data
- `fixtures/prescriptions/`: synthetic prescription images (valid, missing registration number, unknown doctor, contains Schedule H drug, contains an unlisted drug).
- `drug_schedules` and `doctor_registry_mock` from the curated seed (Task 9).

### 19.2 Graph (`graphs/prescription.py`)
- **Prescription Parser Agent:** extracts doctor name, registration number, patient initials, drug list with doses (structured output).
- **Schedule H Compliance Agent:** classifies each drug via the `lookup_schedule` tool; for drugs not in the table, it reports "unknown" and does not guess.
- **Doctor Verification Agent:** checks the registry via a `verify_doctor` tool; failure routes to HITL.
- Decision node: `approve_dispense | flag | reject`; writes `prescriptions` and `compliance_logs`; audit entry.

### 19.3 Integration
- Approved prescriptions get an ID that sale events can reference; Task 11's `check_prescription_link` reads it.

### 19.4 API
- `POST /api/v1/prescriptions` (multipart image upload), `GET /api/v1/prescriptions/{id}`, `GET /api/v1/compliance/logs`.

**Deliverables:** graph, tools, fixtures, endpoints, tests.

**Acceptance criteria:**
- [ ] The valid fixture is approved; the unknown-doctor fixture is flagged for HITL; the missing-number fixture is rejected or flagged.
- [ ] No prescription content is ever sent to a hosted provider (test asserts the route).
- [ ] A Schedule H sale event linked to an approved prescription passes the pharmacy agent check.

**Depends on:** Tasks 5, 9, 11, 15, 16.

---

## Task 20: Cold-chain telemetry graph

**Objective:** Monitor simulated IoT readings, estimate remaining shelf life and quarantine batches that breach limits.

**Context:** RFP 3.2: the Cold-Chain Telemetry Agent tracks temperature, humidity and shock for biological assets, calculates remaining shelf life on the fly and auto-quarantines batches that deviate. Sensor data is simulated.

### 20.1 Sensor simulator
- `simulator/sensor_simulator.py`: emits readings for cold-chain batches at stockist hubs and in shipments, with modes `normal`, `excursion` (temperature climbs out of range for a duration), `shock`.
- Posts `SensorReadingEvent` to `POST /api/v1/events/sensor` (stored in `sensor_readings`).

### 20.2 Graph (`graphs/coldchain.py`)
- **Cold-Chain Telemetry Agent:** inputs are recent readings and the product's storage range; uses a `estimate_shelf_life` tool (excursion duration/degree based; define the formula clearly and document it as a simplified model) and decides `ok | warn | quarantine`.
- **Excursion Analyst Agent:** explains the decision in plain language for the audit log.
- On quarantine: set batch status `quarantined`, create `quarantine_actions`, emit `coldchain` event, trigger an inventory re-balance run (Dynamic Balancing Agent) and a webhook event, write audit.
- Optional HITL for high-value batches via policy config.

### 20.3 API
- `GET /api/v1/coldchain/batches` (status, last reading, shelf-life estimate), `GET /api/v1/coldchain/quarantines`.

**Deliverables:** simulator, graph, endpoints, tests.

**Acceptance criteria:**
- [ ] An excursion run leads to a quarantine and the batch disappears from available stock.
- [ ] Normal readings produce no action but update shelf-life estimates.
- [ ] The quarantine triggers a rebalancing activity visible in the trace.

**Depends on:** Tasks 12, 16, 9.

---

# PHASE 6: COPILOT AND DEVELOPER PLATFORM

## Task 21: Embeddings, semantic search and Network Copilot

**Objective:** Add vector search and a natural-language agent over the network's data.

**Context:** The RFP requires pgvector. Embeddings come from Ollama (e.g., `nomic-embed-text`) or an embedding model from a free hosted provider; confirm the model's dimension and make sure the table columns match (Task 2 note). The copilot must be read-only and respect the caller's RLS scope.

### 21.1 Embedding service
- `llm/embeddings.py` with provider config; batch embedding helper; fallback to Ollama.
- Embed and store: demand signal summaries, regulatory notices, agent decision summaries (selected), product descriptions.
- Search endpoint `GET /api/v1/search?q=` returning mixed results with type and score.

### 21.2 Copilot graph (`graphs/copilot.py`)
- **Copilot Planner Agent:** decides which tools to call for a question.
- Tools (parameterized, read-only; no free-form SQL): `search_semantic`, `get_stockout_risk(product, region)`, `get_inventory_summary`, `get_open_hitl_tasks`, `get_recent_agent_activity`, `get_demand_signals`, `get_cold_chain_status`.
- **Answer Agent:** composes the answer and lists the records used as references.
- Runs with the user's scope so RLS limits what it can see.

### 21.3 API
- `POST /api/v1/copilot/query {question}` returns the answer, references and trace id; optional streaming via SSE.

**Deliverables:** embeddings, copilot graph, endpoints, tests.

**Acceptance criteria:**
- [ ] "Which pharmacies are at risk of running out of product X?" returns correct pharmacies from seeded data with references.
- [ ] A pharmacy user cannot get data from other pharmacies through the copilot.
- [ ] Semantic search finds a regulatory notice by meaning, not exact words.

**Depends on:** Tasks 5, 14, 18, 20.

---

## Task 22: API keys, scopes, webhooks and sample third-party client

**Objective:** Make the platform genuinely buildable-upon by outsiders.

**Context:** Interview requirement: "must have APIs so others can build over it". Redis is deferred, so rate limiting is in-memory (document this limitation).

### 22.1 API keys
- `POST /api/v1/developer/keys` (admin or developer role) creates a key; show the plaintext once; store only a SHA-256 hash.
- Scopes such as `read:inventory`, `write:events`, `read:stream`, `read:audit`, `use:copilot`, `manage:adapters`; each key bound to a node (RLS scope) and rate limit.
- `X-API-Key` authentication in `get_actor`; scope checks per endpoint via a dependency; usage logging (`last_used`, counts).
- In-memory token-bucket rate limiter per key.

### 22.2 Webhooks
- `webhook_subscriptions` (url, events, secret, key owner); event types: `order.created`, `shipment.dispatched`, `batch.quarantined`, `hitl.created`, `hitl.decided`, `module.activated`.
- Delivery worker: HMAC-SHA256 signature header, retry with exponential backoff, `webhook_deliveries` log, auto-disable after repeated failures.
- Endpoints: create/list/delete subscriptions, list deliveries, "send test event".

### 22.3 Sample client (`clients/sample_client/`)
- A small Python app/script that creates its own key, posts a sale, reads inventory, listens to SSE, and runs a local webhook receiver, demonstrating the full flow. Includes a README.
- Optional: generate a typed client from the OpenAPI spec.

### 22.4 API documentation
- Ensure every endpoint has description, examples and scope requirements in OpenAPI; write `docs/API_GUIDE.md` (auth, scopes, rate limits, events, webhooks, errors).

**Deliverables:** key system, webhooks, sample client, API guide, tests.

**Acceptance criteria:**
- [ ] The sample client runs end to end against a fresh backend.
- [ ] A key without `write:events` cannot post a sale.
- [ ] Webhook signatures verify; failed deliveries retry and are logged.
- [ ] Exceeding the rate limit returns 429.

**Depends on:** Tasks 4, 6, 15.

---

## Task 23: MCP server (stretch goal)

**Objective:** Expose NexusChain to other AI agents through the Model Context Protocol.

**Context:** Stretch item; do only after Tasks 1 to 22 are working. Use the official MCP Python SDK (check its current docs for server setup and transport options). Auth is the same API key system.

### 23.1 Tools exposed
- Read: `get_inventory`, `get_stockout_risk`, `list_open_approvals`, `get_cascade_trace`, `ask_copilot`.
- Safe action: `submit_sale_event` (scope-protected), `decide_approval` (only for keys with the right scope; consider leaving this out for safety).

### 23.2 Behavior
- Each call is authenticated with an API key, scope-checked and audited.
- Provide a short docs page showing how to connect an MCP-capable client.

**Deliverables:** MCP server module, docs, tests.

**Acceptance criteria:**
- [ ] An MCP client can list tools and call `get_inventory` with a valid key.
- [ ] Calls with insufficient scope are rejected and audited.

**Depends on:** Tasks 21, 22.

---

# PHASE 7: FRONTEND AND DESKTOP

## Task 24: Frontend shell, auth and shared infrastructure

**Objective:** Create the React app skeleton used by all screens.

**Context:** React + TypeScript + Vite + Tailwind + shadcn/ui. The same build is used for web and desktop (Task 28). The UI must work against the real API, not mocks.

### 24.1 Setup
- Routing (React Router), data fetching (TanStack Query), API client generated from or typed against the OpenAPI schema, environment-based API base URL (needed for Tauri).
- Supabase JS client for login; role-aware navigation (menu items visible per role).

### 24.2 Shared components
- App layout (sidebar, header with role/node badge), toasts, loading/error states, empty states, data table, status badges, JSON viewer.
- `useEventStream(topics)` hook over SSE with reconnect and `Last-Event-ID`.
- Dark/light theme.

### 24.3 Pages created as placeholders
- Overview, Cascade, Agents, Approvals, Adapter Forge, Regulatory Lab, Prescriptions, Cold Chain, Audit, Copilot, Developer.

**Deliverables:** frontend scaffold, login working with seeded demo users.

**Acceptance criteria:**
- [ ] Each role can log in and sees only its allowed menu items.
- [ ] The SSE hook shows live events in a debug panel.

**Depends on:** Tasks 3, 4, 6.

---

## Task 25: Live operations screens (Overview, Cascade Replay, Agent Console)

**Objective:** Build the screens that make the single-strip cascade visible. This is the core demo.

**Context:** "Strip Cascade Replay" is one of the four unique features: click a sale and watch its journey through all four tiers with each agent's reasoning.

### 25.1 Network Overview
- KPI cards (events today, stockout risks, open approvals, quarantined batches), a live event feed, inventory table with low-stock highlighting, simulator controls (single, steady, burst, stockout) for admins.

### 25.2 Cascade Replay
- Flow visualization (React Flow or similar) showing the four tiers and their agents.
- Select an event or correlation_id; nodes light up in order using the stored trace (`/cascade/{id}`); a side panel shows each agent's input, output, reasoning, model, tokens and duration.
- Live mode: watch a new sale animate in real time via SSE; replay mode with speed control.

### 25.3 Agent Console
- Table of `agent_runs` with filters (graph, agent, status), detail drawer (full input/output JSON, errors), and aggregated metrics (runs, failures, average latency, tokens by agent and provider).

**Deliverables:** three screens wired to real endpoints.

**Acceptance criteria:**
- [ ] Clicking "Sell 1 strip" produces a visible animated cascade through all tiers within seconds.
- [ ] Replaying an old correlation_id shows the same trace.
- [ ] Agent Console shows token totals matching `agent_runs`.

**Depends on:** Tasks 10 to 14, 24.

---

## Task 26: Workflow screens (Approvals, Audit, Adapter Forge, Regulatory Lab)

**Objective:** Build the UI for the human-in-the-loop and AI-engineering features.

**Context:** These screens showcase "Adapter Forge Marketplace", "Regulatory Hot-Swap Lab" and the "Audit Ledger" ideas.

### 26.1 Approvals inbox
- List pending/decided tasks with risk level; detail view showing the request payload (e.g., diff, shipment, schedule change), agent reasoning, approve/reject with note; live updates and desktop notification hook for new tasks.

### 26.2 Audit Ledger viewer
- Filterable table, entry detail (explanation, payload, hashes), "Verify chain" button showing result.

### 26.3 Adapter Forge
- Upload a sample payload (or choose a fixture), add an optional description, start generation; live progress showing each agent step (inspect, code, test, fix attempts); final view with generated source, tests and results; registry list with versions and rollback; a "try it" box posting a raw payload to `/ingest/{adapter_id}`.

### 26.4 Regulatory Lab
- Paste text, upload, or pick a fixture; start the pipeline; step view (analysis → code diff → tests → approval gate → hot-swap); side-by-side diff viewer of old vs. new module; before/after test of the rule (e.g., price check input); rollback button.

**Deliverables:** four screens wired to real endpoints.

**Acceptance criteria:**
- [ ] A full regulatory demo can be run from the UI only.
- [ ] A full adapter generation demo can be run from the UI only.
- [ ] Approving from the UI resumes the paused graph.

**Depends on:** Tasks 15 to 18, 24.

---

## Task 27: Compliance, Copilot and Developer Portal screens

**Objective:** Finish the remaining UI.

**Context:** Prescription data is sensitive; the UI must not display more than needed. The developer portal supports the "others can build over it" requirement.

### 27.1 Prescription Scanner
- Upload image, preview, show parsed fields, per-drug schedule class, doctor verification result, final decision, link to the compliance log; handling for flagged items sent to Approvals.

### 27.2 Cold Chain Monitor
- Batches with live temperature/humidity/shock charts (Recharts), shelf-life estimate, status badges, quarantine history; buttons to run a normal/excursion sensor simulation (admin).

### 27.3 Copilot
- Chat interface with streaming answers, reference chips linking to the underlying records, suggested questions.

### 27.4 Developer Portal
- API key management (create, scopes, revoke, show-once secret), webhook subscriptions and delivery log, link to `/docs`, code snippets (curl, Python, JavaScript), and MCP connection info if Task 23 is done.

**Deliverables:** four screens wired to real endpoints.

**Acceptance criteria:**
- [ ] The prescription flow works end to end from upload to decision in the UI.
- [ ] A quarantine can be triggered and observed live on the monitor.
- [ ] A new API key created in the portal works from the sample client.

**Depends on:** Tasks 19 to 22, 24.

---

## Task 28: Desktop application packaging

**Objective:** Ship the same React app as an installable desktop app.

**Context:** Interview requirement: both a desktop and a web version. Tauri needs the Rust toolchain, platform build tools (on Windows: MSVC build tools) and WebView2; check Tauri's current setup guide. If setup consumes too much time, fall back to Electron wrapping the same Vite build. Backend sidecar bundling is post-MVP; the desktop app connects to a configurable backend URL (local FastAPI by default).

### 28.1 Wrapper
- Initialize Tauri in `desktop/`, pointing to the Vite build output; app name, icon, window defaults.
- Settings screen for the backend URL stored locally; connection status indicator.

### 28.2 Native touches
- Native notifications for new approval tasks and quarantines.
- App menu and tray (optional); single-instance behavior.

### 28.3 Build
- Produce a Windows installer; document build steps; test that login, SSE and file upload work in the desktop build.
- CORS/origin configuration for the Tauri app in the backend.

### 28.4 Convenience
- `scripts/start-all` option that starts the backend then launches the desktop app.

**Deliverables:** desktop project, installer, build docs.

**Acceptance criteria:**
- [ ] The installed desktop app logs in and runs the cascade demo against the local backend.
- [ ] A new approval triggers a native notification.
- [ ] Web and desktop show identical features.

**Depends on:** Tasks 24 to 27.

---

# PHASE 8: HARDENING AND SUBMISSION

## Task 29: Testing and demo reliability

**Objective:** Make the demo robust against free-tier rate limits, bad model outputs and network trouble.

**Context:** This project determines the interview outcome, so the demo must be repeatable. LLM outputs are non-deterministic, so tests and demo fallbacks rely on the cache and the FakeLLM.

### 29.1 Automated tests
- Unit tests for guard, registry, hash ledger, router, event bus; graph tests with FakeLLM for cascade, forge, regulatory, prescription, cold-chain, copilot; API tests for auth/RLS/scopes/webhooks.
- One end-to-end script: seed → single sale → assert cascade rows, audit entries, SSE events.
- Optional browser test (Playwright) of the main demo path.

### 29.2 Failure handling
- Inject failures and confirm behavior: provider 429s, invalid JSON from the model, Ollama offline (sensitive calls fail clearly), HITL expiry, duplicate events, partial cascade failure.
- Standardize user-visible error messages for LLM failures in the UI.

### 29.3 Demo mode
- `DEMO_MODE=true` with `LLM_CACHE_MODE=replay` runs the full scripted demo from recorded outputs; record these by running the demo once online with `record`.
- Verify the demo also works with only Ollama running.
- Reset script that restores the database to the demo starting state.

### 29.4 Quality
- Lint/type checks (ruff, mypy if used, ESLint, tsc) pass; remove dead code; secrets check (no keys committed).

**Deliverables:** test suites, demo mode, reset script.

**Acceptance criteria:**
- [ ] Full test suite passes on a fresh clone with only `.env` filled in.
- [ ] The scripted demo completes in replay mode with the network disconnected.
- [ ] Killing one provider mid-demo does not break the flow.

**Depends on:** all previous tasks.

---

## Task 30: Benchmarks, token budget, documentation and submission package

**Objective:** Produce the evidence and documents that an RFP-style reviewer expects, honestly scoped to the MVP.

**Context:** RFP Section 6 asks for throughput proof, sovereign deployment plan, sandbox/vector/RLS design and a cost/token matrix. The MVP delivers measured data for what exists and a clear post-MVP path for the rest. Do not claim results you did not measure.

### 30.1 Benchmarks
- Script to measure the ingestion path (no LLM): events/second and p50/p95/p99 latency at increasing concurrency, using the batch endpoint and parallel clients; record hardware and configuration.
- Measure cascade latency per event (per-event and micro-batch modes) and LLM failure/fallback rates from `agent_runs`.
- Write `docs/BENCHMARKS.md` with methods, results and limitations.

### 30.2 Token and cost report
- Aggregate `agent_runs` into tokens per agent, per cascade, per feature (adapter generation, regulatory run, prescription).
- Table: MVP cost is zero (free models); show a clearly labeled extrapolation (tokens per event × volume) for hosted pricing as an estimate, not a measurement.

### 30.3 Architecture and design docs
- `docs/ARCHITECTURE.md`: diagram, graphs, agents list, data flow, event model, module registry, security (RLS, API keys, guard).
- `docs/POST_MVP.md`: Redpanda/Kafka swap behind `EventBus` with partitioning and consumer-group scaling reasoning, WASM isolation replacing the guard, Redis, Docker/Compose, sovereign Llama-3.3-70B deployment on Indian cloud, observability. State what is simulated (doctor registry, IoT, banking, regulatory sources).
- `docs/SECURITY_AND_COMPLIANCE.md`: RLS design, key handling, sensitive-data routing, audit chain, known MVP limitations (guard vs sandbox, in-memory rate limiting).

### 30.4 README
- Overview, features mapped to RFP sections, quick start (clone, `.env`, seed, run), demo script link, API guide link, desktop install, deferred items table, the "How AI built this" section from `HOW_AI_BUILT_THIS.md`.

### 30.5 Demo script and video
- Timed script (about 8 to 10 minutes): (1) one strip sale cascade, (2) burst and JIT production change, (3) cross-border/in-progress approval, (4) cold-chain quarantine, (5) prescription check, (6) Adapter Forge on a new legacy format, (7) regulatory hot-swap, (8) audit verify, (9) sample third-party client plus API docs, (10) desktop app.
- Record a backup video of the full demo.

### 30.6 Final checklist
- Fresh clone test, secrets removed, `.env.example` complete, tag a release, export OpenAPI JSON into `docs/`.

**Deliverables:** benchmark report, token report, docs, README, demo script, video.

**Acceptance criteria:**
- [ ] Every number in the docs comes from a recorded run.
- [ ] A reviewer can run the project from the README alone.
- [ ] The demo script runs cleanly twice in a row from the reset state.

**Depends on:** Task 29.
