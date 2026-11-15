/**
 * MediFlux / NexusChain SSE and Real-Time Event Types.
 */

import { HitlStatus } from './enums';

export interface SseEventEnvelope<T = unknown> {
  id?: string;
  event: string;
  topic: string;
  data: T;
  timestamp: string;
  correlation_id?: string;
}

export interface CascadeStepEvent {
  tier: number;
  tier_label: string;
  node_id: string;
  node_name: string;
  agent_name: string;
  state: 'idle' | 'active' | 'completed' | 'failed';
  quantity?: number;
  product_id?: string;
  timestamp: string;
  correlation_id: string;
  decision_snippet?: string;
  token_count?: number;
  model_name?: string;
}

export interface AgentActivityEvent {
  agent_id: string;
  agent_name: string;
  graph: string;
  status: 'started' | 'running' | 'completed' | 'failed' | 'paused';
  latency_ms?: number;
  tokens?: number;
  correlation_id: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export interface ColdChainAlertEvent {
  batch_id: string;
  product_name: string;
  temperature: number;
  min_temp: number;
  max_temp: number;
  status: 'normal' | 'warning' | 'quarantined';
  excursion_duration_min?: number;
  shelf_life_impact_pct?: number;
  timestamp: string;
  node_id?: string;
  location?: string;
}

export interface HitlTaskEvent {
  task_id: string;
  task_type: string;
  title: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  status: HitlStatus;
  node_id?: string;
  node_name?: string;
  timestamp: string;
  correlation_id?: string;
  summary?: string;
  reasoning?: string;
}
