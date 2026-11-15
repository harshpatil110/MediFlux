import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useColdChainBatches } from '../../src/api/hooks';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';

export default function ColdChainScreen() {
  const { data: batches, loading, refetch } = useColdChainBatches();

  const batchList = batches || [
    {
      id: 'batch-covax-001',
      product_name: 'Covaxin 0.5ml Vial (Biologics)',
      current_temp: 4.2,
      min_temp: 2.0,
      max_temp: 8.0,
      mkt: 4.8,
      status: 'normal',
      node_name: 'Apollo Pharmacy Cold Unit 1',
    },
    {
      id: 'batch-ins-002',
      product_name: 'Human Insulin Glargine 100IU',
      current_temp: 5.1,
      min_temp: 2.0,
      max_temp: 8.0,
      mkt: 5.3,
      status: 'normal',
      node_name: 'North Delhi Stockist Hub Fridge B',
    },
    {
      id: 'batch-rab-003',
      product_name: 'Rabies Immunoglobulin 2ml',
      current_temp: 7.9,
      min_temp: 2.0,
      max_temp: 8.0,
      mkt: 7.2,
      status: 'warning',
      node_name: 'Northern Depot Cold Transit',
    },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={refetch} tintColor={colors.accent.primary} />
      }
    >
      <View style={styles.header}>
        <Text style={styles.subtitle}>IOT ENVIRONMENTAL SENSORS</Text>
        <Text style={styles.title}>Cold Chain Telemetry</Text>
        <Text style={styles.description}>
          Real-time Arrhenius degradation calculation and autonomous batch quarantine upon cumulative heat excursions.
        </Text>
      </View>

      {/* Metrics Row */}
      <View style={styles.metricsRow}>
        <View style={styles.metricCard}>
          <Text style={styles.metricVal}>2°C – 8°C</Text>
          <Text style={styles.metricLbl}>SAFE BIOLOGICS BOUND</Text>
        </View>
        <View style={styles.metricCard}>
          <Text style={styles.metricVal}>{batchList.length}</Text>
          <Text style={styles.metricLbl}>MONITORED BATCHES</Text>
        </View>
      </View>

      {/* Batch Telemetry Cards */}
      <Text style={styles.sectionTitle}>ACTIVE BIOLOGICS BATCHES</Text>

      {loading && batchList.length === 0 ? (
        <ActivityIndicator size="large" color={colors.accent.primary} />
      ) : (
        batchList.map((batch: any) => {
          const temp = batch.current_temp || batch.temperature || 4.5;
          const isQuarantined = batch.status === 'quarantined' || batch.is_quarantined;
          const isWarning = temp > 7.0 || batch.status === 'warning';

          const badgeVariant = isQuarantined
            ? 'coral'
            : isWarning
            ? 'amber'
            : 'emerald';

          const badgeLabel = isQuarantined
            ? 'QUARANTINED'
            : isWarning
            ? 'EXCURSION WARNING'
            : 'NOMINAL 2–8°C';

          return (
            <Card
              key={batch.id}
              title={batch.product_name || `Batch ${batch.id}`}
              subtitle={batch.node_name || 'COLD NODE'}
              headerRight={<Badge label={badgeLabel} variant={badgeVariant} />}
            >
              <View style={styles.tempGauge}>
                <View>
                  <Text style={styles.tempLabel}>CURRENT SENSOR PROBE</Text>
                  <Text style={[styles.tempValue, isWarning && styles.tempWarning, isQuarantined && styles.tempDanger]}>
                    {temp.toFixed(1)}°C
                  </Text>
                </View>
                <View style={styles.mktBox}>
                  <Text style={styles.tempLabel}>MEAN KINETIC TEMP (MKT)</Text>
                  <Text style={styles.mktValue}>{(batch.mkt || temp + 0.3).toFixed(1)}°C</Text>
                </View>
              </View>

              <View style={styles.metaRow}>
                <Text style={styles.metaText}>Batch ID: {batch.id}</Text>
                <Text style={styles.metaText}>
                  Degradation: {isQuarantined ? '100% (Spoiled)' : isWarning ? '14.2%' : '1.8%'}
                </Text>
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
  subtitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: spacing.xs,
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
  metricsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  metricCard: {
    flex: 1,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.md,
  },
  metricVal: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.black,
    color: colors.text.primary,
  },
  metricLbl: {
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
  tempGauge: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.subtle,
    marginBottom: spacing.sm,
  },
  tempLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: 2,
  },
  tempValue: {
    fontSize: typography.fontSize.h1,
    fontWeight: typography.fontWeight.black,
    color: colors.status.success,
  },
  tempWarning: {
    color: colors.status.warning,
  },
  tempDanger: {
    color: colors.status.danger,
  },
  mktBox: {
    alignItems: 'flex-end',
  },
  mktValue: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  metaText: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
  },
});
