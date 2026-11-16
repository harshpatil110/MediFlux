-- Migration: Create device_tokens table with Row-Level Security for Mobile Push Notifications (Task M7)

CREATE TABLE IF NOT EXISTS public.device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    role VARCHAR(50),
    node_id UUID REFERENCES public.nodes(id) ON DELETE SET NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    platform VARCHAR(32) NOT NULL DEFAULT 'android',
    preferences JSONB DEFAULT '{"hitl": true, "coldchain": true}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_tokens_user_id ON public.device_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_device_tokens_role ON public.device_tokens(role);
CREATE INDEX IF NOT EXISTS idx_device_tokens_node_id ON public.device_tokens(node_id);
CREATE INDEX IF NOT EXISTS idx_device_tokens_token ON public.device_tokens(token);

-- Enable Row-Level Security
ALTER TABLE public.device_tokens ENABLE ROW LEVEL SECURITY;

-- Policies for Authenticated Users (users can manage their own device tokens)
DROP POLICY IF EXISTS "Users can select own device tokens" ON public.device_tokens;
CREATE POLICY "Users can select own device tokens" ON public.device_tokens
    FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own device tokens" ON public.device_tokens;
CREATE POLICY "Users can insert own device tokens" ON public.device_tokens
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own device tokens" ON public.device_tokens;
CREATE POLICY "Users can update own device tokens" ON public.device_tokens
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own device tokens" ON public.device_tokens;
CREATE POLICY "Users can delete own device tokens" ON public.device_tokens
    FOR DELETE
    USING (auth.uid() = user_id);

-- Service role bypass for backend push sender
DROP POLICY IF EXISTS "Service role full access on device_tokens" ON public.device_tokens;
CREATE POLICY "Service role full access on device_tokens" ON public.device_tokens
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
