/**
 * Tappable deep-linking Reference Chips component and resolver (Task M8.1).
 */

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ViewStyle } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { CopilotReference } from './types';
import { colors, spacing, typography, radii } from '../../theme/tokens';

export function resolveReferenceDeepLink(ref: CopilotReference, userRole?: string): string {
  if (ref.deep_link && ref.deep_link.trim().length > 0) {
    return ref.deep_link;
  }

  const normType = (ref.type || '').toLowerCase();
  switch (normType) {
    case 'inventory': {
      const pid = ref.product_id || ref.id;
      return `/(tabs)/sell?product_id=${encodeURIComponent(pid)}`;
    }
    case 'batch':
    case 'coldchain_batch': {
      return `/cold-chain/${encodeURIComponent(ref.id)}`;
    }
    case 'approval':
    case 'hitl_task': {
      return `/approvals/${encodeURIComponent(ref.id)}`;
    }
    case 'cascade':
    case 'agent_run': {
      return `/cascade/${encodeURIComponent(ref.id)}?mode=replay`;
    }
    default: {
      return '/(tabs)';
    }
  }
}

function getReferenceIcon(type: string): keyof typeof Ionicons.glyphMap {
  const norm = type.toLowerCase();
  if (norm === 'inventory') return 'cube-outline';
  if (norm === 'batch' || norm === 'coldchain_batch') return 'thermometer-outline';
  if (norm === 'approval' || norm === 'hitl_task') return 'shield-checkmark-outline';
  if (norm === 'cascade' || norm === 'agent_run') return 'git-network-outline';
  return 'open-outline';
}

function getReferenceBadgeLabel(type: string): string {
  const norm = type.toLowerCase();
  if (norm === 'inventory') return 'INV';
  if (norm === 'batch' || norm === 'coldchain_batch') return 'BATCH';
  if (norm === 'approval' || norm === 'hitl_task') return 'HITL';
  if (norm === 'cascade' || norm === 'agent_run') return 'CASC';
  return 'REF';
}

interface ReferenceChipListProps {
  references?: CopilotReference[];
  userRole?: string;
  onReferencePress?: (ref: CopilotReference, link: string) => void;
  style?: ViewStyle;
}

export function ReferenceChipList({
  references,
  userRole,
  onReferencePress,
  style,
}: ReferenceChipListProps) {
  const router = useRouter();

  if (!references || references.length === 0) {
    return null;
  }

  const handlePress = (ref: CopilotReference) => {
    const link = resolveReferenceDeepLink(ref, userRole);
    if (onReferencePress) {
      onReferencePress(ref, link);
    } else {
      router.push(link as any);
    }
  };

  return (
    <View style={[styles.container, style]}>
      <Text style={styles.sectionHeader}>GROUNDED REFERENCES ({references.length})</Text>
      <View style={styles.chipsWrapper}>
        {references.map((ref, idx) => {
          const icon = getReferenceIcon(ref.type);
          const badgeLabel = getReferenceBadgeLabel(ref.type);
          return (
            <TouchableOpacity
              key={`${ref.id}-${idx}`}
              style={styles.chip}
              onPress={() => handlePress(ref)}
              activeOpacity={0.75}
              accessibilityRole="button"
              accessibilityLabel={`Reference: ${ref.label}`}
            >
              <View style={styles.chipPrefix}>
                <Ionicons name={icon} size={14} color={colors.accent.primary} />
                <Text style={styles.badgeText}>{badgeLabel}</Text>
              </View>
              <Text style={styles.chipLabel} numberOfLines={1}>
                {ref.label}
              </Text>
              <Ionicons name="chevron-forward" size={12} color={colors.text.muted} />
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: spacing.sm,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border.subtle,
  },
  sectionHeader: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.muted,
    letterSpacing: typography.letterSpacing.widest,
    marginBottom: spacing.xs,
  },
  chipsWrapper: {
    flexDirection: 'column',
    gap: 6,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    paddingVertical: 6,
    paddingHorizontal: 8,
    gap: 6,
  },
  chipPrefix: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.canvas.elevated,
    paddingHorizontal: 4,
    paddingVertical: 2,
    borderRadius: radii.xs,
  },
  badgeText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  chipLabel: {
    flex: 1,
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
    fontWeight: typography.fontWeight.medium,
  },
});
