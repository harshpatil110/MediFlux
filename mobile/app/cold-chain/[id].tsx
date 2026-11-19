/**
 * Cold-Chain Batch Telemetry & Excursion Audit View (Task M7).
 * Displays native SVG telemetry chart, Arrhenius degradation breakdown,
 * Excursion Analyst explanation, and rebalancing cascade trace deep-links.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Platform,
} from 'react-native';
import { useLocalSearchParams, useRouter, Stack } from 'expo-router';
import {
  ArrowLeft,
  ShieldAlert,
  Thermometer,
  Layers,
  GitBranch,
  FileCheck2,
  ExternalLink,
} from 'lucide-react-native';
import { apiClient } from '../../src/api/client';
import { TelemetryChart, ColdChainBatchItem } from '../../src/features/coldchain';

export default function ColdChainBatchDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [batch, setBatch] = useState<ColdChainBatchItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBatchDetail = useCallback(async () => {
    if (!id) return;
    try {
      setError(null);
      const res = await apiClient.get<ColdChainBatchItem>(`/api/v1/coldchain/batches/${id}`);
      setBatch(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load cold-chain batch details.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [id]);

  useEffect(() => {
    void fetchBatchDetail();
  }, [fetchBatchDetail]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    void fetchBatchDetail();
  }, [fetchBatchDetail]);

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#00AEBB" />
        <Text style={styles.loadingText}>Fetching telemetry records...</Text>
      </View>
    );
  }

  if (error || !batch) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>{error || 'Batch not found.'}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={fetchBatchDetail}>
          <Text style={styles.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const isQuarantined = batch.status === 'quarantined';
  const isWarn = batch.status === 'warn';
  const statusBadgeBg = isQuarantined ? '#EF4444' : isWarn ? '#F59E0B' : '#10B981';

  const shelf = batch.shelf_life_estimate || {
    nominal_remaining_days: 180,
    estimated_remaining_days: 180,
    shelf_life_pct: 100,
    thermal_penalty_days: 0,
    shock_penalty_days: 0,
    formula_model: 'Arrhenius Degree-Hour Degradation Model',
    decision: 'ok',
  };

  const q = batch.quarantine;

  return (
    <>
      <Stack.Screen
        options={{
          title: `Batch ${batch.batch_no}`,
          headerShown: false,
        }}
      />
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#00AEBB"
            colors={['#00AEBB']}
          />
        }
      >
        {/* Navigation Bar */}
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
        >
          <ArrowLeft size={18} color="#031211" />
          <Text style={styles.backButtonText}>Cold-Chain Monitor</Text>
        </TouchableOpacity>

        {/* Batch Header Card */}
        <View style={[styles.headerCard, isQuarantined && styles.headerCardQuarantined]}>
          <View style={styles.headerRow}>
            <View style={styles.headerTitleCol}>
              <Text style={styles.productName}>{batch.product_name}</Text>
              <Text style={styles.skuText}>
                SKU: <Text style={styles.monoText}>{batch.sku}</Text>
              </Text>
              <Text style={styles.batchNoText}>
                Batch: <Text style={styles.monoText}>{batch.batch_no}</Text>
              </Text>
            </View>
            <View style={[styles.statusBadge, { backgroundColor: statusBadgeBg }]}>
              <Text style={styles.statusBadgeText}>
                {batch.status.toUpperCase()}
              </Text>
            </View>
          </View>

          <Text style={styles.nodeText}>📍 Location: {batch.node_name}</Text>

          <View style={styles.stockStrip}>
            <Text style={styles.stockLabel}>Available Shelf Stock:</Text>
            <Text style={[styles.stockValue, isQuarantined && styles.stockValueZero]}>
              {isQuarantined ? '0 units (LOCKED IN QUARANTINE)' : `${batch.available_quantity} units`}
            </Text>
          </View>
        </View>

        {/* Excursion Analyst Quarantine Section */}
        {isQuarantined && q && (
          <View style={styles.quarantineAlertCard}>
            <View style={styles.alertHeader}>
              <ShieldAlert size={20} color="#EF4444" />
              <Text style={styles.alertTitle}>EXCURSION ANALYST AUTONOMOUS QUARANTINE</Text>
            </View>

            <Text style={styles.quarantineExplanation}>
              {q.explanation || q.reason}
            </Text>

            <View style={styles.quarantineMetaGrid}>
              <View style={styles.metaRow}>
                <Text style={styles.metaKey}>ACTION STATUS:</Text>
                <Text style={styles.metaValRed}>AUTOMATICALLY QUARANTINED</Text>
              </View>

              {q.audit_entry_id ? (
                <View style={styles.metaRow}>
                  <Text style={styles.metaKey}>AUDIT LEDGER SEQ:</Text>
                  <Text style={styles.metaValMono}>#{q.audit_entry_id}</Text>
                </View>
              ) : null}

              {q.correlation_id ? (
                <View style={styles.metaRow}>
                  <Text style={styles.metaKey}>CASCADE TRACE ID:</Text>
                  <Text style={styles.metaValMono}>{q.correlation_id}</Text>
                </View>
              ) : null}
            </View>

            {q.correlation_id && (
              <TouchableOpacity
                style={styles.cascadeLinkBtn}
                activeOpacity={0.85}
                onPress={() => router.push(`/cascade/${q.correlation_id}` as any)}
              >
                <GitBranch size={16} color="#FFFFFF" />
                <Text style={styles.cascadeLinkBtnText}>
                  View Dynamic Rebalancing Cascade Trace →
                </Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Native SVG Telemetry Chart */}
        <TelemetryChart
          readings={batch.readings || []}
          storageMinC={batch.storage_min_c ?? 2.0}
          storageMaxC={batch.storage_max_c ?? 8.0}
          height={210}
        />

        {/* Arrhenius Shelf-Life Model Breakdown */}
        <View style={styles.shelfLifeCard}>
          <View style={styles.sectionHeader}>
            <Thermometer size={16} color="#00AEBB" />
            <Text style={styles.sectionTitle}>ARRHENIUS SHELF-LIFE DEGRADATION</Text>
          </View>

          <View style={styles.shelfGrid}>
            <View style={styles.shelfRow}>
              <Text style={styles.shelfRowLabel}>Nominal Remaining Life:</Text>
              <Text style={styles.shelfRowValue}>
                {shelf.nominal_remaining_days.toFixed(1)} days
              </Text>
            </View>

            <View style={styles.shelfRow}>
              <Text style={styles.shelfRowLabel}>Thermal Excursion Penalty:</Text>
              <Text style={[styles.shelfRowValue, shelf.thermal_penalty_days > 0 && styles.penaltyText]}>
                -{shelf.thermal_penalty_days.toFixed(1)} days
              </Text>
            </View>

            <View style={styles.shelfRow}>
              <Text style={styles.shelfRowLabel}>Mechanical Shock Penalty:</Text>
              <Text style={styles.shelfRowValue}>
                -{shelf.shock_penalty_days.toFixed(1)} days
              </Text>
            </View>

            <View style={styles.divider} />

            <View style={styles.shelfRowTotal}>
              <Text style={styles.totalLabel}>Effective Remaining Life:</Text>
              <Text
                style={[
                  styles.totalValue,
                  { color: isQuarantined ? '#EF4444' : isWarn ? '#F59E0B' : '#00AEBB' },
                ]}
              >
                {isQuarantined ? '0.0 days (Quarantined)' : `${shelf.estimated_remaining_days.toFixed(1)} days (${Math.round(shelf.shelf_life_pct)}%)`}
              </Text>
            </View>
          </View>

          <Text style={styles.formulaNotice}>
            Formula: {shelf.formula_model || 'Arrhenius Degree-Hour Degradation Model'}
          </Text>
        </View>

        {/* Audit Compliance Verification */}
        <View style={styles.complianceCard}>
          <View style={styles.sectionHeader}>
            <FileCheck2 size={16} color="#10B981" />
            <Text style={styles.sectionTitle}>REGULATORY & AUDIT INTEGRITY</Text>
          </View>
          <Text style={styles.complianceText}>
            All IoT sensor transmissions are cryptographically chained to public.audit_ledger using SHA-256 tamper-evident seals. Batch quarantine actions invoke the Dynamic Balancing Agent to reorder stock automatically.
          </Text>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#E8E4D3',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#E8E4D3',
    padding: 24,
  },
  loadingText: {
    fontSize: 13,
    color: '#5C584E',
    marginTop: 10,
  },
  errorText: {
    fontSize: 14,
    color: '#EF4444',
    textAlign: 'center',
    marginBottom: 12,
  },
  retryBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: '#031211',
    borderRadius: 6,
  },
  retryBtnText: {
    color: '#F7F5F0',
    fontSize: 12,
    fontWeight: '700',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 6,
  },
  backButtonText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#031211',
  },
  headerCard: {
    backgroundColor: '#F7F5F0',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#D8D3C3',
    padding: 14,
    marginBottom: 12,
  },
  headerCardQuarantined: {
    borderColor: '#EF4444',
    borderWidth: 1.5,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  headerTitleCol: {
    flex: 1,
    marginRight: 8,
  },
  productName: {
    fontSize: 16,
    fontWeight: '800',
    color: '#031211',
  },
  skuText: {
    fontSize: 12,
    color: '#5C584E',
    marginTop: 2,
  },
  batchNoText: {
    fontSize: 12,
    color: '#5C584E',
    marginTop: 1,
  },
  nodeText: {
    fontSize: 12,
    color: '#5C584E',
    marginTop: 6,
    marginBottom: 10,
  },
  monoText: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontWeight: '700',
    color: '#031211',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#FFFFFF',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  stockStrip: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#DFDBCA',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  stockLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#5C584E',
  },
  stockValue: {
    fontSize: 12,
    fontWeight: '800',
    color: '#031211',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  stockValueZero: {
    color: '#EF4444',
  },
  quarantineAlertCard: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1.5,
    borderColor: '#EF4444',
    borderRadius: 8,
    padding: 14,
    marginBottom: 12,
  },
  alertHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  alertTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: '#991B1B',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 0.5,
  },
  quarantineExplanation: {
    fontSize: 13,
    color: '#7F1D1D',
    lineHeight: 18,
    marginBottom: 10,
  },
  quarantineMetaGrid: {
    backgroundColor: '#FFFFFF',
    borderRadius: 6,
    padding: 10,
    gap: 4,
    marginBottom: 10,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  metaKey: {
    fontSize: 10,
    fontWeight: '700',
    color: '#5C584E',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  metaValRed: {
    fontSize: 10,
    fontWeight: '800',
    color: '#DC2626',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  metaValMono: {
    fontSize: 10,
    fontWeight: '700',
    color: '#031211',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  cascadeLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#991B1B',
    paddingVertical: 10,
    borderRadius: 6,
  },
  cascadeLinkBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  shelfLifeCard: {
    backgroundColor: '#F7F5F0',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#D8D3C3',
    padding: 14,
    marginTop: 8,
    marginBottom: 12,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: '#031211',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 0.5,
  },
  shelfGrid: {
    gap: 6,
  },
  shelfRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  shelfRowLabel: {
    fontSize: 12,
    color: '#5C584E',
  },
  shelfRowValue: {
    fontSize: 12,
    fontWeight: '700',
    color: '#031211',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  penaltyText: {
    color: '#EF4444',
  },
  divider: {
    height: 1,
    backgroundColor: '#D8D3C3',
    marginVertical: 4,
  },
  shelfRowTotal: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  totalLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: '#031211',
  },
  totalValue: {
    fontSize: 13,
    fontWeight: '800',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  formulaNotice: {
    fontSize: 10,
    color: '#8C887B',
    marginTop: 8,
    fontStyle: 'italic',
  },
  complianceCard: {
    backgroundColor: '#F7F5F0',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#D8D3C3',
    padding: 14,
  },
  complianceText: {
    fontSize: 12,
    color: '#5C584E',
    lineHeight: 17,
  },
});
