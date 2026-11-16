import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ViewStyle } from 'react-native';
import { colors, spacing, radii, typography } from '../theme/tokens';
import { ApiError } from '../api/generated';

export interface ErrorStateProps {
  error: ApiError | Error | string | null;
  onRetry?: () => void;
  style?: ViewStyle;
}

export const ErrorState: React.FC<ErrorStateProps> = ({ error, onRetry, style }) => {
  if (!error) return null;

  const code = error instanceof ApiError ? error.code : 'ERROR';
  const message =
    error instanceof Error ? error.message : typeof error === 'string' ? error : 'An error occurred';
  const details = error instanceof ApiError && error.details ? JSON.stringify(error.details) : null;

  return (
    <View
      style={[styles.container, style]}
      accessibilityRole="alert"
      accessibilityLabel={`Error ${code}: ${message}`}
    >
      <View style={styles.header}>
        <Text style={styles.code}>{code}</Text>
      </View>
      <Text style={styles.message}>{message}</Text>
      {details && <Text style={styles.details}>{details}</Text>}
      {onRetry && (
        <TouchableOpacity
          style={styles.button}
          onPress={onRetry}
          activeOpacity={0.8}
          accessibilityRole="button"
          accessibilityLabel="Retry failed request"
          accessibilityHint="Attempts to re-execute the failed operation"
        >
          <Text style={styles.buttonText}>RETRY</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: spacing.base,
    backgroundColor: colors.status.dangerSubtle,
    borderWidth: 1,
    borderColor: colors.status.danger,
    borderRadius: radii.md,
    marginVertical: spacing.md,
  },
  header: {
    marginBottom: spacing.xs,
  },
  code: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.status.danger,
    letterSpacing: typography.letterSpacing.widest,
  },
  message: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  details: {
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
    fontFamily: 'monospace',
    marginBottom: spacing.sm,
  },
  button: {
    backgroundColor: colors.status.danger,
    minHeight: 44, // Touch target >= 44pt
    minWidth: 100,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
    alignSelf: 'flex-start',
  },
  buttonText: {
    color: colors.text.onAccent,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
});
