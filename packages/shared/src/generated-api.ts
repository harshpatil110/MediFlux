/**
 * AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.
 * Generated from docs/openapi.json via scripts/gen_api.py.
 * Run 'npm run gen:api' in mobile/ or 'python scripts/gen_api.py' to regenerate.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ============================================================================
// 1. OpenAPI Components & DTOs
// ============================================================================

export interface AgentMetricByAgent {
  agent: string;
  avg_latency_ms: number;
  completion_tokens: number;
  failures: number;
  graph: string;
  prompt_tokens: number;
  runs: number;
  total_tokens: number;
}

export interface AgentMetricByProvider {
  avg_latency_ms: number;
  failures: number;
  model: string;
  provider: string;
  runs: number;
  total_tokens: number;
}

export interface AgentMetricsResponse {
  average_latency_ms: number;
  by_agent: AgentMetricByAgent[];
  by_provider: AgentMetricByProvider[];
  failed_runs: number;
  succeeded_runs: number;
  total_completion_tokens: number;
  total_prompt_tokens: number;
  total_runs: number;
  total_tokens: number;
}

/** Response containing plaintext API key returned once upon creation. */
export interface ApiKeyCreatedResponse {
  /** Plaintext key alias */
  api_key: string;
  created_at: string;
  id: string;
  /** Plaintext key returned once and only once */
  key: string;
  key_prefix: string;
  name: string;
  node_id?: string | null;
  rate_limit: number;
  scopes: string[];
}

export interface Body_upload_prescription_api_v1_prescriptions_post {
  correlation_id?: string | null;
  file?: string | null;
  fixture_hint?: string | null;
  fixture_name?: string | null;
  node_id?: string | null;
}

export interface CascadeFullTrace {
  completed_at: string;
  correlation_id: string;
  started_at: string;
  status?: string;
  steps?: CascadeStepDetail[];
  total_duration_ms: number;
  total_tokens: number;
  trigger_event?: Record<string, unknown>;
}

export interface CascadeStepDetail {
  agent_name: string;
  completion_tokens?: number;
  duration_ms?: number;
  entities_created?: Record<string, unknown>;
  hitl_task_id?: string | null;
  input?: Record<string, unknown>;
  model?: string;
  node_id: string;
  node_name: string;
  output?: Record<string, unknown>;
  prompt_tokens?: number;
  provider?: string;
  reasoning: string;
  skip_reason?: string | null;
  stage?: string | null;
  state?: string | null;
  status?: string;
  structured_output?: Record<string, unknown>;
  /** Tier level: 5 (Supervisor) -> 4 (Pharmacy) -> 3 (Stockist) -> 2 (Distributor) -> 1 (Manufacturer) */
  tier: number;
  tier_label: string;
  timestamp?: string;
  total_tokens?: number;
}

export interface CascadeSummaryItem {
  correlation_id: string;
  created_at: string;
  outcome?: string;
  pharmacy_name: string;
  pharmacy_node_id?: string;
  product_id?: string;
  product_name: string;
  quantity?: number;
  sku?: string;
  status?: string;
  steps_completed?: number;
  summary?: string;
  tiers_completed?: string;
  timestamp?: string | null;
  total_duration_ms: number;
  total_steps?: number;
  total_tokens: number;
  trigger_summary?: string;
}

/** Schema for triggering synthetic IoT telemetry simulation. */
export interface ColdChainSimulateRequest {
  /** Target cold-chain batch ID (e.g. BIO-INS-01) */
  batch_id?: string | null;
  /** Simulation telemetry profile: 'normal' (2-8°C), 'excursion' (>8°C), 'shock' (>8g) */
  mode?: "normal" | "excursion" | "shock";
  /** Number of chronological telemetry reading steps */
  steps?: number;
}

/** Payload for conversational copilot query. */
export interface CopilotQueryRequest {
  /** Optional target node ID */
  node_id?: string | null;
  /** Alternative field for operational question */
  query?: string | null;
  /** Operational question to ask the Copilot */
  question?: string | null;
  /** Optional region filter */
  region?: string | null;
  /** Enable Server-Sent Events progressive streaming */
  stream?: boolean;
}

/** Response returned for standard Copilot query. */
export interface CopilotQueryResponse {
  activity_steps?: string[];
  answer: string;
  correlation_id?: string | null;
  question: string;
  references?: Record<string, unknown>[];
  scope?: Record<string, unknown>;
  tools_used?: string[];
  trace_id: string;
}

/** Schema for provisioning a new scoped developer API key. */
export interface CreateApiKeyRequest {
  /** Human-readable label for key */
  name?: string;
  /** Optional node UUID binding */
  node_id?: string | null;
  /** Requests permitted per minute */
  rate_limit?: number;
  /** Allowed scopes: read:inventory, write:events, read:stream, read:audit, use:copilot, manage:adapters, * */
  scopes?: string[];
}

/** Schema for registering an outbound webhook subscription. */
export interface CreateWebhookRequest {
  /** Event types: order.created, shipment.dispatched, batch.quarantined, hitl.created, hitl.decided, module.activated, * */
  events?: string[];
  /** Optional node UUID scoping */
  node_id?: string | null;
  /** Optional shared secret; auto-generated if omitted */
  secret?: string | null;
  /** Target HTTPS/HTTP webhook receiver URL */
  url: string;
}

/** Payload schema for registering or updating a client device push token. */
export interface DeviceTokenRegisterRequest {
  /** Client device platform */
  platform?: "android" | "ios" | "web" | "expo";
  /** Notification preference overrides */
  preferences?: Record<string, unknown> | null;
  /** Device push notification token (e.g. ExponentPushToken[...]) */
  token: string;
}

export interface EnrichedUserProfile {
  allowed_routes?: string[];
  email?: string | null;
  full_name?: string | null;
  id: string;
  node_id?: string | null;
  node_name?: string | null;
  permissions?: Record<string, unknown>;
  region?: string | null;
  role: string;
  role_name?: string | null;
  tier?: string | null;
  user_id: string;
}

/** Payload to trigger autonomous adapter synthesis and testing. */
export interface GenerateAdapterRequest {
  /** Human-readable description of source system */
  description?: string | null;
  /** Optional target canonical dictionary */
  expected_output?: Record<string, unknown> | null;
  /** Test hook for guard violation verification */
  injected_bad_code?: string | null;
  /** Maximum self-healing retry iterations */
  max_attempts?: number;
  /** Unique alphanumeric identifier for the adapter module */
  name: string;
  /** Raw legacy sample payload (CSV text, XML string, or JSON dict/list) */
  sample_payload: unknown;
  /** Target canonical schema ('SaleEvent' or 'BatchUpdate') */
  target_schema?: string;
}

/** Payload for submitting an approval or rejection decision on a pending HITL task. */
export interface HITLDecisionRequest {
  /** Operator identity submitting the decision. */
  decided_by?: string | null;
  /** Decision choice: 'approve'/'approved' to execute gated action, 'reject'/'rejected' to abort/cancel. */
  decision?: "approve" | "approved" | "reject" | "rejected";
  /** Justification note for human decision audit trail. */
  note?: string | null;
  /** Alias for justification note. */
  reason?: string | null;
}

/** Response returned upon submitting a decision for a HITL task. */
export interface HITLDecisionResponse {
  already_finalized?: boolean;
  audit_entry_id?: string | null;
  decided_at?: string | null;
  decided_by?: string | null;
  decision: string;
  execution_outcome?: Record<string, unknown> | null;
  outcome?: string | null;
  resumed?: boolean;
  resumed_cascade_correlation_id?: string | null;
  resumed_workflow?: Record<string, unknown> | null;
  status: string;
  task?: Record<string, unknown>;
  task_id: string;
}

/** Response returned by GET /api/v1/hitl/policies. */
export interface HITLPoliciesResponse {
  policies?: Record<string, unknown>;
}

/** Payload for triggering a simulated HITL task. */
export interface HITLTriggerRequest {
  /** Optional correlation ID to link with a cascade */
  correlation_id?: string | null;
  /** Custom details/payload override */
  details?: Record<string, unknown> | null;
  /** Originating node ID */
  node_id?: string | null;
  /** HITL task type to simulate */
  task_type?: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/** Payload to submit a regulatory notice for ingestion and pipeline execution. */
export interface IngestNoticeRequest {
  /** Override auto-deploy gating */
  auto_deploy?: boolean | null;
  /** Publishing authority */
  source?: string | null;
  /** Raw regulatory text or Gazette order */
  text?: string | null;
  /** Subject or Gazette reference title */
  title?: string | null;
  /** URL of official regulatory portal */
  url?: string | null;
}

/** Inventory item balance with batch and SKU information. */
export interface InventoryItemResponse {
  batch_id: string;
  batch_no?: string | null;
  id: string;
  node_id: string;
  product_id: string;
  product_name?: string | null;
  quantity: number;
  reserved?: number;
  safety_stock?: number;
  updated_at?: string;
}

export interface JSONRPCRequest {
  id?: string | number | null;
  jsonrpc?: string;
  method: string;
  params?: Record<string, unknown>;
}

export interface LoginRequest {
  email?: string | null;
  password?: string | null;
  role?: string | null;
}

export interface LoginResponse {
  access_token: string;
  token?: string | null;
  token_type?: string;
  user: Record<string, unknown>;
}

export interface MCPContentItem {
  text: string;
  type?: string;
}

export interface MCPToolCallRequest {
  /** Arguments to pass to the tool */
  arguments?: Record<string, unknown>;
  /** Tool name to execute */
  name?: string | null;
  /** Alias for arguments */
  parameters?: Record<string, unknown> | null;
  /** Alias for tool name */
  tool?: string | null;
}

export interface MCPToolCallResponse {
  content: MCPContentItem[];
  is_error?: boolean;
  structured_content?: Record<string, unknown> | null;
}

export interface MCPToolsListResponse {
  count: number;
  protocol_version?: string;
  tools: Record<string, unknown>[];
}

export interface MobileSaleRequest {
  /** Scanned barcode string */
  barcode?: string | null;
  /** Selected pharmaceutical batch UUID */
  batch_id?: string | null;
  /** Selected pharmaceutical batch number */
  batch_number?: string | null;
  /** Channel origin */
  channel?: string | null;
  /** Client unique UUID for idempotency */
  event_id?: string | null;
  /** Dispensing pharmacy node ID */
  node_id?: string | null;
  /** Pharmacy node ID alias */
  pharmacy_id?: string | null;
  /** Attached prescription UUID */
  prescription_id?: string | null;
  /** Product UUID or SKU */
  product_id: string;
  /** Quantity to dispense */
  quantity?: number;
  /** POS source indicator */
  source?: string;
  /** Unit retail price */
  unit_price?: number | null;
}

export interface MobileSaleResponse {
  /** Whether inventory was decremented in this call */
  applied: boolean;
  /** Full 5-stage demand cascade trace */
  cascade?: Record<string, unknown> | null;
  /** Alias for cascade trace */
  cascade_trace?: Record<string, unknown> | null;
  /** Whether 4-tier demand cascade was triggered */
  cascade_triggered?: boolean;
  /** True if flagged for Schedule H compliance review */
  compliance_hold?: boolean;
  /** Compliance verification status ('VERIFIED_COMPLIANT', 'FLAGGED_FOR_REVIEW') */
  compliance_status?: string | null;
  /** Alias for compliance warning */
  compliance_warning?: string | null;
  /** Demand cascade correlation ID */
  correlation_id: string;
  /** Event UUID */
  event_id: string;
  /** True if this event_id was previously executed */
  idempotent_replay?: boolean;
  /** Units dispensed */
  quantity_sold?: number;
  /** Remaining batch stock */
  remaining_quantity?: number | null;
  /** Remaining batch stock alias */
  remaining_stock?: number | null;
  /** Execution status ('succeeded', 'accepted', 'duplicate') */
  status: string;
  /** Compliance or inventory warning message */
  warning?: string | null;
}

export interface MobileScope {
  /** Bound supply chain node ID */
  node_id?: string | null;
  /** Bound supply chain node display name */
  node_name?: string | null;
  /** Active user role */
  role: string;
}

export interface MobileSummaryResponse {
  /** Number of events recorded today within user RLS scope */
  events_today: number;
  /** ISO 8601 timestamp of summary generation */
  generated_at: string;
  /** Correlation ID of the latest supply chain demand cascade */
  last_cascade_correlation_id?: string | null;
  /** Number of inventory items at or below safety stock threshold */
  low_stock_count: number;
  /** Number of pending HITL approval decisions visible to caller */
  open_approvals: number;
  /** Number of quarantined pharmaceutical batches within scope */
  quarantined_batches: number;
  /** Active user and bound node RLS context */
  scope: MobileScope;
}

/** Represents a specific version of a dynamic business rule or adapter module. */
export interface ModuleVersion {
  checksum?: string | null;
  created_at?: string;
  created_by?: string;
  id?: string;
  /** Category of rule or adapter */
  kind: string;
  /** Unique module identifier, e.g. margin_rules */
  name: string;
  /** Executable Python code adhering to def run(input: dict) -> dict */
  source_code: string;
  /** staging, active, or retired */
  status?: "staging" | "active" | "retired";
  /** Executable verification code def test_run() or test assertions */
  tests_source: string;
  /** Sequential integer version */
  version?: number;
}

/** Pharma supply chain node representation. */
export interface NodeResponse {
  address?: string | null;
  created_at?: string;
  id: string;
  is_active?: boolean;
  name: string;
  parent_id?: string | null;
  region: string;
  tier: string;
}

export interface NormalizedEvent {
  /** Display name of emitting agent */
  agent_name: string;
  /** Supply cascade correlation ID */
  correlation_id: string;
  /** Event generation ISO timestamp */
  created_at: string;
  /** Canonical event UUID */
  event_id: string;
  /** Domain event type / topic */
  event_type: string;
  /** Unique event identifier */
  id: string;
  /** Originating node ID */
  node_id?: string | null;
  /** Originating node display name */
  node_name?: string | null;
  /** Detailed domain event payload */
  payload?: Record<string, unknown>;
  /** One-line operational description */
  summary: string;
  /** Supply chain tier of event origin */
  tier: string;
  /** Event bus topic */
  topic: string;
}

export interface OverviewKpisResponse {
  active_batches?: number;
  events_today: number;
  inventory_records?: number;
  open_approvals: number;
  quarantined_batches: number;
  stockout_risks: number;
  total_events: number;
  total_nodes?: number;
  total_products?: number;
}

export interface PaginatedResponse_InventoryItemResponse_ {
  has_more?: boolean;
  items: InventoryItemResponse[];
  next_cursor?: string | null;
  total_count?: number | null;
}

export interface PaginatedResponse_NodeResponse_ {
  has_more?: boolean;
  items: NodeResponse[];
  next_cursor?: string | null;
  total_count?: number | null;
}

export interface PaginatedResponse_ProductResponse_ {
  has_more?: boolean;
  items: ProductResponse[];
  next_cursor?: string | null;
  total_count?: number | null;
}

export interface PosTriggerRequest {
  mode?: "single" | "steady" | "burst" | "stockout";
  node_id?: string | null;
  pharmacy_id?: string | null;
  product_id?: string | null;
  quantity?: number;
}

export interface PosTriggerResponse {
  cascade: Record<string, unknown>;
  correlation_id: string;
  events_created: number;
  mode: string;
  status?: string;
}

/** Payload to test live pricing calculation against active pricing module. */
export interface PriceCheckRequest {
  /** Optional drug name */
  drug_name?: string | null;
  /** Module kind */
  module_kind?: string | null;
  /** Arbitrary extra fields */
  payload?: Record<string, unknown> | null;
  /** Quantity */
  quantity?: number;
  /** Product SKU */
  sku?: string;
  /** Base unit price before regulatory cap */
  unit_price?: number;
}

export interface ProductBarcodeLookupResponse {
  barcode: string;
  batches?: ProductBatchDetail[];
  generic_name: string;
  id: string;
  is_cold_chain: boolean;
  is_lifesaving: boolean;
  name: string;
  requires_prescription: boolean;
  schedule_class: string;
  sku: string;
  storage_max_c?: number | null;
  storage_min_c?: number | null;
  unit_price: number;
}

export interface ProductBatchDetail {
  available_quantity: number;
  batch_id: string;
  batch_no: string;
  batch_number: string;
  days_to_expiry: number;
  expiry_date: string;
  is_near_expiry?: boolean;
  is_quarantined?: boolean;
  node_id?: string | null;
  quarantine_reason?: string | null;
  reserved_quantity?: number;
  safety_stock?: number;
  status?: string;
}

/** Pharmaceutical product catalog item. */
export interface ProductResponse {
  barcode?: string | null;
  created_at?: string;
  generic_name: string;
  id: string;
  is_cold_chain?: boolean;
  is_lifesaving?: boolean;
  name: string;
  price_per_unit: number;
  schedule_class?: string;
  sku?: string | null;
  storage_max_c?: number | null;
  storage_min_c?: number | null;
  unit?: string;
}

export interface RecentEventsResponse {
  /** Number of events returned */
  count: number;
  /** List of chronologically ordered recent events */
  events: NormalizedEvent[];
  /** Latest event ID cursor for subsequent queries */
  latest_event_id?: string | null;
  /** Server ISO timestamp at query evaluation */
  server_ts: string;
}

export interface RefreshRequest {
  refresh_token?: string | null;
  token?: string | null;
}

export interface RefreshResponse {
  access_token: string;
  expires_in?: number;
  refresh_token?: string | null;
  token_type?: string;
}

/** Payload to revert an adapter to a prior version. */
export interface RollbackAdapterRequest {
  /** Specific target version to restore */
  target_version?: number | null;
}

/** Point-of-Sale dispense event for instantaneous single-unit propagation. */
export interface SaleEvent {
  /** Dispensed pharmaceutical batch ID */
  batch_id: string;
  event_id?: string;
  /** ID of the dispensing pharmacy node */
  pharmacy_id: string;
  /** Master catalog product ID */
  product_id: string;
  /** Quantity dispensed in units / strips */
  quantity?: number;
  /** Event source identifier */
  source?: string;
  timestamp?: string;
}

/** Cold-chain IoT telemetry event for temperature, humidity, and shock tracking. */
export interface SensorReadingEvent {
  /** Cold-chain pharmaceutical batch ID */
  batch_id?: string;
  correlation_id?: string;
  /** Duration interval in minutes */
  duration_minutes?: number;
  event_id?: string;
  /** Relative humidity percentage */
  humidity?: number;
  /** Simulation mode: normal, excursion, shock */
  mode?: string;
  /** Node or vehicle holding the sensor */
  node_id?: string | null;
  /** Master catalog product ID */
  product_id?: string | null;
  /** Physical or virtual IoT sensor identifier */
  sensor_id?: string;
  /** Active transit shipment ID */
  shipment_id?: string | null;
  /** Physical acceleration / shock impact in Gs */
  shock_g?: number;
  /** Backward-compatible temperature field */
  temperature?: number | null;
  /** Current temperature in Celsius */
  temperature_c?: number;
  timestamp?: string;
  /** Timestamp string */
  ts?: string | null;
}

/** Payload to trigger a background POS traffic simulation. */
export interface SimulationRunRequest {
  /** Simulation duration in seconds */
  duration_seconds?: number;
  /** Total sales for burst mode */
  intensity?: number;
  mode?: "single" | "steady" | "burst" | "stockout_run";
  /** Sales per second for steady mode */
  rate?: number;
  /** Optional geographic region filter */
  region?: string | null;
  /** Optional target pharmacy UUID */
  target_node_id?: string | null;
  /** Optional target product UUID */
  target_product_id?: string | null;
}

export interface SimulationRunResponse {
  mode: string;
  simulation_id: string;
  status: string;
}

export interface SimulationStatusResponse {
  errors_count?: number;
  events_sent?: number;
  last_event_time?: string | null;
  mode?: string | null;
  rate?: number | null;
  simulation_id?: string | null;
  status: string;
  target_node_id?: string | null;
  target_product_id?: string | null;
}

/** Schema for manually triggering a signed test webhook delivery. */
export interface TestWebhookRequest {
  /** Payload data */
  data?: Record<string, unknown>;
  /** Event type to simulate */
  event_type?: string;
  /** Subscription ID to test */
  subscription_id?: string | null;
}

export interface ValidationError {
  ctx?: Record<string, unknown>;
  input?: unknown;
  loc: (string | number)[];
  msg: string;
  type: string;
}

// ============================================================================
// 2. Typed API Endpoint Registry & Operation Definitions
// ============================================================================

export interface ApiOperations {
  /** List Registered Adapters */
  'GET /api/v1/adapters': {
    operationId: 'get__api_v1_adapters';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Get Pre-packaged Legacy Format Fixtures for Quick 1-Click Synthesis */
  'GET /api/v1/adapters/fixtures': {
    operationId: 'get__api_v1_adapters_fixtures';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Trigger Autonomous Adapter Generation Workflow */
  'POST /api/v1/adapters/generate': {
    operationId: 'post__api_v1_adapters_generate';
    parameters: { "X-API-Key"?: string | null };
    requestBody: GenerateAdapterRequest;
    response: Record<string, unknown>;
  };
  /** Get Forge Job Status or SSE Stream */
  'GET /api/v1/adapters/jobs/{job_id}': {
    operationId: 'get__api_v1_adapters_jobs__job_id_';
    parameters: { job_id: string };
    requestBody: undefined;
    response: unknown;
  };
  /** Real-Time Forge SSE Progress Stream */
  'GET /api/v1/adapters/jobs/{job_id}/stream': {
    operationId: 'get__api_v1_adapters_jobs__job_id__stream';
    parameters: { job_id: string };
    requestBody: undefined;
    response: unknown;
  };
  /** Get Adapter Details and Version History */
  'GET /api/v1/adapters/{identifier}': {
    operationId: 'get__api_v1_adapters__identifier_';
    parameters: { identifier: string; version?: number | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Rollback Adapter to Prior Stable Version */
  'POST /api/v1/adapters/{identifier}/rollback': {
    operationId: 'post__api_v1_adapters__identifier__rollback';
    parameters: { identifier: string };
    requestBody: RollbackAdapterRequest | null;
    response: Record<string, unknown>;
  };
  /** List Agent Execution Runs Alias */
  'GET /api/v1/agents': {
    operationId: 'get__api_v1_agents';
    parameters: { graph?: string | null; agent?: string | null; agent_name?: string | null; status?: string | null; correlation_id?: string | null; limit?: number; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Get Aggregated Agent Telemetry Metrics */
  'GET /api/v1/agents/metrics': {
    operationId: 'get__api_v1_agents_metrics';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: AgentMetricsResponse;
  };
  /** List AI Agent Execution Traces */
  'GET /api/v1/agents/runs': {
    operationId: 'get__api_v1_agents_runs';
    parameters: { graph?: string | null; agent?: string | null; agent_name?: string | null; status?: string | null; correlation_id?: string | null; limit?: number; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Query and Filter Audit Ledger Entries */
  'GET /api/v1/audit': {
    operationId: 'get__api_v1_audit';
    parameters: { entity_type?: string | null; entity_id?: string | null; actor?: string | null; action?: string | null; node_id?: string | null; correlation_id?: string | null; search?: string | null; start_date?: string | null; end_date?: string | null; limit?: number; offset?: number; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Query and Filter Audit Ledger Entries Alias */
  'GET /api/v1/audit/ledger': {
    operationId: 'get__api_v1_audit_ledger';
    parameters: { entity_type?: string | null; entity_id?: string | null; actor?: string | null; action?: string | null; node_id?: string | null; correlation_id?: string | null; search?: string | null; start_date?: string | null; end_date?: string | null; limit?: number; offset?: number; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Verify Audit Hash Chain Integrity (GET) */
  'GET /api/v1/audit/verify': {
    operationId: 'get__api_v1_audit_verify';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Verify Audit Hash Chain Integrity (POST) */
  'POST /api/v1/audit/verify': {
    operationId: 'post__api_v1_audit_verify';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** List Seeded Demo Users Across All 7 Supply Chain Roles */
  'GET /api/v1/auth/demo-users': {
    operationId: 'get__api_v1_auth_demo_users';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Authenticate User or Demo Role */
  'POST /api/v1/auth/login': {
    operationId: 'post__api_v1_auth_login';
    parameters: undefined;
    requestBody: LoginRequest;
    response: LoginResponse;
  };
  /** Get Enriched Profile for Authenticated User */
  'GET /api/v1/auth/me': {
    operationId: 'get__api_v1_auth_me';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: EnrichedUserProfile;
  };
  /** Refresh Session Access Token */
  'POST /api/v1/auth/refresh': {
    operationId: 'post__api_v1_auth_refresh';
    parameters: undefined;
    requestBody: RefreshRequest;
    response: RefreshResponse;
  };
  /** List Recent Cascade Runs */
  'GET /api/v1/cascade': {
    operationId: 'get__api_v1_cascade';
    parameters: { limit?: number; outcome?: string | null; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: CascadeSummaryItem[];
  };
  /** Trigger Demand Cascade Alias */
  'POST /api/v1/cascade/trigger': {
    operationId: 'post__api_v1_cascade_trigger';
    parameters: undefined;
    requestBody: PosTriggerRequest;
    response: PosTriggerResponse;
  };
  /** Get Full 4-Tier Cascade Execution Trace */
  'GET /api/v1/cascade/{correlation_id}': {
    operationId: 'get__api_v1_cascade__correlation_id_';
    parameters: { correlation_id: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: CascadeFullTrace;
  };
  /** List Cold-Chain Batches with Telemetry & Shelf-Life Estimates */
  'GET /api/v1/coldchain/batches': {
    operationId: 'get__api_v1_coldchain_batches';
    parameters: undefined;
    requestBody: undefined;
    response: unknown;
  };
  /** Get Cold-Chain Batch Details & Telemetry */
  'GET /api/v1/coldchain/batches/{batch_id}': {
    operationId: 'get__api_v1_coldchain_batches__batch_id_';
    parameters: { batch_id: string };
    requestBody: undefined;
    response: unknown;
  };
  /** List Cold-Chain Quarantine Actions */
  'GET /api/v1/coldchain/quarantines': {
    operationId: 'get__api_v1_coldchain_quarantines';
    parameters: undefined;
    requestBody: undefined;
    response: unknown;
  };
  /** Direct Cold-Chain Sensor Telemetry Ingestion */
  'POST /api/v1/coldchain/sensor': {
    operationId: 'post__api_v1_coldchain_sensor';
    parameters: { "X-Correlation-ID"?: string | null };
    requestBody: SensorReadingEvent | Record<string, unknown>;
    response: unknown;
  };
  /** Simulate IoT Cold-Chain Telemetry (Normal, Thermal Excursion, Mechanical Shock) */
  'POST /api/v1/coldchain/simulate': {
    operationId: 'post__api_v1_coldchain_simulate';
    parameters: { "X-Correlation-ID"?: string | null };
    requestBody: ColdChainSimulateRequest;
    response: unknown;
  };
  /** Get Compliance Logs */
  'GET /api/v1/compliance/logs': {
    operationId: 'get__api_v1_compliance_logs';
    parameters: { prescription_id?: string | null; action?: string | null; node_id?: string | null; limit?: number };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Query Network Copilot */
  'POST /api/v1/copilot/query': {
    operationId: 'post__api_v1_copilot_query';
    parameters: { "X-User-Role"?: string | null; "X-Node-Id"?: string | null; "X-User-Region"?: string | null; "X-User-Id"?: string | null; "X-Correlation-ID"?: string | null; "X-API-Key"?: string | null };
    requestBody: CopilotQueryRequest;
    response: CopilotQueryResponse;
  };
  /** Reset Demo State to Clean Baseline */
  'POST /api/v1/demo/reset': {
    operationId: 'post__api_v1_demo_reset';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Get Demo & Cache Runtime Status */
  'GET /api/v1/demo/status': {
    operationId: 'get__api_v1_demo_status';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** List Developer API Keys */
  'GET /api/v1/developer/keys': {
    operationId: 'get__api_v1_developer_keys';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Provision Scoped Developer API Key */
  'POST /api/v1/developer/keys': {
    operationId: 'post__api_v1_developer_keys';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: CreateApiKeyRequest;
    response: ApiKeyCreatedResponse;
  };
  /** Revoke Developer API Key */
  'DELETE /api/v1/developer/keys/{key_id}': {
    operationId: 'delete__api_v1_developer_keys__key_id_';
    parameters: { key_id: string };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** List Webhook Subscriptions */
  'GET /api/v1/developer/webhooks': {
    operationId: 'get__api_v1_developer_webhooks';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Register Webhook Subscription */
  'POST /api/v1/developer/webhooks': {
    operationId: 'post__api_v1_developer_webhooks';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: CreateWebhookRequest;
    response: Record<string, unknown>;
  };
  /** List Webhook Deliveries */
  'GET /api/v1/developer/webhooks/deliveries': {
    operationId: 'get__api_v1_developer_webhooks_deliveries';
    parameters: { limit?: number };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Test Webhook Delivery (General) */
  'POST /api/v1/developer/webhooks/test': {
    operationId: 'post__api_v1_developer_webhooks_test';
    parameters: undefined;
    requestBody: TestWebhookRequest;
    response: Record<string, unknown>;
  };
  /** Deactivate Webhook Subscription */
  'DELETE /api/v1/developer/webhooks/{subscription_id}': {
    operationId: 'delete__api_v1_developer_webhooks__subscription_id_';
    parameters: { subscription_id: string };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** List Deliveries for Subscription */
  'GET /api/v1/developer/webhooks/{subscription_id}/deliveries': {
    operationId: 'get__api_v1_developer_webhooks__subscription_id__deliveries';
    parameters: { subscription_id: string; limit?: number };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Test Webhook Delivery */
  'POST /api/v1/developer/webhooks/{subscription_id}/test': {
    operationId: 'post__api_v1_developer_webhooks__subscription_id__test';
    parameters: { subscription_id: string };
    requestBody: TestWebhookRequest | null;
    response: Record<string, unknown>;
  };
  /** List Registered Device Tokens */
  'GET /api/v1/devices': {
    operationId: 'get__api_v1_devices';
    parameters: { all?: boolean; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: unknown;
  };
  /** Register Device Push Token */
  'POST /api/v1/devices': {
    operationId: 'post__api_v1_devices';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: DeviceTokenRegisterRequest;
    response: Record<string, unknown>;
  };
  /** Delete Device Push Token */
  'DELETE /api/v1/devices/{token}': {
    operationId: 'delete__api_v1_devices__token_';
    parameters: { token: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: unknown;
  };
  /** List Recent Domain Events */
  'GET /api/v1/events': {
    operationId: 'get__api_v1_events';
    parameters: { topic?: string | null; limit?: number };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Canonical Event Ingestion */
  'POST /api/v1/events': {
    operationId: 'post__api_v1_events';
    parameters: { "X-Correlation-ID"?: string | null; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: Record<string, unknown>;
    response: unknown;
  };
  /** Point-of-Sale Event Ingestion Alias */
  'POST /api/v1/events/pos': {
    operationId: 'post__api_v1_events_pos';
    parameters: { "X-Correlation-ID"?: string | null; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: MobileSaleRequest;
    response: MobileSaleResponse;
  };
  /** Get Recent Normalized Events (Mobile & Polling Fallback) */
  'GET /api/v1/events/recent': {
    operationId: 'get__api_v1_events_recent';
    parameters: { since?: string | null; topics?: string | null; limit?: number; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: RecentEventsResponse;
  };
  /** Ingest Point-of-Sale Dispense Event */
  'POST /api/v1/events/sale': {
    operationId: 'post__api_v1_events_sale';
    parameters: { "X-Correlation-ID"?: string | null; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: MobileSaleRequest;
    response: MobileSaleResponse;
  };
  /** Batch Ingest Point-of-Sale Dispense Events */
  'POST /api/v1/events/sale/batch': {
    operationId: 'post__api_v1_events_sale_batch';
    parameters: { "X-Correlation-ID"?: string | null };
    requestBody: SaleEvent[];
    response: unknown;
  };
  /** Ingest IoT Sensor Telemetry Reading */
  'POST /api/v1/events/sensor': {
    operationId: 'post__api_v1_events_sensor';
    parameters: { "X-Correlation-ID"?: string | null; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: SensorReadingEvent | SensorReadingEvent[] | Record<string, unknown> | Record<string, unknown>[];
    response: unknown;
  };
  /** List HITL Tasks Alias */
  'GET /api/v1/hitl': {
    operationId: 'get__api_v1_hitl';
    parameters: { status?: string | null; task_type?: string | null; risk_level?: string | null; limit?: number; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Get Configured HITL Policies */
  'GET /api/v1/hitl/policies': {
    operationId: 'get__api_v1_hitl_policies';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: HITLPoliciesResponse;
  };
  /** List HITL Tasks */
  'GET /api/v1/hitl/tasks': {
    operationId: 'get__api_v1_hitl_tasks';
    parameters: { status?: string | null; task_type?: string | null; risk_level?: string | null; limit?: number; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Simulate Trigger of a HITL Task (Tasks Alias) */
  'POST /api/v1/hitl/tasks/trigger': {
    operationId: 'post__api_v1_hitl_tasks_trigger';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: HITLTriggerRequest;
    response: Record<string, unknown>;
  };
  /** Get HITL Task Details */
  'GET /api/v1/hitl/tasks/{task_id}': {
    operationId: 'get__api_v1_hitl_tasks__task_id_';
    parameters: { task_id: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Submit Human Approval or Rejection Decision (Tasks Prefix) */
  'POST /api/v1/hitl/tasks/{task_id}/decide': {
    operationId: 'post__api_v1_hitl_tasks__task_id__decide';
    parameters: { task_id: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: HITLDecisionRequest;
    response: HITLDecisionResponse;
  };
  /** Submit Human Approval or Rejection Decision Legacy Alias */
  'POST /api/v1/hitl/tasks/{task_id}/decision': {
    operationId: 'post__api_v1_hitl_tasks__task_id__decision';
    parameters: { task_id: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: HITLDecisionRequest;
    response: HITLDecisionResponse;
  };
  /** Simulate Trigger of a HITL Task */
  'POST /api/v1/hitl/trigger': {
    operationId: 'post__api_v1_hitl_trigger';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: HITLTriggerRequest;
    response: Record<string, unknown>;
  };
  /** Submit Human Approval or Rejection Decision */
  'POST /api/v1/hitl/{task_id}/decide': {
    operationId: 'post__api_v1_hitl__task_id__decide';
    parameters: { task_id: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: HITLDecisionRequest;
    response: HITLDecisionResponse;
  };
  /** Submit Human Approval or Rejection Decision (Decision Alias) */
  'POST /api/v1/hitl/{task_id}/decision': {
    operationId: 'post__api_v1_hitl__task_id__decision';
    parameters: { task_id: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: HITLDecisionRequest;
    response: HITLDecisionResponse;
  };
  /** Ingest Legacy Format Payload via Active Adapter */
  'POST /api/v1/ingest/{adapter_id}': {
    operationId: 'post__api_v1_ingest__adapter_id_';
    parameters: { adapter_id: string; "X-Correlation-ID"?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: unknown;
  };
  /** List Scoped Inventory */
  'GET /api/v1/inventory': {
    operationId: 'get__api_v1_inventory';
    parameters: { product_id?: string | null; limit?: number; cursor?: string | null; jwt_token?: string | null; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: undefined;
    response: PaginatedResponse_InventoryItemResponse_;
  };
  /** Execute MCP Tool Call */
  'POST /api/v1/mcp/call': {
    operationId: 'post__api_v1_mcp_call';
    parameters: { "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: MCPToolCallRequest;
    response: MCPToolCallResponse;
  };
  /** JSON-RPC 2.0 MCP Protocol Handler */
  'POST /api/v1/mcp/rpc': {
    operationId: 'post__api_v1_mcp_rpc';
    parameters: { "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: JSONRPCRequest;
    response: Record<string, unknown>;
  };
  /** MCP Server-Sent Events Transport */
  'GET /api/v1/mcp/sse': {
    operationId: 'get__api_v1_mcp_sse';
    parameters: undefined;
    requestBody: undefined;
    response: unknown;
  };
  /** List Registered MCP Tools */
  'GET /api/v1/mcp/tools': {
    operationId: 'get__api_v1_mcp_tools';
    parameters: undefined;
    requestBody: undefined;
    response: MCPToolsListResponse;
  };
  /** Get Current User Profile (Alias) */
  'GET /api/v1/me': {
    operationId: 'get__api_v1_me';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: EnrichedUserProfile;
  };
  /** Get Mobile Operational Summary KPIs */
  'GET /api/v1/mobile/summary': {
    operationId: 'get__api_v1_mobile_summary';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: MobileSummaryResponse;
  };
  /** List Active Modules */
  'GET /api/v1/modules': {
    operationId: 'get__api_v1_modules';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: ModuleVersion[];
  };
  /** Rollback Module Version */
  'POST /api/v1/modules/{name}/rollback': {
    operationId: 'post__api_v1_modules__name__rollback';
    parameters: { name: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: ModuleVersion;
  };
  /** List Module Version History */
  'GET /api/v1/modules/{name}/versions': {
    operationId: 'get__api_v1_modules__name__versions';
    parameters: { name: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: ModuleVersion[];
  };
  /** List Visible Network Nodes */
  'GET /api/v1/nodes': {
    operationId: 'get__api_v1_nodes';
    parameters: { limit?: number; cursor?: string | null; jwt_token?: string | null; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: PaginatedResponse_NodeResponse_;
  };
  /** Get Live Network Operational KPIs */
  'GET /api/v1/overview/kpis': {
    operationId: 'get__api_v1_overview_kpis';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: OverviewKpisResponse;
  };
  /** List Prescriptions Endpoint */
  'GET /api/v1/prescriptions': {
    operationId: 'get__api_v1_prescriptions';
    parameters: { node_id?: string | null; limit?: number; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Upload Prescription */
  'POST /api/v1/prescriptions': {
    operationId: 'post__api_v1_prescriptions';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Get Prescription Fixtures */
  'GET /api/v1/prescriptions/fixtures': {
    operationId: 'get__api_v1_prescriptions_fixtures';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Get Prescription By Id */
  'GET /api/v1/prescriptions/{prescription_id}': {
    operationId: 'get__api_v1_prescriptions__prescription_id_';
    parameters: { prescription_id: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** List Products */
  'GET /api/v1/products': {
    operationId: 'get__api_v1_products';
    parameters: { search?: string | null; q?: string | null; schedule_class?: string | null; is_cold_chain?: boolean | null; limit?: number; cursor?: string | null };
    requestBody: undefined;
    response: PaginatedResponse_ProductResponse_;
  };
  /** Lookup Product by Barcode or SKU */
  'GET /api/v1/products/by-barcode/{code}': {
    operationId: 'get__api_v1_products_by_barcode__code_';
    parameters: { code: string; authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: ProductBarcodeLookupResponse;
  };
  /** Trigger Manual Regulatory Crawl Across Configured Sources */
  'POST /api/v1/regulatory/check-now': {
    operationId: 'post__api_v1_regulatory_check_now';
    parameters: { use_fixtures?: boolean };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Get Pre-packaged Synthetic Regulatory Directives */
  'GET /api/v1/regulatory/fixtures': {
    operationId: 'get__api_v1_regulatory_fixtures';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** List Ingested Regulatory Notifications */
  'GET /api/v1/regulatory/notifications': {
    operationId: 'get__api_v1_regulatory_notifications';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Ingest Regulatory Notice and Execute Analysis Pipeline */
  'POST /api/v1/regulatory/notifications': {
    operationId: 'post__api_v1_regulatory_notifications';
    parameters: undefined;
    requestBody: IngestNoticeRequest;
    response: Record<string, unknown>;
  };
  /** Execute Live Pricing Calculation via Active Module */
  'POST /api/v1/regulatory/price-check': {
    operationId: 'post__api_v1_regulatory_price_check';
    parameters: undefined;
    requestBody: PriceCheckRequest;
    response: Record<string, unknown>;
  };
  /** List Regulatory Pipeline Runs */
  'GET /api/v1/regulatory/runs': {
    operationId: 'get__api_v1_regulatory_runs';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Get Regulatory Pipeline Run Details */
  'GET /api/v1/regulatory/runs/{run_id}': {
    operationId: 'get__api_v1_regulatory_runs__run_id_';
    parameters: { run_id: string };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Approve Staged Regulatory Update and Trigger Hot-Swap */
  'POST /api/v1/regulatory/runs/{run_id}/approve': {
    operationId: 'post__api_v1_regulatory_runs__run_id__approve';
    parameters: { run_id: string; approver?: string };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Rollback Deployed Regulatory Module */
  'POST /api/v1/regulatory/runs/{run_id}/rollback': {
    operationId: 'post__api_v1_regulatory_runs__run_id__rollback';
    parameters: { run_id: string; actor?: string };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Semantic Vector Search Across Network Knowledge */
  'GET /api/v1/search': {
    operationId: 'get__api_v1_search';
    parameters: { q: string; types?: string | null; limit?: number; "X-User-Role"?: string | null; "X-Node-Id"?: string | null; "X-User-Region"?: string | null; "X-User-Id"?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: unknown;
  };
  /** Trigger POS Retail Dispense & 4-Tier Demand Cascade */
  'POST /api/v1/simulator/pos': {
    operationId: 'post__api_v1_simulator_pos';
    parameters: undefined;
    requestBody: PosTriggerRequest;
    response: PosTriggerResponse;
  };
  /** Start background POS simulation */
  'POST /api/v1/simulator/run': {
    operationId: 'post__api_v1_simulator_run';
    parameters: undefined;
    requestBody: SimulationRunRequest;
    response: SimulationRunResponse;
  };
  /** Get active POS simulation status */
  'GET /api/v1/simulator/status': {
    operationId: 'get__api_v1_simulator_status';
    parameters: undefined;
    requestBody: undefined;
    response: SimulationStatusResponse;
  };
  /** Stop active POS simulation */
  'POST /api/v1/simulator/stop': {
    operationId: 'post__api_v1_simulator_stop';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Get Api V1 Status */
  'GET /api/v1/status': {
    operationId: 'get__api_v1_status';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Real-Time Server-Sent Events (SSE) Stream */
  'GET /api/v1/stream': {
    operationId: 'get__api_v1_stream';
    parameters: { topics?: string; last_event_id?: string | null; named_events?: boolean; "Last-Event-ID"?: string | null; "X-API-Key"?: string | null; authorization?: string | null };
    requestBody: undefined;
    response: unknown;
  };
  /** Get Webhooks */
  'GET /api/v1/webhooks': {
    operationId: 'get__api_v1_webhooks';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Register Webhook */
  'POST /api/v1/webhooks': {
    operationId: 'post__api_v1_webhooks';
    parameters: { authorization?: string | null; "X-API-Key"?: string | null };
    requestBody: CreateWebhookRequest;
    response: Record<string, unknown>;
  };
  /** Get Deliveries */
  'GET /api/v1/webhooks/deliveries': {
    operationId: 'get__api_v1_webhooks_deliveries';
    parameters: { limit?: number };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Test Webhook General */
  'POST /api/v1/webhooks/test': {
    operationId: 'post__api_v1_webhooks_test';
    parameters: undefined;
    requestBody: TestWebhookRequest;
    response: Record<string, unknown>;
  };
  /** Deactivate Webhook */
  'DELETE /api/v1/webhooks/{subscription_id}': {
    operationId: 'delete__api_v1_webhooks__subscription_id_';
    parameters: { subscription_id: string };
    requestBody: undefined;
    response: Record<string, unknown>;
  };
  /** Get Subscription Deliveries */
  'GET /api/v1/webhooks/{subscription_id}/deliveries': {
    operationId: 'get__api_v1_webhooks__subscription_id__deliveries';
    parameters: { subscription_id: string; limit?: number };
    requestBody: undefined;
    response: Record<string, unknown>[];
  };
  /** Test Webhook By Id */
  'POST /api/v1/webhooks/{subscription_id}/test': {
    operationId: 'post__api_v1_webhooks__subscription_id__test';
    parameters: { subscription_id: string };
    requestBody: TestWebhookRequest | null;
    response: Record<string, unknown>;
  };
  /** Liveness & Readiness Health Probe */
  'GET /health': {
    operationId: 'get__health';
    parameters: undefined;
    requestBody: undefined;
    response: Record<string, unknown>;
  };
}

// ============================================================================
// 3. Typed API Client Contract
// ============================================================================

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

export interface ApiClientContract {
  get<T = unknown>(path: string, params?: Record<string, unknown>): Promise<T>;
  post<T = unknown>(path: string, body?: unknown, params?: Record<string, unknown>): Promise<T>;
  put<T = unknown>(path: string, body?: unknown): Promise<T>;
  delete<T = unknown>(path: string, params?: Record<string, unknown>): Promise<T>;
  uploadMultipart<T = unknown>(path: string, formData: any, onProgress?: (pct: number) => void): Promise<T>;
}
