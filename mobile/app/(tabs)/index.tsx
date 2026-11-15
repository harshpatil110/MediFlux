import React from 'react';
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
import { useNodes, useInventory, usePendingHitlTasks, useColdChainBatches } from '../../src/api/hooks';
import { apiClient } from '../../src/api/client';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';
import { formatRoleName } from '../../src/lib/format';

export default function HomeScreen() {
  const router = useRouter();
  const auth = apiClient.getAuth();
  const { data: nodes, loading: loadingNodes, refetch: refetchNodes } = useNodes();
  const { data: inventory, loading: loadingInv, refetch: refetchInv } = useInventory();
  const { data: hitlTasks, refetch: refetchHitl } = usePendingHitlTasks();
  const { data: coldBatches, refetch: refetchCold } = useColdChainBatches();

  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([refetchNodes(), refetchInv(), refetchHitl(), refetchCold()]);
    setRefreshing(false);
  };

  const pendingCount = hitlTasks?.length ?? 0;
  const coldCount = coldBatches?.length ?? 0;
  const nodeCount = nodes?.length ?? 0;
  const invCount = inventory?.length ?? 0;

  const currentRole = auth.role || 'pharmacy';

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent.primary} />
      }
    >
      {/* Node & Session Scope Header */}
      <View style={styles.header}>
        <View style={styles.roleTag}>
          <Text style={styles.headerSubtitle}>CURRENT OPERATIONAL NODE</Text>
          <Badge label={formatRoleName(currentRole)} variant="teal" />
        </View>
        <Text style={styles.headerTitle}>
          {auth.nodeId ? `Node ${auth.nodeId}` : 'Apollo Pharmacy — CP'}
        </Text>
        <Text style={styles.headerMeta}>
          Autonomous demand cascade propagation enabled across 4 supply tiers.
        </Text>
      </View>

      {/* Network Metrics Cards */}
      <View style={styles.metricsGrid}>
        <View style={styles.metricCard}>
          <Text style={styles.metricValue}>{nodeCount > 0 ? nodeCount : '25'}</Text>
          <Text style={styles.metricLabel}>NETWORK NODES</Text>
        </View>
        <View style={styles.metricCard}>
          <Text style={styles.metricValue}>{invCount > 0 ? invCount : '425'}</Text>
          <Text style={styles.metricLabel}>SKU BATCHES</Text>
        </View>
        <View style={styles.metricCard}>
          <Text style={[styles.metricValue, pendingCount > 0 ? styles.metricAlert : null]}>
            {pendingCount}
          </Text>
          <Text style={styles.metricLabel}>PENDING HITL</Text>
        </View>
        <View style={styles.metricCard}>
          <Text style={styles.metricValue}>{coldCount > 0 ? coldCount : '6'}</Text>
          <Text style={styles.metricLabel}>COLD BATCHES</Text>
        </View>
      </View>

      {/* Operational Actions */}
      <Text style={styles.sectionTitle}>OPERATIONAL MODULES</Text>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push('/(tabs)/sell')}
        activeOpacity={0.7}
      >
        <View style={styles.actionCardHeader}>
          <Text style={styles.actionTitle}>Retail Point of Sale (POS)</Text>
          <Badge label="SINGLE-UNIT CASCADE" variant="teal" />
        </View>
        <Text style={styles.actionDesc}>
          Scan barcode or sell 1 medicine strip to propagate demand upstream to stockist, distributor, and formulation plant.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push('/(tabs)/approvals')}
        activeOpacity={0.7}
      >
        <View style={styles.actionCardHeader}>
          <Text style={styles.actionTitle}>HITL Approvals Queue</Text>
          <Badge
            label={pendingCount > 0 ? `${pendingCount} PENDING` : 'CLEARED'}
            variant={pendingCount > 0 ? 'amber' : 'emerald'}
          />
        </View>
        <Text style={styles.actionDesc}>
          Review and approve autonomous agent purchase orders, quarantine overrides, and credit line escalations.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push('/(tabs)/cold-chain')}
        activeOpacity={0.7}
      >
        <View style={styles.actionCardHeader}>
          <Text style={styles.actionTitle}>Cold Chain Telemetry</Text>
          <Badge label="IOT MONITORED" variant="teal" />
        </View>
        <Text style={styles.actionDesc}>
          Live biologics fridge temperature sensors, Arrhenius kinetic shelf-life degradation, and quarantine alerts.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push('/(tabs)/scan-rx')}
        activeOpacity={0.7}
      >
        <View style={styles.actionCardHeader}>
          <Text style={styles.actionTitle}>Sovereign Rx Scanner</Text>
          <Badge label="SCHEDULE H/H1/X" variant="neutral" />
        </View>
        <Text style={styles.actionDesc}>
          Camera capture and multimodal clinical extraction with CDSCO regulatory compliance validation.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push('/(tabs)/copilot')}
        activeOpacity={0.7}
      >
        <View style={styles.actionCardHeader}>
          <Text style={styles.actionTitle}>Supply Chain Copilot</Text>
          <Badge label="AI ASSISTANT" variant="teal" />
        </View>
        <Text style={styles.actionDesc}>
          Ask natural-language questions about network stock, demand spikes, supplier lead times, and regulatory alerts.
        </Text>
      </TouchableOpacity>

      {/* Live Topology Preview */}
      <Card title="Supply Chain Topology" subtitle="4-Tier Network">
        {loadingNodes ? (
          <ActivityIndicator color={colors.accent.primary} />
        ) : (
          <View style={styles.topologyList}>
            {(nodes || []).slice(0, 4).map((node, i) => (
              <View key={node.id || i} style={styles.topologyItem}>
                <View style={styles.topologyDot} />
                <View style={styles.topologyInfo}>
                  <Text style={styles.topologyName}>{node.name}</Text>
                  <Text style={styles.topologyTier}>
                    {node.tier.toUpperCase()} • {node.city}, {node.state}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </Card>
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
  roleTag: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  headerSubtitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
  },
  headerTitle: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.black,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.tight,
    marginBottom: 4,
  },
  headerMeta: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  metricCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.md,
  },
  metricValue: {
    fontSize: typography.fontSize.h1,
    fontWeight: typography.fontWeight.black,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.tight,
  },
  metricAlert: {
    color: colors.status.warning,
  },
  metricLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: spacing.sm,
  },
  actionCard: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.base,
    marginBottom: spacing.sm,
  },
  actionCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  actionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  actionDesc: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    lineHeight: typography.fontSize.caption * 1.4,
  },
  topologyList: {
    gap: spacing.sm,
  },
  topologyItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  topologyDot: {
    width: 6,
    height: 6,
    backgroundColor: colors.accent.primary,
    borderRadius: radii.full,
    marginRight: spacing.sm,
  },
  topologyInfo: {
    flex: 1,
  },
  topologyName: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  topologyTier: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
  },
});

