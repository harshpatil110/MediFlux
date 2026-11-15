/**
 * MediFlux / NexusChain Core Domain Enums.
 */

export type UserRole =
  | 'pharmacy'
  | 'stockist'
  | 'distributor'
  | 'manufacturer'
  | 'regulator'
  | 'developer'
  | 'admin';

export const USER_ROLES: readonly UserRole[] = [
  'pharmacy',
  'stockist',
  'distributor',
  'manufacturer',
  'regulator',
  'developer',
  'admin',
] as const;

export type SupplyTier =
  | 'manufacturer'
  | 'distributor'
  | 'stockist'
  | 'pharmacy';

export const SUPPLY_TIERS: readonly SupplyTier[] = [
  'manufacturer',
  'distributor',
  'stockist',
  'pharmacy',
] as const;

export type HitlStatus = 'pending' | 'approved' | 'rejected' | 'expired';

export const HITL_STATUSES: readonly HitlStatus[] = [
  'pending',
  'approved',
  'rejected',
  'expired',
] as const;

export type EventType =
  | 'sale'
  | 'order.created'
  | 'shipment.dispatched'
  | 'batch.quarantined'
  | 'hitl.created'
  | 'hitl.decided'
  | 'module.activated'
  | 'agent.activity'
  | 'cascade.updates'
  | 'sensor';

export const EVENT_TYPES: readonly EventType[] = [
  'sale',
  'order.created',
  'shipment.dispatched',
  'batch.quarantined',
  'hitl.created',
  'hitl.decided',
  'module.activated',
  'agent.activity',
  'cascade.updates',
  'sensor',
] as const;

export type DrugSchedule =
  | 'OTC'
  | 'Schedule_H'
  | 'Schedule_H1'
  | 'Schedule_X'
  | 'Narcotic';

export type ColdChainStatus = 'active' | 'warning' | 'quarantined' | 'compromised';
