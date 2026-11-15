/**
 * MediFlux / NexusChain Core Domain Models and DTOs.
 */

import { DrugSchedule, HitlStatus, SupplyTier, UserRole } from './enums';

export interface NodeEntity {
  id: string;
  name: string;
  tier: SupplyTier | string;
  type: string;
  address?: string;
  city?: string;
  state?: string;
  pincode?: string;
  license_number?: string;
  latitude?: number;
  longitude?: number;
  is_active: boolean;
  parent_node_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ProductEntity {
  id: string;
  name: string;
  sku: string;
  generic_name: string;
  dosage_form: string;
  schedule_type: DrugSchedule | string;
  unit_price: number;
  storage_condition: string;
  is_cold_chain: boolean;
  min_temperature?: number | null;
  max_temperature?: number | null;
  manufacturer_node_id?: string;
  created_at?: string;
}

export interface InventoryRecord {
  id: string;
  node_id: string;
  product_id: string;
  batch_id?: string | null;
  available_quantity: number;
  reserved_quantity: number;
  reorder_point: number;
  safe_stock_level: number;
  product?: ProductEntity;
  node?: NodeEntity;
  updated_at?: string;
}

export interface ColdChainBatch {
  batch_id: string;
  product_id: string;
  product_name: string;
  current_temp: number;
  min_temp: number;
  max_temp: number;
  status: 'active' | 'warning' | 'quarantined';
  shelf_life_hours: number;
  remaining_viability_pct: number;
  carrier_name?: string;
  sensor_id?: string;
  last_reading_time?: string;
}

export interface HitlTask {
  id: string;
  task_id: string;
  task_type: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  summary: string;
  reasoning?: string;
  status: HitlStatus;
  node_id?: string;
  node_name?: string;
  correlation_id?: string;
  details?: Record<string, unknown>;
  created_at: string;
  expires_at?: string;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_note?: string | null;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  node_id?: string | null;
  node_name?: string | null;
  allowed_routes?: string[];
  is_active: boolean;
}

export interface HealthCheckResponse {
  status: string;
  app: string;
  version: string;
  environment?: string;
  timestamp?: string;
  active_nodes?: number;
  database?: string;
}

