import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { colors, spacing, radii, typography, shadows } from '../theme/tokens';

export interface CardProps {
  title?: string;
  subtitle?: string;
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  style?: ViewStyle;
  variant?: 'surface' | 'elevated';
}

export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  headerRight,
  children,
  style,
  variant = 'surface',
}) => {
  const isElevated = variant === 'elevated';

  return (
    <View
      style={[
        styles.card,
        isElevated ? styles.elevated : styles.surface,
        style,
      ]}
    >
      {(title || subtitle || headerRight) && (
        <View style={styles.header}>
          <View style={styles.headerTextContainer}>
            {subtitle && <Text style={styles.subtitle}>{subtitle.toUpperCase()}</Text>}
            {title && <Text style={styles.title}>{title}</Text>}
          </View>
          {headerRight && <View style={styles.headerRight}>{headerRight}</View>}
        </View>
      )}
      <View style={styles.content}>{children}</View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.md,
    padding: spacing.base,
    marginBottom: spacing.base,
    ...shadows.subtle,
  },
  surface: {
    backgroundColor: colors.canvas.surface,
  },
  elevated: {
    backgroundColor: colors.canvas.elevated,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.subtle,
  },
  headerTextContainer: {
    flex: 1,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    letterSpacing: typography.letterSpacing.tight,
  },
  subtitle: {
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.secondary,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: 2,
  },
  headerRight: {
    marginLeft: spacing.sm,
  },
  content: {},
});

