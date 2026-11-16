import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Switch,
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
import {
  loadNotificationPreferences,
  saveNotificationPreferences,
  NotificationPreferences,
} from '../../src/features/notifications/preferences';
import { scheduleLocalNotification } from '../../src/features/notifications/notificationService';
import { apiClient } from '../../src/api/client';
import { useNetworkStatus, setSimulatedOffline } from '../../src/hooks/useNetworkStatus';

export default function SettingsScreen() {
  const router = useRouter();
  const { user, status, logout, reloadProfile, isLoading: authLoading, registeredPushToken } = useAuth();
  const { isDark, themePreference, setThemePreference, toggleTheme } = useTheme();
  const { isOffline } = useNetworkStatus();

  const [url, setUrl] = useState(getBackendUrl());
  const [originalUrl, setOriginalUrl] = useState(getBackendUrl());
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<HealthCheckResult | null>(null);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [reloadingProfile, setReloadingProfile] = useState(false);
  const [devPanelExpanded, setDevPanelExpanded] = useState(true);
  const [devMessage, setDevMessage] = useState<string | null>(null);

  const [notifPrefs, setNotifPrefs] = useState<NotificationPreferences>({
    coldchainAlerts: true,
    approvalAlerts: true,
    pushEnabled: true,
  });
  const [testNotifSent, setTestNotifSent] = useState<boolean>(false);

  const presets = getLanPresetUrls();
  const isAuthenticated = status === 'authenticated' && !!user;
  const badgeInfo = getRoleBadgeInfo(user?.role);

  useEffect(() => {
    setUrl(getBackendUrl());
    void loadNotificationPreferences().then(setNotifPrefs);
  }, []);

  const handleToggleColdChain = async (val: boolean) => {
    const updated = await saveNotificationPreferences({ coldchainAlerts: val });
    setNotifPrefs(updated);
  };

  const handleToggleApprovals = async (val: boolean) => {
    const updated = await saveNotificationPreferences({ approvalAlerts: val });
    setNotifPrefs(updated);
  };

  const handleSendTestNotification = async () => {
    await scheduleLocalNotification(
      'MediFlux Test Alert',
      'Local push delivery operational. Tap to open Cold-Chain.',
      { type: 'batch.quarantined', batchId: 'BIO-INS-01', deepLink: '/cold-chain/BIO-INS-01' },
      'mediflux-coldchain'
    );
    setTestNotifSent(true);
    setTimeout(() => setTestNotifSent(false), 3000);
  };

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

  const handleToggleSimulatedOffline = () => {
    const nextState = !isOffline;
    setSimulatedOffline(nextState);
    setDevMessage(
      nextState
        ? '⚡ Scenario 1 Active: Simulated Network Offline. GlobalOfflineBanner is now displayed.'
        : '✓ Network connection restored to online mode.'
    );
  };

  const handleSimulateBackendDown = async () => {
    if (url.includes(':59999')) {
      await setBackendUrl(originalUrl);
      setUrl(originalUrl);
      setDevMessage('✓ Scenario 2 Restored: Reconnected to active backend: ' + originalUrl);
    } else {
      setOriginalUrl(url);
      const deadUrl = 'http://127.0.0.1:59999';
      await setBackendUrl(deadUrl);
      setUrl(deadUrl);
      setDevMessage('⚡ Scenario 2 Active: Simulated Backend Down. API pointed to unreachable port 59999.');
    }
  };

  const handleSimulateExpiredToken = () => {
    apiClient.setAuth({ token: `simulated.expired.token.${Date.now()}` });
    setDevMessage('⚡ Scenario 3 Active: Simulated Expired JWT Token (401). Next API request triggers silent refresh or clean logout.');
  };

  const handleSimulateStreamDrop = () => {
    setSimulatedOffline(true);
    setDevMessage('⚡ Scenario 4 Active: SSE Stream Drop simulated. Disconnecting for 2s...');
    setTimeout(() => {
      setSimulatedOffline(false);
      setDevMessage('✓ SSE Stream recovering with Last-Event-ID replay or polling fallback.');
    }, 2000);
  };

  const handleSimulateSlowResponse = () => {
    setDevMessage('⚡ Scenario 5 Active: Slow LLM / Network delay simulated (3s)...');
    setTimeout(() => {
      setDevMessage('✓ Simulation complete. Handlers and progress states responded gracefully.');
    }, 3000);
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

      {/* Notification Preferences Card */}
      <Card title="Notification Preferences" subtitle="Push & Local Alert Triggers (Task M7)">
        <View style={styles.notifToggleRow}>
          <View style={styles.notifTextCol}>
            <Text style={styles.notifLabel}>Cold-Chain Quarantine Alerts</Text>
            <Text style={styles.notifSub}>
              Immediate notifications for thermal excursions & auto-quarantine actions
            </Text>
          </View>
          <Switch
            value={notifPrefs.coldchainAlerts}
            onValueChange={handleToggleColdChain}
            trackColor={{ false: '#DFDBCA', true: '#00AEBB' }}
            thumbColor={notifPrefs.coldchainAlerts ? '#F7F5F0' : '#8C887B'}
          />
        </View>

        <View style={styles.divider} />

        <View style={styles.notifToggleRow}>
          <View style={styles.notifTextCol}>
            <Text style={styles.notifLabel}>HITL Approval Alerts</Text>
            <Text style={styles.notifSub}>
              Notifications when a new approval task matches your authorized role
            </Text>
          </View>
          <Switch
            value={notifPrefs.approvalAlerts}
            onValueChange={handleToggleApprovals}
            trackColor={{ false: '#DFDBCA', true: '#00AEBB' }}
            thumbColor={notifPrefs.approvalAlerts ? '#F7F5F0' : '#8C887B'}
          />
        </View>

        <View style={styles.divider} />

        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>DEVICE PUSH TOKEN</Text>
          <Text style={[styles.metaValueMono, !registeredPushToken && styles.metaValueMuted]} numberOfLines={1}>
            {registeredPushToken || 'Not Registered'}
          </Text>
        </View>

        <TouchableOpacity
          style={[styles.testNotifBtn, testNotifSent && styles.testNotifBtnSuccess]}
          onPress={handleSendTestNotification}
          activeOpacity={0.8}
        >
          <Ionicons name="notifications-outline" size={16} color="#FFFFFF" />
          <Text style={styles.testNotifBtnText}>
            {testNotifSent ? 'TEST NOTIFICATION FIRED ✓' : 'SEND TEST NOTIFICATION'}
          </Text>
        </TouchableOpacity>
      </Card>

      {/* Application Metadata & Theme Footer */}
      <Card title="Application Metadata" subtitle="Build & Environment">
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>APP NAME</Text>
          <Text style={styles.metaValue}>NexusChain India (MediFlux)</Text>
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
          <View style={styles.themeLabelCol}>
            <Text style={styles.themeLabel}>INTERFACE THEME</Text>
            <Text style={styles.themeSub}>
              {isDark ? 'Dark Mode (Deep Editorial)' : 'Light Mode (Warm Ivory)'} ({themePreference.toUpperCase()})
            </Text>
          </View>
          <View style={styles.themePillsRow}>
            {(['light', 'dark', 'system'] as const).map((pref) => (
              <TouchableOpacity
                key={pref}
                style={[
                  styles.themePill,
                  themePreference === pref && styles.themePillActive,
                ]}
                onPress={() => setThemePreference(pref)}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel={`Set theme to ${pref}`}
              >
                <Text
                  style={[
                    styles.themePillText,
                    themePreference === pref && styles.themePillTextActive,
                  ]}
                >
                  {pref.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </Card>

      {/* Resilience & Failure Injection Card (__DEV__ mode) */}
      {(typeof __DEV__ === 'undefined' || __DEV__) && (
        <Card
          title="🧪 Resilience & Failure Injection (Dev / Demo)"
          subtitle="1-Tap Mid-Flow Network, Auth, and Stream Failure Scenarios"
        >
          <TouchableOpacity
            style={styles.devCollapseHeader}
            onPress={() => setDevPanelExpanded((prev) => !prev)}
            activeOpacity={0.8}
            accessibilityRole="button"
            accessibilityLabel="Toggle Resilience Failure Injection controls"
          >
            <Text style={styles.devCollapseTitle}>
              {devPanelExpanded ? '▼ HIDE DEV CONTROLS' : '▶ EXPAND 5 RESILIENCE TEST SCENARIOS'}
            </Text>
            <Badge label={isOffline ? 'OFFLINE ACTIVE' : 'ONLINE'} variant={isOffline ? 'coral' : 'emerald'} />
          </TouchableOpacity>

          {devPanelExpanded && (
            <View style={styles.devControlsContainer}>
              <Text style={styles.devDescription}>
                Inject real runtime faults to verify non-crashing recovery, GlobalOfflineBanner, retry handlers, and silent token refresh.
              </Text>

              {devMessage && (
                <View style={styles.devMessageBox}>
                  <Text style={styles.devMessageText}>{devMessage}</Text>
                </View>
              )}

              {/* Scenario 1: Network Offline / Online Toggle */}
              <TouchableOpacity
                style={[styles.devActionBtn, isOffline && styles.devActionBtnActive]}
                onPress={handleToggleSimulatedOffline}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel="Simulate Network Offline or Online"
              >
                <View style={styles.devActionIconCol}>
                  <Ionicons
                    name={isOffline ? 'cloud-done-outline' : 'cloud-offline-outline'}
                    size={20}
                    color={isOffline ? '#10B981' : '#EF4444'}
                  />
                </View>
                <View style={styles.devActionTextCol}>
                  <Text style={styles.devActionTitle}>
                    1. {isOffline ? 'Restore Network (Go Online)' : 'Simulate Network Offline Drop'}
                  </Text>
                  <Text style={styles.devActionSub}>
                    Triggers GlobalOfflineBanner at top and tests queued action recovery.
                  </Text>
                </View>
              </TouchableOpacity>

              {/* Scenario 2: Simulate Backend Down */}
              <TouchableOpacity
                style={[styles.devActionBtn, url.includes(':59999') && styles.devActionBtnActive]}
                onPress={handleSimulateBackendDown}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel="Simulate Backend Server Down"
              >
                <View style={styles.devActionIconCol}>
                  <Ionicons name="server-outline" size={20} color="#F59E0B" />
                </View>
                <View style={styles.devActionTextCol}>
                  <Text style={styles.devActionTitle}>
                    2. {url.includes(':59999') ? 'Restore Active Backend Target' : 'Simulate Backend Down (Port 59999)'}
                  </Text>
                  <Text style={styles.devActionSub}>
                    Points client to unreachable port to test graceful ErrorState and Retry.
                  </Text>
                </View>
              </TouchableOpacity>

              {/* Scenario 3: Simulate Expired JWT Token */}
              <TouchableOpacity
                style={styles.devActionBtn}
                onPress={handleSimulateExpiredToken}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel="Simulate Expired JWT Token 401"
              >
                <View style={styles.devActionIconCol}>
                  <Ionicons name="key-outline" size={20} color="#8B5CF6" />
                </View>
                <View style={styles.devActionTextCol}>
                  <Text style={styles.devActionTitle}>3. Simulate Expired JWT Token (401)</Text>
                  <Text style={styles.devActionSub}>
                    Injects expired token to verify 1-time refresh retry or clean logout.
                  </Text>
                </View>
              </TouchableOpacity>

              {/* Scenario 4: Simulate SSE Stream Drop */}
              <TouchableOpacity
                style={styles.devActionBtn}
                onPress={handleSimulateStreamDrop}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel="Simulate SSE Stream Disconnection"
              >
                <View style={styles.devActionIconCol}>
                  <Ionicons name="radio-outline" size={20} color="#00AEBB" />
                </View>
                <View style={styles.devActionTextCol}>
                  <Text style={styles.devActionTitle}>4. Simulate SSE Stream Drop & Fallback</Text>
                  <Text style={styles.devActionSub}>
                    Drops live SSE connection to verify polling fallback and Last-Event-ID resume.
                  </Text>
                </View>
              </TouchableOpacity>

              {/* Scenario 5: Simulate Slow Response / Camera Permission Denied */}
              <TouchableOpacity
                style={styles.devActionBtn}
                onPress={handleSimulateSlowResponse}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel="Simulate Slow LLM Response and Camera Permission Denied"
              >
                <View style={styles.devActionIconCol}>
                  <Ionicons name="hourglass-outline" size={20} color="#3B82F6" />
                </View>
                <View style={styles.devActionTextCol}>
                  <Text style={styles.devActionTitle}>5. Simulate Slow LLM & Camera Permission Guide</Text>
                  <Text style={styles.devActionSub}>
                    Demonstrates loading spinner states and manual fallback search flows.
                  </Text>
                </View>
              </TouchableOpacity>
            </View>
          )}
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
  notifToggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  notifTextCol: {
    flex: 1,
    marginRight: 12,
  },
  notifLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  notifSub: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    marginTop: 2,
    lineHeight: 14,
  },
  metaValueMono: {
    fontSize: typography.fontSize.micro,
    color: colors.text.primary,
    fontFamily: 'monospace',
    maxWidth: 180,
  },
  metaValueMuted: {
    color: colors.text.muted,
  },
  testNotifBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#031211',
    borderRadius: radii.sm,
    paddingVertical: 10,
    marginTop: 10,
  },
  testNotifBtnSuccess: {
    backgroundColor: '#166534',
  },
  testNotifBtnText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  themeLabelCol: {
    flex: 1,
  },
  themePillsRow: {
    flexDirection: 'row',
    gap: 6,
  },
  themePill: {
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: spacing.xs + 2,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  themePillActive: {
    backgroundColor: colors.accent.primary,
    borderColor: colors.accent.primary,
  },
  themePillText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.normal,
  },
  themePillTextActive: {
    color: '#031211',
  },
  devCollapseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    minHeight: 44,
  },
  devCollapseTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.wide,
  },
  devControlsContainer: {
    marginTop: spacing.sm,
    gap: spacing.sm,
  },
  devDescription: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    lineHeight: 14,
    marginBottom: spacing.xs,
  },
  devMessageBox: {
    backgroundColor: colors.status.warningSubtle,
    borderWidth: 1,
    borderColor: colors.status.warning,
    borderRadius: radii.sm,
    padding: spacing.sm,
  },
  devMessageText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
  },
  devActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    minHeight: 52,
    gap: spacing.md,
  },
  devActionBtnActive: {
    borderColor: colors.status.warning,
    backgroundColor: colors.status.warningSubtle,
  },
  devActionIconCol: {
    width: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  devActionTextCol: {
    flex: 1,
  },
  devActionTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  devActionSub: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    marginTop: 2,
    lineHeight: 13,
  },
});
