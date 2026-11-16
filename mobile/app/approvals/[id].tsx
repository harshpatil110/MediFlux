import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Modal,
  ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as LocalAuthentication from 'expo-local-authentication';
import { apiClient } from '../../src/api/client';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';
import { TaskPayloadRenderer } from '../../src/features/approvals/renderers';
import { useAuth } from '../../src/features/auth/AuthContext';
import { formatDateTime } from '../../src/lib/format';

interface ServerOutcome {
  status: string;
  outcome?: string;
  already_finalized?: boolean;
  resumed_cascade_correlation_id?: string;
  audit_entry_id?: string;
  decided_by?: string;
  decided_at?: string;
  decision_note?: string;
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

export default function ApprovalDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();

  const [task, setTask] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Decision state
  const [decisionNote, setDecisionNote] = useState<string>('');
  const [confirmModalVisible, setConfirmModalVisible] = useState<boolean>(false);
  const [chosenAction, setChosenAction] = useState<'approved' | 'rejected' | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [outcome, setOutcome] = useState<ServerOutcome | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [, setTick] = useState<number>(0);

  const fetchTask = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<any>(`/api/v1/hitl/tasks/${id}`);
      setTask(data);
      if (data?.status && data.status !== 'pending') {
        setOutcome({
          status: data.status,
          outcome: data.status,
          already_finalized: true,
          decided_by: data.decided_by,
          decided_at: data.decided_at,
          decision_note: data.decision_note,
          resumed_cascade_correlation_id: data.correlation_id,
          audit_entry_id: data.audit_entry_id,
        });
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load task details.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchTask();
  }, [fetchTask]);

  // Live timer tick
  useEffect(() => {
    const timer = setInterval(() => {
      setTick((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const openConfirmation = (action: 'approved' | 'rejected') => {
    setChosenAction(action);
    setSubmissionError(null);
    setConfirmModalVisible(true);
  };

  const handleExecuteDecision = async () => {
    if (!chosenAction || !id) return;

    // Biometric Authentication (Optional / Graceful Fallback)
    try {
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();
      if (hasHardware && isEnrolled) {
        const bioResult = await LocalAuthentication.authenticateAsync({
          promptMessage: `Confirm MediFlux HITL ${chosenAction.toUpperCase()}`,
          cancelLabel: 'Cancel',
          disableDeviceFallback: false,
        });
        if (!bioResult.success) {
          setSubmissionError('Biometric authentication cancelled or failed.');
          return;
        }
      }
    } catch {
      // Proceed on web or emulators
    }

    setConfirmModalVisible(false);
    setSubmitting(true);
    setSubmissionError(null);

    const note =
      decisionNote.trim() ||
      (chosenAction === 'approved'
        ? 'Approved via mobile operator credentials.'
        : 'Rejected via mobile operator credentials.');

    try {
      const res = await apiClient.post<any>(`/api/v1/hitl/tasks/${id}/decision`, {
        decision: chosenAction,
        note,
      });

      setOutcome({
        status: res.status || (chosenAction === 'approved' ? 'approved' : 'rejected'),
        outcome: res.outcome,
        already_finalized: res.already_finalized,
        resumed_cascade_correlation_id:
          res.resumed_cascade_correlation_id || task?.correlation_id,
        audit_entry_id: res.audit_entry_id || task?.audit_entry_id,
        decided_by: res.decided_by || user?.email,
        decided_at: res.decided_at || new Date().toISOString(),
        decision_note: note,
      });

      if (res.task) {
        setTask(res.task);
      }
    } catch (err: any) {
      if (err?.status === 403 || err?.code === 'HITL_FORBIDDEN_ROLE') {
        setSubmissionError(
          err?.message ||
            `Role '${user?.role?.toUpperCase()}' is not authorized to decide this task under config/hitl_policies.yaml.`
        );
      } else {
        setSubmissionError(err?.message || 'Failed to submit decision.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.accent.primary} />
        <Text style={styles.loadingText}>Retrieving Task Details...</Text>
      </View>
    );
  }

  if (error || !task) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle-outline" size={36} color={colors.status.danger} />
        <Text style={styles.errorTitle}>Task Unavailable</Text>
        <Text style={styles.errorSubtitle}>{error || 'The requested HITL task could not be found.'}</Text>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Text style={styles.backBtnText}>← Return to Approvals Queue</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const isPending = task.status === 'pending' && !outcome?.status?.includes('approved') && !outcome?.status?.includes('rejected');
  const countdown = formatCountdown(task.expires_at);
  const canDecide = Boolean(task.can_current_user_decide);

  const riskVariant =
    task.risk_level === 'critical' || task.risk_level === 'high'
      ? 'coral'
      : task.risk_level === 'medium'
      ? 'amber'
      : 'neutral';

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Top Navigation Row */}
      <View style={styles.topNavRow}>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.navBackBtn}
          activeOpacity={0.7}
        >
          <Ionicons name="arrow-back" size={18} color={colors.text.primary} />
          <Text style={styles.navBackText}>Approvals</Text>
        </TouchableOpacity>

        <Badge
          label={String(task.task_type || 'APPROVAL').replace(/_/g, ' ').toUpperCase()}
          variant="teal"
        />
      </View>

      {/* Task Header Card */}
      <Card
        title={task.title || `Task #${task.id?.slice(0, 8)}`}
        subtitle={`CORRELATION: ${task.correlation_id || 'STANDALONE'}`}
        headerRight={
          <View style={styles.badgeGroup}>
            <Badge
              label={String(task.risk_level || 'MEDIUM').toUpperCase()}
              variant={riskVariant}
            />
            <Badge
              label={String(task.status || 'PENDING').toUpperCase()}
              variant={
                task.status === 'approved'
                  ? 'emerald'
                  : task.status === 'rejected'
                  ? 'coral'
                  : task.status === 'expired'
                  ? 'neutral'
                  : 'amber'
              }
            />
          </View>
        }
      >
        <Text style={styles.headerSummary}>{task.summary}</Text>

        <View style={styles.headerMetaRow}>
          <View style={styles.headerMetaItem}>
            <Text style={styles.headerMetaLabel}>REQUESTING AGENT</Text>
            <Text style={styles.headerMetaValue}>
              {task.requesting_agent || 'Autonomous Agent'}
            </Text>
          </View>
          <View style={styles.headerMetaItem}>
            <Text style={styles.headerMetaLabel}>ORIGIN NODE</Text>
            <Text style={styles.headerMetaValue}>
              {task.node_name || 'Network Facility'}
            </Text>
          </View>
        </View>

        {isPending && (
          <View style={styles.countdownRow}>
            <Ionicons name="time-outline" size={14} color={colors.status.warning} />
            <Text style={styles.countdownRowText}>
              {countdown.isExpired ? 'TASK WINDOW EXPIRED' : countdown.text}
            </Text>
          </View>
        )}
      </Card>

      {/* Agent Reasoning Section */}
      {task.reasoning && (
        <Card title="Agent Intervention Reasoning" subtitle="AUTONOMOUS EXPLANATION">
          <View style={styles.reasoningBox}>
            <Ionicons name="bulb-outline" size={16} color={colors.accent.primary} />
            <Text style={styles.reasoningText}>{task.reasoning}</Text>
          </View>
        </Card>
      )}

      {/* Type-Specific Payload Renderer */}
      <TaskPayloadRenderer task={task} />

      {/* Related Cascade Timeline Link */}
      {task.correlation_id && (
        <TouchableOpacity
          style={styles.cascadeLinkBtn}
          onPress={() =>
            router.push({
              pathname: '/cascade/[id]',
              params: { id: task.correlation_id },
            } as any)
          }
          activeOpacity={0.8}
        >
          <View style={styles.cascadeLinkLeft}>
            <Ionicons name="git-network-outline" size={18} color={colors.accent.primary} />
            <View>
              <Text style={styles.cascadeLinkTitle}>Related Cascade Timeline</Text>
              <Text style={styles.cascadeLinkSub} numberOfLines={1}>
                Trace: {task.correlation_id}
              </Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.accent.primary} />
        </TouchableOpacity>
      )}

      {/* Cryptographic Audit Ledger Reference */}
      {(task.audit_entry_id || outcome?.audit_entry_id) && (
        <View style={styles.auditReferenceCard}>
          <Ionicons name="shield-checkmark" size={14} color={colors.status.success} />
          <Text style={styles.auditReferenceText}>
            Cryptographic Audit Ledger Block: #{String(task.audit_entry_id || outcome?.audit_entry_id).slice(0, 16)}...
          </Text>
        </View>
      )}

      {/* Server Outcome Card (Strict Non-Optimistic Result) */}
      {outcome && (
        <View
          style={[
            styles.outcomeCard,
            outcome.status === 'approved' && styles.outcomeApproved,
            outcome.status === 'rejected' && styles.outcomeRejected,
            outcome.status === 'expired' && styles.outcomeExpired,
          ]}
        >
          <View style={styles.outcomeHeaderRow}>
            <Ionicons
              name={
                outcome.status === 'approved'
                  ? 'checkmark-circle'
                  : outcome.status === 'rejected'
                  ? 'close-circle'
                  : 'time'
              }
              size={20}
              color={
                outcome.status === 'approved'
                  ? colors.status.success
                  : outcome.status === 'rejected'
                  ? colors.status.danger
                  : colors.status.warning
              }
            />
            <Text
              style={[
                styles.outcomeTitle,
                outcome.status === 'approved' && styles.outcomeTextApproved,
                outcome.status === 'rejected' && styles.outcomeTextRejected,
                outcome.status === 'expired' && styles.outcomeTextExpired,
              ]}
            >
              {outcome.status === 'approved'
                ? '✓ Approved — Paused Agent Graph Resumed'
                : outcome.status === 'rejected'
                ? '✕ Rejected — Agent Action Aborted & Logged'
                : '⏰ Task Expired — Approval Window Closed'}
            </Text>
          </View>

          {outcome.already_finalized && (
            <Text style={styles.outcomeAlreadyFinalizedNote}>
              Note: This task was previously finalized by {outcome.decided_by || 'an operator'}.
            </Text>
          )}

          {outcome.decision_note && (
            <Text style={styles.outcomeNoteText}>"{outcome.decision_note}"</Text>
          )}

          {outcome.decided_at && (
            <Text style={styles.outcomeMetaText}>
              Decided by {outcome.decided_by || 'operator'} at {formatDateTime(outcome.decided_at)}
            </Text>
          )}

          {outcome.status === 'approved' && outcome.resumed_cascade_correlation_id && (
            <TouchableOpacity
              style={styles.watchCascadeBtn}
              onPress={() =>
                router.push({
                  pathname: '/cascade/[id]',
                  params: { id: outcome.resumed_cascade_correlation_id },
                } as any)
              }
              activeOpacity={0.8}
            >
              <Text style={styles.watchCascadeBtnText}>Watch Resumed Cascade Timeline →</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Submission Error Banner */}
      {submissionError && (
        <View style={styles.submissionErrorBox}>
          <Ionicons name="alert-circle" size={16} color={colors.status.danger} />
          <Text style={styles.submissionErrorText}>{submissionError}</Text>
        </View>
      )}

      {/* Decision Section (Visible only when task is pending and not yet decided locally) */}
      {isPending && !outcome && (
        <Card title="Operator Field Decision" subtitle="HUMAN-IN-THE-LOOP ACTION">
          {!canDecide ? (
            <View style={styles.restrictedBox}>
              <Ionicons name="lock-closed" size={18} color={colors.status.danger} />
              <Text style={styles.restrictedText}>
                {task.cannot_decide_reason ||
                  `🔒 Decision Restricted: Your role (${user?.role?.toUpperCase()}) does not have approver rights for this task under config/hitl_policies.yaml.`}
              </Text>
            </View>
          ) : (
            <View>
              <Text style={styles.inputLabel}>DECISION JUSTIFICATION NOTE</Text>
              <TextInput
                style={styles.textInput}
                placeholder="Enter justification note for audit ledger..."
                placeholderTextColor={colors.text.muted}
                value={decisionNote}
                onChangeText={setDecisionNote}
                multiline
                numberOfLines={3}
              />

              {/* Quick Fill Chips */}
              <View style={styles.quickChipsRow}>
                {['Customs transit permit verified', 'Approved post QA inspection', 'Schedule H override cleared'].map(
                  (chip, idx) => (
                    <TouchableOpacity
                      key={idx}
                      style={styles.quickChip}
                      onPress={() => setDecisionNote(chip)}
                      activeOpacity={0.7}
                    >
                      <Text style={styles.quickChipText}>{chip}</Text>
                    </TouchableOpacity>
                  )
                )}
              </View>

              {/* Action Buttons */}
              <View style={styles.decisionActionsRow}>
                <TouchableOpacity
                  style={[styles.actionBtn, styles.rejectBtn, submitting && styles.btnDisabled]}
                  onPress={() => openConfirmation('rejected')}
                  disabled={submitting}
                  activeOpacity={0.8}
                >
                  <Ionicons name="close-outline" size={16} color={colors.status.danger} />
                  <Text style={styles.rejectBtnText}>REJECT</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.actionBtn, styles.approveBtn, submitting && styles.btnDisabled]}
                  onPress={() => openConfirmation('approved')}
                  disabled={submitting}
                  activeOpacity={0.8}
                >
                  {submitting ? (
                    <ActivityIndicator size="small" color={colors.text.onAccent} />
                  ) : (
                    <>
                      <Ionicons name="checkmark-outline" size={16} color={colors.text.onAccent} />
                      <Text style={styles.approveBtnText}>APPROVE ACTION →</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          )}
        </Card>
      )}

      {/* Confirmation Modal with Biometric Trigger */}
      <Modal
        visible={confirmModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setConfirmModalVisible(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Ionicons
                name={chosenAction === 'approved' ? 'shield-checkmark-outline' : 'warning-outline'}
                size={24}
                color={chosenAction === 'approved' ? colors.accent.primary : colors.status.danger}
              />
              <Text style={styles.modalTitle}>
                Confirm {chosenAction?.toUpperCase()}
              </Text>
            </View>

            <Text style={styles.modalBodyText}>
              You are about to record a permanent cryptographic audit ledger decision for task:
            </Text>
            <Text style={styles.modalTaskTitle}>"{task.title}"</Text>

            {decisionNote ? (
              <View style={styles.modalNoteBox}>
                <Text style={styles.modalNoteLabel}>JUSTIFICATION:</Text>
                <Text style={styles.modalNoteText}>"{decisionNote}"</Text>
              </View>
            ) : null}

            <Text style={styles.modalBiometricPrompt}>
              Press confirm to verify identity via device biometrics / security credentials.
            </Text>

            <View style={styles.modalActionsRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setConfirmModalVisible(false)}
                activeOpacity={0.8}
              >
                <Text style={styles.modalCancelText}>CANCEL</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[
                  styles.modalConfirmBtn,
                  chosenAction === 'rejected' && styles.modalConfirmReject,
                ]}
                onPress={handleExecuteDecision}
                activeOpacity={0.8}
              >
                <Text style={styles.modalConfirmText}>
                  CONFIRM {chosenAction?.toUpperCase()}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
    paddingBottom: spacing.xxl * 3,
    gap: spacing.base,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing.sm,
  },
  loadingText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  errorTitle: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  errorSubtitle: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    textAlign: 'center',
  },
  backBtn: {
    marginTop: spacing.base,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    backgroundColor: colors.accent.subtle,
    borderWidth: 1,
    borderColor: colors.accent.border,
    borderRadius: radii.sm,
  },
  backBtnText: {
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.bold,
    fontSize: typography.fontSize.caption,
  },

  // Nav Row
  topNavRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  navBackBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  navBackText: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },

  // Header Card
  badgeGroup: {
    flexDirection: 'row',
    gap: spacing.xs,
  },
  headerSummary: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    lineHeight: typography.fontSize.body * 1.45,
    marginBottom: spacing.md,
  },
  headerMetaRow: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
    paddingTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  headerMetaItem: {
    flex: 1,
  },
  headerMetaLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: 2,
  },
  headerMetaValue: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
  },
  countdownRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.status.warningSubtle,
    padding: spacing.xs + 2,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.status.warning,
  },
  countdownRowText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.status.warning,
    fontFamily: typography.fontFamily.mono,
  },

  // Reasoning
  reasoningBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    backgroundColor: colors.canvas.elevated,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.subtle,
  },
  reasoningText: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    flex: 1,
    lineHeight: typography.fontSize.body * 1.45,
  },

  // Cascade Link
  cascadeLinkBtn: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.accent.border,
    padding: spacing.md,
    borderRadius: radii.md,
  },
  cascadeLinkLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1,
  },
  cascadeLinkTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  cascadeLinkSub: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.mono,
  },

  // Audit Reference
  auditReferenceCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    padding: spacing.sm,
    borderRadius: radii.sm,
  },
  auditReferenceText: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.secondary,
    flex: 1,
  },

  // Server Outcome
  outcomeCard: {
    padding: spacing.base,
    borderRadius: radii.md,
    borderWidth: 1,
    gap: spacing.xs,
  },
  outcomeApproved: {
    backgroundColor: colors.status.successSubtle,
    borderColor: colors.status.success,
  },
  outcomeRejected: {
    backgroundColor: colors.status.dangerSubtle,
    borderColor: colors.status.danger,
  },
  outcomeExpired: {
    backgroundColor: colors.status.warningSubtle,
    borderColor: colors.status.warning,
  },
  outcomeHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  outcomeTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
  },
  outcomeTextApproved: {
    color: colors.status.success,
  },
  outcomeTextRejected: {
    color: colors.status.danger,
  },
  outcomeTextExpired: {
    color: colors.status.warning,
  },
  outcomeAlreadyFinalizedNote: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    fontStyle: 'italic',
  },
  outcomeNoteText: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    fontStyle: 'italic',
  },
  outcomeMetaText: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.mono,
  },
  watchCascadeBtn: {
    marginTop: spacing.xs,
    alignSelf: 'flex-start',
    backgroundColor: colors.status.success,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm,
  },
  watchCascadeBtnText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
  },

  // Submission Error
  submissionErrorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.status.dangerSubtle,
    borderWidth: 1,
    borderColor: colors.status.danger,
    padding: spacing.sm,
    borderRadius: radii.sm,
  },
  submissionErrorText: {
    fontSize: typography.fontSize.caption,
    color: colors.status.danger,
    flex: 1,
  },

  // Decision Card
  restrictedBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.status.dangerSubtle,
    borderWidth: 1,
    borderColor: colors.status.danger,
    padding: spacing.md,
    borderRadius: radii.sm,
  },
  restrictedText: {
    fontSize: typography.fontSize.caption,
    color: colors.status.danger,
    flex: 1,
    lineHeight: typography.fontSize.caption * 1.45,
    fontWeight: typography.fontWeight.medium,
  },
  inputLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: spacing.xs,
  },
  textInput: {
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.sm,
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    minHeight: 64,
    textAlignVertical: 'top',
    marginBottom: spacing.sm,
  },
  quickChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.base,
  },
  quickChip: {
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.sm,
  },
  quickChipText: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
  },
  decisionActionsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
  },
  rejectBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.status.danger,
    backgroundColor: colors.status.dangerSubtle,
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

  // Modal
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(3, 18, 17, 0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.base,
  },
  modalCard: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.md,
    padding: spacing.base,
    gap: spacing.sm,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  modalTitle: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.black,
    color: colors.text.primary,
  },
  modalBodyText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
  },
  modalTaskTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  modalNoteBox: {
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    padding: spacing.sm,
    borderRadius: radii.sm,
  },
  modalNoteLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
  },
  modalNoteText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontStyle: 'italic',
  },
  modalBiometricPrompt: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    fontStyle: 'italic',
  },
  modalActionsRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  modalCancelBtn: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.base,
    borderRadius: radii.sm,
  },
  modalCancelText: {
    color: colors.text.secondary,
    fontWeight: typography.fontWeight.bold,
    fontSize: typography.fontSize.caption,
  },
  modalConfirmBtn: {
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.base,
    borderRadius: radii.sm,
  },
  modalConfirmReject: {
    backgroundColor: colors.status.danger,
  },
  modalConfirmText: {
    color: colors.text.onAccent,
    fontWeight: typography.fontWeight.bold,
    fontSize: typography.fontSize.caption,
    letterSpacing: typography.letterSpacing.wide,
  },
});
