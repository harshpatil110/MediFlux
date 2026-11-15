import React from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, typography } from '../../src/theme/tokens';

export default function TabsLayout() {
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
          fontSize: 17,
          letterSpacing: -0.2,
        },
        headerShadowVisible: false,
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
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="chatbubbles-outline" size={size - 2} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
