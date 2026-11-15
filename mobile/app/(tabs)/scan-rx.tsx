import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Card } from '../../src/components/Card';
import { Badge } from '../../src/components/Badge';

export default function ScanRxScreen() {
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<any | null>(null);

  const handleSimulateScan = () => {
    setScanning(true);
    setScanResult(null);
    setTimeout(() => {
      setScanResult({
        scan_id: `rx-${Date.now()}`,
        prescriber: 'Dr. Vikram Malhotra, MD (AIIMS Delhi)',
        doctor_reg: 'DMC/R/104928 (Verified Active)',
        patient: 'Sunita Sharma, 48F',
        drugs: [
          { name: 'Azithromycin 500mg', qty: '1 strip (5 tabs)', schedule: 'Schedule H' },
          { name: 'Pantoprazole 40mg', qty: '1 strip (10 tabs)', schedule: 'Schedule H' },
        ],
        cdsco_compliant: true,
        audit_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      });
      setScanning(false);
    }, 1200);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.subtitle}>SOVEREIGN PRESCRIPTION VISION</Text>
        <Text style={styles.title}>Multimodal Rx Scanner</Text>
        <Text style={styles.description}>
          AI-driven prescription OCR, Doctor registry verification, and CDSCO Schedule H/H1 compliance logging.
        </Text>
      </View>

      {/* Camera Viewfinder Placeholder */}
      <View style={styles.cameraBox}>
        <View style={styles.reticleCornerTL} />
        <View style={styles.reticleCornerTR} />
        <View style={styles.reticleCornerBL} />
        <View style={styles.reticleCornerBR} />

        <Text style={styles.cameraPrompt}>POINT CAMERA AT PHYSICIAN PRESCRIPTION</Text>
        <Text style={styles.cameraSubprompt}>
          Align registration number, patient name, and dosage details within borders
        </Text>

        <TouchableOpacity
          style={styles.captureButton}
          onPress={handleSimulateScan}
          disabled={scanning}
          activeOpacity={0.8}
        >
          {scanning ? (
            <ActivityIndicator color={colors.text.onAccent} />
          ) : (
            <Text style={styles.captureButtonText}>CAPTURE & EXTRACT Rx →</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Scan Results */}
      {scanResult && (
        <Card
          title="Clinical Extraction"
          subtitle="Verification Passed"
          headerRight={<Badge label="CDSCO COMPLIANT" variant="emerald" />}
        >
          <View style={styles.resultRow}>
            <Text style={styles.fieldLabel}>PRESCRIBING PHYSICIAN</Text>
            <Text style={styles.fieldValue}>{scanResult.prescriber}</Text>
          </View>

          <View style={styles.resultRow}>
            <Text style={styles.fieldLabel}>MEDICAL REGISTRATION</Text>
            <Text style={styles.fieldValue}>{scanResult.doctor_reg}</Text>
          </View>

          <View style={styles.resultRow}>
            <Text style={styles.fieldLabel}>PATIENT</Text>
            <Text style={styles.fieldValue}>{scanResult.patient}</Text>
          </View>

          <View style={styles.drugsSection}>
            <Text style={styles.fieldLabel}>SCHEDULED MEDICINES IDENTIFIED</Text>
            {scanResult.drugs.map((drug: any, i: number) => (
              <View key={i} style={styles.drugItem}>
                <View>
                  <Text style={styles.drugName}>{drug.name}</Text>
                  <Text style={styles.drugQty}>{drug.qty}</Text>
                </View>
                <Badge label={drug.schedule} variant="amber" />
              </View>
            ))}
          </View>

          <View style={styles.auditBox}>
            <Text style={styles.auditLabel}>AUDIT LEDGER PROOF HASH:</Text>
            <Text style={styles.auditHash} numberOfLines={1}>
              {scanResult.audit_hash}
            </Text>
          </View>
        </Card>
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
  cameraBox: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: colors.border.default,
    borderRadius: radii.md,
    padding: spacing.xxl,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
    position: 'relative',
    minHeight: 220,
  },
  reticleCornerTL: {
    position: 'absolute',
    top: 8,
    left: 8,
    width: 16,
    height: 16,
    borderTopWidth: 2,
    borderLeftWidth: 2,
    borderColor: colors.accent.primary,
  },
  reticleCornerTR: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 16,
    height: 16,
    borderTopWidth: 2,
    borderRightWidth: 2,
    borderColor: colors.accent.primary,
  },
  reticleCornerBL: {
    position: 'absolute',
    bottom: 8,
    left: 8,
    width: 16,
    height: 16,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    borderColor: colors.accent.primary,
  },
  reticleCornerBR: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    width: 16,
    height: 16,
    borderBottomWidth: 2,
    borderRightWidth: 2,
    borderColor: colors.accent.primary,
  },
  cameraPrompt: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.wide,
    textAlign: 'center',
    marginBottom: 4,
  },
  cameraSubprompt: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    textAlign: 'center',
    maxWidth: 240,
    marginBottom: spacing.lg,
  },
  captureButton: {
    backgroundColor: colors.accent.primary,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radii.sm,
  },
  captureButtonText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  resultRow: {
    marginBottom: spacing.sm,
  },
  fieldLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: 2,
  },
  fieldValue: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
  },
  drugsSection: {
    marginVertical: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  drugItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  drugName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  drugQty: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
  },
  auditBox: {
    backgroundColor: colors.canvas.elevated,
    padding: spacing.sm,
    borderRadius: radii.sm,
    marginTop: spacing.sm,
  },
  auditLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    marginBottom: 2,
  },
  auditHash: {
    fontSize: typography.fontSize.micro,
    fontFamily: 'monospace',
    color: colors.text.muted,
  },
});

