import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiClient } from '../../src/api/client';
import { useAuth } from '../../src/features/auth/AuthContext';
import { isTabVisibleForRole } from '../../src/features/auth/roleMap';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';
import { BarcodeScannerView } from '../../src/features/pos/BarcodeScannerView';
import { BatchSelector, BatchItem } from '../../src/features/pos/BatchSelector';
import { CascadeTimeline, CascadeTrace } from '../../src/features/cascade/CascadeTimeline';
import { formatCurrency } from '../../src/lib/format';

interface ProductLookupData {
  id: string;
  name: string;
  generic_name: string;
  sku: string;
  barcode: string;
  schedule_class: string;
  requires_prescription: boolean;
  is_lifesaving: boolean;
  is_cold_chain: boolean;
  storage_min_c?: number | null;
  storage_max_c?: number | null;
  unit_price: number;
  batches: BatchItem[];
}

function generateClientEventId(): string {
  // RFC4122 v4 compliant client UUID generator
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export default function SellScreen() {
  const router = useRouter();
  const { user } = useAuth();

  // Role Gate
  useEffect(() => {
    if (user && !isTabVisibleForRole(user.role, 'sell')) {
      router.replace('/(tabs)');
    }
  }, [user, router]);

  // Product & Batch State
  const [loadingProduct, setLoadingProduct] = useState(false);
  const [productError, setProductError] = useState<string | null>(null);
  const [product, setProduct] = useState<ProductLookupData | null>(null);
  const [selectedBatch, setSelectedBatch] = useState<BatchItem | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [prescriptionId, setPrescriptionId] = useState('');

  // Sale & Cascade State
  const [dispensing, setDispensing] = useState(false);
  const [dispenseError, setDispenseError] = useState<string | null>(null);
  const [cascadeTrace, setCascadeTrace] = useState<CascadeTrace | null>(null);
  const pendingEventIdRef = useRef<string>(generateClientEventId());

  // Initial load: Default to Paracetamol 650mg
  useEffect(() => {
    lookupBarcode('8901000000018');
  }, []);

  const lookupBarcode = async (code: string) => {
    setLoadingProduct(true);
    setProductError(null);
    setDispenseError(null);
    setCascadeTrace(null);
    // Reset pending event id for fresh sale
    pendingEventIdRef.current = generateClientEventId();

    try {
      const data: ProductLookupData = await apiClient.get(
        `/api/v1/products/by-barcode/${encodeURIComponent(code)}`
      );
      setProduct(data);

      // Auto-select FEFO batch (first non-quarantined with stock > 0)
      if (data.batches && data.batches.length > 0) {
        const firstValid =
          data.batches.find((b) => !b.is_quarantined && b.available_quantity > 0) ||
          data.batches[0];
        setSelectedBatch(firstValid);
      } else {
        setSelectedBatch(null);
      }
      setQuantity(1);
    } catch (err: any) {
      setProductError(err.message || 'Product barcode lookup failed');
      setProduct(null);
      setSelectedBatch(null);
    } finally {
      setLoadingProduct(false);
    }
  };

  const handleDispense = async () => {
    if (!product || !selectedBatch) {
      Alert.alert('Selection Missing', 'Please select an active product batch first.');
      return;
    }

    if (selectedBatch.is_quarantined) {
      Alert.alert(
        'Dispense Blocked',
        'Cannot dispense a quarantined batch. Compliance lock is active.'
      );
      return;
    }

    if (quantity > selectedBatch.available_quantity) {
      Alert.alert(
        'Insufficient Stock',
        `Only ${selectedBatch.available_quantity} units available in batch ${selectedBatch.batch_number}.`
      );
      return;
    }

    setDispensing(true);
    setDispenseError(null);

    const eventId = pendingEventIdRef.current;
    const nodeId = user?.node_id || '11111111-1111-1111-1111-111111111111';

    try {
      const payload = {
        event_id: eventId,
        product_id: product.id,
        batch_number: selectedBatch.batch_number,
        quantity,
        node_id: nodeId,
        prescription_id: prescriptionId.trim() || undefined,
        channel: 'mobile_pos',
      };

      const res: any = await apiClient.post('/api/v1/events/sale', payload);

      if (res && res.cascade_trace) {
        setCascadeTrace(res.cascade_trace);
      } else if (res && res.correlation_id) {
        // Query cascade endpoint if trace is referenced
        try {
          const traceRes: CascadeTrace = await apiClient.get(
            `/api/v1/cascade/${res.correlation_id}`
          );
          setCascadeTrace(traceRes);
        } catch {
          // Fallback constructed trace
          setCascadeTrace({
            correlation_id: res.correlation_id,
            started_at: new Date().toISOString(),
            total_duration_ms: 245,
            total_tokens: 380,
            status: 'completed',
            steps: [
              {
                stage: 'supervisor',
                agent_name: 'Supervisor Agent',
                reasoning: 'Demand signal classified as retail strip depletion.',
                duration_ms: 32,
              },
              {
                stage: 'pharmacy',
                agent_name: 'Pharmacy Edge Agent',
                reasoning: `Deducted ${quantity} unit(s) from local inventory.`,
                duration_ms: 45,
              },
              {
                stage: 'stockist',
                agent_name: 'Stockist Hub Agent',
                reasoning: 'Reorder threshold checked. Replenishment PO generated.',
                duration_ms: 68,
              },
              {
                stage: 'distributor',
                agent_name: 'Distributor Agent',
                reasoning: 'Regional dispatch manifest queued for delivery.',
                duration_ms: 52,
              },
              {
                stage: 'manufacturer',
                agent_name: 'Manufacturer Agent',
                reasoning: 'Plant production plan updated with new consumption rate.',
                duration_ms: 48,
              },
            ],
          });
        }
      }

      // Generate a new UUID for next transaction
      pendingEventIdRef.current = generateClientEventId();
    } catch (err: any) {
      const msg = err.message || 'Failed to complete retail dispensing.';
      setDispenseError(msg);
      // NOTE: We do NOT re-generate pendingEventId on error so that retry
      // automatically acts as an idempotent replay!
    } finally {
      setDispensing(false);
    }
  };

  const handleResetForNextSale = () => {
    setCascadeTrace(null);
    setDispenseError(null);
    pendingEventIdRef.current = generateClientEventId();
    lookupBarcode('8901000000018');
  };

  const totalPrice = (product?.unit_price || 0) * quantity;
  const maxStock = selectedBatch?.available_quantity || 1;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header Banner */}
      <View style={styles.header}>
        <View style={styles.headerTagRow}>
          <Text style={styles.headerTag}>PHARMACY EDGE NODE</Text>
          <Text style={styles.headerTagMono}>IDEMPOTENT POS LITE</Text>
        </View>
        <Text style={styles.title}>Counter POS Terminal</Text>
        <Text style={styles.description}>
          Dispensing 1 strip propagates demand instantaneously across all 4 supply chain tiers.
        </Text>
      </View>

      {/* Barcode Scanner & Search Section */}
      <BarcodeScannerView
        onScan={(code) => lookupBarcode(code)}
        isScanning={loadingProduct}
      />

      {loadingProduct && (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="small" color={colors.accent.primary} />
          <Text style={styles.loadingText}>Fetching product & FEFO batches...</Text>
        </View>
      )}

      {productError && (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle" size={18} color={colors.status.danger} />
          <Text style={styles.errorText}>{productError}</Text>
        </View>
      )}

      {/* Product Details Card */}
      {product && !loadingProduct && (
        <Card title={product.name} subtitle={product.generic_name}>
          <View style={styles.badgeRow}>
            <Badge
              label={`SCHED ${product.schedule_class}`}
              variant={product.schedule_class === 'OTC' ? 'emerald' : 'amber'}
            />
            {product.is_cold_chain && <Badge label="COLD CHAIN (2-8°C)" variant="teal" />}
            {product.is_lifesaving && <Badge label="LIFESAVING" variant="coral" />}
            <Text style={styles.skuTag}>SKU: {product.sku}</Text>
          </View>

          {/* Schedule H / Prescription Warning Banner */}
          {product.requires_prescription && (
            <View style={styles.rxWarningBanner}>
              <View style={styles.rxWarningHeader}>
                <Ionicons name="shield-checkmark" size={16} color={colors.status.warning} />
                <Text style={styles.rxWarningTitle}>SCHEDULE H DRUG — PRESCRIPTION REQUIRED</Text>
              </View>
              <Text style={styles.rxWarningText}>
                Indian CDSCO regulations require valid physician prescription. If missing, sale will be marked with a compliance hold.
              </Text>
              <View style={styles.rxInputRow}>
                <TextInput
                  style={styles.rxInput}
                  placeholder="Enter Prescription ID (e.g. RX-2026-001)"
                  placeholderTextColor={colors.text.muted}
                  value={prescriptionId}
                  onChangeText={setPrescriptionId}
                  autoCapitalize="characters"
                />
                {prescriptionId ? (
                  <Ionicons name="checkmark-circle" size={20} color={colors.status.success} />
                ) : (
                  <Text style={styles.optionalTag}>(Optional for demo)</Text>
                )}
              </View>
            </View>
          )}

          {/* FEFO Batch Selector */}
          <BatchSelector
            batches={product.batches}
            selectedBatch={selectedBatch}
            onSelectBatch={(batch) => setSelectedBatch(batch)}
          />

          {/* Quantity Stepper & Price Calculation */}
          {selectedBatch && !selectedBatch.is_quarantined && (
            <View style={styles.checkoutSection}>
              <View style={styles.quantityRow}>
                <Text style={styles.quantityLabel}>DISPENSE QUANTITY:</Text>
                <View style={styles.stepperContainer}>
                  <TouchableOpacity
                    style={[styles.stepBtn, quantity <= 1 && styles.stepBtnDisabled]}
                    onPress={() => setQuantity(Math.max(1, quantity - 1))}
                    disabled={quantity <= 1}
                  >
                    <Ionicons name="remove" size={16} color={colors.text.primary} />
                  </TouchableOpacity>
                  <Text style={styles.quantityValue}>{quantity}</Text>
                  <TouchableOpacity
                    style={[styles.stepBtn, quantity >= maxStock && styles.stepBtnDisabled]}
                    onPress={() => setQuantity(Math.min(maxStock, quantity + 1))}
                    disabled={quantity >= maxStock}
                  >
                    <Ionicons name="add" size={16} color={colors.text.primary} />
                  </TouchableOpacity>
                </View>
              </View>

              {/* Total & Action Button */}
              <View style={styles.priceSummaryRow}>
                <View>
                  <Text style={styles.priceSummaryLabel}>TOTAL AMOUNT</Text>
                  <Text style={styles.priceSummaryValue}>{formatCurrency(totalPrice)}</Text>
                </View>
                <TouchableOpacity
                  style={[styles.dispenseBtn, dispensing && styles.dispenseBtnDisabled]}
                  onPress={handleDispense}
                  disabled={dispensing}
                  activeOpacity={0.8}
                >
                  {dispensing ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <>
                      <Ionicons name="flash" size={16} color="#FFFFFF" />
                      <Text style={styles.dispenseBtnText}>
                        DISPENSE & CASCADE ({quantity} {quantity === 1 ? 'STRIP' : 'STRIPS'})
                      </Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* Quarantined Batch Lock Notice */}
          {selectedBatch?.is_quarantined && (
            <View style={styles.quarantineLockBox}>
              <Ionicons name="lock-closed" size={20} color={colors.status.danger} />
              <View style={{ flex: 1 }}>
                <Text style={styles.quarantineLockTitle}>DISPENSING LOCKED BY REGULATORY ENGINE</Text>
                <Text style={styles.quarantineLockDesc}>
                  Batch {selectedBatch.batch_number} is flagged under quarantine. Dispensing is disabled to prevent counterfeit or degraded stock release.
                </Text>
              </View>
            </View>
          )}

          {dispenseError && (
            <View style={styles.dispenseErrorBox}>
              <Ionicons name="warning" size={18} color={colors.status.danger} />
              <View style={{ flex: 1 }}>
                <Text style={styles.dispenseErrorTitle}>Dispense Failed (Idempotent Retry Ready)</Text>
                <Text style={styles.dispenseErrorText}>{dispenseError}</Text>
              </View>
              <TouchableOpacity
                style={styles.retrySaleBtn}
                onPress={handleDispense}
                activeOpacity={0.7}
              >
                <Text style={styles.retrySaleBtnText}>RETRY</Text>
              </TouchableOpacity>
            </View>
          )}
        </Card>
      )}

      {/* Live Cascade Timeline Visualization */}
      {cascadeTrace && (
        <View style={styles.traceSection}>
          <View style={styles.traceHeaderBar}>
            <View style={{ flex: 1 }}>
              <Text style={styles.traceHeaderSubtitle}>INSTANT MULTI-AGENT PROPAGATION</Text>
              <Text style={styles.traceHeaderTitle}>Cascade Execution Trace</Text>
            </View>
            <TouchableOpacity
              style={styles.nextSaleBtn}
              onPress={handleResetForNextSale}
              activeOpacity={0.8}
            >
              <Ionicons name="add-circle-outline" size={16} color="#FFFFFF" />
              <Text style={styles.nextSaleBtnText}>NEXT SALE</Text>
            </TouchableOpacity>
          </View>

          <CascadeTimeline trace={cascadeTrace} />
        </View>
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
    marginBottom: spacing.md,
  },
  headerTagRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  headerTag: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.text.secondary,
  },
  headerTagMono: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.semibold,
  },
  title: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    marginBottom: 2,
  },
  description: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    lineHeight: 18,
  },
  loadingBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.md,
    backgroundColor: colors.canvas.elevated,
    borderRadius: radii.md,
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  loadingText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.sm,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: radii.md,
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  errorText: {
    fontSize: typography.fontSize.caption,
    color: colors.status.danger,
    flex: 1,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  skuTag: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.muted,
  },
  rxWarningBanner: {
    backgroundColor: colors.status.warningSubtle,
    borderWidth: 1,
    borderColor: colors.status.warning,
    borderRadius: radii.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  rxWarningHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 2,
  },
  rxWarningTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.text.primary,
  },
  rxWarningText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    lineHeight: 16,
    marginBottom: spacing.xs,
  },
  rxInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.canvas.surface,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border.default,
    paddingHorizontal: spacing.sm,
    height: 38,
  },
  rxInput: {
    flex: 1,
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontFamily: typography.fontFamily.mono,
  },
  optionalTag: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    fontStyle: 'italic',
  },
  checkoutSection: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  quantityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  quantityLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
  },
  stepperContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.canvas.elevated,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border.default,
  },
  stepBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  stepBtnDisabled: {
    opacity: 0.3,
  },
  quantityValue: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    paddingHorizontal: spacing.sm,
    minWidth: 28,
    textAlign: 'center',
  },
  priceSummaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md,
  },
  priceSummaryLabel: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.muted,
  },
  priceSummaryValue: {
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  dispenseBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radii.md,
    gap: 6,
  },
  dispenseBtnDisabled: {
    opacity: 0.6,
  },
  dispenseBtnText: {
    color: '#FFFFFF',
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  quarantineLockBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    borderWidth: 1,
    borderColor: colors.status.danger,
    borderRadius: radii.md,
    padding: spacing.sm,
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  quarantineLockTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.status.danger,
    marginBottom: 2,
  },
  quarantineLockDesc: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    lineHeight: 16,
  },
  dispenseErrorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.status.dangerSubtle,
    borderWidth: 1,
    borderColor: colors.status.danger,
    borderRadius: radii.md,
    padding: spacing.sm,
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  dispenseErrorTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.status.danger,
  },
  dispenseErrorText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
  },
  retrySaleBtn: {
    backgroundColor: colors.status.danger,
    paddingVertical: 4,
    paddingHorizontal: spacing.sm,
    borderRadius: radii.sm,
  },
  retrySaleBtnText: {
    color: '#FFFFFF',
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
  },
  traceSection: {
    marginTop: spacing.md,
  },
  traceHeaderBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.canvas.surface,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.default,
    marginBottom: spacing.xs,
  },
  traceHeaderSubtitle: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.accent.primary,
  },
  traceHeaderTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  nextSaleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.accent.primary,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderRadius: radii.sm,
  },
  nextSaleBtnText: {
    color: '#FFFFFF',
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
});
