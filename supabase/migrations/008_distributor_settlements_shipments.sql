-- =============================================================================
-- Migration 008: Add / update settlements and shipments tables for Distributor Tier
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.settlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES public.orders(id),
    buyer_id UUID NOT NULL REFERENCES public.nodes(id),
    distributor_id UUID NOT NULL REFERENCES public.nodes(id),
    unit_price NUMERIC(10, 2) NOT NULL,
    gross_total NUMERIC(10, 2) NOT NULL,
    discount_amount NUMERIC(10, 2) DEFAULT 0,
    net_total NUMERIC(10, 2) NOT NULL,
    margin_percentage NUMERIC(5, 2) NOT NULL,
    financing_needed BOOLEAN DEFAULT FALSE,
    financing_approved BOOLEAN DEFAULT NULL,
    status VARCHAR(50) DEFAULT 'settled',
    correlation_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure all required columns exist if settlements table was previously created
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS order_id UUID REFERENCES public.orders(id);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS buyer_id UUID REFERENCES public.nodes(id);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS distributor_id UUID REFERENCES public.nodes(id);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS unit_price NUMERIC(10, 2);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS gross_total NUMERIC(10, 2);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10, 2) DEFAULT 0;
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS net_total NUMERIC(10, 2);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS margin_percentage NUMERIC(5, 2);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS financing_needed BOOLEAN DEFAULT FALSE;
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS financing_approved BOOLEAN DEFAULT NULL;
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'settled';
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
ALTER TABLE public.settlements ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_ids JSONB NOT NULL,
    vehicle_id UUID NOT NULL,
    distributor_id UUID NOT NULL REFERENCES public.nodes(id),
    sequence INT NOT NULL DEFAULT 1,
    priority VARCHAR(20) DEFAULT 'medium',
    is_cold_chain BOOLEAN DEFAULT FALSE,
    requires_hitl BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'scheduled',
    eta_hours NUMERIC(5, 2),
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure all required columns exist if shipments table was previously created
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS order_ids JSONB;
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS vehicle_id UUID;
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS distributor_id UUID REFERENCES public.nodes(id);
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS sequence INT DEFAULT 1;
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium';
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS is_cold_chain BOOLEAN DEFAULT FALSE;
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS requires_hitl BOOLEAN DEFAULT FALSE;
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'scheduled';
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS eta_hours NUMERIC(5, 2);
ALTER TABLE public.shipments ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_settlements_buyer ON public.settlements(buyer_id);
CREATE INDEX IF NOT EXISTS idx_settlements_distributor ON public.settlements(distributor_id);
CREATE INDEX IF NOT EXISTS idx_settlements_correlation ON public.settlements(correlation_id);
CREATE INDEX IF NOT EXISTS idx_shipments_distributor ON public.shipments(distributor_id);
CREATE INDEX IF NOT EXISTS idx_shipments_vehicle ON public.shipments(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_shipments_correlation ON public.shipments(correlation_id);
