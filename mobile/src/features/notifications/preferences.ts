/**
 * Notification Preferences Store (Task M7).
 * Manages persistent user preferences for Cold-Chain and HITL push/local alerts.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

export const NOTIFICATION_PREFS_KEY = 'mediflux_notification_prefs_v1';

export interface NotificationPreferences {
  coldchainAlerts: boolean;
  approvalAlerts: boolean;
  pushEnabled: boolean;
}

export const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  coldchainAlerts: true,
  approvalAlerts: true,
  pushEnabled: true,
};

export async function loadNotificationPreferences(): Promise<NotificationPreferences> {
  try {
    const raw = await AsyncStorage.getItem(NOTIFICATION_PREFS_KEY);
    if (!raw) return DEFAULT_NOTIFICATION_PREFERENCES;
    const parsed = JSON.parse(raw);
    return {
      coldchainAlerts: parsed.coldchainAlerts ?? true,
      approvalAlerts: parsed.approvalAlerts ?? true,
      pushEnabled: parsed.pushEnabled ?? true,
    };
  } catch {
    return DEFAULT_NOTIFICATION_PREFERENCES;
  }
}

export async function saveNotificationPreferences(
  updates: Partial<NotificationPreferences>
): Promise<NotificationPreferences> {
  try {
    const current = await loadNotificationPreferences();
    const merged: NotificationPreferences = { ...current, ...updates };
    await AsyncStorage.setItem(NOTIFICATION_PREFS_KEY, JSON.stringify(merged));
    return merged;
  } catch {
    return { ...DEFAULT_NOTIFICATION_PREFERENCES, ...updates };
  }
}
