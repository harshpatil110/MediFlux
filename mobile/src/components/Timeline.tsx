import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { colors, spacing, radii, typography } from '../theme/tokens';

export interface TimelineItem {
  id: string;
  title: string;
  subtitle?: string;
  timestamp?: string;
  status: 'completed' | 'active' | 'pending' | 'failed';
  description?: string;
}

export interface TimelineProps {
  items: TimelineItem[];
  style?: ViewStyle;
}

export const Timeline: React.FC<TimelineProps> = ({ items, style }) => {
  return (
    <View style={[styles.container, style]}>
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        const isCompleted = item.status === 'completed';
        const isActive = item.status === 'active';
        const isFailed = item.status === 'failed';

        const dotColor = isFailed
          ? colors.status.danger
          : isCompleted
          ? colors.status.success
          : isActive
          ? colors.accent.primary
          : colors.border.default;

        return (
          <View key={item.id} style={styles.row}>
            <View style={styles.indicatorContainer}>
              <View style={[styles.dot, { backgroundColor: dotColor }]} />
              {!isLast && <View style={styles.line} />}
            </View>
            <View style={[styles.content, isLast ? styles.lastContent : null]}>
              <View style={styles.itemHeader}>
                <Text style={styles.title}>{item.title}</Text>
                {item.timestamp && <Text style={styles.timestamp}>{item.timestamp}</Text>}
              </View>
              {item.subtitle && <Text style={styles.subtitle}>{item.subtitle}</Text>}
              {item.description && <Text style={styles.description}>{item.description}</Text>}
            </View>
          </View>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingVertical: spacing.sm,
  },
  row: {
    flexDirection: 'row',
  },
  indicatorContainer: {
    width: 20,
    alignItems: 'center',
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: radii.full,
    marginTop: 4,
  },
  line: {
    width: 2,
    flex: 1,
    backgroundColor: colors.border.subtle,
    marginVertical: 4,
  },
  content: {
    flex: 1,
    paddingLeft: spacing.md,
    paddingBottom: spacing.base,
  },
  lastContent: {
    paddingBottom: 0,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
  },
  title: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.semibold,
    color: colors.text.primary,
  },
  timestamp: {
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
  },
  subtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: 2,
  },
  description: {
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    marginTop: 4,
  },
});
