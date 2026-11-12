# Task 11 Specification: Pharmacy Tier (Inventory Telemetry Agent)

## 1. Overview & Objective

Task 11 implements the **Pharmacy Tier Node Agent** (Inventory Telemetry Agent), completing the edge intelligence layer of the MediFlux pharmaceutical supply chain. Atomic stock decrements occur immediately upon POS sale ingestion (Task 6); `PharmacyAgent` layers reasoning intelligence on top of streaming POS events (`sale`, `return`, `expiry_alert`).

The agent:
1. Analyzes updated stock levels against `safety_stock` and triggers replenishment signals (`needed = True`, target stockist resolution, and capacity-based order quantity calculation).
2. Evaluates return conditions (`damaged` vs `sellable`), marking damaged items for quarantine/disposal and restoring sellable items to inventory.
3. Scans near-expiry batches using First-Expired, First-Out (FEFO) heuristics and flags affected stock for rotation or removal.
4. Enforces regulatory compliance under the Drugs and Cosmetics Act for **Schedule H** (and Schedule G/X) substances, requiring a verified prescription linked to a registered physician before authorizing replenishment or dispense.
5. Persists purchase orders (`status: 'requested'`) into the Supabase `orders` table targeting the parent stockist node.

---

## 2. Key Components & Implementation Details

### 2.1 Agent Definition & Output Schemas (`app/agents/pharmacy_agent.py`)

- **`PharmacyAgent`**: Inherits from `BaseAgent`, utilizing deterministic domain heuristics and bounded LLM reasoning loops.
- **Pydantic Models**:
  ```python
  class ExpiryFlag(BaseModel):
      batch_id: str
      sku: str
      days_to_expiry: int
      quantity_affected: int
      recommendation: str  # e.g. "FEFO_ORDER_REQUIRED" or "MARK_FOR_REMOVAL"

  class ReplenishmentSignal(BaseModel):
      needed: bool = Field(..., description="Whether stock replenishment order is required")
      quantity: int = Field(0, description="Recommended replenishment quantity in units/strips")
      urgency: str = Field("low", description="Urgency level: low, medium, high, critical")
      reason: str = Field(..., description="Detailed explanation for the replenishment signal or hold")
      target_stockist_id: Optional[str] = Field(None, description="Parent stockist node UUID")
      compliance_hold: bool = Field(
          False,
          description="True if sale/order is held due to missing prescription or regulatory compliance check",
      )
      expiry_flags: list[ExpiryFlag] = Field(
          default_factory=list,
          description="List of batches near or past expiry",
      )
  ```

- **`PharmacyAgentResult`**: Specialized dictionary subclass providing dual dictionary and attribute access (`result.needed`, `result["needed"]`, `result.output["needed"]`, `result.model_dump()`).

### 2.2 Dedicated Pharmacy Telemetry Tools (`app/tools/pharmacy_tools.py`)

Registered with `@tool` in `app.tools.registry` and `app.agents.tools.registry`:
1. `get_inventory(node_id: str, product_id: Optional[str] = None) -> list[dict]`: Queries stock, safety stock levels, and reorder points with database connectivity and in-memory mock fallback.
2. `get_recent_sales(node_id: str, product_id: Optional[str] = None, days: int = 7) -> list[dict]`: Retrieves chronological POS retail dispense transactions for trend estimation.
3. `get_batches_near_expiry(node_id: str, threshold_days: int = 30) -> list[dict]`: Scans active stock batches expiring within the threshold window.
4. `check_prescription_link(event_id: str, prescription_ref: Optional[str] = None) -> dict`: Validates whether a Schedule H sale is tied to a registered doctor in `fixtures/doctor_registry.json` or event metadata. Returns `{"valid": bool, "doctor_id": Optional[str], "reason": str}`.

### 2.3 Cascade Graph Integration & Order Persistence (`graphs/cascade.py`)

- **`pharmacy_node` Integration**:
  - Replaces minimal stub with `PharmacyAgent.run(state)`.
  - Ingests `event`, `pharmacy_id`, `product_id`, `quantity`, `batch_id`, and `correlation_id`.
  - Emits dual telemetry (`agent.activity`, `cascade.updates`) for real-time observability.
  - Saves validated `ReplenishmentSignal` dictionary into `state["pharmacy_result"]`.
- **Database Order Persistence**:
  - When `signal.needed == True` and `compliance_hold == False`:
    - Inserts a record into the Supabase `orders` table (with in-memory fallback for test isolation):
      - `pharmacy_id`: `state["pharmacy_id"]`
      - `stockist_id`: `signal.target_stockist_id`
      - `product_id`: `state["product_id"]`
      - `quantity`: `signal.quantity`
      - `status`: `'requested'`
      - `priority`: `signal.urgency`
      - `correlation_id`: `state["correlation_id"]`
      - `metadata`: `{"is_synthetic": true, "reason": signal.reason}`

### 2.4 SQL Migration (`supabase/migrations/006_pharmacy_orders.sql`)

- Extends `public.orders` table with columns: `pharmacy_id`, `stockist_id`, `product_id`, `quantity`, `status`, `priority`, `correlation_id`, `metadata`.
- Adds performance indexes on `pharmacy_id`, `stockist_id`, and `correlation_id`.

---

## 3. Automated Test Suite (`backend/tests/test_pharmacy_agent.py`)

1. `test_safety_stock_replenishment`: Verifies stock falling below `safety_stock` yields `needed=True`, valid quantity, and creates a `'requested'` order row.
2. `test_return_and_expiry_events`: Verifies damaged returns trigger replacement orders while expiry alerts populate FEFO recommendations.
3. `test_schedule_h_compliance_hold`: Verifies Schedule H sales without verified prescriptions trigger `compliance_hold=True`, `urgency='high'`, and zero order records.
4. `test_schedule_h_with_valid_prescription`: Verifies Schedule H sales with valid registered doctors pass compliance and initiate restocking.
5. `test_sellable_return_restores_stock`: Verifies sellable returns restore inventory without creating redundant purchase orders.
6. `test_pharmacy_tools_direct_execution`: Tests direct execution of all four pharmacy tools.
7. `test_mock_supabase_client_order_insertion`: Asserts database client calls `table("orders").insert(...).execute()` when client is configured.
8. `test_cascade_graph_invokes_pharmacy_agent`: Confirms `cascade_graph` executes `pharmacy_node` and updates cascade traces.
