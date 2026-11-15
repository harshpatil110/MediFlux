import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, typography, radii } from '../../theme/tokens';
import { apiClient } from '../../api/client';

export interface BarcodeScannerViewProps {
  onScan: (barcode: string) => void;
  isScanning?: boolean;
}

const SAMPLE_BARCODES = [
  { label: 'Paracetamol 650mg', code: '8901000000018', tag: 'OTC' },
  { label: 'Amoxicillin 500mg', code: '8901000000025', tag: 'Rx H' },
  { label: 'Human Insulatard', code: '8901000000056', tag: 'Cold Chain' },
  { label: 'Azithral 500mg', code: '8901000000032', tag: 'Rx H' },
  { label: 'Quarantine Test', code: '8901000000087', tag: 'Quarantine' },
];

export function BarcodeScannerView({ onScan, isScanning = false }: BarcodeScannerViewProps) {
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraActive, setCameraActive] = useState<boolean>(Platform.OS !== 'web');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const lastScannedTimeRef = useRef<number>(0);

  // Debounced Barcode Handler
  const handleBarcodeScanned = ({ data }: { data: string }) => {
    const now = Date.now();
    if (now - lastScannedTimeRef.current < 2500) {
      return; // Debounce 2500ms
    }
    lastScannedTimeRef.current = now;

    if (Platform.OS !== 'web') {
      try {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      } catch {
        // ignore
      }
    }

    onScan(data.trim());
  };

  // Search autocomplete
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setSearchResults([]);
      return;
    }

    const handler = setTimeout(async () => {
      setSearching(true);
      try {
        const res: any = await apiClient.get('/api/v1/products', {
          params: { q: searchQuery.trim(), limit: 5 },
        });
        const items = res?.items || (Array.isArray(res) ? res : []);
        setSearchResults(items);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => clearTimeout(handler);
  }, [searchQuery]);

  const selectSample = (code: string) => {
    if (Platform.OS !== 'web') {
      try {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      } catch {
        // ignore
      }
    }
    onScan(code);
  };

  return (
    <View style={styles.container}>
      {/* 1-Tap Sample Barcode Chips Picker (Ideal for Web & Testing) */}
      <View style={styles.sampleBar}>
        <View style={styles.sampleHeader}>
          <Text style={styles.sampleTitle}>QUICK SAMPLE BARCODES (1-TAP)</Text>
          <Text style={styles.sampleSubtitle}>EAN-13 GS1 India</Text>
        </View>
        <View style={styles.chipsContainer}>
          {SAMPLE_BARCODES.map((item) => (
            <TouchableOpacity
              key={item.code}
              style={styles.chip}
              onPress={() => selectSample(item.code)}
              activeOpacity={0.7}
            >
              <Text style={styles.chipLabel}>{item.label}</Text>
              <Text style={styles.chipCodeMono}>{item.code}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Camera Scanner View / Toggle */}
      <View style={styles.scannerWrapper}>
        <View style={styles.scannerHeader}>
          <View style={styles.titleRow}>
            <Ionicons name="barcode-outline" size={18} color={colors.accent.primary} />
            <Text style={styles.scannerSectionTitle}>OPTICAL SCANNER</Text>
          </View>
          <TouchableOpacity
            style={styles.toggleCameraBtn}
            onPress={() => {
              if (!permission?.granted) {
                requestPermission();
              }
              setCameraActive(!cameraActive);
            }}
          >
            <Ionicons
              name={cameraActive ? 'videocam' : 'videocam-off-outline'}
              size={16}
              color={colors.accent.primary}
            />
            <Text style={styles.toggleCameraText}>
              {cameraActive ? 'Camera ON' : 'Camera OFF'}
            </Text>
          </TouchableOpacity>
        </View>

        {cameraActive ? (
          !permission?.granted ? (
            <View style={styles.permissionBox}>
              <Ionicons name="camera-outline" size={36} color={colors.text.muted} />
              <Text style={styles.permissionTitle}>Camera Permission Needed</Text>
              <Text style={styles.permissionDesc}>
                Enable camera access to scan GS1 barcodes directly with your device lens.
              </Text>
              <TouchableOpacity
                style={styles.grantBtn}
                onPress={requestPermission}
                activeOpacity={0.8}
              >
                <Text style={styles.grantBtnText}>GRANT PERMISSION</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.cameraContainer}>
              <CameraView
                style={styles.cameraView}
                barcodeScannerSettings={{
                  barcodeTypes: ['ean13', 'ean8', 'code128', 'qr', 'upc_a'],
                }}
                onBarcodeScanned={isScanning ? undefined : handleBarcodeScanned}
              >
                {/* Aiming Reticle Frame */}
                <View style={styles.reticleOverlay}>
                  <View style={styles.reticleFrame}>
                    <View style={styles.laserLine} />
                  </View>
                  <Text style={styles.aimInstruction}>
                    Center medicine barcode inside frame
                  </Text>
                </View>
              </CameraView>
            </View>
          )
        ) : (
          <View style={styles.cameraDisabledBox}>
            <Text style={styles.cameraDisabledText}>
              Camera standby. Use quick chips above or search medicine below.
            </Text>
          </View>
        )}
      </View>

      {/* Manual Search Bar Fallback */}
      <View style={styles.searchSection}>
        <View style={styles.searchInputWrapper}>
          <Ionicons name="search" size={16} color={colors.text.muted} style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search medicine by name, generic, or SKU..."
            placeholderTextColor={colors.text.muted}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCapitalize="none"
          />
          {searching && <ActivityIndicator size="small" color={colors.accent.primary} />}
          {searchQuery.length > 0 && !searching && (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={16} color={colors.text.muted} />
            </TouchableOpacity>
          )}
        </View>

        {/* Search Results Dropdown */}
        {searchResults.length > 0 && (
          <View style={styles.resultsList}>
            {searchResults.map((prod) => (
              <TouchableOpacity
                key={prod.id || prod.barcode}
                style={styles.resultItem}
                onPress={() => {
                  setSearchQuery('');
                  setSearchResults([]);
                  onScan(prod.barcode || prod.sku);
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.resultName}>{prod.name}</Text>
                  <Text style={styles.resultSub}>
                    {prod.generic_name || prod.sku} • {prod.schedule_class || 'OTC'}
                  </Text>
                </View>
                <Text style={styles.resultBarcode}>{prod.barcode || prod.sku}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  sampleBar: {
    backgroundColor: colors.canvas.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.default,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  sampleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  sampleTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.text.secondary,
  },
  sampleSubtitle: {
    fontSize: typography.fontSize.micro,
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.semibold,
  },
  chipsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  chip: {
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
    marginRight: 4,
    marginBottom: 4,
  },
  chipLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
  },
  chipCodeMono: {
    fontSize: typography.fontSize.micro,
    fontFamily: typography.fontFamily.mono,
    color: colors.text.muted,
  },
  scannerWrapper: {
    backgroundColor: colors.canvas.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.default,
    overflow: 'hidden',
    marginBottom: spacing.sm,
  },
  scannerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.subtle,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  scannerSectionTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
    color: colors.text.primary,
  },
  toggleCameraBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.sm,
    backgroundColor: colors.accent.subtle,
  },
  toggleCameraText: {
    fontSize: typography.fontSize.caption,
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.semibold,
  },
  cameraContainer: {
    height: 180,
    backgroundColor: '#000000',
    position: 'relative',
  },
  cameraView: {
    flex: 1,
  },
  reticleOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.3)',
  },
  reticleFrame: {
    width: 220,
    height: 110,
    borderWidth: 2,
    borderColor: colors.accent.primary,
    borderRadius: radii.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  laserLine: {
    width: '90%',
    height: 2,
    backgroundColor: colors.accent.primary,
    opacity: 0.8,
  },
  aimInstruction: {
    marginTop: spacing.xs,
    fontSize: typography.fontSize.micro,
    color: '#FFFFFF',
    fontWeight: typography.fontWeight.medium,
  },
  permissionBox: {
    padding: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.canvas.elevated,
  },
  permissionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    marginTop: spacing.xs,
  },
  permissionDesc: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textAlign: 'center',
    marginVertical: spacing.xs,
    maxWidth: 280,
  },
  grantBtn: {
    backgroundColor: colors.accent.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm,
    marginTop: spacing.xs,
  },
  grantBtnText: {
    color: '#FFFFFF',
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  cameraDisabledBox: {
    padding: spacing.md,
    backgroundColor: colors.canvas.elevated,
    alignItems: 'center',
  },
  cameraDisabledText: {
    fontSize: typography.fontSize.caption,
    color: colors.text.muted,
  },
  searchSection: {
    backgroundColor: colors.canvas.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border.default,
    padding: spacing.sm,
  },
  searchInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.canvas.elevated,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border.subtle,
    paddingHorizontal: spacing.sm,
    height: 40,
  },
  searchIcon: {
    marginRight: spacing.xs,
  },
  searchInput: {
    flex: 1,
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    paddingVertical: 0,
  },
  resultsList: {
    marginTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  resultItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.subtle,
  },
  resultName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
  },
  resultSub: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
  },
  resultBarcode: {
    fontSize: typography.fontSize.caption,
    fontFamily: typography.fontFamily.mono,
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.bold,
  },
});
