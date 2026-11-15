/**
 * Approvals Feature Module
 * Human-in-the-Loop field decisions, order overrides, and batch release signatures.
 */

export interface HitlDecisionRequest {
  taskId: string;
  decision: 'approved' | 'rejected';
  reason?: string;
}

