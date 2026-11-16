import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator, ViewStyle } from 'react-native';
import { colors, spacing, typography, radii } from '../theme/tokens';

export interface LoadingStateProps {
  message?: string;
  subtitle?: string;
  style?: ViewStyle;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading data...',
  subtitle,
  style,
}) => {
  return (
    <View
      style={[styles.container, style]}
      accessibilityRole="progressbar"
      accessibilityLabel={message}
    >
      <ActivityIndicator size="large" color={colors.accent.primary} style={styles.spinner} />
      <Text style={styles.message}>{message}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
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
    borderColor: colors.border.default,
    borderRadius: radii.md,
    marginVertical: spacing.md,
  },
  spinner: {
    marginBottom: spacing.md,
  },
  message: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    textAlign: 'center',
    lineHeight: typography.fontSize.caption * 1.4,
    maxWidth: 280,
  },
});
