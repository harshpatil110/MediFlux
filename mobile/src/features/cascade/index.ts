/**
 * Cascade Feature Module
 * Single-unit retail demand propagation across 4 supply chain tiers.
 */

export interface CascadeStep {
  tier: 'pharmacy' | 'stockist' | 'distributor' | 'manufacturer';
  nodeName: string;
  action: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
  timestamp: string;
}
