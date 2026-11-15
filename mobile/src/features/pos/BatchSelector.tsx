import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, typography, radii } from '../../theme/tokens';
import { Badge } from '../../components/Badge';

export interface BatchItem {
  id?: string;
  batch_number: string;
  expiry_date: string;
  available_quantity: number;
  is_quarantined?: boolean;
  quarantine_reason?: string | null;
  days_to_expiry?: number;
  is_near_expiry?: boolean;
}

export interface BatchSelectorProps {
  batches: BatchItem[];
  selectedBatch: BatchItem | null;
  onSelectBatch: (batch: BatchItem) => void;
}

export function BatchSelector({
  batches,
  selectedBatch,
  onSelectBatch,
}: BatchSelectorProps) {
  if (!batches || batches.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="cube-outline" size={24} color={colors.text.muted} />
        <Text style={styles.emptyText}>No active inventory batches found for this product.</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <View style={styles.titleWithIcon}>
          <Ionicons name="layers-outline" size={16} color={colors.accent.primary} />
          <Text style={styles.sectionTitle}>FEFO BATCH SELECTION (FIRST-EXPIRY-FIRST-OUT)</Text>
        </View>
        <Text style={styles.fefoBadgeText}>AUTO-OPTIMIZED</Text>
      </View>

      <View style={styles.batchList}>
        {batches.map((batch, index) => {
          const isSelected = selectedBatch?.batch_number === batch.batch_number;
          const isQuarantined = Boolean(batch.is_quarantined);
          const isNearExpiry = Boolean(batch.is_near_expiry || (batch.days_to_expiry !== undefined && batch.days_to_expiry <= 60));
          const isFefoRecommended = index === 0 && !isQuarantined && batch.available_quantity > 0;

          return (
            <TouchableOpacity
              key={batch.batch_number}
              style={[
                styles.batchCard,
                isSelected && styles.batchCardSelected,
                isQuarantined && styles.batchCardQuarantined,
              ]}
              onPress={() => {
                if (isQuarantined) {
                  // Locked, do not select
                  return;
                }
                onSelectBatch(batch);
              }}
              activeOpacity={isQuarantined ? 1 : 0.7}
              disabled={isQuarantined}
            >
              {/* Radio indicator */}
              <View style={styles.radioCol}>
                {isQuarantined ? (
                  <Ionicons name="ban-outline" size={20} color={colors.status.danger} />
                ) : (
                  <View
                    style={[
                      styles.radioOuter,
                      isSelected && styles.radioOuterSelected,
                    ]}
                  >
                    {isSelected && <View style={styles.radioInner} />}
                  </View>
                )}
              </View>

              {/* Main Details */}
              <View style={styles.batchDetailsCol}>
                <View style={styles.batchTopRow}>
                  <Text style={styles.batchNumberMono}>{batch.batch_number}</Text>
                  {isFefoRecommended && (
                    <Badge label="FEFO RECOMMENDED" variant="emerald" />
                  )}
                  {isNearExpiry && !isQuarantined && (
                    <Badge label={`EXPIRING SOON (${batch.days_to_expiry}d)`} variant="amber" />
                  )}
                  {isQuarantined && (
                    <Badge label="QUARANTINED" variant="coral" />
                  )}
                </View>

                <View style={styles.batchMetaRow}>
                  <Text style={styles.batchMetaText}>
                    Expires: <Text style={styles.batchMetaBold}>{batch.expiry_date}</Text>
                  </Text>
                  <Text style={styles.batchMetaDivider}>•</Text>
                  <Text style={styles.batchMetaText}>
                    Available Stock:{' '}
                    <Text
                      style={[
                        styles.batchMetaBold,
                        batch.available_quantity <= 5 && !isQuarantined ? styles.lowStockText : null,
                      ]}
                    >
                      {batch.available_quantity} units
                    </Text>
                  </Text>
                </View>

                {/* Quarantined alert warning */}
                {isQuarantined && (
                  <View style={styles.quarantineCallout}>
                    <Ionicons name="warning" size={14} color={colors.status.danger} />
                    <Text style={styles.quarantineCalloutText}>
                      QUARANTINED — DO NOT DISPENSE
                      {batch.quarantine_reason ? `: ${batch.quarantine_reason}` : ''}
                    </Text>
                  </View>
                )}
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: spacing.sm,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  titleWithIcon: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  sectionTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.text.secondary,
  },
  fefoBadgeText: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  emptyContainer: {
    padding: spacing.md,
    backgroundColor: colors.canvas.elevated,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: spacing.sm,
  },
  emptyText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.muted,
    marginTop: spacing.xs,
  },
  batchList: {
    gap: spacing.xs,
  },
  batchCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.md,
    padding: spacing.sm,
    gap: spacing.sm,
  },
  batchCardSelected: {
    borderColor: colors.accent.primary,
    borderWidth: 1.5,
    backgroundColor: colors.accent.subtle,
  },
  batchCardQuarantined: {
    borderColor: colors.status.danger,
    backgroundColor: 'rgba(239, 68, 68, 0.05)',
    opacity: 0.85,
  },
  radioCol: {
    paddingTop: 2,
  },
  radioOuter: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1.5,
    borderColor: colors.border.emphasis,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioOuterSelected: {
    borderColor: colors.accent.primary,
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.accent.primary,
  },
  batchDetailsCol: {
    flex: 1,
  },
  batchTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: 4,
  },
  batchNumberMono: {
    fontSize: typography.fontSize.body,
    fontFamily: typography.fontFamily.mono,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  batchMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  batchMetaText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
  },
  batchMetaBold: {
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
  },
  batchMetaDivider: {
    color: colors.text.muted,
  },
  lowStockText: {
    color: colors.status.warning,
  },
  quarantineCallout: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 6,
    paddingVertical: 4,
    paddingHorizontal: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
    borderRadius: radii.sm,
  },
  quarantineCalloutText: {
    fontSize: typography.fontSize.micro,
    color: colors.status.danger,
    fontWeight: typography.fontWeight.bold,
    flex: 1,
  },
});
