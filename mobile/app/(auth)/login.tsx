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
import { apiClient } from '../../src/api/client';
import { useBackendHealth } from '../../src/lib/config';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Badge } from '../../src/components/Badge';
import { Card } from '../../src/components/Card';

const DEMO_ROLES = [
  { role: 'pharmacy', title: 'Retail Pharmacist', email: 'pharmacist@mediflux.in', node: 'Apollo Pharmacy - CP' },
  { role: 'stockist', title: 'Stockist Hub Manager', email: 'stockist@mediflux.in', node: 'North Delhi Stockist Hub' },
  { role: 'distributor', title: 'Logistics Director', email: 'distributor@mediflux.in', node: 'Northern Depot' },
  { role: 'manufacturer', title: 'Plant Ops Manager', email: 'plant@mediflux.in', node: 'Sun Pharma Plant - Baddi' },
  { role: 'regulator', title: 'CDSCO Regulator', email: 'regulator@mediflux.in', node: 'CDSCO HQ' },
  { role: 'admin', title: 'Network Admin', email: 'admin@mediflux.in', node: 'Control Tower' },
];

export default function LoginScreen() {
  const router = useRouter();
  const { health } = useBackendHealth();
  const [email, setEmail] = useState('pharmacist@mediflux.in');
  const [password, setPassword] = useState('mediflux-demo-2026');
  const [loading, setLoading] = useState(false);
  const [selectedRole, setSelectedRole] = useState('pharmacy');

  const handleDemoSelect = (roleItem: (typeof DEMO_ROLES)[0]) => {
    setEmail(roleItem.email);
    setSelectedRole(roleItem.role);
  };

  const handleLogin = async () => {
    setLoading(true);
    try {
      // Set auth context for operational calls
      apiClient.setAuth({
        token: `demo-token-${selectedRole}`,
        role: selectedRole,
        userId: `usr-${selectedRole}-001`,
        nodeId: `node-${selectedRole}-001`,
      });

      router.replace('/(tabs)');
    } catch {
      // In Task M1, proceed directly to workspace
      router.replace('/(tabs)');
    } finally {
      setLoading(false);
    }
  };

  const isReachable = health.status === 'reachable';

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.brandSubtitle}>SUPPLY CHAIN ACCESS PORTAL</Text>
        <Text style={styles.brandTitle}>Sign In to MediFlux</Text>
        <Text style={styles.description}>
          Authenticate via Supabase Auth or select a seeded operational role to inspect node operations.
        </Text>
      </View>

      {/* Backend Status Card */}
      <Card style={styles.statusCard}>
        <View style={styles.statusRow}>
          <View>
            <Text style={styles.statusLabel}>BACKEND ENDPOINT</Text>
            <Text style={styles.statusUrl} numberOfLines={1}>{health.url}</Text>
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

      {/* Credentials Form */}
      <View style={styles.form}>
        <Text style={styles.inputLabel}>EMAIL ADDRESS</Text>
        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          placeholder="operator@mediflux.in"
          placeholderTextColor={colors.text.muted}
          autoCapitalize="none"
          keyboardType="email-address"
        />

        <Text style={styles.inputLabel}>PASSWORD</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          placeholder="••••••••••••"
          placeholderTextColor={colors.text.muted}
          secureTextEntry
        />

        <TouchableOpacity
          style={styles.submitButton}
          onPress={handleLogin}
          disabled={loading}
          activeOpacity={0.8}
        >
          {loading ? (
            <ActivityIndicator color={colors.text.onAccent} />
          ) : (
            <Text style={styles.submitButtonText}>CONTINUE TO OPERATIONAL WORKSPACE →</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Seeded Quick-Login Roles */}
      <View style={styles.rolesSection}>
        <Text style={styles.rolesTitle}>SEEDED DEMO ROLES (7 TIERS)</Text>
        <Text style={styles.rolesSubtitle}>
          Tap any seeded role for instant evaluation credentials:
        </Text>

        {DEMO_ROLES.map((item) => {
          const isSelected = selectedRole === item.role;
          return (
            <TouchableOpacity
              key={item.role}
              style={[styles.roleCard, isSelected && styles.roleCardSelected]}
              onPress={() => handleDemoSelect(item)}
              activeOpacity={0.7}
            >
              <View style={styles.roleCardHeader}>
                <Text style={styles.roleTitle}>{item.title}</Text>
                <Badge
                  label={item.role}
                  variant={isSelected ? 'teal' : 'neutral'}
                />
              </View>
              <Text style={styles.roleEmail}>{item.email}</Text>
              <Text style={styles.roleNode}>{item.node}</Text>
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
    marginTop: spacing.base,
    marginBottom: spacing.base,
  },
  brandSubtitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: spacing.xs,
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
  statusLabel: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.wide,
  },
  statusUrl: {
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontWeight: typography.fontWeight.medium,
    marginTop: 2,
  },
  settingsLink: {
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  settingsLinkText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
    letterSpacing: typography.letterSpacing.wide,
  },
  form: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.md,
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
    backgroundColor: colors.canvas.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    marginBottom: spacing.md,
  },
  submitButton: {
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.md,
    borderRadius: radii.sm, // Editorial crisp 2px radius
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  submitButtonText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
  rolesSection: {
    marginTop: spacing.sm,
  },
  rolesTitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: 2,
  },
  rolesSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginBottom: spacing.sm,
  },
  roleCard: {
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  roleCardSelected: {
    borderColor: colors.accent.primary,
    borderWidth: 1.5,
    backgroundColor: colors.canvas.elevated,
  },
  roleCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  roleTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  roleEmail: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
  },
  roleNode: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    marginTop: 2,
  },
});

