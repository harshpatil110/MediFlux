-- =============================================================================
-- MediFlux Complete Database Setup (Combined Migrations 01 - 04)
-- Run this entire script in Supabase Dashboard SQL Editor
-- =============================================================================

-- -----------------------------------------------------------------------------
-- SECTION 1: Extensions & Enumerations
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
    CREATE TYPE node_tier AS ENUM ('pharmacy', 'stockist', 'distributor', 'manufacturer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE batch_status AS ENUM ('active', 'quarantined', 'expired');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE order_status AS ENUM ('pending', 'approved', 'dispatched', 'delivered', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE transfer_status AS ENUM ('requested', 'in_transit', 'completed', 'rejected');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE shipment_status AS ENUM ('scheduled', 'in_transit', 'delivered', 'delayed', 'quarantined');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE production_status AS ENUM ('planned', 'in_progress', 'completed', 'halted');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE module_kind AS ENUM ('business_rule', 'adapter', 'parser');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE module_status AS ENUM ('staging', 'active', 'retired');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE hitl_status AS ENUM ('pending', 'approved', 'rejected', 'timed_out');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE schedule_class AS ENUM ('SCHEDULE_H', 'SCHEDULE_H1', 'SCHEDULE_X', 'OTC', 'GENERAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- -----------------------------------------------------------------------------
-- SECTION 2: Network & Catalog Layers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tier node_tier NOT NULL,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    parent_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
    address TEXT,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL,
    role TEXT NOT NULL,
    node_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    schedule_class schedule_class NOT NULL DEFAULT 'GENERAL',
    is_cold_chain BOOLEAN DEFAULT false NOT NULL,
    storage_min_c NUMERIC(4,2),
    storage_max_c NUMERIC(4,2),
    is_lifesaving BOOLEAN DEFAULT false NOT NULL,
    unit TEXT DEFAULT 'strip' NOT NULL,
    price_per_unit NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    manufacturer_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    batch_no TEXT UNIQUE NOT NULL,
    mfg_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    status batch_status DEFAULT 'active' NOT NULL,
    initial_quantity INT NOT NULL CHECK (initial_quantity >= 0),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- -----------------------------------------------------------------------------
-- SECTION 3: Stock, Events & Operations Layers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    quantity INT DEFAULT 0 NOT NULL CHECK (quantity >= 0),
    reserved INT DEFAULT 0 NOT NULL CHECK (reserved >= 0),
    safety_stock INT DEFAULT 10 NOT NULL CHECK (safety_stock >= 0),
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_inventory_node_product_batch UNIQUE (node_id, product_id, batch_id)
);

CREATE TABLE IF NOT EXISTS api_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    quantity NUMERIC(12,3) NOT NULL CHECK (quantity >= 0),
    unit TEXT DEFAULT 'kg' NOT NULL,
    reorder_level NUMERIC(12,3) NOT NULL CHECK (reorder_level >= 0),
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
    payload JSONB NOT NULL,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    seller_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    status order_status DEFAULT 'pending' NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (total_amount >= 0),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    to_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    quantity INT NOT NULL CHECK (quantity > 0),
    status transfer_status DEFAULT 'requested' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS fleet_vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distributor_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    vehicle_number TEXT NOT NULL UNIQUE,
    vehicle_type TEXT NOT NULL,
    is_reefer BOOLEAN DEFAULT false NOT NULL,
    temperature_capacity_min NUMERIC(4,2),
    temperature_capacity_max NUMERIC(4,2),
    is_available BOOLEAN DEFAULT true NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES fleet_vehicles(id) ON DELETE SET NULL,
    is_cross_border BOOLEAN DEFAULT false NOT NULL,
    priority TEXT DEFAULT 'standard' NOT NULL,
    eta TIMESTAMPTZ,
    status shipment_status DEFAULT 'scheduled' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID UNIQUE NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    credit_limit NUMERIC(12,2) DEFAULT 100000.00 NOT NULL CHECK (credit_limit >= 0),
    used_credit NUMERIC(12,2) DEFAULT 0.00 NOT NULL CHECK (used_credit >= 0),
    credit_score INT DEFAULT 750 NOT NULL CHECK (credit_score BETWEEN 300 AND 900),
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS settlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    seller_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    discount_applied NUMERIC(12,2) DEFAULT 0.00 NOT NULL CHECK (discount_applied >= 0),
    status TEXT DEFAULT 'settled' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- -----------------------------------------------------------------------------
-- SECTION 4: Manufacturing, Compliance & Cold Chain
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS production_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plant_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    line_code TEXT NOT NULL,
    capacity_per_day INT NOT NULL CHECK (capacity_per_day > 0),
    is_active BOOLEAN DEFAULT true NOT NULL,
    CONSTRAINT uq_plant_line_code UNIQUE (plant_id, line_code)
);

CREATE TABLE IF NOT EXISTS production_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    line_id UUID NOT NULL REFERENCES production_lines(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    batch_no TEXT NOT NULL,
    planned_quantity INT NOT NULL CHECK (planned_quantity > 0),
    actual_quantity INT DEFAULT 0 NOT NULL CHECK (actual_quantity >= 0),
    status production_status DEFAULT 'planned' NOT NULL,
    scheduled_start TIMESTAMPTZ,
    scheduled_end TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS demand_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    signal_strength NUMERIC(8,2) NOT NULL,
    regional_breakdown JSONB,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS drug_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_name TEXT NOT NULL UNIQUE,
    regulatory_body TEXT DEFAULT 'CDSCO' NOT NULL,
    prescription_required BOOLEAN DEFAULT true NOT NULL,
    max_refills INT DEFAULT 0 NOT NULL,
    warning_label TEXT
);

CREATE TABLE IF NOT EXISTS doctor_registry_mock (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_no TEXT UNIQUE NOT NULL,
    doctor_name TEXT NOT NULL,
    qualification TEXT NOT NULL,
    is_valid BOOLEAN DEFAULT true NOT NULL
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rx_number TEXT UNIQUE NOT NULL,
    doctor_reg_no TEXT NOT NULL,
    patient_masked_id TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    is_verified BOOLEAN DEFAULT false NOT NULL,
    verified_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS compliance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    prescription_id UUID REFERENCES prescriptions(id) ON DELETE SET NULL,
    schedule_class TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    audit_note TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID REFERENCES batches(id) ON DELETE SET NULL,
    node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
    temperature_c NUMERIC(5,2) NOT NULL,
    humidity_pct NUMERIC(5,2),
    shock_g NUMERIC(5,2),
    timestamp TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    breach_duration_minutes INT NOT NULL,
    temp_recorded NUMERIC(5,2) NOT NULL,
    action_status TEXT DEFAULT 'quarantined' NOT NULL,
    triggered_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- -----------------------------------------------------------------------------
-- SECTION 5: AI Governance & Platform Layers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id TEXT NOT NULL,
    graph_name TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    model_used TEXT,
    provider TEXT,
    tokens_in INT DEFAULT 0 NOT NULL,
    tokens_out INT DEFAULT 0 NOT NULL,
    duration_ms INT DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    kind module_kind NOT NULL,
    version INT NOT NULL,
    status module_status DEFAULT 'staging' NOT NULL,
    source_code TEXT NOT NULL,
    tests_source TEXT NOT NULL,
    checksum TEXT NOT NULL,
    created_by TEXT DEFAULT 'system' NOT NULL,
    parent_version INT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_module_name_version UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS adapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    format_type TEXT NOT NULL,
    sample_payload TEXT,
    generated_parser_code TEXT,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS reg_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    notification_ref TEXT UNIQUE NOT NULL,
    publication_date DATE NOT NULL,
    summary TEXT,
    full_text TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS hitl_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id TEXT NOT NULL,
    workflow_name TEXT NOT NULL,
    step_name TEXT NOT NULL,
    task_data JSONB NOT NULL,
    status hitl_status DEFAULT 'pending' NOT NULL,
    reviewer_id UUID,
    decision_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id BIGSERIAL,
    previous_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    action_type TEXT NOT NULL,
    node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
    payload JSONB NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash TEXT UNIQUE NOT NULL,
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    scopes TEXT[] NOT NULL,
    rate_limit INT DEFAULT 60 NOT NULL,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_url TEXT NOT NULL,
    event_types TEXT[] NOT NULL,
    secret_key TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES webhook_subscriptions(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    status_code INT,
    payload JSONB,
    error TEXT,
    delivered_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- -----------------------------------------------------------------------------
-- SECTION 6: Atomic Stored Functions
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION apply_sale(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_current_qty INT;
    v_new_qty INT;
BEGIN
    IF p_qty <= 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'new_quantity', 0,
            'oversold', false,
            'error', 'Quantity must be positive'
        );
    END IF;

    SELECT quantity INTO v_current_qty
    FROM inventory
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'new_quantity', 0,
            'oversold', true,
            'error', 'Inventory record not found'
        );
    END IF;

    IF v_current_qty < p_qty THEN
        RETURN jsonb_build_object(
            'success', false,
            'new_quantity', v_current_qty,
            'oversold', true
        );
    END IF;

    UPDATE inventory
    SET quantity = quantity - p_qty,
        updated_at = now()
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    RETURNING quantity INTO v_new_qty;

    RETURN jsonb_build_object(
        'success', true,
        'new_quantity', v_new_qty,
        'oversold', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION apply_return(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_new_qty INT;
BEGIN
    IF p_qty <= 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Quantity must be positive'
        );
    END IF;

    INSERT INTO inventory (node_id, product_id, batch_id, quantity, updated_at)
    VALUES (p_node_id, p_product_id, p_batch_id, p_qty, now())
    ON CONFLICT (node_id, product_id, batch_id)
    DO UPDATE SET
        quantity = inventory.quantity + EXCLUDED.quantity,
        updated_at = now()
    RETURNING quantity INTO v_new_qty;

    RETURN jsonb_build_object(
        'success', true,
        'new_quantity', v_new_qty
    );
END;
$$;

CREATE OR REPLACE FUNCTION apply_expiry(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_current_qty INT;
    v_deduct_qty INT;
    v_new_qty INT;
    v_total_batch_qty INT;
    v_batch_status TEXT;
BEGIN
    IF p_qty <= 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Quantity must be positive'
        );
    END IF;

    SELECT quantity INTO v_current_qty
    FROM inventory
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'remaining_quantity', 0,
            'batch_status', 'not_found'
        );
    END IF;

    v_deduct_qty := LEAST(v_current_qty, p_qty);

    UPDATE inventory
    SET quantity = quantity - v_deduct_qty,
        updated_at = now()
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    RETURNING quantity INTO v_new_qty;

    SELECT COALESCE(SUM(quantity), 0) INTO v_total_batch_qty
    FROM inventory
    WHERE batch_id = p_batch_id;

    IF v_total_batch_qty = 0 THEN
        UPDATE batches
        SET status = 'expired'
        WHERE id = p_batch_id;
        v_batch_status := 'expired';
    ELSE
        SELECT status::text INTO v_batch_status
        FROM batches
        WHERE id = p_batch_id;
    END IF;

    RETURN jsonb_build_object(
        'success', true,
        'remaining_quantity', v_new_qty,
        'batch_status', v_batch_status
    );
END;
$$;

-- -----------------------------------------------------------------------------
-- SECTION 7: Indexes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_correlation_id ON events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_agent_runs_correlation_id ON agent_runs(correlation_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at ON agent_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_node_product ON inventory(node_id, product_id);
CREATE INDEX IF NOT EXISTS idx_batches_product ON batches(product_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
CREATE INDEX IF NOT EXISTS idx_nodes_tier_region ON nodes(tier, region);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_orders_buyer_status ON orders(buyer_node_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_seller_status ON orders(seller_node_id, status);
CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);
CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_batch_time ON sensor_readings(batch_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_quarantine_actions_batch ON quarantine_actions(batch_id);
CREATE INDEX IF NOT EXISTS idx_compliance_logs_node ON compliance_logs(node_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prescriptions_rx ON prescriptions(rx_number);
CREATE INDEX IF NOT EXISTS idx_hitl_tasks_status_corr ON hitl_tasks(status, correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_seq ON audit_ledger(sequence_id);

CREATE INDEX IF NOT EXISTS idx_demand_signals_embedding 
    ON demand_signals USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_reg_notifications_embedding 
    ON reg_notifications USING hnsw (embedding vector_cosine_ops);

-- -----------------------------------------------------------------------------
-- SECTION 8: Row-Level Security (RLS) & visible_node_ids() Function
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION visible_node_ids()
RETURNS SETOF UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
DECLARE
    v_user_id UUID;
    v_node_id UUID;
    v_role TEXT;
BEGIN
    v_user_id := auth.uid();
    
    IF v_user_id IS NULL THEN
        RETURN;
    END IF;

    SELECT node_id, role INTO v_node_id, v_role
    FROM profiles
    WHERE user_id = v_user_id;

    IF v_role = 'admin' THEN
        RETURN QUERY SELECT id FROM nodes;
        RETURN;
    END IF;

    IF v_node_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH RECURSIVE downstream_nodes AS (
        SELECT id, parent_id
        FROM nodes
        WHERE id = v_node_id
        
        UNION ALL
        
        SELECT n.id, n.parent_id
        FROM nodes n
        INNER JOIN downstream_nodes dn ON n.parent_id = dn.id
    )
    SELECT id FROM downstream_nodes;
END;
$$;

ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS nodes_select_policy ON nodes;
CREATE POLICY nodes_select_policy ON nodes
    FOR SELECT TO authenticated
    USING (id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS nodes_insert_policy ON nodes;
CREATE POLICY nodes_insert_policy ON nodes
    FOR INSERT TO authenticated
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE user_id = auth.uid() AND role = 'admin'));

DROP POLICY IF EXISTS nodes_update_policy ON nodes;
CREATE POLICY nodes_update_policy ON nodes
    FOR UPDATE TO authenticated
    USING (EXISTS (SELECT 1 FROM profiles WHERE user_id = auth.uid() AND role = 'admin'));

DROP POLICY IF EXISTS profiles_select_policy ON profiles;
CREATE POLICY profiles_select_policy ON profiles
    FOR SELECT TO authenticated
    USING (
        user_id = auth.uid() 
        OR node_id IN (SELECT visible_node_ids())
        OR EXISTS (SELECT 1 FROM profiles p WHERE p.user_id = auth.uid() AND p.role = 'admin')
    );

DROP POLICY IF EXISTS profiles_update_policy ON profiles;
CREATE POLICY profiles_update_policy ON profiles
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS inventory_select_policy ON inventory;
CREATE POLICY inventory_select_policy ON inventory
    FOR SELECT TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS inventory_insert_policy ON inventory;
CREATE POLICY inventory_insert_policy ON inventory
    FOR INSERT TO authenticated
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS inventory_update_policy ON inventory;
CREATE POLICY inventory_update_policy ON inventory
    FOR UPDATE TO authenticated
    USING (node_id IN (SELECT visible_node_ids()))
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS inventory_delete_policy ON inventory;
CREATE POLICY inventory_delete_policy ON inventory
    FOR DELETE TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS batches_select_policy ON batches;
CREATE POLICY batches_select_policy ON batches
    FOR SELECT TO authenticated
    USING (
        manufacturer_id IN (SELECT visible_node_ids())
        OR id IN (SELECT batch_id FROM inventory WHERE node_id IN (SELECT visible_node_ids()))
    );

DROP POLICY IF EXISTS batches_insert_policy ON batches;
CREATE POLICY batches_insert_policy ON batches
    FOR INSERT TO authenticated
    WITH CHECK (manufacturer_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS batches_update_policy ON batches;
CREATE POLICY batches_update_policy ON batches
    FOR UPDATE TO authenticated
    USING (manufacturer_id IN (SELECT visible_node_ids()))
    WITH CHECK (manufacturer_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS audit_ledger_select_policy ON audit_ledger;
CREATE POLICY audit_ledger_select_policy ON audit_ledger
    FOR SELECT TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS audit_ledger_insert_policy ON audit_ledger;
CREATE POLICY audit_ledger_insert_policy ON audit_ledger
    FOR INSERT TO authenticated
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS events_select_policy ON events;
CREATE POLICY events_select_policy ON events
    FOR SELECT TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS events_insert_policy ON events;
CREATE POLICY events_insert_policy ON events
    FOR INSERT TO authenticated
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

-- -----------------------------------------------------------------------------
-- SECTION 7: Atomic Functions & Stored Procedures (Task 6)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION apply_sale(
    p_event_id TEXT,
    p_pharmacy_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_quantity INT,
    p_correlation_id TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_exists BOOLEAN;
    v_prev_hash TEXT;
    v_curr_hash TEXT;
    v_current_qty INT;
BEGIN
    -- 1. Idempotency Check: if event already exists, return duplicate status
    SELECT EXISTS(
        SELECT 1 FROM events WHERE event_id = p_event_id::text
    ) INTO v_exists;

    IF v_exists THEN
        RETURN jsonb_build_object(
            'status', 'duplicate',
            'applied', false,
            'event_id', p_event_id
        );
    END IF;

    -- 2. Insert into events table
    INSERT INTO events (
        event_id,
        type,
        node_id,
        payload,
        correlation_id,
        created_at
    ) VALUES (
        p_event_id::text,
        'pos.sale',
        p_pharmacy_id,
        jsonb_build_object(
            'pharmacy_id', p_pharmacy_id,
            'product_id', p_product_id,
            'batch_id', p_batch_id,
            'quantity', p_quantity,
            'source', 'pos'
        ),
        p_correlation_id,
        now()
    );

    -- 3. Decrement quantity in inventory atomically
    UPDATE inventory
    SET quantity = GREATEST(quantity - p_quantity, 0),
        updated_at = now()
    WHERE node_id = p_pharmacy_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    RETURNING quantity INTO v_current_qty;

    -- 4. Append audit ledger entry
    SELECT current_hash INTO v_prev_hash
    FROM audit_ledger
    ORDER BY sequence_id DESC
    LIMIT 1;

    IF v_prev_hash IS NULL THEN
        v_prev_hash := 'GENESIS';
    END IF;

    v_curr_hash := md5(v_prev_hash || p_event_id::text || p_quantity::text);

    INSERT INTO audit_ledger (
        previous_hash,
        current_hash,
        action_type,
        node_id,
        payload,
        timestamp
    ) VALUES (
        v_prev_hash,
        v_curr_hash,
        'INVENTORY_DECREMENT',
        p_pharmacy_id,
        jsonb_build_object(
            'event_id', p_event_id::text,
            'product_id', p_product_id,
            'batch_id', p_batch_id,
            'quantity_deducted', p_quantity,
            'remaining_quantity', v_current_qty,
            'correlation_id', p_correlation_id
        ),
        now()
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'applied', true,
        'event_id', p_event_id,
        'remaining_quantity', v_current_qty
    );
END;
$$;


