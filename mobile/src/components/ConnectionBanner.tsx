import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ViewStyle } from 'react-native';
import { useRouter } from 'expo-router';
import { useBackendHealth } from '../lib/config';
import { colors, spacing, typography, radii } from '../theme/tokens';

export interface ConnectionBannerProps {
  style?: ViewStyle;
  showWhenReachable?: boolean;
}

export const ConnectionBanner: React.FC<ConnectionBannerProps> = ({
  style,
  showWhenReachable = true,
}) => {
  const router = useRouter();
  const { health, refresh } = useBackendHealth(15000);

  const handlePress = () => {
    try {
      router.push('/(auth)/settings' as any);
    } catch {
      // Fallback
      refresh();
    }
  };

  if (health.status === 'reachable' && !showWhenReachable) {
    return null;
  }

  const isReachable = health.status === 'reachable';
  const isChecking = health.status === 'checking';

  const bgColor = isReachable
    ? colors.status.successSubtle
    : isChecking
    ? colors.accent.subtle
    : colors.status.dangerSubtle;

  const borderColor = isReachable
    ? colors.status.success
    : isChecking
    ? colors.accent.primary
    : colors.status.danger;

  const textColor = isReachable
    ? colors.status.success
    : isChecking
    ? colors.accent.primary
    : colors.status.danger;

  let message = 'Checking backend connectivity...';
  if (isReachable) {
    message = `Backend reachable (${health.latencyMs ?? 0} ms) • ${health.url}`;
  } else if (!isChecking) {
    message = `Backend unreachable • Tap to configure URL`;
  }

  return (
    <TouchableOpacity
      style={[
        styles.banner,
        { backgroundColor: bgColor, borderColor },
        style,
      ]}
      onPress={handlePress}
      activeOpacity={0.8}
    >
      <View style={styles.content}>
        <View style={[styles.dot, { backgroundColor: textColor }]} />
        <Text style={[styles.text, { color: textColor }]} numberOfLines={1}>
          {message}
        </Text>
      </View>
      <Text style={[styles.actionText, { color: textColor }]}>
        {isReachable ? 'SETTINGS' : 'CONFIGURE'}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  banner: {
    borderBottomWidth: 1,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.xs + 2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: spacing.sm,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: radii.full,
    marginRight: spacing.sm,
  },
  text: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.medium,
    flex: 1,
  },
  actionText: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.widest,
  },
});

