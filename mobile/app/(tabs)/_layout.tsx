import React, { useState, useEffect, useCallback } from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../../src/theme/tokens';
import { useAuth } from '../../src/features/auth/AuthContext';
import { isTabVisibleForRole } from '../../src/features/auth/roleMap';
import { RoleNodeHeaderBadge } from '../../src/components/RoleNodeHeaderBadge';
import { useEventStream } from '../../src/hooks/useEventStream';
import { apiClient } from '../../src/api/client';

export default function TabsLayout() {
  const { user } = useAuth();
  const role = user?.role;
  const [pendingCount, setPendingCount] = useState<number>(0);

  const fetchPendingApprovals = useCallback(async () => {
    try {
      const data = await apiClient.get<any[]>('/api/v1/hitl/tasks?status=pending');
      if (Array.isArray(data)) {
        setPendingCount(data.length);
      }
    } catch {
      // Retain previous count on error
    }
  }, []);

  useEffect(() => {
    fetchPendingApprovals();
  }, [fetchPendingApprovals]);

  // Live SSE update when new hitl task is created or decided
  const { lastEvent } = useEventStream('hitl');
  useEffect(() => {
    if (lastEvent) {
      fetchPendingApprovals();
    }
  }, [lastEvent, fetchPendingApprovals]);

  return (
    <Tabs
      screenOptions={{
        headerStyle: {
          backgroundColor: colors.canvas.primary,
          borderBottomWidth: 1,
          borderBottomColor: colors.border.default,
        },
        headerTintColor: colors.text.primary,
        headerTitleStyle: {
          fontWeight: '700',
          fontSize: 16,
          letterSpacing: -0.2,
        },
        headerShadowVisible: false,
        headerRight: () => <RoleNodeHeaderBadge />,
        tabBarStyle: {
          backgroundColor: colors.canvas.surface,
          borderTopWidth: 1,
          borderTopColor: colors.border.default,
          height: 60,
          paddingBottom: 6,
          paddingTop: 6,
        },
        tabBarActiveTintColor: colors.accent.primary,
        tabBarInactiveTintColor: colors.text.secondary,
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: '700',
          letterSpacing: 0.5,
          textTransform: 'uppercase',
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          headerTitle: 'MediFlux Network Node',
          href: isTabVisibleForRole(role, 'index') ? undefined : null,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="grid-outline" size={size - 2} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="sell"
        options={{
          title: 'Sell',
          headerTitle: 'Pharmacy POS Counter',
          href: isTabVisibleForRole(role, 'sell') ? undefined : null,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="cart-outline" size={size - 2} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="approvals"
        options={{
          title: 'Approvals',
          headerTitle: 'HITL Decisions Queue',
          href: isTabVisibleForRole(role, 'approvals') ? undefined : null,
          tabBarBadge: pendingCount > 0 ? pendingCount : undefined,
          tabBarBadgeStyle: {
            backgroundColor: colors.status.warning,
            color: colors.text.primary,
            fontSize: 10,
            fontWeight: '700',
          },
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="checkbox-outline" size={size - 2} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="scan-rx"
        options={{
          title: 'Scan Rx',
          headerTitle: 'Sovereign Rx Scanner',
          href: isTabVisibleForRole(role, 'scan-rx') ? undefined : null,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="scan-outline" size={size - 2} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="cold-chain"
        options={{
          title: 'Cold Chain',
          headerTitle: 'Biologics IoT Telemetry',
          href: isTabVisibleForRole(role, 'cold-chain') ? undefined : null,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="thermometer-outline" size={size - 2} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="copilot"
        options={{
          title: 'Copilot',
          headerTitle: 'Supply Chain Copilot',
          href: isTabVisibleForRole(role, 'copilot') ? undefined : null,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="chatbubbles-outline" size={size - 2} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
