import {
  getAllowedTabsForRole,
  isTabVisibleForRole,
  canRoleDecideApprovals,
  getRoleBadgeInfo,
} from '../features/auth/roleMap';

describe('Role-Aware Tab Navigation & Authorization Mapping', () => {
  test('pharmacy role sees Home, Sell, Scan Rx, Approvals (view-only), Copilot and NOT Cold Chain', () => {
    const tabs = getAllowedTabsForRole('pharmacy');
    expect(tabs).toContain('index');
    expect(tabs).toContain('sell');
    expect(tabs).toContain('scan-rx');
    expect(tabs).toContain('approvals');
    expect(tabs).toContain('copilot');
    expect(tabs).not.toContain('cold-chain');

    expect(isTabVisibleForRole('pharmacy', 'sell')).toBe(true);
    expect(isTabVisibleForRole('pharmacy', 'scan-rx')).toBe(true);
    expect(isTabVisibleForRole('pharmacy', 'cold-chain')).toBe(false);

    // Pharmacy is view-only for approvals
    expect(canRoleDecideApprovals('pharmacy')).toBe(false);
  });

  test('stockist, distributor, and manufacturer see Home, Approvals, Cold Chain, Copilot and NOT Sell or Scan Rx', () => {
    const midTierRoles = ['stockist', 'distributor', 'manufacturer'] as const;

    for (const role of midTierRoles) {
      const tabs = getAllowedTabsForRole(role);
      expect(tabs).toContain('index');
      expect(tabs).toContain('approvals');
      expect(tabs).toContain('cold-chain');
      expect(tabs).toContain('copilot');
      expect(tabs).not.toContain('sell');
      expect(tabs).not.toContain('scan-rx');

      expect(isTabVisibleForRole(role, 'cold-chain')).toBe(true);
      expect(isTabVisibleForRole(role, 'sell')).toBe(false);
      expect(isTabVisibleForRole(role, 'scan-rx')).toBe(false);

      expect(canRoleDecideApprovals(role)).toBe(true);
    }
  });

  test('admin sees all 6 tabs and has full decision authority', () => {
    const tabs = getAllowedTabsForRole('admin');
    expect(tabs).toEqual(['index', 'sell', 'approvals', 'scan-rx', 'cold-chain', 'copilot']);
    expect(tabs.length).toBe(6);

    expect(isTabVisibleForRole('admin', 'index')).toBe(true);
    expect(isTabVisibleForRole('admin', 'sell')).toBe(true);
    expect(isTabVisibleForRole('admin', 'approvals')).toBe(true);
    expect(isTabVisibleForRole('admin', 'scan-rx')).toBe(true);
    expect(isTabVisibleForRole('admin', 'cold-chain')).toBe(true);
    expect(isTabVisibleForRole('admin', 'copilot')).toBe(true);

    expect(canRoleDecideApprovals('admin')).toBe(true);
  });

  test('regulator and developer roles mapped accurately', () => {
    const regTabs = getAllowedTabsForRole('regulator');
    expect(regTabs).toContain('approvals');
    expect(regTabs).toContain('cold-chain');
    expect(regTabs).not.toContain('sell');
    expect(canRoleDecideApprovals('regulator')).toBe(true);

    const devTabs = getAllowedTabsForRole('developer');
    expect(devTabs).toContain('approvals');
    expect(canRoleDecideApprovals('developer')).toBe(false);
  });

  test('fallback for undefined role returns minimal safe tabs', () => {
    const fallbackTabs = getAllowedTabsForRole(undefined);
    expect(fallbackTabs).toEqual(['index']);
    expect(canRoleDecideApprovals(undefined)).toBe(false);
  });

  test('role badge info formats labels and approval permissions properly', () => {
    const adminBadge = getRoleBadgeInfo('admin');
    expect(adminBadge.label).toBe('ADMIN');
    expect(adminBadge.isApprover).toBe(true);

    const pharmacyBadge = getRoleBadgeInfo('pharmacy');
    expect(pharmacyBadge.label).toBe('PHARMACY');
    expect(pharmacyBadge.isApprover).toBe(false);
  });
});

