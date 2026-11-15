import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../features/auth/AuthContext';
import { getRoleBadgeInfo } from '../features/auth/roleMap';

export function RoleNodeHeaderBadge() {
  const router = useRouter();
  const { user } = useAuth();

  const role = user?.role || 'pharmacy';
  const badgeInfo = getRoleBadgeInfo(role);
  const nodeName = user?.node_name || (role === 'admin' ? 'Network Control Tower' : 'Unassigned Node');

  const handlePress = () => {
    router.push('/(auth)/settings');
  };

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={handlePress}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`Current role ${badgeInfo.label}, node ${nodeName}. Tap to open settings.`}
    >
      <View style={styles.textContainer}>
        <View style={styles.badgeRow}>
          <View style={[styles.rolePill, { backgroundColor: badgeInfo.badgeBg }]}>
            <Text style={[styles.roleText, { color: badgeInfo.badgeTextColor }]}>
              {badgeInfo.label}
            </Text>
          </View>
          {!badgeInfo.isApprover && (
            <View style={styles.viewOnlyPill}>
              <Text style={styles.viewOnlyText}>VIEW-ONLY</Text>
            </View>
          )}
        </View>
        <Text style={styles.nodeText} numberOfLines={1} ellipsizeMode="tail">
          {nodeName}
        </Text>
      </View>

      <View style={styles.iconButton}>
        <Ionicons name="settings-outline" size={16} color="#031211" />
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 8,
    backgroundColor: '#F7F5F0',
    borderColor: '#D8D3C3',
    borderWidth: 1,
    borderRadius: 6,
    marginRight: 12,
    maxWidth: 220,
  },
  textContainer: {
    marginRight: 6,
    flexShrink: 1,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  rolePill: {
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 3,
  },
  roleText: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
    fontFamily: 'monospace',
  },
  viewOnlyPill: {
    backgroundColor: '#F2EFE9',
    borderColor: '#D8D3C3',
    borderWidth: 0.5,
    paddingHorizontal: 3,
    paddingVertical: 1,
    borderRadius: 3,
  },
  viewOnlyText: {
    fontSize: 8,
    color: '#5C584E',
    fontWeight: '600',
  },
  nodeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#031211',
    marginTop: 1,
  },
  iconButton: {
    padding: 3,
    borderRadius: 4,
    backgroundColor: '#DFDBCA',
  },
});
