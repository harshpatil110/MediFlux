-- 016_developer_platform.sql
-- Extension and enhancements for Developer API Keys, Scopes, Rate Limiting, and Outbound Webhooks (Task 22)

-- 1. Enhance api_keys table
ALTER TABLE IF EXISTS api_keys
    ADD COLUMN IF NOT EXISTS name TEXT DEFAULT 'Default API Key' NOT NULL,
    ADD COLUMN IF NOT EXISTS key_prefix TEXT DEFAULT 'mfx_live_' NOT NULL,
    ADD COLUMN IF NOT EXISTS usage_count INT DEFAULT 0 NOT NULL,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true NOT NULL;

-- Allow node_id to be NULL for network-wide / admin developer keys
ALTER TABLE IF EXISTS api_keys ALTER COLUMN node_id DROP NOT NULL;

-- 2. Enhance webhook_subscriptions table
ALTER TABLE IF EXISTS webhook_subscriptions
    ADD COLUMN IF NOT EXISTS url TEXT,
    ADD COLUMN IF NOT EXISTS failure_count INT DEFAULT 0 NOT NULL,
    ADD COLUMN IF NOT EXISTS api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL;

-- Allow node_id to be NULL for network-wide webhook subscriptions
ALTER TABLE IF EXISTS webhook_subscriptions ALTER COLUMN node_id DROP NOT NULL;

-- 3. Enhance webhook_deliveries table
ALTER TABLE IF EXISTS webhook_deliveries
    ADD COLUMN IF NOT EXISTS event_type TEXT,
    ADD COLUMN IF NOT EXISTS response_body TEXT,
    ADD COLUMN IF NOT EXISTS success BOOLEAN DEFAULT false NOT NULL,
    ADD COLUMN IF NOT EXISTS attempt INT DEFAULT 1 NOT NULL,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now() NOT NULL;

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_node ON api_keys(node_id);
CREATE INDEX IF NOT EXISTS idx_webhook_subs_node ON webhook_subscriptions(node_id);
CREATE INDEX IF NOT EXISTS idx_webhook_subs_active ON webhook_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_sub ON webhook_deliveries(subscription_id);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_created ON webhook_deliveries(created_at);
