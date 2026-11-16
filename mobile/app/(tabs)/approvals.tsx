import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiClient } from '../../src/api/client';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';
import { EmptyState } from '../../src/components/EmptyState';
import { useAuth } from '../../src/features/auth/AuthContext';
import { useEventStream } from '../../src/hooks/useEventStream';

type FilterTab = 'pending' | 'decided';

function formatRelativeTime(dateStr?: string | Date | null): string {
  if (!dateStr) return '—';
  try {
    const diff = Math.max(0, (Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch {
    return '—';
  }
}

function formatCountdown(expiresAt?: string | Date | null): { text: string; isExpired: boolean } {
  if (!expiresAt) return { text: 'No Expiry', isExpired: false };
  try {
    const remaining = (new Date(expiresAt).getTime() - Date.now()) / 1000;
    if (remaining <= 0) return { text: 'EXPIRED', isExpired: true };
    const h = Math.floor(remaining / 3600);
    const m = Math.floor((remaining % 3600) / 60);
    const s = Math.floor(remaining % 60);
    if (h > 0) return { text: `Expires in ${h}h ${m}m ${s}s`, isExpired: false };
    if (m > 0) return { text: `Expires in ${m}m ${s}s`, isExpired: false };
    return { text: `Expires in ${s}s`, isExpired: false };
  } catch {
    return { text: '—', isExpired: false };
  }
}

export default function ApprovalsScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<FilterTab>('pending');
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [triggering, setTriggering] = useState<boolean>(false);
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);
  const [, setTick] = useState<number>(0);

  const fetchTasks = useCallback(async () => {
    try {
      const data = await apiClient.get<any[]>('/api/v1/hitl/tasks?status=all');
      setTasks(Array.isArray(data) ? data : []);
    } catch {
      // Retain existing state on fetch error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Live ticking countdown timer
  useEffect(() => {
    const timer = setInterval(() => {
      setTick((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Live SSE listener on hitl topic
  const { lastEvent } = useEventStream('hitl');
  useEffect(() => {
    if (lastEvent) {
      fetchTasks();
    }
  }, [lastEvent, fetchTasks]);

  const handleSimulateCrossBorder = async () => {
    setTriggering(true);
    setTriggerMessage(null);
    try {
      await apiClient.post('/api/v1/hitl/tasks/trigger', {
        task_type: 'cross_border_shipment',
      });
      setTriggerMessage('Cross-Border Shipment task simulated!');
      await fetchTasks();
      setTimeout(() => setTriggerMessage(null), 4000);
    } catch {
      setTriggerMessage('Simulation failed to trigger.');
    } finally {
      setTriggering(false);
    }
  };

  const pendingTasks = useMemo(
    () => tasks.filter((t) => t.status === 'pending'),
    [tasks]
  );

  const decidedTasks = useMemo(
    () => tasks.filter((t) => t.status !== 'pending'),
    [tasks]
  );

  const displayedList = activeTab === 'pending' ? pendingTasks : decidedTasks;

  const isPharmacyRole = user?.role?.toLowerCase() === 'pharmacy';

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={loading}
          onRefresh={fetchTasks}
          tintColor={colors.accent.primary}
        />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.tagRow}>
          <Text style={styles.subtitle}>HUMAN-IN-THE-LOOP CONTROL PLANE</Text>
          <Badge
            label={pendingTasks.length > 0 ? `${pendingTasks.length} PENDING` : 'ALL CLEAR'}
            variant={pendingTasks.length > 0 ? 'amber' : 'emerald'}
          />
        </View>
        <Text style={styles.title}>Field Approvals Queue</Text>
        <Text style={styles.description}>
          Inspect and decide autonomous agent recommendations requiring human oversight.
        </Text>
      </View>

      {/* Role Policy Banner */}
      {isPharmacyRole && (
        <View style={styles.roleBanner}>
          <Ionicons name="information-circle-outline" size={16} color={colors.text.secondary} />
          <Text style={styles.roleBannerText}>
            VIEW-ONLY MODE — Your role can inspect HITL tasks, but decisions require Stockist, Distributor, Manufacturer, Regulator, or Admin authorization.
          </Text>
        </View>
      )}

      {/* Quick Demo Trigger Bar */}
      <View style={styles.triggerBar}>
        <TouchableOpacity
          style={[styles.triggerBtn, triggering && styles.btnDisabled]}
          onPress={handleSimulateCrossBorder}
          disabled={triggering}
          activeOpacity={0.8}
        >
          {triggering ? (
            <ActivityIndicator size="small" color={colors.accent.primary} />
          ) : (
            <>
              <Ionicons name="flash-outline" size={14} color={colors.accent.primary} />
              <Text style={styles.triggerBtnText}>⚡ Simulate Cross-Border Shipment Hold</Text>
            </>
          )}
        </TouchableOpacity>
        {triggerMessage && (
          <Text style={styles.triggerSuccessText}>{triggerMessage}</Text>
        )}
      </View>

      {/* Segmented Filter Tabs */}
      <View style={styles.segmentedContainer}>
        <TouchableOpacity
          style={[styles.segmentBtn, activeTab === 'pending' && styles.segmentActive]}
          onPress={() => setActiveTab('pending')}
          activeOpacity={0.8}
        >
          <Text
            style={[
              styles.segmentText,
              activeTab === 'pending' && styles.segmentTextActive,
            ]}
          >
            Pending ({pendingTasks.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.segmentBtn, activeTab === 'decided' && styles.segmentActive]}
          onPress={() => setActiveTab('decided')}
          activeOpacity={0.8}
        >
          <Text
            style={[
              styles.segmentText,
              activeTab === 'decided' && styles.segmentTextActive,
            ]}
          >
            Decided ({decidedTasks.length})
          </Text>
        </TouchableOpacity>
      </View>

      {/* Content List */}
      {loading && tasks.length === 0 ? (
        <ActivityIndicator size="large" color={colors.accent.primary} style={styles.loader} />
      ) : displayedList.length === 0 ? (
        <EmptyState
          title={activeTab === 'pending' ? 'No Pending Approvals' : 'No Decided Tasks'}
          description={
            activeTab === 'pending'
              ? 'All autonomous purchase orders, batch transfers, and shipments are cleared.'
              : 'Decided tasks will be archived here once approved, rejected, or expired.'
          }
          actionLabel="REFRESH QUEUE"
          onAction={fetchTasks}
        />
      ) : (
        displayedList.map((task: any) => {
          const isPending = task.status === 'pending';
          const countdown = formatCountdown(task.expires_at);
          const relativeAge = formatRelativeTime(task.created_at);
          const formattedType = String(
            task.task_type || task.action_type || 'APPROVAL'
          )
            .replace(/_/g, ' ')
            .toUpperCase();

          const riskVariant =
            task.risk_level === 'critical' || task.risk_level === 'high'
              ? 'coral'
              : task.risk_level === 'medium'
              ? 'amber'
              : 'neutral';

          const statusVariant =
            task.status === 'approved'
              ? 'emerald'
              : task.status === 'rejected'
              ? 'coral'
              : task.status === 'expired'
              ? 'neutral'
              : 'amber';

          return (
            <TouchableOpacity
              key={task.id}
              activeOpacity={0.9}
              onPress={() =>
                router.push({
                  pathname: '/approvals/[id]',
                  params: { id: task.id },
                } as any)
              }
            >
              <Card
                title={task.title || `Task #${task.id?.slice(0, 8)}`}
                subtitle={formattedType}
                headerRight={
                  <View style={styles.headerRightWrapper}>
                    {!isPending && (
                      <Badge
                        label={String(task.status).toUpperCase()}
                        variant={statusVariant}
                      />
                    )}
                    <Badge
                      label={String(task.risk_level || 'MEDIUM').toUpperCase()}
                      variant={riskVariant}
                    />
                  </View>
                }
              >
                <Text style={styles.taskSummary} numberOfLines={2}>
                  {task.summary || task.description || task.reasoning}
                </Text>

                <View style={styles.metaRow}>
                  <View style={styles.agentCol}>
                    <Ionicons name="hardware-chip-outline" size={13} color={colors.text.secondary} />
                    <Text style={styles.agentText} numberOfLines={1}>
                      {task.requesting_agent || 'Autonomous Agent'} • {task.node_name || 'Network Node'}
                    </Text>
                  </View>
                </View>

                <View style={styles.cardFooter}>
                  <Text style={styles.ageText}>{relativeAge}</Text>

                  {isPending ? (
                    countdown.isExpired ? (
                      <Badge label="EXPIRED" variant="neutral" />
                    ) : (
                      <View style={styles.countdownBox}>
                        <Ionicons name="time-outline" size={12} color={colors.status.warning} />
                        <Text style={styles.countdownText}>{countdown.text}</Text>
                      </View>
                    )
                  ) : (
                    <Text style={styles.decidedInfoText}>
                      Decided: {formatRelativeTime(task.decided_at || task.created_at)}
                    </Text>
                  )}
                </View>
              </Card>
            </TouchableOpacity>
          );
        })
      )}
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
  header: {
    marginBottom: spacing.base,
  },
  tagRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
  },
  title: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.black,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.tight,
    marginBottom: spacing.xs,
  },
  description: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    lineHeight: typography.fontSize.caption * 1.5,
  },

  // Role Banner
  roleBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    padding: spacing.sm,
    borderRadius: radii.sm,
    marginBottom: spacing.base,
  },
  roleBannerText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    flex: 1,
    lineHeight: typography.fontSize.caption * 1.45,
  },

  // Quick Demo Trigger
  triggerBar: {
    marginBottom: spacing.base,
  },
  triggerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.accent.subtle,
    borderWidth: 1,
    borderColor: colors.accent.border,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.base,
    borderRadius: radii.sm,
  },
  triggerBtnText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
    letterSpacing: typography.letterSpacing.wide,
  },
  triggerSuccessText: {
    fontSize: typography.fontSize.micro,
    color: colors.status.success,
    textAlign: 'center',
    marginTop: spacing.xs,
    fontFamily: typography.fontFamily.mono,
  },

  // Segmented Filter
  segmentedContainer: {
    flexDirection: 'row',
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: 3,
    marginBottom: spacing.base,
  },
  segmentBtn: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    borderRadius: radii.sm,
  },
  segmentActive: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
  },
  segmentText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
  },
  segmentTextActive: {
    color: colors.text.primary,
  },

  // Task Cards
  loader: {
    marginTop: spacing.xxl,
  },
  headerRightWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  taskSummary: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    lineHeight: typography.fontSize.body * 1.45,
    marginBottom: spacing.sm,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  agentCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    flex: 1,
  },
  agentText: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    fontWeight: typography.fontWeight.medium,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
    paddingTop: spacing.xs + 2,
    marginTop: spacing.xs,
  },
  ageText: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
  },
  countdownBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  countdownText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.status.warning,
    fontFamily: typography.fontFamily.mono,
  },
  decidedInfoText: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.mono,
  },
  btnDisabled: {
    opacity: 0.6,
  },
});
