/**
 * Prescription Data Types & Models (Task M6)
 */

export interface PrescriptionStep {
  stage: 'parsing' | 'schedule_check' | 'doctor_verification' | 'decision' | string;
  status: 'pending' | 'in_progress' | 'done' | 'failed' | 'flagged';
  summary: string;
}

export interface DrugItem {
  name: string;
  dose?: string;
  frequency?: string;
  quantity?: number;
  sku?: string | null;
  product_id?: string | null;
  schedule_class?: 'OTC' | 'H' | 'H1' | 'X' | 'unknown' | string;
  requires_prescription?: boolean;
  lookup_reason?: string;
}

export interface PrescriptionRecord {
  id: string;
  prescription_id: string;
  node_id?: string;
  rx_number?: string;
  status: 'approved' | 'flagged' | 'rejected' | 'pending';
  decision: 'approve_dispense' | 'flag' | 'reject';
  patient_initials: string;
  doctor_name?: string;
  doctor_registration_no?: string | null;
  doctor_verified?: boolean;
  doctor_verification_reason?: string;
  drugs: DrugItem[];
  steps?: PrescriptionStep[];
  compliance_log_id?: string | null;
  compliance_log_ids?: string[];
  hitl_task_id?: string | null;
  sensitivity?: string;
  privacy_notice?: string;
  provider?: string;
  created_at?: string;
  updated_at?: string;
}

export interface FixturePreset {
  id: string;
  filename: string;
  label: string;
  doctor_name: string;
  reg_no: string;
  description: string;
  category: string;
  expected_verdict: string;
  expected_status: string;
  data_uri?: string | null;
}
