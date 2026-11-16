import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, typography, radii } from '../theme/tokens';

export interface OfflineStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  style?: ViewStyle;
}

export const OfflineState: React.FC<OfflineStateProps> = ({
  title = 'Network Offline',
  message = 'Device is disconnected from the network. Queued actions will sync automatically when reconnected.',
  onRetry,
  style,
}) => {
  return (
    <View
      style={[styles.container, style]}
      accessibilityRole="alert"
      accessibilityLabel={`${title}: ${message}`}
    >
      <View style={styles.iconContainer}>
        <Ionicons name="cloud-offline-outline" size={40} color={colors.status.warning} />
      </View>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.message}>{message}</Text>
      {onRetry && (
        <TouchableOpacity
          style={styles.button}
          onPress={onRetry}
          activeOpacity={0.8}
          accessibilityRole="button"
          accessibilityLabel="Retry Connection"
          accessibilityHint="Attempts to reconnect and fetch fresh data"
        >
          <Text style={styles.buttonText}>RETRY CONNECTION</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: spacing.xxl,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.status.warning,
    borderRadius: radii.md,
    marginVertical: spacing.md,
  },
  iconContainer: {
    marginBottom: spacing.md,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    marginBottom: spacing.xs,
    textAlign: 'center',
  },
  message: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textAlign: 'center',
    lineHeight: typography.fontSize.caption * 1.5,
    marginBottom: spacing.base,
    maxWidth: 290,
  },
  button: {
    backgroundColor: colors.status.warning,
    minHeight: 44, // Touch target >= 44pt
    minWidth: 160,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    color: '#031211',
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
});
