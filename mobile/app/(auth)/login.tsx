import React, { useState } from 'react';
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
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../src/features/auth/AuthContext';
import { useBackendHealth } from '../../src/lib/config';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Badge } from '../../src/components/Badge';
import { Card } from '../../src/components/Card';

const DEMO_ROLES = [
  {
    role: 'pharmacy',
    title: 'Retail Pharmacist',
    email: 'pharmacy@mediflux.in',
    node: 'Apollo Pharmacy - CP',
    tier: 'Tier 1 (Retail)',
  },
  {
    role: 'stockist',
    title: 'Stockist Hub Manager',
    email: 'stockist@mediflux.in',
    node: 'North Delhi Stockist Hub',
    tier: 'Tier 2 (Stockist)',
  },
  {
    role: 'distributor',
    title: 'Logistics Director',
    email: 'distributor@mediflux.in',
    node: 'Northern India Regional Depot',
    tier: 'Tier 3 (Distributor)',
  },
  {
    role: 'manufacturer',
    title: 'Plant Operations Manager',
    email: 'manufacturer@mediflux.in',
    node: 'Sun Pharma Plant - Baddi',
    tier: 'Tier 4 (Manufacturer)',
  },
  {
    role: 'admin',
    title: 'Network Control Tower Admin',
    email: 'admin@mediflux.in',
    node: 'National Control Tower',
    tier: 'All Tiers',
  },
];

export default function LoginScreen() {
  const router = useRouter();
  const { login, loginAsDemoRole, error, clearError, isLoading } = useAuth();
  const { health } = useBackendHealth();

  const [email, setEmail] = useState('pharmacy@mediflux.in');
  const [password, setPassword] = useState('PharmPassword123!');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const isReachable = health.status === 'reachable';
  const showDevChips = typeof __DEV__ !== 'undefined' ? __DEV__ : process.env.NODE_ENV !== 'production';

  const handleLogin = async () => {
    clearError();
    setLocalError(null);
    if (!email.trim()) {
      setLocalError('Please enter your email address.');
      return;
    }
    if (!password) {
      setLocalError('Please enter your password.');
      return;
    }

    try {
      await login(email.trim(), password);
      router.replace('/(tabs)');
    } catch {
      // Error handled via AuthContext
    }
  };

  const handleDemoQuickLogin = async (role: string, roleEmail: string) => {
    clearError();
    setLocalError(null);
    setEmail(roleEmail);
    try {
      await loginAsDemoRole(role);
      router.replace('/(tabs)');
    } catch {
      // Error handled via AuthContext
    }
  };

  const displayedError = localError || error;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Brand Header */}
      <View style={styles.header}>
        <View style={styles.topRow}>
          <Text style={styles.brandSubtitle}>SUPPLY CHAIN ACCESS PORTAL</Text>
          <TouchableOpacity
            style={styles.settingsHeaderBtn}
            onPress={() => router.push('/(auth)/settings')}
            accessibilityLabel="Backend Settings"
          >
            <Ionicons name="settings-outline" size={18} color={colors.text.secondary} />
          </TouchableOpacity>
        </View>
        <Text style={styles.brandTitle}>Sign In to MediFlux</Text>
        <Text style={styles.description}>
          Authenticate via Supabase Auth or select a seeded operational role to inspect node operations.
        </Text>
      </View>

      {/* Backend Status Card */}
      <Card style={styles.statusCard}>
        <View style={styles.statusRow}>
          <View style={styles.statusInfo}>
            <Text style={styles.statusLabel}>TARGET FASTAPI BACKEND</Text>
            <Text style={styles.statusUrl} numberOfLines={1}>
              {health.url}
            </Text>
          </View>
          <Badge
            label={isReachable ? `${health.latencyMs ?? 0}ms OK` : 'OFFLINE'}
            variant={isReachable ? 'emerald' : 'coral'}
          />
        </View>
        <TouchableOpacity
          style={styles.settingsLink}
          onPress={() => router.push('/(auth)/settings')}
        >
          <Text style={styles.settingsLinkText}>CONFIGURE SERVER SETTINGS →</Text>
        </TouchableOpacity>
      </Card>

      {/* Error Banner */}
      {displayedError ? (
        <View style={styles.errorBanner}>
          <Ionicons name="alert-circle-outline" size={16} color="#DC2626" />
          <Text style={styles.errorBannerText}>{displayedError}</Text>
        </View>
      ) : null}

      {/* Credentials Form */}
      <View style={styles.form}>
        <Text style={styles.inputLabel}>EMAIL ADDRESS</Text>
        <TextInput
          style={styles.input}
          value={email}
          onChangeText={(val) => {
            setEmail(val);
            if (localError) setLocalError(null);
          }}
          placeholder="operator@mediflux.in"
          placeholderTextColor={colors.text.muted}
          autoCapitalize="none"
          keyboardType="email-address"
          autoCorrect={false}
        />

        <Text style={styles.inputLabel}>PASSWORD</Text>
        <View style={styles.passwordContainer}>
          <TextInput
            style={styles.passwordInput}
            value={password}
            onChangeText={(val) => {
              setPassword(val);
              if (localError) setLocalError(null);
            }}
            placeholder="••••••••••••"
            placeholderTextColor={colors.text.muted}
            secureTextEntry={!showPassword}
          />
          <TouchableOpacity
            style={styles.eyeButton}
            onPress={() => setShowPassword((prev) => !prev)}
            accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? (
              <Ionicons name="eye-off-outline" size={18} color={colors.text.secondary} />
            ) : (
              <Ionicons name="eye-outline" size={18} color={colors.text.secondary} />
            )}
          </TouchableOpacity>
        </View>

        <TouchableOpacity
          style={[styles.loginButton, isLoading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={isLoading}
          activeOpacity={0.8}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <View style={styles.buttonInner}>
              <Text style={styles.loginButtonText}>AUTHENTICATE & ENTER</Text>
              <Ionicons name="arrow-forward" size={16} color="#FFFFFF" />
            </View>
          )}
        </TouchableOpacity>
      </View>

      {/* Development Quick-Login Chips */}
      {showDevChips && (
        <View style={styles.demoSection}>
          <View style={styles.demoHeader}>
            <Text style={styles.demoSectionTitle}>QUICK DEMO ROLES (DEV MODE)</Text>
            <Badge label="SEEDED" variant="teal" />
          </View>
          <Text style={styles.demoSubtitle}>
            Tap any role to authenticate instantly with its pre-bound supply node and permissions:
          </Text>

          <View style={styles.demoChipsContainer}>
            {DEMO_ROLES.map((d) => {
              return (
                <TouchableOpacity
                  key={d.role}
                  style={styles.demoCard}
                  onPress={() => handleDemoQuickLogin(d.role, d.email)}
                  disabled={isLoading}
                  activeOpacity={0.7}
                >
                  <View style={styles.demoCardHeader}>
                    <Text style={styles.demoCardTitle}>{d.title}</Text>
                    <View style={styles.roleTag}>
                      <Text style={styles.roleTagText}>{d.role.toUpperCase()}</Text>
                    </View>
                  </View>
                  <Text style={styles.demoCardNode}>{d.node}</Text>
                  <Text style={styles.demoCardTier}>{d.tier}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      )}

      {/* Footer Info */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={styles.footerLink}
          onPress={() => router.push('/(auth)/settings')}
        >
          <Text style={styles.footerLinkText}>⚙ Open Networking & Runtime Settings</Text>
        </TouchableOpacity>
        <Text style={styles.footerSecurityNote}>
          MediFlux enforces strict Row-Level Security (RLS). Operations are cryptographically
          anchored to your authenticated node ID.
        </Text>
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
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  brandSubtitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
  },
  settingsHeaderBtn: {
    padding: 6,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    borderColor: colors.border.default,
    borderWidth: 1,
  },
  brandTitle: {
    fontSize: typography.fontSize.h1,
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
  statusCard: {
    marginBottom: spacing.base,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  statusInfo: {
    flex: 1,
    marginRight: spacing.sm,
  },
  statusLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: 2,
  },
  statusUrl: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontFamily: 'monospace',
  },
  settingsLink: {
    borderTopWidth: 1,
    borderTopColor: colors.border.default,
    paddingTop: spacing.xs + 2,
  },
  settingsLinkText: {
    fontSize: typography.fontSize.micro,
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEE2E2',
    borderWidth: 1,
    borderColor: '#F87171',
    borderRadius: radii.sm,
    padding: spacing.sm,
    marginBottom: spacing.base,
    gap: spacing.xs,
  },
  errorBannerText: {
    flex: 1,
    fontSize: typography.fontSize.caption,
    color: '#991B1B',
    fontWeight: typography.fontWeight.medium,
  },
  form: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.base,
    marginBottom: spacing.lg,
  },
  inputLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    marginBottom: spacing.md,
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.primary,
    marginBottom: spacing.lg,
  },
  passwordInput: {
    flex: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
  },
  eyeButton: {
    paddingHorizontal: spacing.sm + 4,
    paddingVertical: spacing.sm,
  },
  loginButton: {
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.md,
    borderRadius: radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  loginButtonText: {
    color: '#FFFFFF',
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  demoSection: {
    marginBottom: spacing.xl,
  },
  demoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  demoSectionTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
  },
  demoSubtitle: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    marginBottom: spacing.sm,
  },
  demoChipsContainer: {
    gap: spacing.sm,
  },
  demoCard: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.sm + 2,
  },
  demoCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  demoCardTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  roleTag: {
    backgroundColor: colors.canvas.elevated,
    borderColor: colors.border.default,
    borderWidth: 0.5,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 3,
  },
  roleTagText: {
    fontSize: 9,
    fontFamily: 'monospace',
    fontWeight: '700',
    color: colors.accent.primary,
  },
  demoCardNode: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginBottom: 1,
  },
  demoCardTier: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
  },
  footer: {
    alignItems: 'center',
    marginTop: spacing.md,
  },
  footerLink: {
    paddingVertical: spacing.sm,
    marginBottom: spacing.xs,
  },
  footerLinkText: {
    fontSize: typography.fontSize.caption,
    color: colors.accent.primary,
    fontWeight: typography.fontWeight.bold,
  },
  footerSecurityNote: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    textAlign: 'center',
    lineHeight: 14,
    paddingHorizontal: spacing.lg,
  },
});
