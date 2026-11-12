# Task 12 Specification: Stockist Tier (Dynamic Balancing Agent)

## 1. Overview & Objective

Task 12 implements the **Stockist Tier Node Agent** (Dynamic Balancing Agent - RFP 3.2), establishing the localized regional rebalancing layer in the MediFlux pharmaceutical supply chain. When a replenishment request or purchase order arrives from a downstream pharmacy tier node, `StockistAgent` determines how to fulfill demand across the local stockist cluster before regional stock deficits become critical.

The agent:
1. Verifies local stockist inventory balances against requested quantities.
2. Identifies peer stockists within the same regional cluster possessing surplus inventory above their safety stock thresholds.
3. Initiates peer-to-peer transfers (`transfers` table) to rebalance stock within the cluster when the local hub has a deficit.
4. Escalates to the parent regional distributor by creating a purchase order (`orders` table) when the entire cluster inventory is depleted.
5. Elevates priority to `"critical"` or `"high"` for lifesaving and cold-chain medications under regulatory and clinical urgency rules.

---

## 2. Key Components & Implementation Details

### 2.1 Agent Definition & Output Schemas (`app/agents/stockist_agent.py`)

- **`StockistAgent`**: Inherits from `BaseAgent`, featuring deterministic cluster balancing algorithms with bounded LLM reasoning loops.
- **Pydantic Models**:
  ```python
  class PeerTransferSpec(BaseModel):
      from_stockist_id: str = Field(..., description="Source stockist node UUID in the cluster")
      to_stockist_id: str = Field(..., description="Destination stockist node UUID")
      product_id: str = Field(..., description="Product UUID being transferred")
      quantity: int = Field(..., description="Number of units to transfer")
      reason: str = Field(..., description="Reason for peer transfer")

  class BalancingDecision(BaseModel):
      action: str = Field(
          ...,
          description="Action taken: 'fulfill_local', 'transfer_from_peer', or 'escalate_to_distributor'",
      )
      priority: str = Field("medium", description="Priority rating: 'low', 'medium', 'high', or 'critical'")
      transfers: list[PeerTransferSpec] = Field(
          default_factory=list,
          description="List of peer-to-peer stock transfers created",
      )
      escalation_order_id: str | None = Field(None, description="Distributor order UUID if escalated")
      reasoning: str = Field(..., description="Detailed explanation of the balancing and allocation decision")
  ```

- **`StockistAgentResult`**: Dictionary subclass providing dual dictionary and attribute access (`result.action`, `result["action"]`, `result.transfers`, `result.model_dump()`).

### 2.2 Dedicated Stockist Tools (`app/tools/stockist_tools.py`)

Registered with `@tool` in `app.tools.registry` and `app.agents.tools.registry`:
1. `list_nodes_in_cluster(node_id: str, cluster_id: Optional[str] = None) -> list[dict]`: Resolves all peer stockist nodes within the regional cluster.
2. `get_cluster_inventory(cluster_id: str, product_id: str) -> list[dict]`: Aggregates current stock, safety stock levels, and calculated surplus (`max(0, quantity - safety_stock)`) for every stockist in the cluster.
3. `get_demand_trend(node_id: str, product_id: str, window_hours: int = 24) -> dict`: Evaluates consumption velocity, velocity growth rate, and predicted depletion time.
4. `create_transfer(from_node_id: str, to_node_id: str, product_id: str, quantity: int, priority: str, correlation_id: str) -> dict`: Inserts a peer-to-peer stock movement record into the `transfers` table (`status: 'pending'`).
5. `create_order(from_node_id: str, to_node_id: str, product_id: str, quantity: int, priority: str, correlation_id: str) -> dict`: Inserts an escalation replenishment order targeting the parent distributor into the `orders` table (`status: 'requested'`).
6. `is_high_priority_drug(product_id: str, metadata: Optional[dict] = None) -> tuple[bool, str]`: Checks `is_lifesaving` and `is_cold_chain` flags across fixtures and input context.

### 2.3 Cascade Graph Integration (`graphs/cascade.py`)

- **`stockist_node` Integration**:
  - Replaced minimal stub with `StockistAgent.run(state)`.
  - Ingests `pharmacy_result`, `event`, `product_id`, `quantity`, `pharmacy_id`, and `correlation_id`.
  - Emits dual telemetry (`agent.activity`, `cascade.updates`) for real-time trace tracking.
  - Updates order status in Supabase `orders` table (`'allocated'` upon fulfillment / peer transfer, `'escalated'` upon distributor escalation).
  - Saves validated `BalancingDecision` dictionary into `state["stockist_result"]`.

### 2.4 SQL Migration (`supabase/migrations/007_stockist_transfers.sql`)

- Ensures `public.transfers` table schema has `priority`, `correlation_id`, `metadata`, and drops strict `batch_id` requirement for planned peer allocations.
- Adds performance indexes on `from_node_id`, `to_node_id`, and `correlation_id`.

---

## 3. Automated Test Suite (`backend/tests/test_stockist_agent.py`)

1. `test_fulfill_local`: Verifies that sufficient local stock fulfills the order locally without generating transfers or escalation orders.
2. `test_transfer_from_peer`: Verifies that a local deficit with peer surplus creates a peer-to-peer transfer in the `transfers` table with correct quantities.
3. `test_escalate_to_distributor`: Verifies that cluster-wide stock depletion creates an escalation order to the parent distributor in the `orders` table.
4. `test_lifesaving_priority_elevation`: Verifies priority elevation to `"critical"` or `"high"` for lifesaving and cold-chain medications.
5. `test_stockist_tools_direct_execution`: Verifies direct execution of all 5 dedicated stockist balancing tools.
6. `test_cascade_graph_invokes_stockist_agent`: Confirms `cascade_graph` executes `stockist_node` with `StockistAgent` and updates cascade state and traces.
