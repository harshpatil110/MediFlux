-- =============================================================================
-- Migration 006: Add / update orders table schema for Pharmacy replenishment orders
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    stockist_id UUID REFERENCES public.nodes(id) ON DELETE SET NULL,
    product_id UUID,
    quantity INT NOT NULL DEFAULT 1,
    status VARCHAR(50) NOT NULL DEFAULT 'requested',
    priority VARCHAR(20) DEFAULT 'low',
    correlation_id VARCHAR(255),
    metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure all required columns exist if orders table was previously created
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS pharmacy_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS stockist_id UUID REFERENCES public.nodes(id) ON DELETE SET NULL;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS product_id UUID;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS quantity INT DEFAULT 1;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'requested';
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'low';
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_orders_pharmacy ON public.orders(pharmacy_id);
CREATE INDEX IF NOT EXISTS idx_orders_stockist ON public.orders(stockist_id);
CREATE INDEX IF NOT EXISTS idx_orders_correlation ON public.orders(correlation_id);
