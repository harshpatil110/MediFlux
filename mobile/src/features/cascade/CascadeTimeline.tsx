import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, typography, radii } from '../../theme/tokens';
import { Badge } from '../../components/Badge';
import { Card } from '../../components/Card';

export type CascadeStageName = 'supervisor' | 'pharmacy' | 'stockist' | 'distributor' | 'manufacturer';
export type CascadeStepState = 'completed' | 'waiting_approval' | 'running' | 'skipped' | 'failed' | 'succeeded' | 'pending';

export interface CascadeStep {
  stage?: CascadeStageName;
  state?: CascadeStepState;
  tier?: number;
  tier_label?: string;
  agent_name?: string;
  node_id?: string;
  node_name?: string;
  status?: string;
  reasoning?: string;
  skip_reason?: string | null;
  hitl_task_id?: string | null;
  structured_output?: Record<string, any>;
  entities_created?: Record<string, any>;
  output?: Record<string, any>;
  input?: Record<string, any>;
  model?: string;
  provider?: string;
  duration_ms?: number;
  total_tokens?: number;
  timestamp?: string;
}

export interface CascadeTrace {
  correlation_id: string;
  started_at: string;
  completed_at?: string;
  total_duration_ms: number;
  total_tokens: number;
  status: string;
  trigger_event?: Record<string, any>;
  steps: CascadeStep[];
}

export interface CascadeTimelineProps {
  trace: CascadeTrace | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
}

const STAGE_CONFIG: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; tierBadge: string }> = {
  supervisor: { label: 'Supervisor Router', icon: 'git-network-outline', tierBadge: 'CTRL' },
  pharmacy: { label: 'Pharmacy Edge (T1)', icon: 'storefront-outline', tierBadge: 'T1' },
  stockist: { label: 'Stockist Hub (T2)', icon: 'business-outline', tierBadge: 'T2' },
  distributor: { label: 'Distributor Layer (T3)', icon: 'trail-sign-outline', tierBadge: 'T3' },
  manufacturer: { label: 'Manufacturer Plant (T4)', icon: 'flask-outline', tierBadge: 'T4' },
};

export function CascadeTimeline({ trace, loading, error, onRefresh }: CascadeTimelineProps) {
  const router = useRouter();
  const [expandedStepIndex, setExpandedStepIndex] = useState<number | null>(null);

  if (loading) {
    return (
      <View style={styles.centerBox}>
        <ActivityIndicator size="large" color={colors.accent.primary} />
        <Text style={styles.loadingText}>Fetching Cascade Progression...</Text>
      </View>
    );
  }

  if (error || !trace) {
    return (
      <View style={styles.errorBox}>
        <Ionicons name="alert-circle-outline" size={32} color="#DC2626" />
        <Text style={styles.errorTitle}>Cascade Trace Not Found</Text>
        <Text style={styles.errorSubtitle}>
          {error || 'No telemetry trace exists for this correlation ID yet.'}
        </Text>
        {onRefresh && (
          <TouchableOpacity style={styles.retryBtn} onPress={onRefresh} activeOpacity={0.8}>
            <Text style={styles.retryBtnText}>RETRY QUERY</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  const trigger = trace.trigger_event || {};
  const isCompleted = trace.status.toLowerCase() === 'completed';

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Trace Overview Card */}
      <Card title="Demand Cascade Trace" subtitle="Instant Multi-Tier Autonomous Propagation">
        <View style={styles.overviewHeader}>
          <View style={styles.idRow}>
            <Text style={styles.idLabel}>CORRELATION ID</Text>
            <Text style={styles.idValueMono} numberOfLines={1}>
              {trace.correlation_id}
            </Text>
          </View>
          <Badge
            label={isCompleted ? 'CASCADE COMPLETED' : trace.status.toUpperCase()}
            variant={isCompleted ? 'emerald' : 'amber'}
          />
        </View>

        <View style={styles.metaGrid}>
          <View style={styles.metaItem}>
            <Text style={styles.metaItemLabel}>DURATION</Text>
            <Text style={styles.metaItemValue}>{Math.round(trace.total_duration_ms || 0)} ms</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaItemLabel}>LLM TOKENS</Text>
            <Text style={styles.metaItemValue}>{trace.total_tokens || 0} tok</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaItemLabel}>STAGES REACHED</Text>
            <Text style={styles.metaItemValue}>
              {trace.steps.length}/5 Propagation
            </Text>
          </View>
        </View>

        {trigger.product_name && (
          <View style={styles.triggerBanner}>
            <Ionicons name="flash-outline" size={16} color={colors.accent.primary} />
            <Text style={styles.triggerText}>
              Trigger: Dispensed {trigger.quantity || 1} strip(s) of{' '}
              <Text style={{ fontWeight: '700' }}>{trigger.product_name}</Text> (Batch{' '}
              {trigger.batch_number || 'N/A'})
            </Text>
          </View>
        )}
      </Card>

      {/* Vertical Steps Progression */}
      <View style={styles.timelineSection}>
        <Text style={styles.sectionTitle}>5-STAGE DEMAND PROPAGATION PIPELINE</Text>
        <Text style={styles.sectionSubtitle}>
          Real-time autonomous dispatch through retail counter, stockist, regional distributor, and manufacturing plant:
        </Text>

        <View style={styles.stepsContainer}>
          {trace.steps.map((step, idx) => {
            const isLast = idx === trace.steps.length - 1;
            const isExpanded = expandedStepIndex === idx;

            const stageKey = (step.stage || `tier-${step.tier}`).toLowerCase();
            const config = STAGE_CONFIG[stageKey] || {
              label: step.tier_label || `Tier ${step.tier || idx}`,
              icon: 'cube-outline',
              tierBadge: step.tier ? `T${step.tier}` : `S${idx}`,
            };

            const rawState = (step.state || step.status || 'completed').toLowerCase();
            const isSuccess = rawState === 'completed' || rawState === 'succeeded';
            const isWaitingApproval = rawState === 'waiting_approval';
            const isSkipped = rawState === 'skipped';
            const isFailed = rawState === 'failed';

            const outputData = step.structured_output || step.entities_created || step.output || {};

            return (
              <View key={`step-${idx}-${stageKey}`} style={styles.stepWrapper}>
                {/* Left Connector Column */}
                <View style={styles.indicatorCol}>
                  <View
                    style={[
                      styles.stepCircle,
                      isSuccess && styles.circleSuccess,
                      isWaitingApproval && styles.circleWaiting,
                      isSkipped && styles.circleSkipped,
                      isFailed && styles.circleFailed,
                    ]}
                  >
                    <Text style={styles.stepTierNum}>{config.tierBadge}</Text>
                  </View>
                  {!isLast && (
                    <View
                      style={[
                        styles.verticalLine,
                        isSuccess ? styles.verticalLineSuccess : null,
                      ]}
                    />
                  )}
                </View>

                {/* Right Step Content */}
                <View style={styles.stepContentCol}>
                  <View
                    style={[
                      styles.stepCard,
                      isWaitingApproval && styles.stepCardWaiting,
                      isSkipped && styles.stepCardSkipped,
                    ]}
                  >
                    <View style={styles.stepHeaderRow}>
                      <View style={styles.tierPill}>
                        <Ionicons name={config.icon} size={14} color={colors.accent.primary} />
                        <Text style={styles.tierPillText}>{config.label}</Text>
                      </View>

                      {isSuccess && <Badge label="COMPLETED" variant="emerald" />}
                      {isWaitingApproval && <Badge label="APPROVAL PENDING" variant="amber" />}
                      {isSkipped && <Badge label="SKIPPED" variant="neutral" />}
                      {isFailed && <Badge label="FAILED" variant="coral" />}
                    </View>

                    <Text style={styles.agentName}>{step.agent_name || config.label}</Text>
                    {step.node_name && <Text style={styles.nodeName}>{step.node_name}</Text>}

                    {/* Step Reasoning */}
                    {step.reasoning ? (
                      <View style={styles.reasoningBox}>
                        <Text style={styles.reasoningText}>{step.reasoning}</Text>
                      </View>
                    ) : null}

                    {/* Skip Reason Callout */}
                    {isSkipped && step.skip_reason && (
                      <View style={styles.skipCallout}>
                        <Ionicons name="information-circle-outline" size={14} color={colors.text.secondary} />
                        <Text style={styles.skipCalloutText}>{step.skip_reason}</Text>
                      </View>
                    )}

                    {/* Actionable Human In The Loop approval button */}
                    {isWaitingApproval && (
                      <View style={styles.hitlActionBox}>
                        <View style={styles.hitlInfoRow}>
                          <Ionicons name="time" size={16} color={colors.status.warning} />
                          <Text style={styles.hitlNoticeText}>
                            High-value replenishment order requires manager sign-off.
                          </Text>
                        </View>
                        <TouchableOpacity
                          style={styles.reviewApprovalBtn}
                          onPress={() => router.push('/(tabs)/approvals' as any)}
                          activeOpacity={0.8}
                        >
                          <Text style={styles.reviewApprovalBtnText}>REVIEW APPROVALS IN APP →</Text>
                        </TouchableOpacity>
                      </View>
                    )}

                    {/* Formatted Output Grid if available */}
                    {outputData && Object.keys(outputData).length > 0 && (
                      <View style={styles.formattedGrid}>
                        {outputData.order_id && (
                          <View style={styles.gridRow}>
                            <Text style={styles.gridLabel}>ORDER GENERATED:</Text>
                            <Text style={styles.gridValMono}>{outputData.order_id}</Text>
                          </View>
                        )}
                        {outputData.reorder_quantity && (
                          <View style={styles.gridRow}>
                            <Text style={styles.gridLabel}>REORDER QUANTITY:</Text>
                            <Text style={styles.gridValBold}>{outputData.reorder_quantity} units</Text>
                          </View>
                        )}
                        {outputData.production_batch_id && (
                          <View style={styles.gridRow}>
                            <Text style={styles.gridLabel}>MFG BATCH ID:</Text>
                            <Text style={styles.gridValMono}>{outputData.production_batch_id}</Text>
                          </View>
                        )}
                      </View>
                    )}

                    {/* Expand / Collapse Raw JSON Toggle */}
                    <TouchableOpacity
                      style={styles.expandActionRow}
                      onPress={() => setExpandedStepIndex(isExpanded ? null : idx)}
                      activeOpacity={0.7}
                    >
                      <Text style={styles.expandActionText}>
                        {isExpanded ? 'HIDE RAW TELEMETRY ▲' : 'VIEW RAW TELEMETRY DATA ▼'}
                      </Text>
                      <Text style={styles.tokenTag}>
                        {Math.round(step.duration_ms || 0)}ms • {step.total_tokens ?? 0} tok
                      </Text>
                    </TouchableOpacity>

                    {isExpanded && (
                      <View style={styles.expandedOutputBox}>
                        <Text style={styles.outputHeading}>Raw Structured Output / Payload:</Text>
                        <Text style={styles.outputJson}>
                          {JSON.stringify(outputData, null, 2)}
                        </Text>
                      </View>
                    )}
                  </View>
                </View>
              </View>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
  },
  content: {
    padding: spacing.base,
    paddingBottom: spacing.xxl * 2,
  },
  centerBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    fontWeight: typography.fontWeight.semibold,
  },
  errorBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.canvas.primary,
  },
  errorTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  errorSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textAlign: 'center',
    maxWidth: 280,
    marginBottom: spacing.md,
  },
  retryBtn: {
    backgroundColor: colors.accent.primary,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontWeight: typography.fontWeight.bold,
    fontSize: typography.fontSize.caption,
    letterSpacing: typography.letterSpacing.wide,
  },
  overviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  idRow: {
    flex: 1,
  },
  idLabel: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    fontFamily: typography.fontFamily.mono,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: 2,
  },
  idValueMono: {
    fontSize: typography.fontSize.body,
    fontFamily: typography.fontFamily.mono,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  metaGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: colors.canvas.elevated,
    borderRadius: radii.md,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    marginBottom: spacing.sm,
  },
  metaItem: {
    flex: 1,
    alignItems: 'center',
  },
  metaItemLabel: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    fontFamily: typography.fontFamily.mono,
    marginBottom: 2,
  },
  metaItemValue: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  triggerBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.accent.subtle,
    borderWidth: 1,
    borderColor: colors.accent.border,
    borderRadius: radii.sm,
    padding: spacing.sm,
    gap: spacing.xs,
  },
  triggerText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    flex: 1,
  },
  timelineSection: {
    marginTop: spacing.lg,
  },
  sectionTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.text.secondary,
    marginBottom: 4,
  },
  sectionSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.muted,
    marginBottom: spacing.md,
  },
  stepsContainer: {
    position: 'relative',
  },
  stepWrapper: {
    flexDirection: 'row',
    marginBottom: spacing.md,
  },
  indicatorCol: {
    width: 36,
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  stepCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1.5,
    borderColor: colors.border.default,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },
  circleSuccess: {
    borderColor: colors.status.success,
    backgroundColor: colors.status.successSubtle,
  },
  circleWaiting: {
    borderColor: colors.status.warning,
    backgroundColor: colors.status.warningSubtle,
  },
  circleSkipped: {
    borderColor: colors.border.default,
    backgroundColor: colors.canvas.elevated,
  },
  circleFailed: {
    borderColor: colors.status.danger,
    backgroundColor: colors.status.dangerSubtle,
  },
  stepTierNum: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  verticalLine: {
    width: 2,
    flex: 1,
    backgroundColor: colors.border.default,
    marginVertical: 4,
  },
  verticalLineSuccess: {
    backgroundColor: colors.accent.primary,
  },
  stepContentCol: {
    flex: 1,
  },
  stepCard: {
    backgroundColor: colors.canvas.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.default,
    padding: spacing.md,
  },
  stepCardWaiting: {
    borderColor: colors.status.warning,
    backgroundColor: '#FFFDF5',
  },
  stepCardSkipped: {
    borderColor: colors.border.subtle,
    backgroundColor: colors.canvas.elevated,
    opacity: 0.9,
  },
  stepHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  tierPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  tierPillText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  agentName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  nodeName: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginBottom: spacing.xs,
  },
  reasoningBox: {
    backgroundColor: colors.canvas.elevated,
    borderRadius: radii.sm,
    padding: spacing.sm,
    marginVertical: spacing.xs,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent.primary,
  },
  reasoningText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    lineHeight: 18,
  },
  skipCallout: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    padding: spacing.xs,
    backgroundColor: colors.canvas.alternate,
    borderRadius: radii.sm,
    marginTop: spacing.xs,
  },
  skipCalloutText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    flex: 1,
    fontStyle: 'italic',
  },
  hitlActionBox: {
    backgroundColor: colors.status.warningSubtle,
    borderWidth: 1,
    borderColor: colors.status.warning,
    borderRadius: radii.sm,
    padding: spacing.sm,
    marginTop: spacing.sm,
  },
  hitlInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: spacing.xs,
  },
  hitlNoticeText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontWeight: typography.fontWeight.medium,
    flex: 1,
  },
  reviewApprovalBtn: {
    backgroundColor: colors.status.warning,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderRadius: radii.sm,
    alignItems: 'center',
  },
  reviewApprovalBtnText: {
    color: '#031211',
    fontWeight: typography.fontWeight.bold,
    fontSize: typography.fontSize.caption,
    letterSpacing: typography.letterSpacing.wide,
  },
  formattedGrid: {
    backgroundColor: colors.canvas.elevated,
    borderRadius: radii.sm,
    padding: spacing.xs,
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border.subtle,
  },
  gridRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 2,
  },
  gridLabel: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.muted,
  },
  gridValMono: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  gridValBold: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  expandActionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  expandActionText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.accent.primary,
  },
  tokenTag: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.muted,
  },
  expandedOutputBox: {
    marginTop: spacing.xs,
    backgroundColor: colors.canvas.dark,
    borderRadius: radii.sm,
    padding: spacing.sm,
  },
  outputHeading: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.accent.primary,
    marginBottom: 4,
  },
  outputJson: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: '#FFFFFF',
  },
});
