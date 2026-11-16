import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import NetInfo from '@react-native-community/netinfo';
import { useNetworkStatus, setSimulatedOffline } from '../hooks/useNetworkStatus';
import { colors, spacing, typography, radii } from '../theme/tokens';

export interface GlobalOfflineBannerProps {
  onRetry?: () => void;
}

export const GlobalOfflineBanner: React.FC<GlobalOfflineBannerProps> = ({ onRetry }) => {
  const { isOffline, setSimulatedOffline: setOffline } = useNetworkStatus();
  const [retrying, setRetrying] = useState(false);

  if (!isOffline) {
    return null;
  }

  const handleRetry = async () => {
    setRetrying(true);
    try {
      // 1. If currently in simulated offline mode, clear simulation
      setOffline(false);
      setSimulatedOffline(false);

      // 2. Fetch fresh hardware network status if NetInfo is available
      if (NetInfo && typeof NetInfo.fetch === 'function') {
        await NetInfo.fetch();
      }

      // 3. Trigger optional external retry callback
      if (onRetry) {
        onRetry();
      }
    } catch {
      // Ignore blips
    } finally {
      setTimeout(() => setRetrying(false), 500);
    }
  };

  return (
    <View
      style={styles.banner}
      accessibilityRole="alert"
      accessibilityLabel="Offline mode warning banner"
    >
      <View style={styles.content}>
        <View style={styles.textContainer}>
          <Text style={styles.title}>
            ⚡ OFFLINE MODE — Network connection lost. Queued actions and live stream will automatically recover when reconnected.
          </Text>
        </View>

        <TouchableOpacity
          style={styles.retryButton}
          onPress={handleRetry}
          disabled={retrying}
          activeOpacity={0.8}
          accessibilityRole="button"
          accessibilityLabel="Retry and reconnect network"
          accessibilityHint="Attempts to re-establish connection to network and server"
        >
          {retrying ? (
            <ActivityIndicator size="small" color="#031211" />
          ) : (
            <Text style={styles.retryButtonText}>Retry / Reconnect Now</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  banner: {
    backgroundColor: '#031211', // High-contrast Ink Black
    borderBottomWidth: 2,
    borderBottomColor: colors.status.warning, // Crisp Warning border
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm + 2,
    zIndex: 9999,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.semibold,
    color: '#E8E4D3', // High-contrast Warm Ivory
    lineHeight: 16,
  },
  retryButton: {
    backgroundColor: colors.accent.primary, // Electric Teal #00AEBB
    minHeight: 44, // Touch target >= 44pt
    minWidth: 140,
    paddingHorizontal: spacing.md,
    borderRadius: radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retryButtonText: {
    color: '#031211', // Ink Black text on Electric Teal button
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.normal,
  },
});
