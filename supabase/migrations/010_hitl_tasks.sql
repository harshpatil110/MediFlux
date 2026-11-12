-- =============================================================================
-- Migration 010: Ensure hitl_tasks schema supports Task 15 fields and indexing
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.hitl_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(100) NOT NULL,
    node_id UUID NOT NULL REFERENCES public.nodes(id),
    correlation_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, approved, rejected, expired
    details JSONB DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ NOT NULL,
    decided_by UUID REFERENCES public.profiles(id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure all required columns exist if hitl_tasks table was previously created
ALTER TABLE public.hitl_tasks ADD COLUMN IF NOT EXISTS task_type VARCHAR(100);
ALTER TABLE public.hitl_tasks ADD COLUMN IF NOT EXISTS node_id UUID REFERENCES public.nodes(id);
ALTER TABLE public.hitl_tasks ADD COLUMN IF NOT EXISTS details JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.hitl_tasks ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE public.hitl_tasks ADD COLUMN IF NOT EXISTS decided_by UUID REFERENCES public.profiles(id);
ALTER TABLE public.hitl_tasks ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;
ALTER TABLE public.hitl_tasks ADD COLUMN IF NOT EXISTS decision_note TEXT;

CREATE INDEX IF NOT EXISTS idx_hitl_tasks_status ON public.hitl_tasks(status);
CREATE INDEX IF NOT EXISTS idx_hitl_tasks_task_type ON public.hitl_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_hitl_tasks_expires_at ON public.hitl_tasks(expires_at);
CREATE INDEX IF NOT EXISTS idx_hitl_tasks_correlation_id ON public.hitl_tasks(correlation_id);
