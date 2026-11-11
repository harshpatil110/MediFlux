# MediFlux Database Schema Reference (`docs/schema.md`)

This document provides a comprehensive specification of the PostgreSQL database schema for MediFlux, deployed on Supabase. The schema powers the 4-tier autonomous pharmaceutical supply chain:

$$\text{Pharmacy Edge Node} \longrightarrow \text{Stockist Hub} \longrightarrow \text{Distributor Layer} \longrightarrow \text{Manufacturer Plant}$$

---

## 1. Architectural Layers & Tables Overview

The schema is partitioned into 10 logical layers comprising 25 tables, custom enumerations, pgvector embeddings, and atomic concurrency routines.

| Layer | Tables Included | Primary Purpose |
| :--- | :--- | :--- |
| **1. Network Layer** | `nodes`, `profiles` | Multi-tier topology nodes (Pharmacy, Stockist, Distributor, Plant) and authenticated user profiles |
| **2. Catalog Layer** | `products`, `batches` | Master medicine catalog (schedule class, cold-chain bounds) and manufacturer batch lineage |
| **3. Stock & Inventory** | `inventory`, `api_inventory` | Real-time node stock balances and manufacturer Active Pharmaceutical Ingredient (API) stockpiles |
| **4. Events Backbone** | `events` | Append-only domain event stream with correlation IDs and idempotency guarantees |
| **5. Flow & Operations** | `orders`, `transfers`, `fleet_vehicles`, `shipments`, `credit_accounts`, `settlements` | Multi-tier commercial fulfillment, logistics fleet, reefer telemetry, and automated financial settlements |
| **6. Manufacturing Tier** | `production_lines`, `production_batches`, `demand_signals` | Production capacity lines, batch manufacturing execution, and vector-embedded demand signals |
| **7. Compliance & Local Edge** | `drug_schedules`, `doctor_registry_mock`, `prescriptions`, `compliance_logs` | CDSCO schedule governance, OCR prescription validation, and regulatory audit trails |
| **8. Cold Chain IoT** | `sensor_readings`, `quarantine_actions` | High-frequency transit temperature telemetry and automated batch quarantine remediation |
| **9. AI Governance** | `agent_runs`, `modules`, `adapters`, `reg_notifications`, `hitl_tasks`, `audit_ledger` | LangGraph agent run telemetry, dynamically synthesized modules, HITL workflows, and hash-chained audit ledger |
| **10. Developer Platform** | `api_keys`, `webhook_subscriptions`, `webhook_deliveries` | Secure external API credentials, webhook dispatch, and delivery telemetry |

---

## 2. Enumerations

```sql
CREATE TYPE node_tier AS ENUM ('pharmacy', 'stockist', 'distributor', 'manufacturer');
CREATE TYPE batch_status AS ENUM ('active', 'quarantined', 'expired');
CREATE TYPE order_status AS ENUM ('pending', 'approved', 'dispatched', 'delivered', 'cancelled');
CREATE TYPE transfer_status AS ENUM ('requested', 'in_transit', 'completed', 'rejected');
CREATE TYPE shipment_status AS ENUM ('scheduled', 'in_transit', 'delivered', 'delayed', 'quarantined');
CREATE TYPE production_status AS ENUM ('planned', 'in_progress', 'completed', 'halted');
CREATE TYPE module_kind AS ENUM ('business_rule', 'adapter', 'parser');
CREATE TYPE module_status AS ENUM ('staging', 'active', 'retired');
CREATE TYPE hitl_status AS ENUM ('pending', 'approved', 'rejected', 'timed_out');
CREATE TYPE schedule_class AS ENUM ('SCHEDULE_H', 'SCHEDULE_H1', 'SCHEDULE_X', 'OTC', 'GENERAL');
```

---

## 3. Entity-Relationship & Table Specifications

### 3.1 Network Layer
- **`nodes`**: Represents physical entities in the Indian pharma supply chain.
  - `id` (UUID PK): Node unique identifier (`DEFAULT gen_random_uuid()`).
  - `tier` (`node_tier` NOT NULL): Tier enum ('pharmacy', 'stockist', 'distributor', 'manufacturer').
  - `name` (TEXT NOT NULL): Trade name of pharmacy, warehouse, depot, or manufacturing plant.
  - `region` (TEXT NOT NULL): State or geopolitical hub (e.g., 'MH-Mumbai', 'DL-Central').
  - `parent_id` (UUID FK `nodes.id`): Parent hierarchy node (e.g., Pharmacy → Stockist Hub).
  - `address` (TEXT): Physical postal location.
  - `is_active` (BOOLEAN DEFAULT true).
  - `created_at` (TIMESTAMPTZ DEFAULT now()).
- **`profiles`**: User identity mapped to a specific supply chain node.
  - `id` (UUID PK): Profile identifier.
  - `user_id` (UUID UNIQUE NOT NULL): Supabase Auth UID.
  - `role` (TEXT NOT NULL): Role designation ('pharmacist', 'stockist_mgr', 'plant_lead', 'auditor').
  - `node_id` (UUID FK `nodes.id` ON DELETE CASCADE).
  - `email` (TEXT).

### 3.2 Catalog Layer
- **`products`**: Master pharmaceutical SKU catalog.
  - `id` (UUID PK): Product identifier.
  - `name` (TEXT NOT NULL): Brand name (e.g., 'Azithral 500mg').
  - `generic_name` (TEXT NOT NULL): Chemical formulation (e.g., 'Azithromycin').
  - `schedule_class` (`schedule_class` NOT NULL DEFAULT 'GENERAL').
  - `is_cold_chain` (BOOLEAN DEFAULT false).
  - `storage_min_c` / `storage_max_c` (NUMERIC(4,2)): Permissible temperature range in °C (e.g., 2.00 to 8.00).
  - `is_lifesaving` (BOOLEAN DEFAULT false).
  - `unit` (TEXT DEFAULT 'strip').
  - `price_per_unit` (NUMERIC(10,2) NOT NULL): Maximum Retail Price (INR).
- **`batches`**: Specific manufactured drug lot.
  - `id` (UUID PK): Batch identifier.
  - `product_id` (UUID FK `products.id` ON DELETE CASCADE).
  - `manufacturer_id` (UUID FK `nodes.id` ON DELETE RESTRICT).
  - `batch_no` (TEXT UNIQUE NOT NULL): Batch serial number.
  - `mfg_date` (DATE NOT NULL) / `expiry_date` (DATE NOT NULL).
  - `status` (`batch_status` DEFAULT 'active').
  - `initial_quantity` (INT NOT NULL CHECK >= 0).

### 3.3 Stock & Inventory
- **`inventory`**: Current SKU lot balance held at an individual network node.
  - `id` (UUID PK).
  - `node_id` (UUID FK `nodes.id` ON DELETE CASCADE).
  - `product_id` (UUID FK `products.id` ON DELETE CASCADE).
  - `batch_id` (UUID FK `batches.id` ON DELETE CASCADE).
  - `quantity` (INT NOT NULL DEFAULT 0 CHECK >= 0): Available sellable units.
  - `reserved` (INT NOT NULL DEFAULT 0 CHECK >= 0): Stock locked for pending orders.
  - `safety_stock` (INT NOT NULL DEFAULT 10): Minimum threshold before restock trigger.
  - `updated_at` (TIMESTAMPTZ DEFAULT now()).
  - **Constraint**: `UNIQUE (node_id, product_id, batch_id)`.
- **`api_inventory`**: Raw chemical active pharmaceutical ingredients at manufacturing plants.
  - `id` (UUID PK).
  - `manufacturer_id` (UUID FK `nodes.id` ON DELETE CASCADE).
  - `ingredient_name` (TEXT NOT NULL).
  - `quantity` (NUMERIC(12,3) NOT NULL CHECK >= 0).
  - `unit` (TEXT DEFAULT 'kg').
  - `reorder_level` (NUMERIC(12,3) NOT NULL CHECK >= 0).

### 3.4 Events Backbone
- **`events`**: Append-only core event log for demand propagation and auditing.
  - `id` (UUID PK DEFAULT gen_random_uuid()).
  - `event_id` (TEXT UNIQUE NOT NULL): Idempotency key.
  - `type` (TEXT NOT NULL): Event name (e.g., `pharma.retail.dispensed`).
  - `node_id` (UUID FK `nodes.id` ON DELETE SET NULL).
  - `payload` (JSONB NOT NULL): Structured domain event contents.
  - `correlation_id` (TEXT NOT NULL): Trace ID linking 4-tier cascade chain.
  - `created_at` (TIMESTAMPTZ DEFAULT now()).

### 3.5 Flow & Operations
- **`orders`**: Wholesale replenishment purchase orders between nodes.
  - `buyer_node_id` / `seller_node_id` (UUID FK `nodes.id`).
  - `status` (`order_status` DEFAULT 'pending').
  - `total_amount` (NUMERIC(12,2) DEFAULT 0.00).
- **`transfers`**: Stock movement between inventory locations.
- **`fleet_vehicles`**: Logistics vehicles with reefer cold-chain capabilities.
- **`shipments`**: Transit orders mapped to fleet vehicles with priority and ETA.
- **`credit_accounts`**: Micro-credit limits, utilized balances, and scoring across tiers.
- **`settlements`**: Financial ledger entries for completed orders.

### 3.6 Manufacturing Tier
- **`production_lines`**: Manufacturing floor lines and daily batch throughput capacity.
- **`production_batches`**: Scheduled and in-progress synthesis runs.
- **`demand_signals`**: Aggregated demand vectors with 1536-dimensional semantic embeddings for neural forecasting.

### 3.7 Compliance & Cold Chain IoT
- **`drug_schedules`**: Regulatory classification, prescription mandates, and refill rules.
- **`doctor_registry_mock`**: Medical council registration verification.
- **`prescriptions`**: Digitized doctor prescription records with verification timestamps.
- **`compliance_logs`**: Schedule audit records for every dispensation.
- **`sensor_readings`**: High-frequency IoT telemetry ($T$, humidity, shock).
- **`quarantine_actions`**: Automated isolation records triggered upon temperature breach.

### 3.8 AI Governance & Runtime
- **`agent_runs`**: LangGraph agent execution trace, model telemetry, and token usage.
- **`modules`**: Dynamically synthesized business rules, adapters, and parsers.
- **`adapters`**: Synthetic data translators.
- **`reg_notifications`**: CDSCO gazette notices with vector embeddings for RAG retrieval.
- **`hitl_tasks`**: Human-in-the-loop approval escalations.
- **`audit_ledger`**: Cryptographically chained SHA-256 ledger (`previous_hash` $\to$ `current_hash`).

### 3.9 Developer Platform
- **`api_keys`**: Cryptographic hashed API keys for external system integrations.
- **`webhook_subscriptions`**: Subscriptions to domain events.
- **`webhook_deliveries`**: Delivery retry logs and HTTP response status codes.

---

## 4. Stored Atomic Functions (PL/pgSQL)

### 4.1 `apply_sale`
Guarantees atomic stock reduction during retail counter dispensing with row-level locking.

```sql
apply_sale(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
) RETURNS JSONB
```

**Behavior**:
- Acquires `FOR UPDATE` lock on `inventory(node_id, product_id, batch_id)`.
- If available quantity $< \text{p\_qty}$, returns `{"success": false, "new_quantity": N, "oversold": true}` without reducing stock below 0.
- Otherwise decrements quantity atomically and returns `{"success": true, "new_quantity": N - p_qty, "oversold": false}`.

### 4.2 `apply_return`
Atomically returns dispensed or rejected stock back to available inventory.

```sql
apply_return(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
) RETURNS JSONB
```

**Behavior**:
- Performs an atomic `INSERT ... ON CONFLICT (node_id, product_id, batch_id) DO UPDATE SET quantity = inventory.quantity + p_qty`.
- Returns `{"success": true, "new_quantity": N}`.

### 4.3 `apply_expiry`
Deducts spoiled or expired units and updates batch status.

```sql
apply_expiry(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
) RETURNS JSONB
```

**Behavior**:
- Atomically deducts expired quantity from node inventory.
- Evaluates total remaining batch stock across all supply chain nodes; if 0, marks `batches.status = 'expired'`.
- Returns `{"success": true, "remaining_quantity": N, "batch_status": "expired"}`.

---

## 5. Indexes Strategy

| Index Name | Table | Type | Indexed Columns / Operator | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `idx_events_created_at` | `events` | B-Tree | `created_at DESC` | Time-range event pagination & SSE streaming |
| `idx_events_correlation_id` | `events` | B-Tree | `correlation_id` | Tracing entire 4-tier cascade chains |
| `idx_agent_runs_correlation_id`| `agent_runs` | B-Tree | `correlation_id` | Associating agent executions with root demand event |
| `idx_inventory_node_product` | `inventory` | B-Tree | `node_id, product_id` | Fast stock availability checks during order routing |
| `idx_batches_product` | `batches` | B-Tree | `product_id` | Product-to-batch lineage lookups |
| `idx_demand_signals_embedding`| `demand_signals`| HNSW | `embedding vector_cosine_ops` | Nearest-neighbor demand pattern clustering |
| `idx_reg_notifications_embedding`| `reg_notifications`| HNSW | `embedding vector_cosine_ops` | RAG semantic retrieval for CDSCO regulatory notices |
