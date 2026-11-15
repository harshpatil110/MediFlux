/**
 * Formatting helpers for currency, dates, and domain values.
 */

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(dateStr: string | Date | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return String(dateStr);
  }
}

export function formatDateTime(dateStr: string | Date | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(dateStr);
  }
}

export function formatRoleName(role: string): string {
  const map: Record<string, string> = {
    pharmacy: 'Retail Pharmacy',
    stockist: 'Stockist Hub',
    distributor: 'Regional Distributor',
    manufacturer: 'Pharma Plant',
    regulator: 'CDSCO Regulator',
    developer: 'Platform Developer',
    admin: 'Network Admin',
  };
  return map[role.toLowerCase()] || role;
}

export function formatTierName(tier: string): string {
  const map: Record<string, string> = {
    pharmacy: 'Tier 1: Retail Pharmacy Node',
    stockist: 'Tier 2: Stockist Transit Hub',
    distributor: 'Tier 3: Regional Distributor Layer',
    manufacturer: 'Tier 4: Manufacturer Formulation Plant',
  };
  return map[tier.toLowerCase()] || tier;
}
