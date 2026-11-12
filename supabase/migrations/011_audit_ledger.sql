-- Migration 011: Cryptographically Hash-Chained Audit Ledger and Immutability Triggers

-- 1. Create audit_ledger table if not exists
CREATE TABLE IF NOT EXISTS public.audit_ledger (
    seq BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation TEXT DEFAULT '',
    prev_hash VARCHAR(64) NOT NULL,
    hash VARCHAR(64) NOT NULL
);

-- Ensure all required columns exist if table was previously defined
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'seq') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN seq BIGSERIAL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'ts') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN ts TIMESTAMPTZ DEFAULT NOW();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'actor') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN actor VARCHAR(100) DEFAULT 'system';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'action') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN action VARCHAR(100) DEFAULT 'UNKNOWN';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'entity_type') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN entity_type VARCHAR(100) DEFAULT 'general';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'entity_id') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN entity_id VARCHAR(255) DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'explanation') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN explanation TEXT DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'prev_hash') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN prev_hash VARCHAR(64) DEFAULT REPEAT('0', 64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_ledger' AND column_name = 'hash') THEN
        ALTER TABLE public.audit_ledger ADD COLUMN hash VARCHAR(64) DEFAULT REPEAT('0', 64);
    END IF;
END $$;

-- 2. Indexes for fast entity filtering, actor lookups, and sequence ordering
CREATE INDEX IF NOT EXISTS idx_audit_ledger_entity ON public.audit_ledger(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_actor ON public.audit_ledger(actor);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_seq ON public.audit_ledger(seq);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_ts ON public.audit_ledger(ts);

-- 3. Immutability Trigger Function (Prevent UPDATE and DELETE)
CREATE OR REPLACE FUNCTION prevent_audit_tampering()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit ledger records are immutable. UPDATE and DELETE operations are strictly forbidden.';
END;
$$ LANGUAGE plpgsql;

-- 4. Attach Triggers to audit_ledger table
DROP TRIGGER IF EXISTS trg_audit_no_update ON public.audit_ledger;
CREATE TRIGGER trg_audit_no_update
BEFORE UPDATE ON public.audit_ledger
FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();

DROP TRIGGER IF EXISTS trg_audit_no_delete ON public.audit_ledger;
CREATE TRIGGER trg_audit_no_delete
BEFORE DELETE ON public.audit_ledger
FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();
