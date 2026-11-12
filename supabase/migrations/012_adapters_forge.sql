-- Migration 012: Adapter Forge Schema Enhancements and Versioning

-- Ensure adapters table exists
CREATE TABLE IF NOT EXISTS public.adapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL DEFAULT '',
    version INT NOT NULL DEFAULT 1,
    format_type TEXT DEFAULT 'json',
    sample_payload TEXT,
    source_code TEXT,
    generated_parser_code TEXT,
    test_results JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'active' NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    description TEXT,
    target_schema TEXT DEFAULT 'SaleEvent',
    error_logs TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Ensure all columns exist for tables created under older migrations
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'name') THEN
        ALTER TABLE public.adapters ADD COLUMN name TEXT NOT NULL DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'version') THEN
        ALTER TABLE public.adapters ADD COLUMN version INT NOT NULL DEFAULT 1;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'source_code') THEN
        ALTER TABLE public.adapters ADD COLUMN source_code TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'test_results') THEN
        ALTER TABLE public.adapters ADD COLUMN test_results JSONB DEFAULT '{}'::jsonb;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'status') THEN
        ALTER TABLE public.adapters ADD COLUMN status TEXT DEFAULT 'active' NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'description') THEN
        ALTER TABLE public.adapters ADD COLUMN description TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'target_schema') THEN
        ALTER TABLE public.adapters ADD COLUMN target_schema TEXT DEFAULT 'SaleEvent';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'error_logs') THEN
        ALTER TABLE public.adapters ADD COLUMN error_logs TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'adapters' AND column_name = 'updated_at') THEN
        ALTER TABLE public.adapters ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now() NOT NULL;
    END IF;
END $$;

-- Indexes for performance and lookup
CREATE INDEX IF NOT EXISTS idx_adapters_name ON public.adapters(name);
CREATE INDEX IF NOT EXISTS idx_adapters_name_version ON public.adapters(name, version);
CREATE INDEX IF NOT EXISTS idx_adapters_status ON public.adapters(status);
CREATE INDEX IF NOT EXISTS idx_adapters_is_active ON public.adapters(is_active);
