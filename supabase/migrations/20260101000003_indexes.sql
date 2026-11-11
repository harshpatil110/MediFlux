-- =============================================================================
-- MediFlux Schema Migration 03: Optimized Indexes
-- High-throughput B-Tree and HNSW Vector Search Indexes
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Core Specified B-Tree Indexes
-- -----------------------------------------------------------------------------

-- Events backbone queries (time-range filtering and correlation tracing)
CREATE INDEX IF NOT EXISTS idx_events_created_at 
    ON events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_correlation_id 
    ON events(correlation_id);

CREATE INDEX IF NOT EXISTS idx_events_type 
    ON events(type);

-- Agent telemetry queries
CREATE INDEX IF NOT EXISTS idx_agent_runs_correlation_id 
    ON agent_runs(correlation_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at 
    ON agent_runs(created_at DESC);

-- Inventory lookups by node and product
CREATE INDEX IF NOT EXISTS idx_inventory_node_product 
    ON inventory(node_id, product_id);

-- Product batch lineage lookups
CREATE INDEX IF NOT EXISTS idx_batches_product 
    ON batches(product_id);

CREATE INDEX IF NOT EXISTS idx_batches_status 
    ON batches(status);

-- -----------------------------------------------------------------------------
-- 2. Supply Chain Operational Indexes
-- -----------------------------------------------------------------------------

-- Node network queries
CREATE INDEX IF NOT EXISTS idx_nodes_tier_region 
    ON nodes(tier, region);

CREATE INDEX IF NOT EXISTS idx_nodes_parent 
    ON nodes(parent_id);

-- Order flow lifecycle
CREATE INDEX IF NOT EXISTS idx_orders_buyer_status 
    ON orders(buyer_node_id, status);

CREATE INDEX IF NOT EXISTS idx_orders_seller_status 
    ON orders(seller_node_id, status);

CREATE INDEX IF NOT EXISTS idx_shipments_order 
    ON shipments(order_id);

CREATE INDEX IF NOT EXISTS idx_shipments_status 
    ON shipments(status);

-- Cold chain telemetry high-frequency ingestion
CREATE INDEX IF NOT EXISTS idx_sensor_readings_batch_time 
    ON sensor_readings(batch_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_quarantine_actions_batch 
    ON quarantine_actions(batch_id);

-- Compliance and prescriptions
CREATE INDEX IF NOT EXISTS idx_compliance_logs_node 
    ON compliance_logs(node_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_prescriptions_rx 
    ON prescriptions(rx_number);

-- Human-in-the-loop task routing
CREATE INDEX IF NOT EXISTS idx_hitl_tasks_status_corr 
    ON hitl_tasks(status, correlation_id);

-- Cryptographic audit trail
CREATE INDEX IF NOT EXISTS idx_audit_ledger_seq 
    ON audit_ledger(sequence_id);

-- -----------------------------------------------------------------------------
-- 3. HNSW Vector Cosine Indexes (Semantic Search & RAG)
-- -----------------------------------------------------------------------------

-- Demand signals multi-dimensional embedding search
CREATE INDEX IF NOT EXISTS idx_demand_signals_embedding 
    ON demand_signals 
    USING hnsw (embedding vector_cosine_ops);

-- Regulatory notifications embedding search
CREATE INDEX IF NOT EXISTS idx_reg_notifications_embedding 
    ON reg_notifications 
    USING hnsw (embedding vector_cosine_ops);
