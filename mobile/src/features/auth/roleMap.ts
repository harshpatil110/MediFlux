import { UserRole } from '../../api/generated';

export type TabKey = 'index' | 'sell' | 'approvals' | 'scan-rx' | 'cold-chain' | 'copilot';

export const ALL_TAB_KEYS: readonly TabKey[] = [
  'index',
  'sell',
  'approvals',
  'scan-rx',
  'cold-chain',
  'copilot',
] as const;

export const ROLE_TAB_MATRIX: Record<UserRole, readonly TabKey[]> = {
  pharmacy: ['index', 'sell', 'scan-rx', 'approvals', 'copilot'],
  stockist: ['index', 'approvals', 'cold-chain', 'copilot'],
  distributor: ['index', 'approvals', 'cold-chain', 'copilot'],
  manufacturer: ['index', 'approvals', 'cold-chain', 'copilot'],
  admin: ['index', 'sell', 'approvals', 'scan-rx', 'cold-chain', 'copilot'],
  regulator: ['index', 'approvals', 'cold-chain', 'copilot'],
  developer: ['index', 'approvals', 'cold-chain', 'copilot'],
};

/**
 * Returns the array of allowed tabs for a given role.
 */
export function getAllowedTabsForRole(
  role: UserRole | string | undefined,
  _policyAllowsPharmacyApprovals?: boolean
): TabKey[] {
  if (!role) {
    return ['index'];
  }
  const normalized = role.toLowerCase() as UserRole;
  const allowed = ROLE_TAB_MATRIX[normalized];
  if (allowed) {
    return [...allowed];
  }
  return ['index', 'approvals', 'cold-chain', 'copilot'];
}

/**
 * Checks whether a given tab key is visible for a specific user role.
 */
export function isTabVisibleForRole(
  role: UserRole | string | undefined,
  tab: TabKey,
  policyAllowsPharmacyApprovals?: boolean
): boolean {
  const allowed = getAllowedTabsForRole(role, policyAllowsPharmacyApprovals);
  return allowed.includes(tab);
}

/**
 * Checks whether the role has rights to decide (approve/reject) HITL tasks.
 * true for admin, stockist, distributor, manufacturer, regulator.
 * false (view-only) for pharmacy and developer by default.
 */
export function canRoleDecideApprovals(role: UserRole | string | undefined): boolean {
  if (!role) return false;
  const normalized = role.toLowerCase();
  return ['admin', 'stockist', 'distributor', 'manufacturer', 'regulator'].includes(normalized);
}

/**
 * Display label and color config per role.
 */
export function getRoleBadgeInfo(role: UserRole | string | undefined): {
  label: string;
  badgeBg: string;
  badgeTextColor: string;
  isApprover: boolean;
} {
  const isApprover = canRoleDecideApprovals(role);
  const normalized = (role || 'pharmacy').toLowerCase();

  switch (normalized) {
    case 'admin':
      return { label: 'ADMIN', badgeBg: '#031211', badgeTextColor: '#00AEBB', isApprover: true };
    case 'stockist':
      return { label: 'STOCKIST', badgeBg: '#DFDBCA', badgeTextColor: '#031211', isApprover: true };
    case 'distributor':
      return { label: 'DISTRIBUTOR', badgeBg: '#DFDBCA', badgeTextColor: '#031211', isApprover: true };
    case 'manufacturer':
      return { label: 'MANUFACTURER', badgeBg: '#DFDBCA', badgeTextColor: '#031211', isApprover: true };
    case 'regulator':
      return { label: 'REGULATOR', badgeBg: '#DFDBCA', badgeTextColor: '#031211', isApprover: true };
    case 'pharmacy':
    default:
      return { label: 'PHARMACY', badgeBg: '#E8E4D3', badgeTextColor: '#00AEBB', isApprover: false };
  }
}

