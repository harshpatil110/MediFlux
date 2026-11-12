-- =============================================================================
-- Migration 007: Add / update transfers table schema for Stockist peer transfers
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_id UUID NOT NULL REFERENCES public.nodes(id),
    to_node_id UUID NOT NULL REFERENCES public.nodes(id),
    product_id UUID NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, in_transit, completed, cancelled
    priority VARCHAR(20) DEFAULT 'medium',
    correlation_id VARCHAR(255),
    metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure all required columns exist if transfers table was previously created
ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium';
ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
ALTER TABLE public.transfers ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;

DO $$ BEGIN
    ALTER TABLE public.transfers ALTER COLUMN batch_id DROP NOT NULL;
EXCEPTION
    WHEN undefined_column THEN null;
END $$;

CREATE INDEX IF NOT EXISTS idx_transfers_from_node ON public.transfers(from_node_id);
CREATE INDEX IF NOT EXISTS idx_transfers_to_node ON public.transfers(to_node_id);
CREATE INDEX IF NOT EXISTS idx_transfers_correlation ON public.transfers(correlation_id);
