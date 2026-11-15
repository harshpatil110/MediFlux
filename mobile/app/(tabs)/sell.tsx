import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { apiClient } from '../../src/api/client';
import { useAuth } from '../../src/features/auth/AuthContext';
import { isTabVisibleForRole } from '../../src/features/auth/roleMap';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';
import { Timeline, TimelineItem } from '../../src/components/Timeline';
import { formatCurrency } from '../../src/lib/format';

const DEMO_PRODUCTS = [
  { id: 'AZI-500', name: 'Azithromycin 500mg', batch: 'AZ-2026-001', price: 145.5, schedule: 'H' },
  { id: 'PAR-650', name: 'Paracetamol 650mg', batch: 'PA-2026-004', price: 32.0, schedule: 'OTC' },
  { id: 'AMO-625', name: 'Amoxicillin + Clav 625mg', batch: 'AC-2026-002', price: 210.0, schedule: 'H1' },
];

export default function SellScreen() {
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    if (user && !isTabVisibleForRole(user.role, 'sell')) {
      router.replace('/(tabs)');
    }
  }, [user, router]);

  const [selectedProduct, setSelectedProduct] = useState(DEMO_PRODUCTS[0]);
  const [quantity, setQuantity] = useState('1');
  const [selling, setSelling] = useState(false);
  const [saleResult, setSaleResult] = useState<any | null>(null);

  const handleSale = async () => {
    setSelling(true);
    setSaleResult(null);
    try {
      // Simulate or call POS transaction
      const qty = parseInt(quantity, 10) || 1;
      const totalAmount = selectedProduct.price * qty;

      try {
        const res = await apiClient.post('/api/v1/pos/simulate', {
          product_id: selectedProduct.id,
          batch_id: selectedProduct.batch,
          quantity: qty,
        });
        setSaleResult(res);
      } catch {
        // Fallback local simulated cascade result for Task M1
        setSaleResult({
          transaction_id: `tx-${Date.now()}`,
          total: totalAmount,
          cascade_triggered: true,
          steps: [
            { tier: 'Pharmacy', status: 'completed', desc: `Deducted ${qty} strip from local shelf` },
            { tier: 'Stockist Hub', status: 'active', desc: 'Auto-reorder threshold evaluated (0.2s)' },
            { tier: 'Distributor Layer', status: 'pending', desc: 'Logistics routing pending batch dispatch' },
            { tier: 'Manufacturer Plant', status: 'pending', desc: 'Production forecast updated' },
          ],
        });
      }
    } finally {
      setSelling(false);
    }
  };

  const cascadeTimelineItems: TimelineItem[] = saleResult?.steps
    ? saleResult.steps.map((s: any, idx: number) => ({
        id: String(idx),
        title: s.tier,
        subtitle: s.desc,
        status: s.status,
      }))
    : [
        { id: '1', title: 'Tier 1: Pharmacy Edge Node', subtitle: 'Instant retail strip checkout', status: 'completed' },
        { id: '2', title: 'Tier 2: Stockist Hub', subtitle: 'Single-unit demand propagation trigger', status: 'active' },
        { id: '3', title: 'Tier 3: Regional Distributor', subtitle: 'Dynamic route consolidation', status: 'pending' },
        { id: '4', title: 'Tier 4: Manufacturer Plant', subtitle: 'Real-time production capacity signal', status: 'pending' },
      ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.subtitle}>INSTANT DEMAND PROPAGATION</Text>
        <Text style={styles.title}>Counter POS Terminal</Text>
        <Text style={styles.description}>
          Selling 1 strip triggers autonomous multi-agent demand cascade upstream to stockist, distributor, and plant.
        </Text>
      </View>

      {/* Product Selection */}
      <Card title="Medicine Selection" subtitle="SKU Master">
        {DEMO_PRODUCTS.map((prod) => {
          const isSelected = selectedProduct.id === prod.id;
          return (
            <TouchableOpacity
              key={prod.id}
              style={[styles.productItem, isSelected && styles.productItemSelected]}
              onPress={() => setSelectedProduct(prod)}
              activeOpacity={0.7}
            >
              <View style={styles.productInfo}>
                <Text style={styles.productName}>{prod.name}</Text>
                <Text style={styles.productMeta}>
                  Batch: {prod.batch} • Schedule {prod.schedule}
                </Text>
              </View>
              <View style={styles.productPriceRow}>
                <Text style={styles.productPrice}>{formatCurrency(prod.price)}</Text>
                <Badge
                  label={isSelected ? 'SELECTED' : 'SELECT'}
                  variant={isSelected ? 'teal' : 'neutral'}
                />
              </View>
            </TouchableOpacity>
          );
        })}
      </Card>

      {/* Sale Controls */}
      <Card title="Dispense Quantity" subtitle="Atomic Counter Sale">
        <View style={styles.qtyRow}>
          <Text style={styles.qtyLabel}>Quantity (Strips):</Text>
          <TextInput
            style={styles.qtyInput}
            value={quantity}
            onChangeText={setQuantity}
            keyboardType="number-pad"
          />
        </View>

        <View style={styles.totalRow}>
          <Text style={styles.totalLabel}>TOTAL DISPENSE VALUE:</Text>
          <Text style={styles.totalAmount}>
            {formatCurrency(selectedProduct.price * (parseInt(quantity, 10) || 1))}
          </Text>
        </View>

        <TouchableOpacity
          style={styles.sellButton}
          onPress={handleSale}
          disabled={selling}
          activeOpacity={0.8}
        >
          {selling ? (
            <ActivityIndicator color={colors.text.onAccent} />
          ) : (
            <Text style={styles.sellButtonText}>
              DISPENSE & PROPAGATE CASCADE (1 STRIP) →
            </Text>
          )}
        </TouchableOpacity>
      </Card>

      {/* Live Cascade Replay */}
      <Card title="Demand Cascade Progress" subtitle="Multi-Tier Autonomous Reaction">
        <Timeline items={cascadeTimelineItems} />
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
  productItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    marginBottom: spacing.xs,
    backgroundColor: colors.canvas.surface,
  },
  productItemSelected: {
    borderColor: colors.accent.primary,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1.5,
  },
  productInfo: {
    flex: 1,
  },
  productName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  productMeta: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    marginTop: 2,
  },
  productPriceRow: {
    alignItems: 'flex-end',
    gap: 4,
  },
  productPrice: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  qtyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  qtyLabel: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
  },
  qtyInput: {
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    width: 80,
    textAlign: 'center',
    paddingVertical: spacing.xs,
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    backgroundColor: colors.canvas.surface,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
    marginBottom: spacing.base,
  },
  totalLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
  },
  totalAmount: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.black,
    color: colors.accent.primary,
  },
  sellButton: {
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.md,
    borderRadius: radii.sm,
    alignItems: 'center',
  },
  sellButtonText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
});

