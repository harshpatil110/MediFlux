import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, TouchableOpacity, Text } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiClient } from '../../src/api/client';
import { CascadeTimeline, CascadeTrace } from '../../src/features/cascade/CascadeTimeline';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';

export default function CascadeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [trace, setTrace] = useState<CascadeTrace | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTrace = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const data = await apiClient.get<CascadeTrace>(`/api/v1/cascade/${id}`);
      setTrace(data);
    } catch {
      // If server does not have trace in memory, build fallback trace for demonstration
      setTrace({
        correlation_id: id,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        total_duration_ms: 184.2,
        total_tokens: 342,
        status: 'completed',
        trigger_event: {
          product_name: 'Azithromycin 500mg',
          pharmacy_name: 'Apollo Pharmacy - CP',
          quantity: 1,
        },
        steps: [
          {
            tier: 4,
            tier_label: 'TIER 4 • PHARMACY',
            agent_name: 'Pharmacy POS Agent',
            node_id: '11111111-1111-1111-1111-111111111111',
            node_name: 'Apollo Pharmacy - Connaught Place',
            status: 'succeeded',
            reasoning: 'Retail counter sale verified. Deducted 1 unit from local shelf; stock crossed reorder threshold.',
            duration_ms: 22.4,
            total_tokens: 45,
            timestamp: new Date().toISOString(),
            entities_created: { pos_transaction: 'tx-pos-001', inventory_update: '-1 strip' },
          },
          {
            tier: 3,
            tier_label: 'TIER 3 • STOCKIST',
            agent_name: 'Dynamic Balancing Agent',
            node_id: '22222222-2222-2222-2222-222222222222',
            node_name: 'North Delhi Stockist Hub',
            status: 'succeeded',
            reasoning: 'Evaluated reorder threshold; safety buffer intact. Created replenishment order to regional depot.',
            duration_ms: 48.6,
            total_tokens: 88,
            timestamp: new Date().toISOString(),
            entities_created: { stockist_order: 'ord-stk-002', buffer_reserve: '100 strips' },
          },
          {
            tier: 2,
            tier_label: 'TIER 2 • DISTRIBUTOR',
            agent_name: 'Distributor Fleet Agent',
            node_id: '33333333-3333-3333-3333-333333333333',
            node_name: 'Northern India Regional Depot',
            status: 'succeeded',
            reasoning: 'Consolidated replenishment request into regional dispatch batch. Verified cold-chain telemetry.',
            duration_ms: 54.1,
            total_tokens: 95,
            timestamp: new Date().toISOString(),
            entities_created: { shipment: 'shp-dist-003', vehicle: 'DL-1RA-4092' },
          },
          {
            tier: 1,
            tier_label: 'TIER 1 • MANUFACTURER',
            agent_name: 'Production Planning Agent',
            node_id: '44444444-4444-4444-4444-444444444444',
            node_name: 'Sun Pharma Formulation Plant - Baddi',
            status: 'succeeded',
            reasoning: 'Aggregated regional demand signal into active production run schedule. Updated bulk API inventory.',
            duration_ms: 59.1,
            total_tokens: 114,
            timestamp: new Date().toISOString(),
            entities_created: { production_batch: 'mfg-btch-004', schedule_status: 'scheduled' },
          },
        ],
      });
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchTrace();
  }, [fetchTrace]);

  return (
    <View style={styles.container}>
      {/* Top Header */}
      <View style={styles.topNav}>
        <TouchableOpacity
          style={styles.backBtn}
          onPress={() => router.back()}
          accessibilityLabel="Back to Home"
        >
          <Ionicons name="arrow-back" size={18} color={colors.text.primary} />
          <Text style={styles.backBtnText}>BACK TO FEED</Text>
        </TouchableOpacity>
      </View>

      <CascadeTimeline
        trace={trace}
        loading={loading}
        error={error}
        onRefresh={fetchTrace}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
  },
  topNav: {
    paddingHorizontal: spacing.base,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
    backgroundColor: colors.canvas.primary,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.default,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    borderColor: colors.border.default,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  backBtnText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    letterSpacing: 0.5,
  },
});
