import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, typography, radii } from '../../theme/tokens';
import { Badge } from '../../components/Badge';
import { Card } from '../../components/Card';

export interface CascadeStep {
  tier: number;
  tier_label: string;
  agent_name: string;
  node_id: string;
  node_name: string;
  status: string;
  reasoning: string;
  input?: Record<string, any>;
  output?: Record<string, any>;
  model?: string;
  provider?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  duration_ms: number;
  timestamp: string;
  entities_created?: Record<string, any>;
}

export interface CascadeTrace {
  correlation_id: string;
  started_at: string;
  completed_at: string;
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

export function CascadeTimeline({ trace, loading, error, onRefresh }: CascadeTimelineProps) {
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
      <Card title="Demand Cascade Trace" subtitle="Multi-Tier Autonomous Propagation">
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
            <Text style={styles.metaItemValue}>{Math.round(trace.total_duration_ms)} ms</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaItemLabel}>LLM TOKENS</Text>
            <Text style={styles.metaItemValue}>{trace.total_tokens} tok</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaItemLabel}>TIERS REACHED</Text>
            <Text style={styles.metaItemValue}>
              {trace.steps.length}/4 (100% Propagation)
            </Text>
          </View>
        </View>

        {trigger.product_name && (
          <View style={styles.triggerBanner}>
            <Ionicons name="flash-outline" size={16} color={colors.accent.primary} />
            <Text style={styles.triggerText}>
              Trigger: Dispensed {trigger.quantity || 1} unit(s) of{' '}
              <Text style={{ fontWeight: '700' }}>{trigger.product_name}</Text> at{' '}
              {trigger.pharmacy_name || 'Retail Pharmacy'}.
            </Text>
          </View>
        )}
      </Card>

      {/* Vertical Steps Progression */}
      <View style={styles.timelineSection}>
        <Text style={styles.sectionTitle}>PROPAGATION CHAIN STEPS</Text>
        <Text style={styles.sectionSubtitle}>
          Instantaneous demand cascade from point-of-sale to manufacturing plant:
        </Text>

        <View style={styles.stepsContainer}>
          {trace.steps.map((step, idx) => {
            const isLast = idx === trace.steps.length - 1;
            const isExpanded = expandedStepIndex === idx;
            const stepSuccess = step.status.toLowerCase() === 'succeeded';

            return (
              <View key={`step-${step.tier}-${idx}`} style={styles.stepWrapper}>
                {/* Left Connector Column */}
                <View style={styles.indicatorCol}>
                  <View
                    style={[
                      styles.stepCircle,
                      stepSuccess ? styles.circleSuccess : styles.circlePending,
                    ]}
                  >
                    <Text style={styles.stepTierNum}>T{step.tier}</Text>
                  </View>
                  {!isLast && <View style={styles.verticalLine} />}
                </View>

                {/* Right Step Content */}
                <View style={styles.stepContentCol}>
                  <TouchableOpacity
                    style={styles.stepCard}
                    onPress={() => setExpandedStepIndex(isExpanded ? null : idx)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.stepHeaderRow}>
                      <View style={styles.tierPill}>
                        <Text style={styles.tierPillText}>
                          {step.tier_label || `TIER ${step.tier}`}
                        </Text>
                      </View>
                      <View style={styles.stepDurationPill}>
                        <Text style={styles.stepDurationText}>
                          {Math.round(step.duration_ms)} ms
                        </Text>
                      </View>
                    </View>

                    <Text style={styles.agentName}>{step.agent_name}</Text>
                    <Text style={styles.nodeName}>{step.node_name}</Text>

                    <View style={styles.reasoningBox}>
                      <Text style={styles.reasoningText}>{step.reasoning}</Text>
                    </View>

                    {/* Expand / Collapse Structured Output */}
                    <View style={styles.expandActionRow}>
                      <Text style={styles.expandActionText}>
                        {isExpanded ? 'HIDE STRUCTURED OUTPUT ▲' : 'VIEW STRUCTURED OUTPUT ▼'}
                      </Text>
                      <Text style={styles.tokenTag}>{step.total_tokens ?? 0} tokens</Text>
                    </View>

                    {isExpanded && (
                      <View style={styles.expandedOutputBox}>
                        <Text style={styles.outputHeading}>Entities Created / Updated:</Text>
                        <Text style={styles.outputJson}>
                          {JSON.stringify(step.entities_created || step.output || {}, null, 2)}
                        </Text>
                      </View>
                    )}
                  </TouchableOpacity>
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
    marginBottom: spacing.base,
  },
  retryBtn: {
    backgroundColor: colors.accent.primary,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: 0.5,
  },
  overviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  idRow: {
    flex: 1,
    marginRight: spacing.sm,
  },
  idLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: 2,
  },
  idValueMono: {
    fontSize: typography.fontSize.caption,
    fontFamily: 'monospace',
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  metaGrid: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border.default,
    paddingVertical: spacing.sm,
    marginVertical: spacing.sm,
  },
  metaItem: {
    flex: 1,
  },
  metaItemLabel: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.text.secondary,
    letterSpacing: 0.5,
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
    backgroundColor: '#F0FDF4',
    borderWidth: 1,
    borderColor: '#BBF7D0',
    padding: spacing.sm,
    borderRadius: radii.sm,
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  triggerText: {
    flex: 1,
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    lineHeight: 18,
  },
  timelineSection: {
    marginTop: spacing.base,
  },
  sectionTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: 2,
  },
  sectionSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginBottom: spacing.base,
  },
  stepsContainer: {
    paddingLeft: 4,
  },
  stepWrapper: {
    flexDirection: 'row',
  },
  indicatorCol: {
    width: 32,
    alignItems: 'center',
  },
  stepCircle: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    zIndex: 2,
  },
  circleSuccess: {
    backgroundColor: '#031211',
    borderColor: '#00AEBB',
  },
  circlePending: {
    backgroundColor: colors.canvas.surface,
    borderColor: colors.border.default,
  },
  stepTierNum: {
    color: '#00AEBB',
    fontSize: 10,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  verticalLine: {
    flex: 1,
    width: 2,
    backgroundColor: '#D8D3C3',
    marginVertical: 2,
  },
  stepContentCol: {
    flex: 1,
    paddingLeft: spacing.sm,
    paddingBottom: spacing.base,
  },
  stepCard: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.md,
  },
  stepHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  tierPill: {
    backgroundColor: colors.canvas.elevated,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    borderWidth: 0.5,
    borderColor: colors.border.default,
  },
  tierPillText: {
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
    color: colors.accent.primary,
  },
  stepDurationPill: {
    backgroundColor: colors.canvas.primary,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 3,
  },
  stepDurationText: {
    fontSize: 9,
    fontFamily: 'monospace',
    fontWeight: '700',
    color: colors.text.secondary,
  },
  agentName: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.black,
    color: colors.text.primary,
  },
  nodeName: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    marginBottom: spacing.xs + 2,
  },
  reasoningBox: {
    backgroundColor: colors.canvas.primary,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.sm,
    marginVertical: spacing.xs,
  },
  reasoningText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    lineHeight: 18,
  },
  expandActionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: 0.5,
    borderTopColor: colors.border.default,
  },
  expandActionText: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.accent.primary,
    letterSpacing: 0.5,
  },
  tokenTag: {
    fontSize: 9,
    fontFamily: 'monospace',
    color: colors.text.muted,
  },
  expandedOutputBox: {
    marginTop: spacing.sm,
    padding: spacing.sm,
    backgroundColor: '#031211',
    borderRadius: radii.sm,
  },
  outputHeading: {
    fontSize: 9,
    fontWeight: '700',
    color: '#00AEBB',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  outputJson: {
    fontSize: 10,
    fontFamily: 'monospace',
    color: '#E8E4D3',
    lineHeight: 14,
  },
});
