import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { usePendingHitlTasks } from '../../src/api/hooks';
import { apiClient } from '../../src/api/client';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';
import { EmptyState } from '../../src/components/EmptyState';

export default function ApprovalsScreen() {
  const { data: tasks, loading, refetch } = usePendingHitlTasks();
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const handleDecision = async (taskId: string, decision: 'approved' | 'rejected') => {
    setDecidingId(taskId);
    try {
      await apiClient.post(`/api/v1/hitl/${taskId}/decision`, {
        decision,
        reason: `Field decision submitted from mobile operator client`,
      });
      await refetch();
    } catch {
      // In Task M1, refresh to clear
      await refetch();
    } finally {
      setDecidingId(null);
    }
  };

  const pendingList = tasks || [];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={refetch} tintColor={colors.accent.primary} />
      }
    >
      <View style={styles.header}>
        <View style={styles.tagRow}>
          <Text style={styles.subtitle}>HUMAN-IN-THE-LOOP CONTROL PLANE</Text>
          <Badge
            label={pendingList.length > 0 ? `${pendingList.length} PENDING` : 'ALL CLEAR'}
            variant={pendingList.length > 0 ? 'amber' : 'emerald'}
          />
        </View>
        <Text style={styles.title}>Field Approvals Queue</Text>
        <Text style={styles.description}>
          Autonomous agent recommendations exceeding confidence or risk thresholds require operator sign-off.
        </Text>
      </View>

      {loading && pendingList.length === 0 ? (
        <ActivityIndicator size="large" color={colors.accent.primary} style={styles.loader} />
      ) : pendingList.length === 0 ? (
        <EmptyState
          title="No Pending Approvals"
          description="All autonomous purchase orders, batch transfers, and quarantine actions are cleared."
          actionLabel="REFRESH QUEUE"
          onAction={refetch}
        />
      ) : (
        pendingList.map((task: any) => {
          const isProcessing = decidingId === task.id;
          return (
            <Card
              key={task.id}
              title={task.title || `Task #${task.id?.slice(0, 8)}`}
              subtitle={task.task_type || 'DECISION REQUIRED'}
              headerRight={
                <Badge
                  label={task.risk_level || 'HIGH RISK'}
                  variant={task.risk_level === 'high' ? 'coral' : 'amber'}
                />
              }
            >
              <Text style={styles.taskDesc}>{task.description || task.summary}</Text>

              {task.proposed_action && (
                <View style={styles.actionPreview}>
                  <Text style={styles.actionPreviewLabel}>PROPOSED AGENT ACTION:</Text>
                  <Text style={styles.actionPreviewText}>{JSON.stringify(task.proposed_action)}</Text>
                </View>
              )}

              <View style={styles.actionsRow}>
                <TouchableOpacity
                  style={[styles.rejectBtn, isProcessing && styles.btnDisabled]}
                  onPress={() => handleDecision(task.id, 'rejected')}
                  disabled={isProcessing}
                  activeOpacity={0.8}
                >
                  <Text style={styles.rejectBtnText}>REJECT</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.approveBtn, isProcessing && styles.btnDisabled]}
                  onPress={() => handleDecision(task.id, 'approved')}
                  disabled={isProcessing}
                  activeOpacity={0.8}
                >
                  {isProcessing ? (
                    <ActivityIndicator size="small" color={colors.text.onAccent} />
                  ) : (
                    <Text style={styles.approveBtnText}>APPROVE ACTION →</Text>
                  )}
                </TouchableOpacity>
              </View>
            </Card>
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
  loader: {
    marginTop: spacing.xxl,
  },
  taskDesc: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    lineHeight: typography.fontSize.body * 1.45,
    marginBottom: spacing.md,
  },
  actionPreview: {
    backgroundColor: colors.canvas.elevated,
    padding: spacing.sm,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    marginBottom: spacing.md,
  },
  actionPreviewLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: 2,
  },
  actionPreviewText: {
    fontSize: typography.fontSize.micro,
    fontFamily: 'monospace',
    color: colors.text.primary,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  rejectBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.status.danger,
    backgroundColor: colors.status.dangerSubtle,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
    alignItems: 'center',
  },
  rejectBtnText: {
    color: colors.status.danger,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  approveBtn: {
    flex: 2,
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
    alignItems: 'center',
  },
  approveBtnText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  btnDisabled: {
    opacity: 0.6,
  },
});

