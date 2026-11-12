-- 015_coldchain_telemetry.sql
-- Extension and enhancements for Cold-Chain Telemetry Graph and Auto-Quarantine (Task 20)

-- 1. Enhance sensor_readings table
ALTER TABLE IF EXISTS sensor_readings
    ADD COLUMN IF NOT EXISTS event_id TEXT,
    ADD COLUMN IF NOT EXISTS shipment_id UUID REFERENCES shipments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS duration_minutes NUMERIC(8,2) DEFAULT 15.0,
    ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'normal',
    ADD COLUMN IF NOT EXISTS correlation_id TEXT;

-- 2. Enhance quarantine_actions table
ALTER TABLE IF EXISTS quarantine_actions
    ADD COLUMN IF NOT EXISTS correlation_id TEXT,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'quarantined',
    ADD COLUMN IF NOT EXISTS rebalance_trace_id TEXT,
    ADD COLUMN IF NOT EXISTS rebalance_transfer_id UUID REFERENCES transfers(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS audit_seq INT;

ALTER TABLE IF EXISTS quarantine_actions ALTER COLUMN breach_duration_minutes DROP NOT NULL;
ALTER TABLE IF EXISTS quarantine_actions ALTER COLUMN temp_recorded DROP NOT NULL;

-- 3. Enhance batches table with cached shelf-life telemetry
ALTER TABLE IF EXISTS batches
    ADD COLUMN IF NOT EXISTS estimated_remaining_days NUMERIC(8,2),
    ADD COLUMN IF NOT EXISTS shelf_life_pct NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS last_reading_temp NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS last_reading_shock NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS last_reading_ts TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_telemetry_status TEXT DEFAULT 'ok';

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_sensor_readings_batch ON sensor_readings(batch_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_quarantine_actions_batch ON quarantine_actions(batch_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_actions_correlation ON quarantine_actions(correlation_id);
