# Task 14 Specification: Manufacturer Tier (Demand Vector Synthesis and JIT Formulation Scheduler Agent)

## 1. Overview & Objective

Task 14 implements the **Manufacturer Tier Agents** (RFP 3.4), closing the vertical loop of the 4-tier MediFlux supply chain ecosystem:
1. **Demand Vector Synthesis Agent (`DemandSynthesisAgent`)**: Converts retail demand events, stockist peer rebalancing deficits, and distributor replenishments into operational manufacturing demand signals using statistical metrics (moving averages, EWMA with $\alpha=0.3$, baseline rate, and spike ratio).
   - Classifies demand anomalies into `"sustained_surge"`, `"one_off_spike"`, or `"stable"`.
   - Distinguishes isolated single-store surges as noise (`is_noise = True`, `forecast_qty = 0`) to prevent bullwhip inventory distortions.
   - Persists classified signals to the `demand_signals` table (with `embedding` field left as `null` until semantic vectorization in Task 21).
2. **JIT Formulation Scheduler Agent (`JITSchedulerAgent`)**: Translates demand signals into production line batch schedules while enforcing active pharmaceutical ingredient (API) inventory constraints and safety guards:
   - **Noise Guard**: Automatically discards signals classified as noise or zero forecast.
   - **API Inventory Guard**: Verifies available raw ingredient inventory against batch requirements ($0.02\text{ kg/unit}$); rejects or caps batch sizes if inventory is insufficient.
   - **In-Progress Batch Modification Guard (HITL Trigger)**: If capacity constraints or urgent reprioritization require modifying, resizing, or cancelling an active batch currently in status `'in_progress'`, the agent marks `modifies_in_progress = True`, `requires_hitl = True`, creates a pending approval record in `hitl_tasks`, and strictly halts DB commits until human operator sign-off.

---

## 2. Architecture & Data Contracts

### 2.1 Demand Vector Synthesis Agent (`app/agents/demand_synthesis_agent.py`)

- **Class**: `DemandSynthesisAgent(BaseAgent)`
- **Output Schema**:
  ```python
  class DemandSignal(BaseModel):
      product_id: str = Field(..., description="Target product UUID")
      region: str = Field(..., description="Geographic region or stockist cluster ID")
      trend: str = Field(..., description="Classified trend: 'sustained_surge', 'one_off_spike', 'stable', or 'declining'")
      forecast_qty: int = Field(..., description="Forecasted additional manufacturing quantity required")
      confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
      reasoning: str = Field(..., description="Statistical and contextual explanation for trend classification")
      is_noise: bool = Field(False, description="True if detected anomaly is classified as noise (no schedule change needed)")
  ```
- **DemandSynthesisResult**: Subclass of `dict` providing dual subscript and attribute access.

### 2.2 JIT Formulation Scheduler Agent (`app/agents/scheduler_agent.py`)

- **Class**: `JITSchedulerAgent(BaseAgent)`
- **Output Schema**:
  ```python
  class BatchAction(BaseModel):
      action_type: str = Field(..., description="Action type: 'add_batch', 'resize_batch', 'reprioritize', or 'none'")
      batch_id: Optional[str] = Field(None, description="Existing batch UUID if modifying/reprioritizing, or None if adding new")
      line_id: str = Field(..., description="Assigned production line UUID")
      product_id: str = Field(..., description="Product UUID")
      quantity: int = Field(..., description="Batch size in units")
      api_required_kg: float = Field(..., description="Quantity of Active Pharmaceutical Ingredient (API) required in kg")
      scheduled_start: str = Field(..., description="ISO 8601 timestamp for batch run start")
      is_in_progress: bool = Field(False, description="True if target batch status is currently 'in_progress'")

  class ScheduleChange(BaseModel):
      actions: List[BatchAction] = Field(default_factory=list, description="List of proposed production schedule modifications")
      api_allocation_kg: float = Field(0.0, description="Total API stock allocated for this schedule change")
      reasoning: str = Field(..., description="Detailed explanation of capacity checks, API stock verification, and action selection")
      modifies_in_progress: bool = Field(False, description="Set to True if any action modifies a batch currently in status 'in_progress'")
      requires_hitl: bool = Field(False, description="Set to True if modifies_in_progress is True or API capacity risk exists")
  ```

### 2.3 Dedicated Manufacturer Tools (`app/tools/manufacturer_tools.py`)

1. `get_events_window(product_id: str, region: str, window_hours: int = 48) -> list[dict]`: Queries historical event telemetry across the specified lookback window.
2. `compute_trend(product_id: str, region: str, window_hours: int = 48) -> dict`: Computes rolling moving averages (12h, 24h, 48h), EWMA ($\alpha=0.3$), baseline rate, and spike ratio.
3. `get_production_schedule(line_id: Optional[str] = None) -> list[dict]`: Queries active and scheduled batches across production lines.
4. `get_api_inventory(product_id: str) -> dict`: Retrieves raw material stock levels (`available_kg`, `committed_kg`, `safety_threshold_kg`).
5. `apply_schedule_change(actions: list[dict], correlation_id: str) -> dict`: Atomically updates `production_batches` and decrements `api_inventory`.

---

## 3. Database Schema & Migration (`supabase/migrations/009_manufacturer_production.sql`)

- **`demand_signals` Table**: Stores synthesized demand vectors, trend classification, forecast quantities, confidence, and noise flags.
- **`production_lines` Table**: Tracks manufacturer formulation lines, daily capacities, and operational statuses (`active`, `maintenance`, `idle`).
- **`production_batches` Table**: Stores scheduled and active batch formulations, status lifecycle, API consumption, and start timestamps.
- **`api_inventory` Table**: Tracks raw chemical API balances, committed volumes, and safety thresholds per therapeutic compound.

---

## 4. Cascade Graph Integration (`app/graphs/cascade.py`)

- **`manufacturer_node`**:
  1. Invokes `DemandSynthesisAgent.run(state)` $\rightarrow$ stores output in `state["demand_signal"]`.
  2. Invokes `JITSchedulerAgent.run(state)` $\rightarrow$ stores output in `state["manufacturer_result"]`.
  3. If `modifies_in_progress == True`:
     - Updates graph state `status = "waiting_hitl"`.
     - Logs waiting step in cascade trace.
     - Routes conditionally to `END` without finalizing, yielding back execution for operator approval.

---

## 5. Verification & Test Suite (`tests/test_manufacturer_agents.py`)

1. `test_burst_demand_synthesis`: Verifies multi-node demand burst generates a `sustained_surge` signal with higher forecast quantity and schedules an `add_batch` action.
2. `test_one_off_spike_noise_classification`: Confirms isolated single-store spikes are classified as `one_off_spike` noise (`is_noise=True`, `forecast_qty=0`) with zero scheduler actions.
3. `test_api_inventory_exceeded_rejection`: Asserts batch additions exceeding raw API inventory are rejected with explicit reasoning and flagged for operator review.
4. `test_in_progress_batch_modification_hitl_guard`: Verifies modifying active batches pauses commits and creates a pending task in `hitl_tasks`.
5. `test_cascade_manufacturer_integration`: Validates full end-to-end 4-tier demand cascade execution including demand synthesis and scheduling.
6. `test_cascade_manufacturer_hitl_pause`: Confirms cascade execution halts with `status = "waiting_hitl"` when in-progress batches are modified.
