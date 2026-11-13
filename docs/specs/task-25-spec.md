# Task 25 Specification: Live Operations Screens (Overview, Cascade Replay, Agent Console)

## 1. Overview & Objective
Task 25 delivers the three flagship live operations screens of the MediFlux platform:
1. **Network Overview (`frontend/src/pages/OverviewPage.tsx`)**: High-density operational control tower with 4 live KPI cards (`events_today` with SSE pulse dot, `stockout_risks`, `open_approvals`, `quarantined_batches`), interactive POS simulator control bar with primary CTA **"Sell 1 Strip"** (`mode: "single"`), real-time live event feed (merging SSE stream and historical events), and inventory table with visual low-stock highlighting (`available <= safety_stock`).
2. **Strip Cascade Replay (`frontend/src/pages/CascadePage.tsx`)**: Interactive 4-tier React Flow canvas (`@xyflow/react`) animating single-unit demand propagation across the supply chain:
   $$\text{Tier 4: Retail Pharmacy} \longrightarrow \text{Tier 3: Regional Stockist} \longrightarrow \text{Tier 2: Logistics Distributor} \longrightarrow \text{Tier 1: Formulation Plant}$$
   Features live trigger action, historical cascade selector dropdown (`GET /api/v1/cascade`), playback controls (Play, Pause, Restart, Step Back, Step Forward), speed selector (`0.5x`, `1x`, `2x`, `4x`), and deep-dive agent reasoning and telemetry side panel with collapsible input/output JSON viewers.
3. **Agent Console (`frontend/src/pages/AgentsPage.tsx`)**: Observability and telemetry console with 4 KPI cards (`total_runs`, `failed_runs`, `average_latency_ms`, `total_tokens`), 2 breakdown panels (by agent/graph and by LLM provider/model), filterable `agent_runs` table, summary footer proving mathematical token invariance, and slide-over run detail drawer.

---

## 2. Architectural Components

### 2.1 Backend Endpoints

1. **POS Demand Simulator (`backend/app/api/v1/endpoints/simulator.py`)**:
   - `POST /api/v1/simulator/pos`: Ingests `{ mode: "single" | "steady" | "burst" | "stockout", product_id, pharmacy_id, quantity }`.
   - Generates unique correlation ID (`casc-<hex12>`).
   - Executes real 4-tier demand cascade under single correlation ID:
     - Tier 4: Retail Pharmacy Node Agent (`pharmacy_node_agent`)
     - Tier 3: Regional Stockist Hub Agent (`dynamic_balancing_agent`)
     - Tier 2: Logistics Distributor Fleet Agent (`distributor_logistics_agent`)
     - Tier 1: Formulation Plant Production Agent (`manufacturer_production_agent`)
   - Logs `agent_runs` entries for each tier and saves complete trace in `_in_memory_cascade_traces`.
   - Publishes SSE events (`pos.sales`, `cascade_step`, `order.created`, `shipment.dispatched`, `production.batch`, `cascade.updates`).

2. **Demand Cascade Observability (`backend/app/api/v1/endpoints/cascade.py`)**:
   - `GET /api/v1/cascade`: Lists recent cascades with summary details (`correlation_id`, `timestamp`, `product_name`, `pharmacy_name`, `tiers_completed="4/4"`, `total_duration_ms`, `total_tokens`, `status`). Seeds initial traces if empty.
   - `GET /api/v1/cascade/{correlation_id}`: Returns exact deterministic 4-tier trace. Querying twice returns identical trace (Acceptance Criterion #2).
   - `POST /api/v1/cascade/trigger`: Alias to simulator endpoint.

3. **Overview KPIs (`backend/app/api/v1/endpoints/overview.py`)**:
   - `GET /api/v1/overview/kpis`: Returns live metrics: `events_today`, `total_events`, `stockout_risks` ($\ge 4$ via seeded low-stock inventory), `open_approvals`, `quarantined_batches`, `total_nodes`, `total_products`.

4. **Agent Telemetry & Invariance (`backend/app/api/v1/endpoints/agents.py`)**:
   - `GET /api/v1/agents/runs`: Filterable by `graph`, `agent`, `status`, `correlation_id`, `limit=100`.
   - `GET /api/v1/agents/metrics`: Aggregates tokens, latencies, and breakdowns directly over normalized runs.
   - **Mathematical Invariance Guarantee (Acceptance Criterion #3)**:
     $$\text{metrics.total\_tokens} \equiv \sum_{r \in \text{agent\_runs}} r.\text{total\_tokens}$$
     $$\sum \text{by\_agent.total\_tokens} \equiv \text{metrics.total\_tokens} \equiv \sum \text{by\_provider.total\_tokens}$$

---

### 2.2 Frontend Screens

1. **Network Overview (`frontend/src/pages/OverviewPage.tsx`)**:
   - 4 Live KPI Cards (Events Today with SSE pulse dot, Stockout Risks with click-to-filter, Open Approvals linking to `/approvals`, Quarantined Batches linking to `/cold-chain`).
   - Interactive POS Simulator Control Bar with Primary CTA **"Sell 1 Strip"**, Secondary buttons (Steady, Burst, Stockout), and Toast with "Watch Cascade Replay →" link (`/cascade?correlation_id=...`).
   - Live Event Feed with real-time SSE updates and historical event merge.
   - Inventory Table with product/facility search, low-stock filter toggle, and row tinting for items where `available <= safety_stock`.

2. **Strip Cascade Replay (`frontend/src/pages/CascadePage.tsx`)**:
   - Top Control Bar with "⚡ Sell 1 Strip & Watch Live" trigger button, historical cascade selector dropdown (`GET /api/v1/cascade`), correlation ID search form, playback controls, and speed buttons (`0.5x`, `1x`, `2x`, `4x`).
   - 4-Tier Interactive React Flow Canvas (`@xyflow/react`):
     - Custom tier nodes with states: `idle`, `active` (Electric Teal `#00AEBB` pulse ring), and `completed` (latency, tokens, decision snippet).
     - Animated connecting edges reflecting propagation state.
     - Node selection synchronizes with deep-dive side panel.
   - Agent Reasoning & Telemetry Side Panel:
     - Tier number, agent name, node name, status badge.
     - Execution telemetry (model, provider, prompt/completion/total tokens, duration ms).
     - Plain-language decision rationale.
     - Created domain artifact badges.
     - Collapsible JSON viewers for input and output payloads.

3. **Agent Console (`frontend/src/pages/AgentsPage.tsx`)**:
   - 4 Primary KPI Cards (Total Runs, Failed Runs & Error Rate, Average Latency, Total Tokens Consumed with prompt/completion subtitle).
   - 2 Breakdown Panels (by Agent/Graph and by LLM Provider/Model).
   - Filterable `agent_runs` table with graph filter, agent filter, status filter, and text search.
   - Summary footer row displaying sum of `total_tokens`, proving token math match.
   - Slide-over run detail drawer with full trace metadata and JSON viewers.

---

## 3. Verification & Acceptance Criteria
- **Acceptance Criterion #1 ("Sell 1 Strip" Cascade)**: Triggering "Sell 1 strip" executes in $< 1.5$ seconds, creates records across all 4 tiers (Pharmacy $\to$ Stockist $\to$ Distributor $\to$ Manufacturer), and streams SSE events. Verified in `tests/test_task25_live_operations.py::test_simulator_pos_single_trigger_and_4_tier_cascade`.
- **Acceptance Criterion #2 (Deterministic Replay)**: Querying `GET /api/v1/cascade/{correlation_id}` multiple times returns identical trace, tokens, and durations. Verified in `tests/test_task25_live_operations.py::test_deterministic_historical_cascade_replay`.
- **Acceptance Criterion #3 (Token Math Invariance)**: `metrics.total_tokens` strictly equals `sum(r["total_tokens"] for r in runs)`. Verified in `tests/test_task25_live_operations.py::test_agent_runs_filtering_and_metrics_invariance`.
- **Frontend Build**: `npm --prefix frontend run build` (`tsc -b && vite build`) compiles with 0 errors.
- **Backend Linter**: `ruff check .` passes with 0 warnings/errors.
