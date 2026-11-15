import React from 'react';
import { View, Text, StyleSheet, ViewStyle, TextStyle } from 'react-native';
import { colors, spacing, radii, typography } from '../theme/tokens';

export type BadgeVariant = 'teal' | 'emerald' | 'amber' | 'coral' | 'neutral';

export interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export const Badge: React.FC<BadgeProps> = ({
  label,
  variant = 'teal',
  style,
  textStyle,
}) => {
  const getColors = () => {
    switch (variant) {
      case 'teal':
        return {
          bg: colors.accent.subtle,
          border: colors.accent.border,
          text: colors.accent.primary,
        };
      case 'emerald':
        return {
          bg: colors.status.successSubtle,
          border: colors.status.success,
          text: colors.status.success,
        };
      case 'amber':
        return {
          bg: colors.status.warningSubtle,
          border: colors.status.warning,
          text: colors.status.warning,
        };
      case 'coral':
        return {
          bg: colors.status.dangerSubtle,
          border: colors.status.danger,
          text: colors.status.danger,
        };
      case 'neutral':
      default:
        return {
          bg: colors.canvas.elevated,
          border: colors.border.default,
          text: colors.text.secondary,
        };
    }
  };

  const scheme = getColors();

  return (
    <View
      style={[
        styles.badge,
        { backgroundColor: scheme.bg, borderColor: scheme.border },
        style,
      ]}
    >
      <Text style={[styles.text, { color: scheme.text }, textStyle]}>
        {label.toUpperCase()}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    borderWidth: 1,
    borderRadius: radii.sm, // Editorial crisp 2px radius — NO pill shape
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    alignSelf: 'flex-start',
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    letterSpacing: typography.letterSpacing.wide,
  },
});
