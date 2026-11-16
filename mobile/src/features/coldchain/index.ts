/**
 * Cold Chain Feature Module (Task M7).
 * Biologics IoT sensor telemetry, Arrhenius shelf-life degradation,
 * and autonomous quarantine monitoring.
 */

export * from './TelemetryChart';

export interface ColdChainBatchItem {
  batch_id: string;
  id?: string;
  batch_no: string;
  product_id: string;
  product_name: string;
  sku: string;
  node_id: string;
  node_name: string;
  storage_min_c: number;
  storage_max_c: number;
  status: 'ok' | 'warn' | 'quarantined';
  available_quantity: number;
  readings: Array<{
    ts: string;
    temperature_c: number;
    humidity?: number;
    shock_g?: number;
    decision?: string;
    estimated_remaining_days?: number;
  }>;
  last_reading?: {
    temperature_c: number;
    humidity?: number;
    shock_g?: number;
    ts?: string;
    mode?: string;
    decision?: string;
  };
  shelf_life_estimate: {
    nominal_remaining_days: number;
    estimated_remaining_days: number;
    shelf_life_pct: number;
    thermal_penalty_days: number;
    shock_penalty_days: number;
    degradation_days: number;
    formula_model: string;
    decision: string;
  };
  quarantine?: {
    id: string;
    reason: string;
    explanation: string;
    correlation_id: string;
    audit_entry_id?: string;
    rebalance_triggered: boolean;
    created_at: string;
  } | null;
}

export interface QuarantineRecord {
  id: string;
  batch_id: string;
  batch_no?: string;
  product_name?: string;
  node_id?: string;
  node_name?: string;
  reason?: string;
  explanation?: string;
  correlation_id?: string;
  audit_seq?: number;
  audit_entry_id?: string;
  triggered_at?: string;
  created_at: string;
}
