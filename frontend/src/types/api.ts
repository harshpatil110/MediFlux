/**
 * Core TypeScript definitions matching MediFlux FastAPI and Supabase schemas.
 */

export type UserRole =
  | "admin"
  | "regulator"
  | "manufacturer"
  | "distributor"
  | "stockist"
  | "pharmacy"
  | "developer";

export type NodeTier = "manufacturer" | "distributor" | "stockist" | "pharmacy";

export interface UserProfile {
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  node_id: string | null;
  node_name?: string | null;
  tier?: string | null;
  region?: string | null;
  scopes: string[];
  allowed_routes?: string[];
}

export type Actor = UserProfile;

export interface DemoUser {
  role: UserRole;
  label: string;
  email: string;
  password?: string;
  token: string;
  node_id: string | null;
  node_name: string | null;
  tier: string | null;
  region: string | null;
  description: string;
  allowed_routes: string[];
}

export interface NetworkNode {
  id: string;
  name: string;
  tier: NodeTier | string;
  region: string;
  city: string;
  license_number: string;
  parent_node_id?: string | null;
  created_at?: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  form: string;
  dosage: string;
  schedule: string;
  is_cold_chain: boolean;
  storage_min_c?: number | null;
  storage_max_c?: number | null;
  unit_price: number;
  gst_rate: number;
}

export interface Batch {
  id: string;
  batch_number: string;
  product_id: string;
  manufacturer_node_id: string;
  mfg_date: string;
  exp_date: string;
  is_quarantined: boolean;
  current_quantity: number;
}

export interface InventoryItem {
  id: string;
  node_id: string;
  product_id: string;
  batch_id: string;
  quantity_on_hand: number;
  safety_stock: number;
  reorder_point: number;
  products?: {
    id?: string;
    sku?: string;
    name?: string;
    form?: string;
    schedule?: string;
    is_cold_chain?: boolean;
    unit_price?: number;
  };
  batches?: {
    batch_number?: string;
    exp_date?: string;
    is_quarantined?: boolean;
  };
}

export interface SystemEvent {
  event_id: string;
  type: string;
  node_id: string;
  correlation_id: string;
  timestamp: string;
  payload: Record<string, any>;
  topic?: string;
  event_type?: string;
}

export interface AgentRun {
  run_id?: string;
  id?: string;
  agent_name: string;
  agent?: string;
  graph: string;
  model: string;
  provider?: string;
  node_id?: string | null;
  node_name?: string | null;
  status: "succeeded" | "completed" | "running" | "pending" | "failed" | string;
  duration_ms: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  correlation_id: string;
  input?: Record<string, any>;
  output?: Record<string, any>;
  reasoning?: string;
  error?: string | null;
  created_at: string;
  summary?: string;
}

export interface CascadeStep {
  tier: number;
  tier_label: "Pharmacy" | "Stockist" | "Distributor" | "Manufacturer" | string;
  agent_name: string;
  node_id: string;
  node_name: string;
  status: "succeeded" | "failed" | "running" | string;
  reasoning: string;
  input: Record<string, any>;
  output: Record<string, any>;
  model: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  duration_ms: number;
  timestamp: string;
  entities_created?: Record<string, any>;
}

export interface CascadeTrace {
  correlation_id: string;
  started_at: string;
  completed_at: string;
  total_duration_ms: number;
  total_tokens: number;
  trigger_event: Record<string, any>;
  steps: CascadeStep[];
  status?: string;
}

export interface CascadeSummary {
  correlation_id: string;
  timestamp: string;
  product_name: string;
  pharmacy_name: string;
  quantity: number;
  tiers_completed: string;
  total_duration_ms: number;
  total_tokens: number;
  status: string;
}

export interface AgentByGraphMetric {
  agent: string;
  graph: string;
  runs: number;
  failures: number;
  avg_latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface AgentByProviderMetric {
  provider: string;
  model: string;
  runs: number;
  failures: number;
  avg_latency_ms: number;
  total_tokens: number;
}

export interface AgentMetrics {
  total_runs: number;
  succeeded_runs: number;
  failed_runs: number;
  average_latency_ms: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  by_agent: AgentByGraphMetric[];
  by_provider: AgentByProviderMetric[];
}

export interface HitlTask {
  id?: string;
  task_id?: string;
  task_type: string;
  workflow_name?: string;
  title?: string;
  summary?: string;
  risk_level?: "critical" | "high" | "medium" | "low" | string;
  node_id?: string | null;
  node_name?: string | null;
  status: "pending" | "approved" | "rejected" | "expired" | string;
  payload?: Record<string, any>;
  details?: Record<string, any>;
  reasoning?: string;
  timeout_seconds?: number;
  created_at: string;
  expires_at?: string;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_note?: string | null;
  correlation_id?: string;
}

export interface AuditLedgerEntry {
  id: string;
  seq?: number;
  sequence_number?: number;
  prev_hash: string;
  entry_hash: string;
  hash?: string;
  actor?: string;
  actor_id?: string;
  actor_role?: string;
  node_id?: string;
  action: string;
  explanation?: string;
  details?: Record<string, any>;
  payload?: Record<string, any>;
  correlation_id?: string;
  created_at: string;
  ts?: string;
}

export interface AuditVerificationResult {
  valid: boolean;
  status: "verified" | "tampered" | string;
  total_entries: number;
  verified_entries: number;
  genesis_hash: string;
  head_hash: string;
  broken_at_id?: string | null;
  broken_at_seq?: number | null;
  verified_at: string;
  message?: string;
  reason?: string;
  details?: Array<{
    seq: number;
    hash: string;
    prev_hash: string;
    action?: string;
    actor?: string;
  }>;
}

export interface AdapterFixture {
  id: string;
  name: string;
  format: "csv" | "xml" | "json" | string;
  description: string;
  target_schema: string;
  sample_payload: any;
  expected_output?: Record<string, any>;
}

export interface AdapterGenerationJob {
  job_id: string;
  name?: string;
  adapter_name?: string;
  status: string;
  adapter_id?: string;
  version?: number;
  events?: Array<{
    step: string;
    status: string;
    message?: string;
    timestamp?: string;
    details?: Record<string, any>;
  }>;
  test_results?: Record<string, any>;
  error_logs?: string[];
  generated_code?: string;
}

export interface RegulatoryFixture {
  id: string;
  title: string;
  source: string;
  category?: string;
  raw_text: string;
  test_payload: {
    sku: string;
    drug_name?: string;
    unit_price: number;
    quantity: number;
  };
  ceiling_price?: number | null;
}

export interface RegulatoryRun {
  id: string;
  notification_id?: string;
  status: "analyzing" | "coding" | "testing" | "awaiting_approval" | "staged" | "deployed" | "failed" | "rolled_back" | string;
  affected_module_kind?: string;
  target_module_name?: string;
  staged_version?: number;
  active_version?: number;
  reg_change?: {
    topic?: string;
    effective_date?: string;
    affected_module_kind?: string;
    target_module_name?: string;
    parameters?: Record<string, any>;
    summary?: string;
    confidence?: number;
  };
  diff?: string;
  test_results?: Record<string, any>;
  hitl_task_id?: string | null;
  old_source_code?: string;
  new_source_code?: string;
  error_logs?: string;
  created_at?: string;
}

export interface PriceCheckResult {
  active_version: number;
  module_name: string;
  input: {
    sku: string;
    unit_price: number;
    quantity: number;
    drug_name?: string;
  };
  output: {
    sku: string;
    unit_price: number;
    effective_price: number;
    final_unit_price: number;
    price_capped: boolean;
    ceiling_applied: number | null;
    total_amount: number;
    compliant: boolean;
  };
  result?: Record<string, any>;
  evaluated_at: string;
}

export interface Adapter {
  id: string;
  name: string;
  erp_system: string;
  version: string;
  status: "active" | "staging" | "deprecated" | "archived" | string;
  transformation_rules: Record<string, any>;
  source_code?: string;
  created_at: string;
}

export interface RegulatoryNotification {
  id: string;
  source: string;
  title: string;
  summary: string;
  affected_schedules?: string[];
  content_hash: string;
  status: string;
  published_at?: string;
  created_at?: string;
}

export interface ComplianceLog {
  id: string;
  prescription_id?: string;
  drug_name: string;
  schedule: string;
  dispensed_qty: number;
  doctor_reg_number: string;
  patient_identifier: string;
  node_id: string;
  is_verified: boolean;
  created_at: string;
}

export interface ColdChainBatch {
  batch_id: string;
  batch_number?: string;
  product_name: string;
  node_id?: string;
  node_name?: string;
  storage_range: string;
  last_temperature: number;
  shelf_life_estimate: string;
  is_quarantined: boolean;
  status: string;
}

export interface CopilotQueryResponse {
  query: string;
  answer: string;
  citations: Array<{
    source: string;
    content: string;
    node_id?: string;
    confidence?: number;
  }>;
  generated_at: string;
}

export interface SearchResult {
  id: string;
  content: string;
  category: string;
  similarity: number;
  metadata?: Record<string, any>;
}

export interface ApiKey {
  key_id: string;
  node_id: string;
  role: string;
  scopes: string[];
  rate_limit_per_minute: number;
  is_active: boolean;
  created_at: string;
}

export interface WebhookSubscription {
  id: string;
  node_id: string;
  target_url: string;
  event_types: string[];
  is_active: boolean;
  consecutive_failures: number;
  created_at: string;
}

export interface OverviewKpis {
  events_today: number;
  total_events: number;
  stockout_risks: number;
  open_approvals: number;
  quarantined_batches: number;
  total_nodes: number;
  total_products: number;
  timestamp?: string;
  active_batches?: number;
  inventory_records?: number;
}
