import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import {
  getBackendUrl,
  setBackendUrl,
  checkBackendHealth,
  getLanPresetUrls,
  HealthCheckResult,
} from '../../src/lib/config';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Badge } from '../../src/components/Badge';
import { Card } from '../../src/components/Card';

export default function SettingsScreen() {
  const router = useRouter();
  const [url, setUrl] = useState(getBackendUrl());
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<HealthCheckResult | null>(null);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const presets = getLanPresetUrls();

  useEffect(() => {
    setUrl(getBackendUrl());
  }, []);

  const handleTest = async () => {
    setTesting(true);
    setSavedSuccess(false);
    try {
      const res = await checkBackendHealth(url);
      setTestResult(res);
    } catch (err: unknown) {
      setTestResult({
        reachable: false,
        latencyMs: null,
        status: 'unreachable',
        url,
        error: (err as Error)?.message || 'Test failed',
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    await setBackendUrl(url);
    setSavedSuccess(true);
    setTimeout(() => {
      router.back();
    }, 800);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.subtitle}>RUNTIME NETWORKING CONFIGURATION</Text>
        <Text style={styles.title}>FastAPI Backend Target</Text>
        <Text style={styles.description}>
          Configure the active backend URL for real-time mobile API synchronization, SSE event streaming, and local reachability probes.
        </Text>
      </View>

      {/* Manual Input Card */}
      <Card title="Backend URL Endpoint" subtitle="Target Connection">
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={(val) => {
            setUrl(val);
            setSavedSuccess(false);
          }}
          placeholder="http://192.168.1.100:8000"
          placeholderTextColor={colors.text.muted}
          autoCapitalize="none"
          autoCorrect={false}
        />

        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.testButton, testing && styles.buttonDisabled]}
            onPress={handleTest}
            disabled={testing}
            activeOpacity={0.8}
          >
            {testing ? (
              <ActivityIndicator size="small" color={colors.text.primary} />
            ) : (
              <Text style={styles.testButtonText}>PROBE /health</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.saveButton}
            onPress={handleSave}
            activeOpacity={0.8}
          >
            <Text style={styles.saveButtonText}>
              {savedSuccess ? 'SAVED ✓' : 'SAVE & APPLY'}
            </Text>
          </TouchableOpacity>
        </View>

        {testResult && (
          <View
            style={[
              styles.probeResultBox,
              testResult.reachable ? styles.probeSuccess : styles.probeFailure,
            ]}
          >
            <View style={styles.probeHeader}>
              <Badge
                label={testResult.reachable ? 'REACHABLE' : 'UNREACHABLE'}
                variant={testResult.reachable ? 'emerald' : 'coral'}
              />
              {testResult.latencyMs !== null && (
                <Text style={styles.latencyText}>{testResult.latencyMs} ms</Text>
              )}
            </View>
            {testResult.serverInfo && (
              <Text style={styles.serverInfo}>
                {testResult.serverInfo.app || 'MediFlux'} v{testResult.serverInfo.version || '1.0'} [
                {testResult.serverInfo.environment || 'local'}]
              </Text>
            )}
            {testResult.error && (
              <Text style={styles.errorText}>Error: {testResult.error}</Text>
            )}
          </View>
        )}
      </Card>

      {/* 1-Tap Presets */}
      <View style={styles.presetsSection}>
        <Text style={styles.presetSectionTitle}>1-TAP ENVIRONMENT PRESETS</Text>
        <Text style={styles.presetSectionSubtitle}>
          Select your host environment to automatically populate the URL:
        </Text>

        {presets.map((preset) => {
          const isSelected = url.trim() === preset.url.trim();
          return (
            <TouchableOpacity
              key={preset.url}
              style={[styles.presetCard, isSelected && styles.presetCardActive]}
              onPress={() => {
                setUrl(preset.url);
                setSavedSuccess(false);
              }}
              activeOpacity={0.7}
            >
              <View style={styles.presetHeader}>
                <Text style={styles.presetLabel}>{preset.label}</Text>
                {isSelected && <Badge label="ACTIVE" variant="teal" />}
              </View>
              <Text style={styles.presetUrl}>{preset.url}</Text>
              <Text style={styles.presetDescription}>{preset.description}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
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
  input: {
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    fontFamily: 'monospace',
    marginBottom: spacing.md,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  testButton: {
    flex: 1,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  testButtonText: {
    color: colors.text.primary,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  saveButton: {
    flex: 1,
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveButtonText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  probeResultBox: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radii.sm,
    borderWidth: 1,
  },
  probeSuccess: {
    backgroundColor: colors.status.successSubtle,
    borderColor: colors.status.success,
  },
  probeFailure: {
    backgroundColor: colors.status.dangerSubtle,
    borderColor: colors.status.danger,
  },
  probeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  latencyText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  serverInfo: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontWeight: typography.fontWeight.medium,
  },
  errorText: {
    fontSize: typography.fontSize.caption,
    color: colors.status.danger,
    marginTop: 2,
  },
  presetsSection: {
    marginTop: spacing.lg,
  },
  presetSectionTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: 2,
  },
  presetSectionSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginBottom: spacing.sm,
  },
  presetCard: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  presetCardActive: {
    borderColor: colors.accent.primary,
    borderWidth: 1.5,
    backgroundColor: colors.canvas.elevated,
  },
  presetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  presetLabel: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  presetUrl: {
    fontSize: typography.fontSize.caption,
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.semibold,
    fontFamily: 'monospace',
    marginTop: 2,
  },
  presetDescription: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    marginTop: spacing.xs,
  },
});
