# Task 13 Specification: Distributor Tier (Settlement Agent and Transit Optimization Agent)

## 1. Overview & Objective

Task 13 implements the **Distributor Tier Agents** (RFP 3.3) in the MediFlux pharmaceutical supply chain:
1. **Multi-Tiered Settlement Agent (`SettlementAgent`)**: Handles financial settlement, dynamic volume discounts, distributor margin compliance, buyer trade credit line underwriting, and automated trade financing simulation via partner banking APIs.
   - **Crucial Rule**: Margin calculations, volume discounts, and credit check rules MUST NOT be hardcoded in Python; they are dynamically executed through the AST/WASM-guarded module runtime (`run_module('margin_rules' | 'volume_discount' | 'credit_check_rules', ...)`).
2. **Transit Optimization Agent (`TransitOptimizationAgent`)**: Generates optimized fleet vehicle dispatch plans enforcing strict pharmaceutical transport constraints:
   - **Cold-Chain Safety Constraint**: Products requiring temperature control (`is_cold_chain == True`) are **strictly** assigned to refrigerated (reefer) vehicles (`is_reefer == True`). Ambient vehicles are strictly forbidden.
   - **Lifesaving Emergency Prioritization**: Critical therapeutics (`is_lifesaving == True`) receive top dispatch sequencing (`sequence = 1`) and `"critical"` priority.
   - **Cross-Border Compliance**: Routes crossing regional or international boundaries flag `requires_hitl = True` for mandatory human operator verification.

---

## 2. Architecture & Data Contracts

### 2.1 Multi-Tiered Settlement Agent (`app/agents/settlement_agent.py`)

- **Class**: `SettlementAgent(BaseAgent)`
- **Output Schema**:
  ```python
  class SettlementDecision(BaseModel):
      approved: bool = Field(..., description="Whether financial settlement and order approval succeeded")
      unit_price: float = Field(..., description="Base unit price of product")
      gross_total: float = Field(..., description="Total order amount before discounts")
      discount_amount: float = Field(..., description="Calculated volume discount amount in currency")
      net_total: float = Field(..., description="Final net order price after volume discount")
      margin_percentage: float = Field(..., description="Distributor margin applied (from active module)")
      credit_before: float = Field(..., description="Buyer available credit before settlement")
      credit_after: float = Field(..., description="Buyer available credit after settlement deduction")
      financing_needed: bool = Field(False, description="True if order exceeded credit limit and required trade financing")
      financing_approved: Optional[bool] = Field(None, description="Trade financing approval status if required")
      reasoning: str = Field(..., description="Detailed explanation of module executions, discounts, and credit check decisions")
  ```
- **SettlementAgentResult**: Dictionary subclass providing backward-compatible subscript and attribute access.

### 2.2 Transit Optimization Agent (`app/agents/transit_agent.py`)

- **Class**: `TransitOptimizationAgent(BaseAgent)`
- **Output Schema**:
  ```python
  class ShipmentSpec(BaseModel):
      shipment_id: Optional[str] = Field(None, description="Generated shipment UUID")
      order_ids: List[str] = Field(..., description="List of order UUIDs included in this shipment")
      vehicle_id: str = Field(..., description="Assigned vehicle UUID")
      vehicle_plate: str = Field(..., description="Assigned vehicle license plate")
      sequence: int = Field(..., description="Dispatch priority order (1 = highest/first)")
      priority: str = Field("medium", description="Priority level: 'low', 'medium', 'high', 'critical'")
      is_cold_chain: bool = Field(False, description="Whether shipment contains cold-chain products")
      requires_hitl: bool = Field(False, description="True if shipment requires HITL approval (e.g. cross-border)")
      eta_hours: float = Field(..., description="Estimated travel and delivery time in hours")

  class DispatchPlan(BaseModel):
      shipments: List[ShipmentSpec] = Field(default_factory=list, description="List of optimized shipment dispatches")
      reasoning: str = Field(..., description="Detailed explanation of vehicle assignment and dispatch sequencing logic")
  ```
- **TransitOptimizationAgentResult**: Dictionary subclass for flexible access across graphs and telemetry subscribers.

### 2.3 Dedicated Distributor Tools (`app/tools/distributor_tools.py`)

1. `get_credit_account(node_id: str) -> dict`: Fetches credit limit, current outstanding balance, and payment terms for a buyer node.
2. `mock_bank_finance(node_id: str, amount: float, credit_score_mock: int = 750) -> dict`: Simulated partner bank underwriting API returning approval, financing ID, and interest rate.
3. `list_vehicles(distributor_id: str, only_available: bool = True) -> list[dict]`: Queries fleet vehicles with license plate, refrigeration capabilities (`is_reefer`), capacity, and status.
4. `create_shipment(...) -> dict`: Inserts scheduled dispatch records into the `shipments` table.

---

## 3. Database Schema & Migration (`supabase/migrations/008_distributor_settlements_shipments.sql`)

- **`settlements` Table**: Stores financial settlement records, applied discount amounts, margins, buyer/distributor references, and trade financing flags.
- **`shipments` Table**: Stores vehicle dispatch schedules, sequence priority, cold-chain refrigeration flags, HITL requirements, and delivery ETAs.

---

## 4. Cascade Graph Integration (`app/graphs/cascade.py`)

- **`distributor_node`**:
  1. Invokes `SettlementAgent.run(state)` $\rightarrow$ writes to `state["settlement_result"]`.
  2. If settlement is approved: invokes `TransitOptimizationAgent.run(state)` $\rightarrow$ writes to `state["distributor_result"]`.
  3. If settlement is rejected: halts downstream cascade propagation to the manufacturer tier, marks `status = "partial"`, and logs explicit rejection telemetry.
- **`_route_from_distributor`**: Halts to `finalize` if settlement was rejected.

---

## 5. Verification & Test Suite (`tests/test_distributor_agents.py`)

1. `test_dynamic_module_margin_change`: Verifies that hot-swapping `margin_rules` from v1 (15%) to v2 (20%) via `module_registry` alters settlement results dynamically with 0 code changes.
2. `test_trade_financing_fallback`: Validates bank trade financing approval when buyer credit is breached, and order rejection when partner bank denies financing.
3. `test_cold_chain_vehicle_assignment`: Proves cold-chain products are strictly matched to reefer vehicles and never ambient vehicles.
4. `test_lifesaving_priority_sequencing`: Validates critical priority and sequence=1 scheduling for emergency therapeutics.
5. `test_cross_border_hitl_requirement`: Confirms cross-border orders trigger human-in-the-loop review.
6. `test_cascade_distributor_integration`: Verifies end-to-end 4-tier demand cascade execution including settlement and transit outputs.
7. `test_cascade_distributor_rejection_halts_propagation`: Ensures financial insolvency stops cascade at distributor and never proceeds to manufacturer.
