/**
 * Cold-Chain Telemetry & Autonomous Quarantine Monitor (Task M7).
 * Displays real-time thermal readings, Arrhenius shelf-life estimates,
 * simulation triggers, and quarantine audit history.
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
  Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import {
  Thermometer,
  AlertTriangle,
  Flame,
  CheckCircle2,
  RefreshCw,
  Clock,
  ShieldAlert,
  ArrowRight,
} from 'lucide-react-native';
import { useAuth } from '../../src/features/auth/AuthContext';
import { isTabVisibleForRole } from '../../src/features/auth/roleMap';
import { useEventStream } from '../../src/hooks/useEventStream';
import { apiClient } from '../../src/api/client';
import { ColdChainBatchItem, QuarantineRecord } from '../../src/features/coldchain';

type ViewMode = 'batches' | 'quarantines';
type StatusFilter = 'all' | 'ok' | 'warn' | 'quarantined';

export default function ColdChainScreen() {
  const router = useRouter();
  const { user } = useAuth();

  const [viewMode, setViewMode] = useState<ViewMode>('batches');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [batches, setBatches] = useState<ColdChainBatchItem[]>([]);
  const [quarantines, setQuarantines] = useState<QuarantineRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [simulating, setSimulating] = useState<string | null>(null);

  // Role guard
  useEffect(() => {
    if (user && !isTabVisibleForRole(user.role, 'cold-chain')) {
      router.replace('/(tabs)');
    }
  }, [user, router]);

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const [batchesRes, quarantinesRes] = await Promise.all([
        apiClient.get<any>('/coldchain/batches'),
        apiClient.get<any>('/coldchain/quarantines'),
      ]);

      const rawBatches = Array.isArray(batchesRes) ? batchesRes : batchesRes?.batches || [];
      const rawQuarantines = Array.isArray(quarantinesRes) ? quarantinesRes : quarantinesRes?.quarantines || [];

      setBatches(rawBatches);
      setQuarantines(rawQuarantines);
    } catch {
      // Fallback
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    void fetchData();
  }, [fetchData]);

  // Live SSE listener: refresh when coldchain events arrive
  const { lastEvent } = useEventStream('coldchain');
  useEffect(() => {
    if (lastEvent) {
      void fetchData();
    }
  }, [lastEvent, fetchData]);

  // Simulation handler
  const handleSimulate = async (mode: 'normal' | 'excursion') => {
    setSimulating(mode);
    try {
      await apiClient.post('/coldchain/simulate', {
        mode,
        batch_id: 'BIO-INS-01',
        steps: 4,
      });
      await fetchData();
    } catch {
      // Handled
    } finally {
      setSimulating(null);
    }
  };

  const filteredBatches = batches.filter((b) => {
    if (statusFilter === 'all') return true;
    return b.status === statusFilter;
  });

  const okCount = batches.filter((b) => b.status === 'ok').length;
  const warnCount = batches.filter((b) => b.status === 'warn').length;
  const quarantinedCount = batches.filter((b) => b.status === 'quarantined').length;

  const renderBatchCard = ({ item }: { item: ColdChainBatchItem }) => {
    const isQuarantined = item.status === 'quarantined';
    const isWarn = item.status === 'warn';

    const statusBadgeBg = isQuarantined ? '#EF4444' : isWarn ? '#F59E0B' : '#10B981';
    const statusText = isQuarantined ? 'QUARANTINED' : isWarn ? 'WARN' : 'NOMINAL';

    const lastTemp = item.last_reading?.temperature_c ?? (item.readings?.length ? item.readings[item.readings.length - 1].temperature_c : 5.0);
    const lastHumidity = item.last_reading?.humidity ?? 50;
    const lastShock = item.last_reading?.shock_g ?? 0.2;

    const remainingDays = item.shelf_life_estimate?.estimated_remaining_days ?? 180;
    const shelfPct = Math.max(0, Math.min(100, item.shelf_life_estimate?.shelf_life_pct ?? 100));

    return (
      <TouchableOpacity
        style={[styles.batchCard, isQuarantined && styles.batchCardQuarantined]}
        activeOpacity={0.85}
        onPress={() => router.push(`/cold-chain/${item.batch_id}` as any)}
      >
        <View style={styles.cardHeader}>
          <View style={styles.titleCol}>
            <Text style={styles.productName} numberOfLines={1}>
              {item.product_name}
            </Text>
            <Text style={styles.batchSkuText}>
              {item.sku} • <Text style={styles.batchNo}>{item.batch_no}</Text>
            </Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: statusBadgeBg }]}>
            <Text style={styles.statusBadgeText}>{statusText}</Text>
          </View>
        </View>

        <Text style={styles.nodeNameText}>📍 {item.node_name}</Text>

        {/* Sensor Readings Strip */}
        <View style={styles.readingsStrip}>
          <View style={styles.readingMetric}>
            <Text style={styles.readingLabel}>TEMP</Text>
            <Text
              style={[
                styles.readingValue,
                { color: isQuarantined ? '#EF4444' : isWarn ? '#F59E0B' : '#00AEBB' },
              ]}
            >
              {typeof lastTemp === 'number' ? `${lastTemp.toFixed(1)}°C` : '5.0°C'}
            </Text>
          </View>

          <View style={styles.readingDivider} />

          <View style={styles.readingMetric}>
            <Text style={styles.readingLabel}>HUMIDITY</Text>
            <Text style={styles.readingValue}>{Math.round(lastHumidity)}%</Text>
          </View>

          <View style={styles.readingDivider} />

          <View style={styles.readingMetric}>
            <Text style={styles.readingLabel}>SHOCK</Text>
            <Text style={styles.readingValue}>{lastShock.toFixed(1)}g</Text>
          </View>

          <View style={styles.readingDivider} />

          <View style={styles.readingMetric}>
            <Text style={styles.readingLabel}>STOCK</Text>
            <Text style={[styles.readingValue, isQuarantined && { color: '#EF4444' }]}>
              {isQuarantined ? '0' : item.available_quantity}
            </Text>
          </View>
        </View>

        {/* Shelf Life Progress Bar */}
        <View style={styles.shelfLifeSection}>
          <View style={styles.shelfLifeHeader}>
            <Text style={styles.shelfLifeLabel}>ARRHENIUS SHELF-LIFE</Text>
            <Text style={styles.shelfLifeValue}>
              {isQuarantined ? '0.0d • QUARANTINED' : `${remainingDays.toFixed(1)}d (${Math.round(shelfPct)}%)`}
            </Text>
          </View>
          <View style={styles.progressBarTrack}>
            <View
              style={[
                styles.progressBarFill,
                {
                  width: `${isQuarantined ? 0 : shelfPct}%`,
                  backgroundColor: isQuarantined ? '#EF4444' : isWarn ? '#F59E0B' : '#00AEBB',
                },
              ]}
            />
          </View>
        </View>

        {/* Footer Link */}
        <View style={styles.cardFooter}>
          <Text style={styles.viewDetailText}>Inspect Telemetry & Audit Trace</Text>
          <ArrowRight size={14} color="#00AEBB" />
        </View>
      </TouchableOpacity>
    );
  };

  const renderQuarantineCard = ({ item }: { item: QuarantineRecord }) => {
    return (
      <TouchableOpacity
        style={styles.quarantineCard}
        activeOpacity={0.85}
        onPress={() => router.push(`/cold-chain/${item.batch_id}` as any)}
      >
        <View style={styles.quarantineHeader}>
          <View style={styles.quarantineBadge}>
            <ShieldAlert size={14} color="#F7F5F0" />
            <Text style={styles.quarantineBadgeText}>AUTONOMOUS QUARANTINE</Text>
          </View>
          <Text style={styles.quarantineTime}>
            {item.created_at ? new Date(item.created_at).toLocaleTimeString() : 'Recent'}
          </Text>
        </View>

        <Text style={styles.quarantineBatchNo}>
          Batch: {item.batch_no || item.batch_id}
        </Text>
        {item.product_name && (
          <Text style={styles.quarantineProduct}>{item.product_name}</Text>
        )}
        {item.node_name && (
          <Text style={styles.quarantineNode}>📍 {item.node_name}</Text>
        )}

        <View style={styles.explanationBox}>
          <Text style={styles.explanationLabel}>EXCURSION ANALYST RATIONALE:</Text>
          <Text style={styles.explanationText}>
            {item.explanation || item.reason || 'Thermal excursion breach beyond CDSCO cold-chain envelope.'}
          </Text>
        </View>

        {item.correlation_id && (
          <Text style={styles.correlationText}>
            Trace: <Text style={styles.monoText}>{item.correlation_id}</Text>
          </Text>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      {/* View Switcher: Batches vs Quarantine History */}
      <View style={styles.topBar}>
        <View style={styles.switcher}>
          <TouchableOpacity
            style={[styles.switchBtn, viewMode === 'batches' && styles.switchBtnActive]}
            onPress={() => setViewMode('batches')}
          >
            <Text
              style={[
                styles.switchBtnText,
                viewMode === 'batches' && styles.switchBtnTextActive,
              ]}
            >
              Batches ({batches.length})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.switchBtn, viewMode === 'quarantines' && styles.switchBtnActive]}
            onPress={() => setViewMode('quarantines')}
          >
            <Text
              style={[
                styles.switchBtnText,
                viewMode === 'quarantines' && styles.switchBtnTextActive,
              ]}
            >
              Quarantine History ({quarantines.length})
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {viewMode === 'batches' ? (
        <>
          {/* Quick Simulation Test Strip */}
          <View style={styles.demoStrip}>
            <Text style={styles.demoStripLabel}>IOT SENSOR SIMULATION:</Text>
            <View style={styles.demoButtonsRow}>
              <TouchableOpacity
                style={[styles.simBtn, styles.simNormalBtn]}
                disabled={simulating !== null}
                onPress={() => handleSimulate('normal')}
              >
                {simulating === 'normal' ? (
                  <ActivityIndicator size="small" color="#10B981" />
                ) : (
                  <>
                    <Thermometer size={14} color="#10B981" />
                    <Text style={styles.simNormalText}>Normal Reading</Text>
                  </>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.simBtn, styles.simExcursionBtn]}
                disabled={simulating !== null}
                onPress={() => handleSimulate('excursion')}
              >
                {simulating === 'excursion' ? (
                  <ActivityIndicator size="small" color="#EF4444" />
                ) : (
                  <>
                    <Flame size={14} color="#EF4444" />
                    <Text style={styles.simExcursionText}>Simulate Excursion</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>

          {/* Filter Chips */}
          <View style={styles.filterChipsRow}>
            {(['all', 'ok', 'warn', 'quarantined'] as StatusFilter[]).map((filter) => {
              const active = statusFilter === filter;
              const count =
                filter === 'all'
                  ? batches.length
                  : filter === 'ok'
                  ? okCount
                  : filter === 'warn'
                  ? warnCount
                  : quarantinedCount;

              return (
                <TouchableOpacity
                  key={filter}
                  style={[styles.filterChip, active && styles.filterChipActive]}
                  onPress={() => setStatusFilter(filter)}
                >
                  <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
                    {filter.toUpperCase()} ({count})
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {loading ? (
            <View style={styles.centerContainer}>
              <ActivityIndicator size="large" color="#00AEBB" />
              <Text style={styles.loadingText}>Loading cold-chain telemetry...</Text>
            </View>
          ) : (
            <FlatList
              data={filteredBatches}
              keyExtractor={(item) => item.batch_id}
              renderItem={renderBatchCard}
              contentContainerStyle={styles.listContent}
              refreshControl={
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={onRefresh}
                  tintColor="#00AEBB"
                  colors={['#00AEBB']}
                />
              }
              ListEmptyComponent={
                <View style={styles.emptyContainer}>
                  <Thermometer size={36} color="#8C887B" />
                  <Text style={styles.emptyText}>No batches found for this filter.</Text>
                </View>
              }
            />
          )}
        </>
      ) : (
        /* Quarantine History View */
        <FlatList
          data={quarantines}
          keyExtractor={(item) => item.id}
          renderItem={renderQuarantineCard}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#00AEBB"
              colors={['#00AEBB']}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <CheckCircle2 size={36} color="#10B981" />
              <Text style={styles.emptyText}>Zero quarantines logged. All units within safe envelope.</Text>
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
    backgroundColor: '#E8E4D3',
  },
  topBar: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    backgroundColor: '#E8E4D3',
    borderBottomWidth: 1,
    borderBottomColor: '#D8D3C3',
  },
  switcher: {
    flexDirection: 'row',
    backgroundColor: '#DFDBCA',
    borderRadius: 6,
    padding: 3,
  },
  switchBtn: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 4,
  },
  switchBtnActive: {
    backgroundColor: '#031211',
  },
  switchBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#5C584E',
  },
  switchBtnTextActive: {
    color: '#F7F5F0',
  },
  demoStrip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#DFDBCA',
    borderBottomWidth: 1,
    borderBottomColor: '#D8D3C3',
  },
  demoStripLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#5C584E',
    letterSpacing: 0.5,
    marginBottom: 6,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  demoButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  simBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
  },
  simNormalBtn: {
    backgroundColor: '#F0FDF4',
    borderColor: '#86EFAC',
  },
  simNormalText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#166534',
  },
  simExcursionBtn: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FCA5A5',
  },
  simExcursionText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#991B1B',
  },
  filterChipsRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  filterChip: {
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 4,
    backgroundColor: '#DFDBCA',
    borderWidth: 1,
    borderColor: '#D8D3C3',
  },
  filterChipActive: {
    backgroundColor: '#031211',
    borderColor: '#031211',
  },
  filterChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#5C584E',
  },
  filterChipTextActive: {
    color: '#F7F5F0',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  batchCard: {
    backgroundColor: '#F7F5F0',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#D8D3C3',
    padding: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  batchCardQuarantined: {
    borderColor: '#EF4444',
    borderWidth: 1.5,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  titleCol: {
    flex: 1,
    marginRight: 8,
  },
  productName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#031211',
  },
  batchSkuText: {
    fontSize: 12,
    color: '#5C584E',
    marginTop: 2,
  },
  batchNo: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontWeight: '600',
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
  nodeNameText: {
    fontSize: 12,
    color: '#5C584E',
    marginBottom: 10,
  },
  readingsStrip: {
    flexDirection: 'row',
    backgroundColor: '#DFDBCA',
    borderRadius: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
    alignItems: 'center',
    marginBottom: 12,
  },
  readingMetric: {
    flex: 1,
    alignItems: 'center',
  },
  readingLabel: {
    fontSize: 9,
    fontWeight: '700',
    color: '#5C584E',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    marginBottom: 2,
  },
  readingValue: {
    fontSize: 13,
    fontWeight: '800',
    color: '#031211',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  readingDivider: {
    width: 1,
    height: 24,
    backgroundColor: '#D8D3C3',
  },
  shelfLifeSection: {
    marginBottom: 10,
  },
  shelfLifeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  shelfLifeLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#5C584E',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  shelfLifeValue: {
    fontSize: 10,
    fontWeight: '700',
    color: '#031211',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  progressBarTrack: {
    height: 6,
    backgroundColor: '#DFDBCA',
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: '#E8E4D3',
    paddingTop: 8,
  },
  viewDetailText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#00AEBB',
  },
  quarantineCard: {
    backgroundColor: '#F7F5F0',
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: '#EF4444',
    padding: 14,
  },
  quarantineHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  quarantineBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#EF4444',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  quarantineBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#FFFFFF',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  quarantineTime: {
    fontSize: 11,
    color: '#8C887B',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  quarantineBatchNo: {
    fontSize: 14,
    fontWeight: '800',
    color: '#031211',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  quarantineProduct: {
    fontSize: 13,
    color: '#5C584E',
    marginTop: 2,
  },
  quarantineNode: {
    fontSize: 12,
    color: '#8C887B',
    marginTop: 2,
    marginBottom: 8,
  },
  explanationBox: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FCA5A5',
    borderRadius: 6,
    padding: 10,
    marginVertical: 6,
  },
  explanationLabel: {
    fontSize: 9,
    fontWeight: '800',
    color: '#991B1B',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    marginBottom: 3,
  },
  explanationText: {
    fontSize: 12,
    color: '#7F1D1D',
    lineHeight: 16,
  },
  correlationText: {
    fontSize: 11,
    color: '#8C887B',
    marginTop: 4,
  },
  monoText: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    color: '#031211',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  loadingText: {
    fontSize: 13,
    color: '#5C584E',
    marginTop: 10,
  },
  emptyContainer: {
    padding: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyText: {
    fontSize: 13,
    color: '#5C584E',
    textAlign: 'center',
    marginTop: 12,
  },
});
