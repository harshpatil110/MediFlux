-- =============================================================================
-- MediFlux Schema Migration 01: Initial Schema
-- Multi-tier Autonomous Pharmaceutical Supply Chain Network
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. PostgreSQL Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- -----------------------------------------------------------------------------
-- 2. Custom Enumerations
-- -----------------------------------------------------------------------------
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
-- 3. Network Layer
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

-- -----------------------------------------------------------------------------
-- 4. Catalog Layer
-- -----------------------------------------------------------------------------
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
-- 5. Stock & Inventory
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

-- -----------------------------------------------------------------------------
-- 6. Events Backbone
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
    payload JSONB NOT NULL,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- -----------------------------------------------------------------------------
-- 7. Flow & Operations
-- -----------------------------------------------------------------------------
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
-- 8. Manufacturing Tier
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

-- -----------------------------------------------------------------------------
-- 9. Compliance & Local Edge
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- 10. Cold Chain IoT
-- -----------------------------------------------------------------------------
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
-- 11. AI-Native Runtime & Governance
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

-- -----------------------------------------------------------------------------
-- 12. Developer Platform
-- -----------------------------------------------------------------------------
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
