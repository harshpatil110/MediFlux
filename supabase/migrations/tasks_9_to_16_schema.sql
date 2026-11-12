-- ============================================================================
-- MediFlux Schema Migration: Tasks 9 through 16
-- ============================================================================

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- Base Prerequisites (Nodes, Profiles, Products)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    tier VARCHAR(50) NOT NULL,
    license_number VARCHAR(100),
    gstin VARCHAR(15),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    pincode VARCHAR(20),
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    parent_id UUID REFERENCES public.nodes(id),
    cluster_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID REFERENCES public.nodes(id),
    email VARCHAR(255) UNIQUE,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'staff',
    phone VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    brand_name VARCHAR(255),
    generic_name VARCHAR(255),
    sku VARCHAR(100) UNIQUE NOT NULL,
    dosage_form VARCHAR(50),
    strength VARCHAR(50),
    package_size INT DEFAULT 1,
    unit_price NUMERIC(10,2) DEFAULT 0.00,
    mrp NUMERIC(10,2) DEFAULT 0.00,
    is_lifesaving BOOLEAN DEFAULT FALSE,
    is_cold_chain BOOLEAN DEFAULT FALSE,
    min_temp_c NUMERIC(4,1),
    max_temp_c NUMERIC(4,1),
    schedule_type VARCHAR(50) DEFAULT 'OTC',
    requires_prescription BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- TASK 9: Fixtures, Registries & Traffic Simulation
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.doctor_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    specialty VARCHAR(150),
    hospital_affinity VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.drug_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    schedule_type VARCHAR(50) NOT NULL, -- 'Schedule_H', 'Schedule_X', 'OTC', etc.
    requires_prescription BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.pos_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    quantity INT NOT NULL,
    prescription_ref VARCHAR(255),
    transaction_type VARCHAR(50) DEFAULT 'sale', -- 'sale', 'return', 'expiry'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- TASK 11: Pharmacy Tier Inventory Telemetry & Replenishment
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(100) UNIQUE,
    source_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    target_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    pharmacy_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    stockist_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    quantity INT NOT NULL,
    status VARCHAR(50) DEFAULT 'requested', -- 'requested', 'approved', 'dispatched', 'fulfilled', 'cancelled'
    urgency VARCHAR(50) DEFAULT 'normal', -- 'low', 'normal', 'urgent', 'critical'
    priority VARCHAR(50) DEFAULT 'low',
    reason TEXT,
    compliance_hold BOOLEAN DEFAULT FALSE,
    correlation_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS order_number VARCHAR(100) UNIQUE;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS source_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS target_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS pharmacy_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS stockist_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS urgency VARCHAR(50) DEFAULT 'normal';
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'low';
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS reason TEXT;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS compliance_hold BOOLEAN DEFAULT FALSE;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- TASK 12: Stockist Tier Dynamic Balancing & Peer Transfers
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_number VARCHAR(100) UNIQUE,
    from_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    to_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    quantity INT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'in_transit', 'completed', 'cancelled'
    priority VARCHAR(50) DEFAULT 'medium',
    correlation_id VARCHAR(255),
    reasoning TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS transfer_number VARCHAR(100) UNIQUE;
    ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'medium';
    ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
    ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS reasoning TEXT;
    ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- TASK 13: Distributor Tier Financial Settlement & Cold-Chain Transit
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.credit_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID UNIQUE REFERENCES public.nodes(id) ON DELETE CASCADE,
    credit_limit NUMERIC(12, 2) NOT NULL DEFAULT 50000.00,
    used NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    currency VARCHAR(10) DEFAULT 'USD',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.settlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES public.orders(id) ON DELETE CASCADE,
    approved BOOLEAN NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    margin NUMERIC(5, 2) NOT NULL,
    discount NUMERIC(5, 2) NOT NULL,
    credit_after NUMERIC(12, 2) NOT NULL,
    financing_needed BOOLEAN DEFAULT FALSE,
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS buyer_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS distributor_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS unit_price NUMERIC(10, 2);
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS gross_total NUMERIC(10, 2);
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10, 2);
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS net_total NUMERIC(10, 2);
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS margin_percentage NUMERIC(5, 2);
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS financing_approved BOOLEAN;
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'settled';
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
    ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS public.fleet_vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distributor_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    vehicle_code VARCHAR(50) NOT NULL,
    is_reefer BOOLEAN DEFAULT FALSE, -- Cold-chain standard
    capacity_kg NUMERIC(10, 2) NOT NULL DEFAULT 1000.00,
    status VARCHAR(50) DEFAULT 'available', -- 'available', 'in_transit', 'maintenance'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_number VARCHAR(100) UNIQUE,
    order_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    vehicle_id UUID REFERENCES public.fleet_vehicles(id) ON DELETE SET NULL,
    distributor_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    sequence INT DEFAULT 1,
    priority VARCHAR(50) DEFAULT 'standard',
    is_cold_chain BOOLEAN DEFAULT FALSE,
    is_cross_border BOOLEAN DEFAULT FALSE,
    requires_hitl BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'manifested', -- 'manifested', 'dispatched', 'delivered', 'halted'
    eta TIMESTAMPTZ,
    eta_hours NUMERIC(5, 2),
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS shipment_number VARCHAR(100) UNIQUE;
    ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS distributor_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
    ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS is_cold_chain BOOLEAN DEFAULT FALSE;
    ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS requires_hitl BOOLEAN DEFAULT FALSE;
    ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS eta_hours NUMERIC(5, 2);
    ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- TASK 14: Manufacturer Tier Demand Vector Synthesis & JIT Scheduler
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.demand_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    region VARCHAR(100) NOT NULL,
    trend VARCHAR(50) NOT NULL, -- 'surge', 'stable', 'declining', 'noise'
    forecast_qty INT NOT NULL,
    confidence NUMERIC(4, 3) NOT NULL,
    reasoning TEXT,
    is_noise BOOLEAN DEFAULT FALSE,
    embedding vector(1536),
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS is_noise BOOLEAN DEFAULT FALSE;
    ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS embedding vector(1536);
    ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS public.production_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    line_name VARCHAR(100) NOT NULL,
    capacity_per_day INT NOT NULL DEFAULT 10000,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'maintenance', 'idle'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.production_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    line_id UUID REFERENCES public.production_lines(id) ON DELETE CASCADE,
    batch_code VARCHAR(100) UNIQUE,
    batch_number VARCHAR(100) UNIQUE,
    quantity INT NOT NULL,
    api_consumed_kg NUMERIC(10, 2) DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'scheduled', -- 'scheduled', 'in_progress', 'completed', 'quarantined'
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    scheduled_start TIMESTAMPTZ,
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.production_batches ADD COLUMN IF NOT EXISTS batch_number VARCHAR(100) UNIQUE;
    ALTER TABLE public.production_batches ADD COLUMN IF NOT EXISTS api_consumed_kg NUMERIC(10, 2) DEFAULT 0.0;
    ALTER TABLE public.production_batches ADD COLUMN IF NOT EXISTS scheduled_start TIMESTAMPTZ;
    ALTER TABLE public.production_batches ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS public.api_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    ingredient_name VARCHAR(150),
    api_name VARCHAR(200),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    quantity_kg NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    available_kg NUMERIC(10, 2) DEFAULT 0.00,
    committed_kg NUMERIC(10, 2) DEFAULT 0.00,
    safety_threshold_kg NUMERIC(10, 2) NOT NULL DEFAULT 100.00,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.api_inventory ADD COLUMN IF NOT EXISTS api_name VARCHAR(200);
    ALTER TABLE public.api_inventory ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES public.products(id) ON DELETE CASCADE;
    ALTER TABLE public.api_inventory ADD COLUMN IF NOT EXISTS available_kg NUMERIC(10, 2) DEFAULT 0.00;
    ALTER TABLE public.api_inventory ADD COLUMN IF NOT EXISTS committed_kg NUMERIC(10, 2) DEFAULT 0.00;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- TASK 15: Human-in-the-Loop Approval System
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.hitl_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(100) NOT NULL,
    node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    correlation_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'expired'
    details JSONB DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ NOT NULL,
    decided_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- TASK 16: Cryptographic Hash-Chained Audit Ledger
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_ledger (
    seq BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation TEXT DEFAULT '',
    prev_hash VARCHAR(64) NOT NULL,
    hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_ledger_entity ON public.audit_ledger(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_actor ON public.audit_ledger(actor);

-- Immutability Triggers for Audit Ledger
CREATE OR REPLACE FUNCTION prevent_audit_tampering()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit ledger records are immutable. UPDATE and DELETE operations are strictly forbidden.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_no_update ON public.audit_ledger;
CREATE TRIGGER trg_audit_no_update
BEFORE UPDATE ON public.audit_ledger
FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();

DROP TRIGGER IF EXISTS trg_audit_no_delete ON public.audit_ledger;
CREATE TRIGGER trg_audit_no_delete
BEFORE DELETE ON public.audit_ledger
FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();

