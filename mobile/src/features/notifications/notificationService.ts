/**
 * Local & Push Notification Service (Task M7).
 * Handles Expo notification channels, local scheduling, push token retrieval,
 * and deep-link payload routing.
 */

import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';

// Configure foreground presentation
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

/**
 * Configure high-importance Android notification channels.
 */
export async function setupNotificationChannels(): Promise<void> {
  if (Platform.OS === 'android') {
    try {
      await Notifications.setNotificationChannelAsync('mediflux-coldchain', {
        name: 'Cold-Chain Quarantines & Excursions',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#EF4444',
        sound: 'default',
        enableVibrate: true,
      });

      await Notifications.setNotificationChannelAsync('mediflux-approvals', {
        name: 'HITL Approvals Required',
        importance: Notifications.AndroidImportance.HIGH,
        sound: 'default',
        enableVibrate: true,
        lightColor: '#00AEBB',
      });
    } catch {
      // Graceful fallback on web or unsupported environments
    }
  }
}

/**
 * Safely request notification permissions across iOS, Android, and Web.
 */
export async function requestNotificationPermissions(): Promise<boolean> {
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      const perm = await window.Notification.requestPermission();
      return perm === 'granted';
    }
    return false;
  }

  try {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    return finalStatus === 'granted';
  } catch {
    return false;
  }
}

/**
 * Retrieve an Expo Push Token or a deterministic simulated token for dev/web/simulators.
 */
export async function getDevicePushToken(userId: string): Promise<string> {
  const shortId = userId ? userId.replace(/-/g, '').slice(0, 8) : 'demo';
  const fallbackToken = `ExponentPushToken[mediflux-${shortId}-${Platform.OS}]`;

  // On Web or Simulator / non-physical device, use deterministic token
  if (Platform.OS === 'web' || !Device.isDevice) {
    return fallbackToken;
  }

  try {
    const granted = await requestNotificationPermissions();
    if (!granted) {
      return fallbackToken;
    }
    const tokenObj = await Notifications.getExpoPushTokenAsync();
    return tokenObj.data || fallbackToken;
  } catch {
    return fallbackToken;
  }
}

export interface NotificationPayloadData {
  type?: string;
  taskId?: string;
  batchId?: string;
  deepLink?: string;
  correlationId?: string;
  [key: string]: any;
}

/**
 * Pure, unit-testable tap deep-linking handler.
 */
export function handleNotificationTapPayload(
  data: NotificationPayloadData | undefined | null,
  router: { push: (path: any) => void }
): boolean {
  if (!data) return false;

  // 1. HITL Approval Task
  if (data.type === 'hitl.created' || data.taskId) {
    const taskId = data.taskId || (data.deepLink ? data.deepLink.split('/').pop() : '');
    if (taskId) {
      router.push(`/approvals/${taskId}`);
      return true;
    }
    router.push('/(tabs)/approvals');
    return true;
  }

  // 2. Cold-Chain Quarantined Batch
  if (data.type === 'batch.quarantined' || data.type === 'coldchain.quarantined' || data.batchId) {
    const batchId = data.batchId || (data.deepLink ? data.deepLink.split('/').pop() : '');
    if (batchId) {
      router.push(`/cold-chain/${batchId}`);
      return true;
    }
    router.push('/(tabs)/cold-chain');
    return true;
  }

  // 3. Generic DeepLink
  if (data.deepLink && typeof data.deepLink === 'string') {
    router.push(data.deepLink);
    return true;
  }

  return false;
}

/**
 * Schedule or immediately trigger a local notification.
 */
export async function scheduleLocalNotification(
  title: string,
  body: string,
  data?: NotificationPayloadData,
  channelId?: 'mediflux-coldchain' | 'mediflux-approvals'
): Promise<string | null> {
  // Web browser native notification fallback
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined' && 'Notification' in window && window.Notification.permission === 'granted') {
      try {
        new window.Notification(title, { body, data });
      } catch {
        // Ignored
      }
    }
  }

  try {
    const notifId = await Notifications.scheduleNotificationAsync({
      content: {
        title,
        body,
        data: data || {},
        sound: 'default',
        ...(channelId && Platform.OS === 'android' ? { channelId } : {}),
      },
      trigger: null, // deliver immediately
    });
    return notifId;
  } catch {
    return null;
  }
}
