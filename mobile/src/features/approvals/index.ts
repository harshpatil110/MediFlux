/**
 * Approvals Feature Module
 * Human-in-the-Loop field decisions, order overrides, and batch release signatures.
 */

export * from './renderers';

export interface HitlDecisionRequest {
  taskId: string;
  decision: 'approved' | 'rejected' | 'approve' | 'reject';
  note?: string;
  reason?: string;
}
