-- =============================================================================
-- Migration 005: Synthetic Data Metadata & SKU Extension
-- =============================================================================

ALTER TABLE nodes ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;
ALTER TABLE products ADD COLUMN IF NOT EXISTS sku TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;
ALTER TABLE batches ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;
ALTER TABLE credit_accounts ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;
ALTER TABLE fleet_vehicles ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;
ALTER TABLE production_lines ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;
ALTER TABLE api_inventory ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{"is_synthetic": true}'::jsonb;

-- Ensure index on sku if not exists
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);

