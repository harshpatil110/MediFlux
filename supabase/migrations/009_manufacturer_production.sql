-- =============================================================================
-- Migration 009: Add / update manufacturer tables for Demand Synthesis & JIT Scheduling
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.demand_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL,
    region VARCHAR(100) NOT NULL,
    trend VARCHAR(50) NOT NULL,
    forecast_qty INT NOT NULL DEFAULT 0,
    confidence NUMERIC(3, 2) NOT NULL DEFAULT 0.0,
    is_noise BOOLEAN DEFAULT FALSE,
    reasoning TEXT,
    embedding vector(1536), -- Vector column for semantic similarity (Task 21)
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure all required columns exist if demand_signals table was previously created
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS product_id UUID;
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS region VARCHAR(100) DEFAULT 'global';
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS trend VARCHAR(50) DEFAULT 'stable';
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS forecast_qty INT DEFAULT 0;
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS confidence NUMERIC(3, 2) DEFAULT 0.0;
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS is_noise BOOLEAN DEFAULT FALSE;
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS reasoning TEXT;
ALTER TABLE public.demand_signals ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);

CREATE TABLE IF NOT EXISTS public.production_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id UUID NOT NULL REFERENCES public.nodes(id),
    line_name VARCHAR(100) NOT NULL,
    capacity_per_day INT NOT NULL,
    status VARCHAR(50) DEFAULT 'active', -- active, maintenance, idle
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.production_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    line_id UUID NOT NULL REFERENCES public.production_lines(id),
    product_id UUID NOT NULL,
    batch_number VARCHAR(100) UNIQUE NOT NULL,
    quantity INT NOT NULL,
    api_consumed_kg NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled', -- scheduled, in_progress, completed, cancelled
    scheduled_start TIMESTAMPTZ NOT NULL,
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.production_batches ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);

CREATE TABLE IF NOT EXISTS public.api_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id UUID NOT NULL REFERENCES public.nodes(id),
    product_id UUID NOT NULL,
    api_name VARCHAR(200) NOT NULL,
    available_kg NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    committed_kg NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    safety_threshold_kg NUMERIC(10, 2) NOT NULL DEFAULT 5.0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demand_signals_product ON public.demand_signals(product_id);
CREATE INDEX IF NOT EXISTS idx_demand_signals_correlation ON public.demand_signals(correlation_id);
CREATE INDEX IF NOT EXISTS idx_production_batches_line ON public.production_batches(line_id);
CREATE INDEX IF NOT EXISTS idx_production_batches_status ON public.production_batches(status);
CREATE INDEX IF NOT EXISTS idx_production_batches_correlation ON public.production_batches(correlation_id);
CREATE INDEX IF NOT EXISTS idx_api_inventory_product ON public.api_inventory(product_id);
