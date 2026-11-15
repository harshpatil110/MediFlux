import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { apiClient } from '../src/api/client';
import { colors, spacing, typography, radii } from '../src/theme/tokens';

export default function IndexScreen() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function checkAuth() {
      try {
        const auth = await apiClient.restoreSession();
        if (auth.token) {
          router.replace('/(tabs)');
        } else {
          router.replace('/(auth)/login');
        }
      } catch {
        router.replace('/(auth)/login');
      } finally {
        setChecking(false);
      }
    }

    checkAuth();
  }, [router]);

  return (
    <View style={styles.container}>
      <Text style={styles.brandSubtitle}>PHARMA 4-TIER AUTONOMOUS SUPPLY CHAIN</Text>
      <Text style={styles.brandTitle}>MEDIFLUX</Text>
      <Text style={styles.tagline}>Operational Field Companion</Text>

      {checking ? (
        <ActivityIndicator size="large" color={colors.accent.primary} style={styles.loader} />
      ) : (
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={styles.button}
            onPress={() => router.replace('/(auth)/login')}
            activeOpacity={0.8}
          >
            <Text style={styles.buttonText}>ENTER PORTAL</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  brandSubtitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: spacing.xs,
  },
  brandTitle: {
    fontSize: typography.fontSize.display,
    fontWeight: typography.fontWeight.black,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.tight,
  },
  tagline: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginTop: spacing.xs,
    marginBottom: spacing.xxl,
  },
  loader: {
    marginTop: spacing.xl,
  },
  actionRow: {
    width: '100%',
    maxWidth: 280,
    marginTop: spacing.xl,
  },
  button: {
    backgroundColor: colors.accent.primary,
    paddingVertical: spacing.md,
    borderRadius: radii.sm, // Editorial crisp 2px
    alignItems: 'center',
  },
  buttonText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.widest,
  },
});

