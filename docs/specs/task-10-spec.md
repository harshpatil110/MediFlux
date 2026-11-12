# Task 10 Specification: Cascade Graph Vertical Slice

## 1. Overview & Objective
Task 10 establishes the core end-to-end multi-tier demand cascade orchestration graph (Phase 3 vertical slice). When a single sale event is ingested at a pharmacy node (Task 6), it triggers an automated multi-agent cascade that propagates demand up the supply chain across four tiers:
$$\text{Pharmacy Edge Node} \longrightarrow \text{Stockist Hub} \longrightarrow \text{Distributor Layer} \longrightarrow \text{Manufacturer Plant}$$

The cascade operates with dynamic supervisor routing, conditional edge skipping, resilient partial-failure isolation, dual-topic telemetry broadcasting (`agent.activity` and `cascade.updates`), and an asynchronous background worker (`CascadeWorker`) supporting both `per_event` and `micro_batch` execution modes.

---

## 2. Key Components & Implementation Details

### 2.1 Configuration Settings (`core/config.py`)
- `CASCADE_MODE: Literal["per_event", "micro_batch"] = "per_event"`: Controls whether events trigger immediate cascade runs or accumulate in time-windowed batches.
- `CASCADE_MICRO_BATCH_WINDOW_SECONDS: int = 5`: Flushing interval for micro-batched event aggregation.
- `CASCADE_MAX_CONCURRENCY: int = 2`: Semaphore ceiling controlling concurrent cascade graph executions.

### 2.2 Cascade State & LangGraph Orchestration (`graphs/cascade.py`)
- **`CascadeState` Schema**:
  ```python
  class CascadeState(TypedDict):
      event: dict[str, Any]
      correlation_id: str
      pharmacy_id: str
      product_id: str
      batch_id: str
      quantity: int
      active_tiers: list[str]  # e.g. ["pharmacy", "stockist", "distributor", "manufacturer"]
      pharmacy_result: dict[str, Any] | None
      stockist_result: dict[str, Any] | None
      distributor_result: dict[str, Any] | None
      manufacturer_result: dict[str, Any] | None
      hitl_status: dict[str, Any] | None
      trace: list[dict[str, Any]]
      errors: list[dict[str, Any]]
      status: Literal["pending", "completed", "partial", "failed"]
  ```

- **Supervisor Node (`supervisor_node`)**:
  - Analyzes retail POS dispense event and current inventory buffer stock.
  - Dynamically flags `active_tiers`.
  - When downstream tiers are skipped, records explicit skip traces with reasons.

- **Conditional Edge Routing**:
  - `supervisor` $\rightarrow$ `pharmacy`
  - `pharmacy` $\rightarrow$ `stockist` if `"stockist" in active_tiers` else `finalize`
  - `stockist` $\rightarrow$ `distributor` if `"distributor" in active_tiers` else `finalize`
  - `distributor` $\rightarrow$ `manufacturer` if `"manufacturer" in active_tiers` else `finalize`
  - `manufacturer` $\rightarrow$ `finalize`
  - `finalize` $\rightarrow$ `END`

- **Resilient Tier Execution & Partial Failure Isolation**:
  - Each tier node wraps a scoped instance of `BaseAgent`.
  - Any unhandled exception or LLM failure within a tier is isolated: error recorded in `state["errors"]`, `state["status"]` marked `"partial"`, and control safely advances to `finalize_node` without terminating the graph or crashing the worker.

### 2.3 Background Event Subscription Worker (`workers/cascade_worker.py`)
- Subscribes to `pos.sales` topic on `InProcessEventBus`.
- Controls concurrency via `asyncio.Semaphore(settings.CASCADE_MAX_CONCURRENCY)`.
- **Modes**:
  - `per_event`: Immediately invokes `cascade_graph.ainvoke(...)` setting `thread_id = correlation_id`.
  - `micro_batch`: Gathers sales events into an async queue, flushes every `CASCADE_MICRO_BATCH_WINDOW_SECONDS`, groups by `(pharmacy_id, product_id)`, and executes aggregated cascade runs.
- **FastAPI Lifespan Integration**:
  - `await cascade_worker.start()` inside startup hook.
  - `await cascade_worker.stop()` inside shutdown hook.

### 2.4 Telemetry Broadcasting & Trace API (`api/v1/endpoints/cascade.py`)
- **Dual Telemetry Events** broadcast on entry and completion of every graph step:
  - `agent.activity`: Node activity, agent name, action, status, and duration.
  - `cascade.updates`: Real-time cascade step summaries streamed to clients over SSE.
- **Trace REST API Endpoint**:
  - `GET /api/v1/cascade/{correlation_id}`: Protected by `get_current_user` dependency.
  - Returns ordered step execution history, latencies, and statuses (`completed`, `partial`, `failed`).

---

## 3. Verification & Test Suite (`tests/test_cascade.py`)
- **Full 4-Tier Cascade Propagation**: Verifies end-to-end execution through Pharmacy, Stockist, Distributor, and Manufacturer, logging individual records in `agent_runs`.
- **Supervisor Conditional Skipping**: Verifies that when Supervisor activates only `["pharmacy"]`, downstream nodes (`stockist`, `distributor`, `manufacturer`) are skipped and logged with explicit skip reasons.
- **Partial Failure Isolation**: Verifies that a network failure injected in `distributor_node` results in a `"partial"` cascade status with errors captured while preserving prior successful results.
- **SSE Stream Sequence**: Confirms that chronological events are emitted to `cascade.updates` across all tiers.
- **Background Worker (`per_event`)**: Verifies that publishing to `pos.sales` automatically triggers cascade graph execution.
- **Cascade Trace REST API**: Confirms structured retrieval of cascade traces and 404 handling for unknown IDs.

