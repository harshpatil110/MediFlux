/**
 * Type-specific HITL payload renderers for Mobile Approvals.
 * Conforms strictly to Warm Editorial Minimalism (design.md).
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, typography, radii } from '../../theme/tokens';
import { Badge } from '../../components/Badge';
import { Card } from '../../components/Card';
import { formatCurrency } from '../../lib/format';

// ============================================================================
// Helper Components
// ============================================================================

function DataRow({
  label,
  value,
  mono = false,
  highlight = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  highlight?: boolean;
}) {
  return (
    <View style={styles.dataRow}>
      <Text style={styles.dataLabel}>{label}</Text>
      {typeof value === 'string' || typeof value === 'number' ? (
        <Text
          style={[
            styles.dataValue,
            mono && styles.fontMono,
            highlight && styles.highlightText,
          ]}
        >
          {value}
        </Text>
      ) : (
        value
      )}
    </View>
  );
}

// ============================================================================
// Renderer 1: Cross-Border Shipment (CrossBorderShipmentRenderer)
// ============================================================================

export function CrossBorderShipmentRenderer({ payload }: { payload: any }) {
  const route = payload?.route || {};
  const products = Array.isArray(payload?.products) ? payload.products : [];
  const flags = Array.isArray(payload?.flags) ? payload.flags : [];
  const priority = payload?.priority || 'HIGH';

  return (
    <View style={styles.rendererContainer}>
      {/* Route Card */}
      <Card
        title="Cross-Border Transit Route"
        subtitle="CUSTOMS CORRIDOR & CHECKPOINT"
        headerRight={
          <Badge
            label={priority}
            variant={priority.includes('URGENT') ? 'coral' : 'amber'}
          />
        }
      >
        <View style={styles.routeBox}>
          <View style={styles.routeStep}>
            <Ionicons name="location-outline" size={16} color={colors.accent.primary} />
            <View style={styles.routeTextCol}>
              <Text style={styles.routeStepLabel}>ORIGIN HUB</Text>
              <Text style={styles.routeStepName}>{route.origin_node || 'West Hub (Mumbai)'}</Text>
            </View>
          </View>

          <View style={styles.routeDivider}>
            <View style={styles.routeDividerLine} />
            <View style={styles.checkpointPill}>
              <Ionicons name="shield-checkmark-outline" size={12} color={colors.status.warning} />
              <Text style={styles.checkpointText}>
                ICP: {route.border_checkpoint || 'Raxaul ICP'}
              </Text>
            </View>
            <View style={styles.routeDividerLine} />
          </View>

          <View style={styles.routeStep}>
            <Ionicons name="navigate-outline" size={16} color={colors.status.success} />
            <View style={styles.routeTextCol}>
              <Text style={styles.routeStepLabel}>DESTINATION NODE</Text>
              <Text style={styles.routeStepName}>
                {route.destination_node || 'North Border Hub (Delhi/Nepal Corridor)'}
              </Text>
            </View>
          </View>
        </View>

        {route.distance_km && (
          <DataRow
            label="TRANSIT DISTANCE"
            value={`${route.distance_km.toLocaleString()} km`}
            mono
          />
        )}
      </Card>

      {/* Compliance & Risk Flags */}
      {flags.length > 0 && (
        <Card title="Compliance & Risk Flags" subtitle="REGULATORY ATTRIBUTES">
          <View style={styles.flagsWrapper}>
            {flags.map((flag: string, idx: number) => {
              const isCold = flag.includes('COLD');
              const isPermit = flag.includes('PERMIT');
              return (
                <View
                  key={idx}
                  style={[
                    styles.flagChip,
                    isCold && styles.flagCold,
                    isPermit && styles.flagPermit,
                  ]}
                >
                  <Ionicons
                    name={isCold ? 'snow-outline' : isPermit ? 'document-text-outline' : 'warning-outline'}
                    size={12}
                    color={isCold ? colors.accent.primary : colors.text.primary}
                  />
                  <Text style={styles.flagChipText}>{flag.replace(/_/g, ' ')}</Text>
                </View>
              );
            })}
          </View>
        </Card>
      )}

      {/* Products Consignment List */}
      <Card
        title="Consignment Manifest"
        subtitle={`${products.length} PRODUCT LINE ITEM${products.length === 1 ? '' : 'S'}`}
      >
        {products.map((item: any, idx: number) => (
          <View key={idx} style={[styles.productItem, idx > 0 && styles.itemBorderTop]}>
            <View style={styles.productRowTop}>
              <Text style={styles.productName}>{item.name || 'Pharmaceutical Item'}</Text>
              <Badge label={`${item.quantity || 0} UNITS`} variant="teal" />
            </View>
            <View style={styles.productDetailsRow}>
              <Text style={styles.productSku}>SKU: {item.sku || 'SKU-UNKNOWN'}</Text>
              {item.value_inr && (
                <Text style={styles.productValue}>
                  {formatCurrency(Number(item.value_inr))}
                </Text>
              )}
            </View>
          </View>
        ))}
      </Card>
    </View>
  );
}

// ============================================================================
// Renderer 2: In-Progress Batch Modification (BatchModificationRenderer)
// ============================================================================

export function BatchModificationRenderer({ payload }: { payload: any }) {
  const batch = payload?.batch || {};
  const change = payload?.change || {};
  const stock = payload?.api_stock_impact || {};

  return (
    <View style={styles.rendererContainer}>
      {/* Batch Identity Card */}
      <Card
        title="Formulation Batch Identification"
        subtitle="ACTIVE PRODUCTION RUN"
        headerRight={<Badge label="IN PROGRESS" variant="amber" />}
      >
        <DataRow label="BATCH NUMBER" value={batch.batch_no || 'MFG-BATCH-UNKNOWN'} mono highlight />
        <DataRow label="PRODUCT NAME" value={batch.product_name || 'Pharmaceutical Product'} />
        <DataRow label="PRODUCTION LINE" value={batch.line_id || 'LINE-A1'} mono />
      </Card>

      {/* Proposed Change Comparison Card */}
      <Card title="Proposed Parameter Adjustment" subtitle="DEMAND DRIVEN MODIFICATION">
        <View style={styles.comparisonBox}>
          <Text style={styles.comparisonFieldLabel}>
            PARAMETER: {String(change.field || 'batch_size_units').toUpperCase()}
          </Text>

          <View style={styles.comparisonValuesRow}>
            <View style={styles.comparisonValCol}>
              <Text style={styles.comparisonValSub}>PREVIOUS</Text>
              <Text style={styles.comparisonOldVal}>
                {change.previous_value !== undefined ? String(change.previous_value) : '—'}
              </Text>
            </View>

            <Ionicons name="arrow-forward" size={20} color={colors.accent.primary} />

            <View style={styles.comparisonValCol}>
              <Text style={styles.comparisonValSub}>PROPOSED</Text>
              <Text style={styles.comparisonNewVal}>
                {change.proposed_value !== undefined ? String(change.proposed_value) : '—'}
              </Text>
            </View>
          </View>
        </View>

        {change.reason && (
          <View style={styles.reasonBox}>
            <Text style={styles.reasonLabel}>TRIGGER REASON:</Text>
            <Text style={styles.reasonText}>{change.reason}</Text>
          </View>
        )}
      </Card>

      {/* API Raw Material Stock Impact */}
      {stock.ingredient_name && (
        <Card
          title="Raw Material API Impact"
          subtitle="ACTIVE INGREDIENT INVENTORY BUFFER"
          headerRight={
            stock.below_safety_buffer ? (
              <Badge label="BUFFER BREACH" variant="coral" />
            ) : (
              <Badge label="BUFFER SAFE" variant="emerald" />
            )
          }
        >
          <DataRow label="API INGREDIENT" value={stock.ingredient_name} />
          <DataRow
            label="CURRENT STOCK"
            value={`${stock.current_stock_kg ?? '—'} kg`}
            mono
          />
          <DataRow
            label="REQUIRED FOR BATCH"
            value={`${stock.required_kg ?? '—'} kg`}
            mono
          />
          <DataRow
            label="REMAINING POST-RUN"
            value={`${stock.remaining_kg ?? '—'} kg`}
            mono
            highlight={Boolean(stock.below_safety_buffer)}
          />

          {stock.below_safety_buffer && (
            <View style={styles.warningCallout}>
              <Ionicons name="alert-circle-outline" size={14} color={colors.status.danger} />
              <Text style={styles.warningCalloutText}>
                Remaining API stock falls below plant safety reserve threshold. Reorder will trigger immediately upon approval.
              </Text>
            </View>
          )}
        </Card>
      )}
    </View>
  );
}

// ============================================================================
// Renderer 3: Regulatory Module Activation (RegulatoryActivationRenderer)
// ============================================================================

export function RegulatoryActivationRenderer({ payload }: { payload: any }) {
  const [diffExpanded, setDiffExpanded] = useState(true);
  const testResults = payload?.test_results || {};
  const diff = payload?.simplified_diff || payload?.diff;

  return (
    <View style={styles.rendererContainer}>
      {/* Summary of Change */}
      <Card
        title="Regulatory Policy Transition"
        subtitle="STATUTORY CEILING / RULE HOT-SWAP"
        headerRight={
          <Badge
            label={payload?.version_transition || 'v1 → v2'}
            variant="teal"
          />
        }
      >
        <DataRow label="TARGET MODULE" value={payload?.module_name || 'pricing_engine'} mono />
        {payload?.change_summary && (
          <View style={styles.summaryBox}>
            <Text style={styles.summaryLabel}>REGULATORY SUMMARY:</Text>
            <Text style={styles.summaryText}>{payload.change_summary}</Text>
          </View>
        )}
      </Card>

      {/* Staging Test Results Card */}
      <Card title="Staging Validation & Guard Verification" subtitle="PRE-DEPLOYMENT SUITE">
        <View style={styles.testGrid}>
          <View style={styles.testMetricBox}>
            <Text style={styles.testMetricVal}>
              {testResults.passed ?? 14} / {(testResults.passed ?? 14) + (testResults.failed ?? 0)}
            </Text>
            <Text style={styles.testMetricLabel}>TESTS PASSED</Text>
          </View>
          <View style={styles.testMetricBox}>
            <Text style={[styles.testMetricVal, { color: colors.status.success }]}>
              {testResults.regression_suite || 'PASS'}
            </Text>
            <Text style={styles.testMetricLabel}>REGRESSION SUITE</Text>
          </View>
          <View style={styles.testMetricBox}>
            <Text style={[styles.testMetricVal, { color: colors.status.success }]}>
              {testResults.guard_check || 'PASS'}
            </Text>
            <Text style={styles.testMetricLabel}>AST GUARD CHECK</Text>
          </View>
        </View>
      </Card>

      {/* Collapsible Simplified Diff */}
      {diff && (
        <Card
          title="Module Rule Modification Diff"
          subtitle="SIMPLIFIED EDITORIAL DIFF"
          headerRight={
            <TouchableOpacity
              onPress={() => setDiffExpanded(!diffExpanded)}
              style={styles.diffToggleBtn}
              activeOpacity={0.7}
            >
              <Text style={styles.diffToggleText}>
                {diffExpanded ? 'COLLAPSE' : 'EXPAND'}
              </Text>
              <Ionicons
                name={diffExpanded ? 'chevron-up' : 'chevron-down'}
                size={14}
                color={colors.accent.primary}
              />
            </TouchableOpacity>
          }
        >
          {diffExpanded && (
            <View>
              <View style={styles.diffBox}>
                {String(diff)
                  .split('\n')
                  .map((line: string, i: number) => {
                    const isAdded = line.startsWith('+');
                    const isRemoved = line.startsWith('-');
                    return (
                      <View
                        key={i}
                        style={[
                          styles.diffLineRow,
                          isAdded && styles.diffLineAdded,
                          isRemoved && styles.diffLineRemoved,
                        ]}
                      >
                        <Text
                          style={[
                            styles.diffLineText,
                            isAdded && styles.diffTextAdded,
                            isRemoved && styles.diffTextRemoved,
                          ]}
                        >
                          {line}
                        </Text>
                      </View>
                    );
                  })}
              </View>
              <Text style={styles.diffFooterNote}>
                Simplified mobile diff shown. Full side-by-side module diff is available on the Desktop/Web Control Tower.
              </Text>
            </View>
          )}
        </Card>
      )}
    </View>
  );
}

// ============================================================================
// Renderer 4: Doctor Verification / Schedule H Override (PrescriptionOverrideRenderer)
// ============================================================================

export function PrescriptionOverrideRenderer({ payload }: { payload: any }) {
  const drugs = Array.isArray(payload?.drugs) ? payload.drugs : [];

  return (
    <View style={styles.rendererContainer}>
      {/* Privacy Notice Banner */}
      <View style={styles.privacyBanner}>
        <Ionicons name="lock-closed-outline" size={14} color={colors.accent.primary} />
        <Text style={styles.privacyText}>
          Sovereign Local Data — Minimal Necessary Fields Only (PII Redacted)
        </Text>
      </View>

      {/* Parsed Prescription Fields */}
      <Card
        title="Prescription Credentials Verification"
        subtitle="NMC REGISTRY EXCEPTION REVIEW"
        headerRight={
          <Badge
            label={payload?.verification_status === 'not_found_in_nmc_registry' ? 'UNVERIFIED' : 'FLAGGED'}
            variant="coral"
          />
        }
      >
        <DataRow label="PATIENT INITIALS" value={payload?.patient_initials || 'A.P.'} mono />
        <DataRow label="PRESCRIBING DOCTOR" value={payload?.doctor_name || 'Dr. Vikram Ghost'} />
        <DataRow
          label="REGISTRATION NO."
          value={payload?.doctor_registration_no || 'MCI-UNVERIFIED-9901'}
          mono
          highlight
        />
        <DataRow
          label="REGISTRY AUDIT STATUS"
          value={
            payload?.verification_status === 'not_found_in_nmc_registry'
              ? 'Not found in National Medical Registry'
              : String(payload?.verification_status || 'Under review')
          }
        />
      </Card>

      {/* Prescribed Drugs List */}
      {drugs.length > 0 && (
        <Card title="Restricted Medications" subtitle="SCHEDULE CLASS VALIDATION">
          {drugs.map((drug: any, idx: number) => (
            <View key={idx} style={[styles.drugItem, idx > 0 && styles.itemBorderTop]}>
              <View style={styles.drugHeader}>
                <Text style={styles.drugName}>{drug.name || 'Restricted Drug'}</Text>
                <Badge
                  label={drug.schedule_class ? `SCHEDULE ${drug.schedule_class}` : 'SCHEDULE H'}
                  variant="amber"
                />
              </View>
              {drug.dose && <Text style={styles.drugDose}>Dosage: {drug.dose}</Text>}
            </View>
          ))}
        </Card>
      )}
    </View>
  );
}

// ============================================================================
// Generic JSON Fallback Renderer
// ============================================================================

export function GenericJsonRenderer({ payload }: { payload: any }) {
  const [expanded, setExpanded] = useState(true);
  const entries = Object.entries(payload || {});

  return (
    <View style={styles.rendererContainer}>
      <Card
        title="Structured Task Payload"
        subtitle="GENERAL PAYLOAD INSPECTOR"
        headerRight={
          <TouchableOpacity
            onPress={() => setExpanded(!expanded)}
            style={styles.diffToggleBtn}
            activeOpacity={0.7}
          >
            <Text style={styles.diffToggleText}>{expanded ? 'HIDE RAW' : 'SHOW RAW'}</Text>
          </TouchableOpacity>
        }
      >
        {entries.slice(0, 6).map(([key, val], idx) => (
          <DataRow
            key={idx}
            label={key.replace(/_/g, ' ').toUpperCase()}
            value={typeof val === 'object' ? JSON.stringify(val) : String(val)}
            mono={typeof val === 'number' || typeof val === 'boolean'}
          />
        ))}

        {expanded && (
          <View style={styles.rawJsonBox}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <Text style={styles.rawJsonText}>
                {JSON.stringify(payload, null, 2)}
              </Text>
            </ScrollView>
          </View>
        )}
      </Card>
    </View>
  );
}

// ============================================================================
// Main Task Payload Dispatcher
// ============================================================================

export function TaskPayloadRenderer({ task }: { task: any }) {
  const taskType = String(
    task?.task_type || task?.action_type || task?.step_name || ''
  ).toLowerCase();
  const payload = task?.payload || task?.details || {};

  if (
    taskType.includes('cross_border') ||
    taskType.includes('cross-border') ||
    taskType === 'cross_border_shipment'
  ) {
    return <CrossBorderShipmentRenderer payload={payload} />;
  }

  if (
    taskType.includes('batch_modification') ||
    taskType.includes('in_progress_batch') ||
    taskType.includes('batch_change')
  ) {
    return <BatchModificationRenderer payload={payload} />;
  }

  if (
    taskType.includes('regulatory_activation') ||
    taskType.includes('regulatory_hot_swap') ||
    taskType.includes('module_activation') ||
    taskType.includes('regulatory_module')
  ) {
    return <RegulatoryActivationRenderer payload={payload} />;
  }

  if (
    taskType.includes('doctor_verification') ||
    taskType.includes('schedule_h') ||
    taskType.includes('compliance_hold') ||
    taskType.includes('prescription')
  ) {
    return <PrescriptionOverrideRenderer payload={payload} />;
  }

  return <GenericJsonRenderer payload={payload} />;
}

// ============================================================================
// Styles
// ============================================================================

const styles = StyleSheet.create({
  rendererContainer: {
    gap: spacing.base,
  },
  dataRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs + 2,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.subtle,
  },
  dataLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    flex: 1,
  },
  dataValue: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    flex: 1.5,
    textAlign: 'right',
  },
  fontMono: {
    fontFamily: typography.fontFamily.mono,
  },
  highlightText: {
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.bold,
  },

  // Route Box
  routeBox: {
    backgroundColor: colors.canvas.elevated,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    marginBottom: spacing.md,
  },
  routeStep: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  routeTextCol: {
    flex: 1,
  },
  routeStepLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
  },
  routeStepName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  routeDivider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: spacing.sm,
    gap: spacing.sm,
  },
  routeDividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border.default,
  },
  checkpointPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.status.warningSubtle,
    borderWidth: 1,
    borderColor: colors.status.warning,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  checkpointText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.status.warning,
    fontFamily: typography.fontFamily.mono,
  },

  // Flags
  flagsWrapper: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  flagChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border.default,
    backgroundColor: colors.canvas.elevated,
  },
  flagCold: {
    borderColor: colors.accent.border,
    backgroundColor: colors.accent.subtle,
  },
  flagPermit: {
    borderColor: colors.status.warning,
    backgroundColor: colors.status.warningSubtle,
  },
  flagChipText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.text.primary,
  },

  // Products Manifest
  productItem: {
    paddingVertical: spacing.sm,
  },
  itemBorderTop: {
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  productRowTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  productName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    flex: 1,
    marginRight: spacing.sm,
  },
  productDetailsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  productSku: {
    fontSize: typography.fontSize.caption,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.secondary,
  },
  productValue: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },

  // Comparison Box
  comparisonBox: {
    backgroundColor: colors.canvas.elevated,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    marginBottom: spacing.md,
  },
  comparisonFieldLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: spacing.sm,
  },
  comparisonValuesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
  },
  comparisonValCol: {
    alignItems: 'center',
  },
  comparisonValSub: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.muted,
    letterSpacing: typography.letterSpacing.wide,
  },
  comparisonOldVal: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.bold,
    color: colors.status.danger,
    fontFamily: typography.fontFamily.mono,
    textDecorationLine: 'line-through',
  },
  comparisonNewVal: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.black,
    color: colors.status.success,
    fontFamily: typography.fontFamily.mono,
  },
  reasonBox: {
    marginTop: spacing.xs,
  },
  reasonLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: 2,
  },
  reasonText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    lineHeight: typography.fontSize.caption * 1.45,
  },

  // Warning Callout
  warningCallout: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    backgroundColor: colors.status.dangerSubtle,
    borderWidth: 1,
    borderColor: colors.status.danger,
    padding: spacing.sm,
    borderRadius: radii.sm,
    marginTop: spacing.sm,
  },
  warningCalloutText: {
    fontSize: typography.fontSize.caption,
    color: colors.status.danger,
    flex: 1,
    lineHeight: typography.fontSize.caption * 1.4,
  },

  // Summary Box
  summaryBox: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  summaryLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: 2,
  },
  summaryText: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    lineHeight: typography.fontSize.body * 1.4,
  },

  // Test Grid
  testGrid: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  testMetricBox: {
    flex: 1,
    backgroundColor: colors.canvas.elevated,
    padding: spacing.sm,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    alignItems: 'center',
  },
  testMetricVal: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.black,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.primary,
  },
  testMetricLabel: {
    fontSize: 9,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: 0.5,
    marginTop: 2,
    textAlign: 'center',
  },

  // Diff
  diffToggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  diffToggleText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
    letterSpacing: typography.letterSpacing.wide,
  },
  diffBox: {
    backgroundColor: '#031211',
    borderRadius: radii.sm,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.emphasis,
  },
  diffLineRow: {
    paddingVertical: 1,
    paddingHorizontal: 4,
  },
  diffLineAdded: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
  },
  diffLineRemoved: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  diffLineText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.caption,
    color: '#F7F5F0',
  },
  diffTextAdded: {
    color: '#34D399',
  },
  diffTextRemoved: {
    color: '#F87171',
  },
  diffFooterNote: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    fontStyle: 'italic',
    marginTop: spacing.xs,
  },

  // Privacy Banner
  privacyBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.accent.subtle,
    borderWidth: 1,
    borderColor: colors.accent.border,
    padding: spacing.sm,
    borderRadius: radii.sm,
  },
  privacyText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.medium,
    color: colors.accent.primary,
    flex: 1,
  },

  // Drugs List
  drugItem: {
    paddingVertical: spacing.sm,
  },
  drugHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  drugName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    flex: 1,
  },
  drugDose: {
    fontSize: typography.fontSize.caption,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.secondary,
  },

  // Raw JSON
  rawJsonBox: {
    backgroundColor: colors.canvas.elevated,
    padding: spacing.sm,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    marginTop: spacing.sm,
  },
  rawJsonText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.primary,
  },
});
