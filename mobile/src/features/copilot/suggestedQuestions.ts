/**
 * Role-aware suggested prompts for MediFlux Network Copilot (Task M8.1).
 */

export function getSuggestedQuestionsForRole(role?: string): string[] {
  const normRole = (role || 'pharmacy').toLowerCase();

  switch (normRole) {
    case 'pharmacy':
      return [
        'Which medicines at my pharmacy are at risk of stockout?',
        'Are there any open compliance approvals or flagged prescriptions for my store?',
        'Show my earliest-expiring batches that should be sold first.',
      ];

    case 'stockist':
    case 'distributor':
    case 'manufacturer':
      return [
        'Which pharmacies in my region are at risk of running out of Paracetamol 500mg?',
        'What is waiting for my approval right now?',
        'Are any cold-chain biologic batches showing thermal warnings or quarantined?',
      ];

    case 'admin':
    case 'regulator':
    default:
      return [
        'Which pharmacies are at risk of running out of Paracetamol 500mg?',
        'What is waiting for my approval across the network?',
        'Summarize quarantined cold-chain batches and recent supply cascades.',
      ];
  }
}
