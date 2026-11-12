-- Migration 013: Regulatory Pipeline, Notifications Tracking, and Staged Runs

-- Ensure reg_notifications table exists and has necessary tracking columns
CREATE TABLE IF NOT EXISTS public.reg_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL DEFAULT '',
    notification_ref TEXT,
    publication_date DATE DEFAULT CURRENT_DATE,
    summary TEXT,
    full_text TEXT NOT NULL DEFAULT '',
    source TEXT DEFAULT 'CDSCO',
    content_hash TEXT,
    correlation_id TEXT,
    status TEXT DEFAULT 'pending',
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Ensure all columns exist for reg_notifications
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reg_notifications' AND column_name = 'source') THEN
        ALTER TABLE public.reg_notifications ADD COLUMN source TEXT DEFAULT 'CDSCO';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reg_notifications' AND column_name = 'content_hash') THEN
        ALTER TABLE public.reg_notifications ADD COLUMN content_hash TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reg_notifications' AND column_name = 'correlation_id') THEN
        ALTER TABLE public.reg_notifications ADD COLUMN correlation_id TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reg_notifications' AND column_name = 'status') THEN
        ALTER TABLE public.reg_notifications ADD COLUMN status TEXT DEFAULT 'pending';
    END IF;
END $$;

-- Create indexes on reg_notifications
CREATE INDEX IF NOT EXISTS idx_reg_notifications_hash ON public.reg_notifications(content_hash);
CREATE INDEX IF NOT EXISTS idx_reg_notifications_source ON public.reg_notifications(source);

-- Create regulatory_runs table for multi-agent mutation lifecycle
CREATE TABLE IF NOT EXISTS public.regulatory_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID REFERENCES public.reg_notifications(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'staged',
    affected_module_kind TEXT NOT NULL DEFAULT 'pricing',
    target_module_name TEXT NOT NULL DEFAULT 'pricing_engine',
    staged_version INT NOT NULL DEFAULT 2,
    active_version INT NOT NULL DEFAULT 1,
    reg_change JSONB DEFAULT '{}'::jsonb,
    diff TEXT DEFAULT '',
    test_results JSONB DEFAULT '{}'::jsonb,
    hitl_task_id UUID,
    error_logs TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Create indexes on regulatory_runs
CREATE INDEX IF NOT EXISTS idx_regulatory_runs_status ON public.regulatory_runs(status);
CREATE INDEX IF NOT EXISTS idx_regulatory_runs_notification ON public.regulatory_runs(notification_id);
