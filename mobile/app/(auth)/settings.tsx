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
import Constants from 'expo-constants';
import { Ionicons } from '@expo/vector-icons';
import {
  getBackendUrl,
  setBackendUrl,
  checkBackendHealth,
  getLanPresetUrls,
  HealthCheckResult,
} from '../../src/lib/config';
import { useAuth } from '../../src/features/auth/AuthContext';
import { getRoleBadgeInfo } from '../../src/features/auth/roleMap';
import { useTheme } from '../../src/theme/ThemeContext';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Badge } from '../../src/components/Badge';
import { Card } from '../../src/components/Card';

export default function SettingsScreen() {
  const router = useRouter();
  const { user, status, logout, reloadProfile, isLoading: authLoading } = useAuth();
  const { isDark, toggleTheme } = useTheme();

  const [url, setUrl] = useState(getBackendUrl());
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<HealthCheckResult | null>(null);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [reloadingProfile, setReloadingProfile] = useState(false);

  const presets = getLanPresetUrls();
  const isAuthenticated = status === 'authenticated' && !!user;
  const badgeInfo = getRoleBadgeInfo(user?.role);

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
      setSavedSuccess(false);
    }, 2000);
  };

  const handleLogout = async () => {
    await logout();
    router.replace('/(auth)/login');
  };

  const handleReloadProfile = async () => {
    setReloadingProfile(true);
    try {
      await reloadProfile();
    } finally {
      setReloadingProfile(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header with back button */}
      <View style={styles.header}>
        <View style={styles.navRow}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => {
              if (router.canGoBack()) {
                router.back();
              } else if (isAuthenticated) {
                router.replace('/(tabs)');
              } else {
                router.replace('/(auth)/login');
              }
            }}
            accessibilityLabel="Back"
          >
            <Ionicons name="arrow-back" size={18} color={colors.text.primary} />
            <Text style={styles.backButtonText}>BACK</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.subtitle}>RUNTIME NETWORKING & IDENTITY</Text>
        <Text style={styles.title}>System Settings</Text>
        <Text style={styles.description}>
          Configure backend connectivity, inspect active role permissions, and control operational environment parameters.
        </Text>
      </View>

      {/* Authenticated User Profile Card */}
      {isAuthenticated && user && (
        <Card title="Active Operator Profile" subtitle="Supabase & RLS Bound Node">
          <View style={styles.profileCard}>
            <View style={styles.profileHeaderRow}>
              <View style={styles.profileNameCol}>
                <Text style={styles.userName}>{user.full_name || user.email}</Text>
                <Text style={styles.userEmail}>{user.email}</Text>
              </View>
              <View style={[styles.roleBadgePill, { backgroundColor: badgeInfo.badgeBg }]}>
                <Text style={[styles.roleBadgeText, { color: badgeInfo.badgeTextColor }]}>
                  {badgeInfo.label}
                </Text>
              </View>
            </View>

            <View style={styles.divider} />

            <View style={styles.profileDetailRow}>
              <Text style={styles.detailLabel}>ASSIGNED NODE</Text>
              <Text style={styles.detailValueBold}>{user.node_name || 'All Nodes'}</Text>
            </View>

            <View style={styles.profileDetailRow}>
              <Text style={styles.detailLabel}>NODE ID</Text>
              <Text style={styles.detailValueMono}>{user.node_id || 'unassigned-root'}</Text>
            </View>

            <View style={styles.profileDetailRow}>
              <Text style={styles.detailLabel}>TIER / REGION</Text>
              <Text style={styles.detailValue}>
                {(user.tier || 'network').toUpperCase()} • {user.region || 'National'}
              </Text>
            </View>

            <View style={styles.profileDetailRow}>
              <Text style={styles.detailLabel}>HITL APPROVAL POLICY</Text>
              <View style={styles.policyRow}>
                <Ionicons
                  name="shield-checkmark-outline"
                  size={14}
                  color={badgeInfo.isApprover ? colors.accent.primary : '#5C584E'}
                />
                <Text
                  style={[
                    styles.policyText,
                    { color: badgeInfo.isApprover ? colors.accent.primary : '#5C584E' },
                  ]}
                >
                  {badgeInfo.isApprover ? 'Decide & Authorize (Approver)' : 'Read-Only (View-Only)'}
                </Text>
              </View>
            </View>

            <View style={styles.profileActionsRow}>
              <TouchableOpacity
                style={styles.refreshProfileBtn}
                onPress={handleReloadProfile}
                disabled={reloadingProfile}
                activeOpacity={0.7}
              >
                <Ionicons name="refresh-outline" size={14} color={colors.text.secondary} />
                <Text style={styles.refreshProfileBtnText}>
                  {reloadingProfile ? 'SYNCING...' : 'SYNC WITH /api/v1/me'}
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.logoutBtn}
                onPress={handleLogout}
                disabled={authLoading}
                activeOpacity={0.7}
              >
                <Ionicons name="log-out-outline" size={14} color="#DC2626" />
                <Text style={styles.logoutBtnText}>LOGOUT</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Card>
      )}

      {/* Backend URL Configuration */}
      <Card title="FastAPI Backend Target" subtitle="Runtime API & SSE Endpoint">
        <Text style={styles.inputHelp}>
          Editing this updates the active API target immediately without restarting the app.
        </Text>
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
              <View style={styles.btnInnerRow}>
                <Ionicons name="server-outline" size={14} color={colors.text.primary} />
                <Text style={styles.testButtonText}>PROBE /health</Text>
              </View>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.saveButton, savedSuccess && styles.saveButtonSuccess]}
            onPress={handleSave}
            activeOpacity={0.8}
          >
            <View style={styles.btnInnerRow}>
              {savedSuccess && <Ionicons name="checkmark-circle-outline" size={14} color="#FFFFFF" />}
              <Text style={styles.saveButtonText}>
                {savedSuccess ? 'SAVED' : 'SAVE BACKEND URL'}
              </Text>
            </View>
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

      {/* Application Metadata & Theme Footer */}
      <Card title="Application Metadata" subtitle="Build & Environment">
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>APP NAME</Text>
          <Text style={styles.metaValue}>MediFlux Field & POS</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>CLIENT VERSION</Text>
          <Text style={styles.metaValue}>
            {Constants.expoConfig?.version ?? '1.0.0'} (Expo SDK 51)
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>BUILD ENVIRONMENT</Text>
          <Text style={styles.metaValue}>
            {typeof __DEV__ !== 'undefined' && __DEV__ ? 'Development' : 'Production'}
          </Text>
        </View>

        <View style={styles.divider} />

        <View style={styles.themeToggleRow}>
          <View>
            <Text style={styles.themeLabel}>INTERFACE THEME</Text>
            <Text style={styles.themeSub}>
              {isDark ? 'Dark Mode (Deep Editorial)' : 'Light Mode (Warm Ivory)'}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.themeBtn}
            onPress={toggleTheme}
            activeOpacity={0.7}
          >
            {isDark ? (
              <Ionicons name="sunny-outline" size={16} color={colors.accent.primary} />
            ) : (
              <Ionicons name="moon-outline" size={16} color={colors.text.primary} />
            )}
            <Text style={styles.themeBtnText}>TOGGLE</Text>
          </TouchableOpacity>
        </View>
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
    gap: spacing.base,
  },
  header: {
    marginBottom: spacing.xs,
  },
  navRow: {
    flexDirection: 'row',
    marginBottom: spacing.sm,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    borderColor: colors.border.default,
    borderWidth: 1,
  },
  backButtonText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    letterSpacing: 0.5,
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
  profileCard: {
    paddingTop: 2,
  },
  profileHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  profileNameCol: {
    flex: 1,
    marginRight: spacing.sm,
  },
  userName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  userEmail: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: 2,
  },
  roleBadgePill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: '#D8D3C3',
  },
  roleBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    fontFamily: 'monospace',
    letterSpacing: 0.5,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border.default,
    marginVertical: spacing.sm + 2,
  },
  profileDetailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs + 2,
  },
  detailLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
  },
  detailValue: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
  },
  detailValueBold: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  detailValueMono: {
    fontSize: typography.fontSize.micro,
    fontFamily: 'monospace',
    color: colors.text.secondary,
  },
  policyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  policyText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.semibold,
  },
  profileActionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginTop: spacing.sm + 2,
  },
  refreshProfileBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: spacing.sm,
    backgroundColor: colors.canvas.surface,
    borderColor: colors.border.default,
    borderWidth: 1,
    borderRadius: radii.sm,
  },
  refreshProfileBtnText: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.text.secondary,
    letterSpacing: 0.5,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: '#FEE2E2',
    borderColor: '#F87171',
    borderWidth: 1,
    borderRadius: radii.sm,
  },
  logoutBtnText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#991B1B',
    letterSpacing: 0.5,
  },
  inputHelp: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    marginBottom: spacing.xs,
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
  btnInnerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
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
  saveButtonSuccess: {
    backgroundColor: '#059669',
  },
  saveButtonText: {
    color: '#FFFFFF',
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
    backgroundColor: '#F0FDF4',
    borderColor: '#86EFAC',
  },
  probeFailure: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FECACA',
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
    fontFamily: 'monospace',
    color: colors.text.primary,
  },
  serverInfo: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontFamily: 'monospace',
  },
  errorText: {
    fontSize: typography.fontSize.caption,
    color: '#DC2626',
    marginTop: spacing.xs,
  },
  presetsSection: {
    marginTop: spacing.xs,
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
  },
  presetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  presetLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  presetUrl: {
    fontSize: typography.fontSize.caption,
    color: colors.accent.primary,
    fontFamily: 'monospace',
    marginBottom: 2,
  },
  presetDescription: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs + 2,
  },
  metaLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
  },
  metaValue: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
  },
  themeToggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  themeLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
  },
  themeSub: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    marginTop: 2,
  },
  themeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 6,
    paddingHorizontal: 10,
    backgroundColor: colors.canvas.surface,
    borderColor: colors.border.default,
    borderWidth: 1,
    borderRadius: radii.sm,
  },
  themeBtnText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.text.primary,
    letterSpacing: 0.5,
  },
});
