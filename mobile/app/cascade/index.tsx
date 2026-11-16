/**
 * Cascade History List Screen (Task M8.2).
 * Displays past multi-tier demand cascades with outcome filters and animated replay navigation.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiClient } from '../../src/api/client';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Badge } from '../../src/components/Badge';

export interface CascadeHistoryItem {
  correlation_id: string;
  product_id?: string;
  product_name: string;
  sku?: string;
  pharmacy_node_id?: string;
  pharmacy_name: string;
  created_at: string;
  timestamp?: string;
  outcome: 'complete' | 'partial' | 'waiting_approval' | string;
  status?: string;
  steps_completed?: number;
  total_steps?: number;
  tiers_completed?: string;
  total_duration_ms: number;
  total_tokens: number;
  summary?: string;
}

type FilterOutcome = 'all' | 'complete' | 'partial' | 'waiting_approval';

export default function CascadeHistoryScreen() {
  const router = useRouter();
  const [cascades, setCascades] = useState<CascadeHistoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [filter, setFilter] = useState<FilterOutcome>('all');
  const [error, setError] = useState<string | null>(null);

  const fetchCascades = useCallback(async () => {
    try {
      setError(null);
      const outcomeQuery = filter !== 'all' ? `&outcome=${filter}` : '';
      const data = await apiClient.get<CascadeHistoryItem[]>(
        `/api/v1/cascade?limit=25${outcomeQuery}`
      );
      setCascades(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load cascade history');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    fetchCascades();
  }, [fetchCascades]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchCascades();
  };

  const renderBadge = (outcome: string) => {
    const norm = outcome.toLowerCase();
    if (norm === 'complete' || norm === 'completed') {
      return <Badge label="COMPLETE" variant="emerald" />;
    } else if (norm === 'waiting_approval' || norm === 'pending') {
      return (
        <View style={styles.badgeWithIcon}>
          <Ionicons name="lock-closed" size={10} color="#B45309" />
          <Badge label="WAITING APPROVAL" variant="amber" />
        </View>
      );
    } else if (norm === 'partial') {
      return <Badge label="PARTIAL" variant="amber" />;
    }
    return <Badge label={outcome.toUpperCase()} variant="neutral" />;
  };

  const renderItem = ({ item }: { item: CascadeHistoryItem }) => {
    const rawOutcome = item.outcome || item.status || 'complete';
    const totalSteps = item.total_steps || 5;
    const completedSteps = item.steps_completed || totalSteps;
    const duration = Math.round(item.total_duration_ms || 0);
    const tokens = item.total_tokens || 0;

    const timeStr = item.created_at || item.timestamp || '';
    const dateFormatted = timeStr ? new Date(timeStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

    return (
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.75}
        onPress={() => router.push(`/cascade/${item.correlation_id}?mode=replay` as any)}
        accessibilityRole="button"
        accessibilityLabel={`Cascade ${item.correlation_id} for ${item.product_name}`}
      >
        {/* Top Header Row */}
        <View style={styles.cardHeader}>
          <View style={styles.productInfo}>
            <Text style={styles.productName} numberOfLines={1}>
              {item.product_name}
            </Text>
            {item.sku && <Text style={styles.skuText}>({item.sku})</Text>}
          </View>
          {renderBadge(rawOutcome)}
        </View>

        {/* Pharmacy Node & Time */}
        <View style={styles.nodeRow}>
          <Ionicons name="storefront-outline" size={13} color={colors.text.secondary} />
          <Text style={styles.nodeNameText} numberOfLines={1}>
            {item.pharmacy_name}
          </Text>
          {dateFormatted ? <Text style={styles.dotSeparator}>•</Text> : null}
          {dateFormatted ? <Text style={styles.timeText}>{dateFormatted}</Text> : null}
        </View>

        {/* Summary text */}
        {item.summary ? (
          <Text style={styles.summaryText} numberOfLines={2}>
            {item.summary}
          </Text>
        ) : null}

        {/* Card Footer with Monospace ID & Telemetry */}
        <View style={styles.cardFooter}>
          <View style={styles.corrIdPill}>
            <Ionicons name="git-network-outline" size={11} color={colors.accent.primary} />
            <Text style={styles.corrIdText} numberOfLines={1}>
              {item.correlation_id}
            </Text>
          </View>

          <View style={styles.telemetryGroup}>
            <Text style={styles.telemetryPill}>
              {completedSteps}/{totalSteps} tiers
            </Text>
            <Text style={styles.telemetryDot}>•</Text>
            <Text style={styles.telemetryPill}>{duration} ms</Text>
            <Text style={styles.telemetryDot}>•</Text>
            <Text style={styles.telemetryPill}>{tokens.toLocaleString()} tok</Text>
          </View>
        </View>

        {/* Tap Action Hint */}
        <View style={styles.replayHintRow}>
          <Text style={styles.replayHintText}>▶ TAP TO ANIMATE REPLAY</Text>
          <Ionicons name="chevron-forward" size={12} color={colors.accent.primary} />
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      {/* Top Header */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => router.back()}
            accessibilityLabel="Back"
          >
            <Ionicons name="arrow-back" size={18} color={colors.text.primary} />
          </TouchableOpacity>
          <View style={styles.headerTitles}>
            <Text style={styles.headerLabel}>OBSERVABILITY & TRACE REPLAY</Text>
            <Text style={styles.headerTitle}>Cascade History</Text>
          </View>
          <TouchableOpacity
            style={styles.copilotNavBtn}
            onPress={() => router.push('/(tabs)/copilot' as any)}
            accessibilityLabel="Open Copilot"
          >
            <Ionicons name="chatbubbles-outline" size={16} color={colors.accent.primary} />
            <Text style={styles.copilotNavText}>COPILOT</Text>
          </TouchableOpacity>
        </View>

        {/* Filter Pills */}
        <View style={styles.filterRow}>
          {(
            [
              { key: 'all', label: 'ALL' },
              { key: 'complete', label: 'COMPLETE' },
              { key: 'partial', label: 'PARTIAL' },
              { key: 'waiting_approval', label: 'WAITING APPROVAL' },
            ] as const
          ).map((p) => {
            const isActive = filter === p.key;
            return (
              <TouchableOpacity
                key={p.key}
                style={[styles.filterPill, isActive && styles.filterPillActive]}
                onPress={() => setFilter(p.key)}
                activeOpacity={0.7}
              >
                <Text style={[styles.filterPillText, isActive && styles.filterPillTextActive]}>
                  {p.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Main List */}
      {loading ? (
        <View style={styles.centerBox}>
          <ActivityIndicator size="large" color={colors.accent.primary} />
          <Text style={styles.loadingText}>Loading cascade runs...</Text>
        </View>
      ) : error ? (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle-outline" size={32} color={colors.status.danger} />
          <Text style={styles.errorTitle}>Failed to Load History</Text>
          <Text style={styles.errorMsg}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={fetchCascades}>
            <Text style={styles.retryBtnText}>RETRY</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={cascades}
          keyExtractor={(item) => item.correlation_id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent.primary}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyBox}>
              <Ionicons name="git-network-outline" size={40} color={colors.text.muted} />
              <Text style={styles.emptyTitle}>No Cascades Found</Text>
              <Text style={styles.emptySubtitle}>
                {filter === 'all'
                  ? 'No past demand cascades recorded yet. Dispense a sale from the counter to trigger one!'
                  : `No cascades matching status "${filter}".`}
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
  },
  header: {
    backgroundColor: colors.canvas.primary,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.default,
    paddingHorizontal: spacing.base,
    paddingTop: spacing.base,
    paddingBottom: spacing.sm,
  },
  headerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  backBtn: {
    padding: 6,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
  },
  headerTitles: {
    flex: 1,
  },
  headerLabel: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.muted,
    letterSpacing: typography.letterSpacing.widest,
  },
  headerTitle: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  copilotNavBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.accent.border,
  },
  copilotNavText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  filterRow: {
    flexDirection: 'row',
    gap: 6,
    flexWrap: 'wrap',
  },
  filterPill: {
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: radii.xs,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
  },
  filterPillActive: {
    backgroundColor: colors.text.primary,
    borderColor: colors.text.primary,
  },
  filterPillText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
  },
  filterPillTextActive: {
    color: colors.text.inverse,
  },
  listContent: {
    padding: spacing.base,
    gap: spacing.md,
  },
  card: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: spacing.xs,
    marginBottom: 4,
  },
  productInfo: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 6,
  },
  productName: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  skuText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.caption,
    color: colors.text.muted,
  },
  badgeWithIcon: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  nodeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginBottom: spacing.xs,
  },
  nodeNameText: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    fontWeight: typography.fontWeight.medium,
  },
  dotSeparator: {
    color: colors.text.muted,
  },
  timeText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.caption,
    color: colors.text.muted,
  },
  summaryText: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: 2,
    marginBottom: spacing.xs,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  corrIdPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.canvas.elevated,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.xs,
    maxWidth: 140,
  },
  corrIdText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.primary,
    fontWeight: typography.fontWeight.bold,
  },
  telemetryGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  telemetryPill: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
  },
  telemetryDot: {
    color: colors.text.muted,
    fontSize: typography.fontSize.micro,
  },
  replayHintRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  replayHintText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
    letterSpacing: typography.letterSpacing.wide,
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
    fontWeight: typography.fontWeight.medium,
  },
  errorBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  errorTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    marginTop: spacing.sm,
  },
  errorMsg: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textAlign: 'center',
    marginTop: 4,
    marginBottom: spacing.md,
  },
  retryBtn: {
    backgroundColor: colors.accent.primary,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
  },
  retryBtnText: {
    color: colors.text.inverse,
    fontWeight: typography.fontWeight.bold,
    fontSize: typography.fontSize.caption,
  },
  emptyBox: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxl,
    gap: spacing.sm,
  },
  emptyTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  emptySubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textAlign: 'center',
    maxWidth: 280,
  },
});
