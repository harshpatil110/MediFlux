-- 014_prescriptions_compliance.sql
-- Extension and enhancements for Sovereign Prescription and Schedule H Compliance Graph (Task 19)

-- 1. Enhance prescriptions table
ALTER TABLE IF EXISTS prescriptions
    ADD COLUMN IF NOT EXISTS doctor_name TEXT,
    ADD COLUMN IF NOT EXISTS doctor_registration_no TEXT,
    ADD COLUMN IF NOT EXISTS patient_initials TEXT,
    ADD COLUMN IF NOT EXISTS doctor_verified BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS drugs_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS decision TEXT,
    ADD COLUMN IF NOT EXISTS hitl_task_id UUID REFERENCES hitl_tasks(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS correlation_id TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Drop constraints if migrating from minimal schema to allow flexible ingestion
ALTER TABLE IF EXISTS prescriptions ALTER COLUMN rx_number DROP NOT NULL;
ALTER TABLE IF EXISTS prescriptions ALTER COLUMN doctor_reg_no DROP NOT NULL;
ALTER TABLE IF EXISTS prescriptions ALTER COLUMN patient_masked_id DROP NOT NULL;
ALTER TABLE IF EXISTS prescriptions ALTER COLUMN drug_name DROP NOT NULL;
ALTER TABLE IF EXISTS prescriptions ALTER COLUMN dosage DROP NOT NULL;
ALTER TABLE IF EXISTS prescriptions ALTER COLUMN quantity DROP NOT NULL;

-- 2. Enhance compliance_logs table
ALTER TABLE IF EXISTS compliance_logs
    ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS action TEXT,
    ADD COLUMN IF NOT EXISTS reason TEXT,
    ADD COLUMN IF NOT EXISTS correlation_id TEXT;

ALTER TABLE IF EXISTS compliance_logs ALTER COLUMN node_id DROP NOT NULL;
ALTER TABLE IF EXISTS compliance_logs ALTER COLUMN schedule_class DROP NOT NULL;
ALTER TABLE IF EXISTS compliance_logs ALTER COLUMN action_taken DROP NOT NULL;
ALTER TABLE IF EXISTS compliance_logs ALTER COLUMN passed DROP NOT NULL;

-- Indexes for efficient lookup
CREATE INDEX IF NOT EXISTS idx_prescriptions_status ON prescriptions(status);
CREATE INDEX IF NOT EXISTS idx_prescriptions_doc_reg ON prescriptions(doctor_registration_no);
CREATE INDEX IF NOT EXISTS idx_prescriptions_correlation ON prescriptions(correlation_id);
CREATE INDEX IF NOT EXISTS idx_compliance_logs_prescription ON compliance_logs(prescription_id);
CREATE INDEX IF NOT EXISTS idx_compliance_logs_action ON compliance_logs(action);
