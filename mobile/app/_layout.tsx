import React, { useEffect, useState, useRef } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { Platform, StyleSheet, View } from 'react-native';
import * as Notifications from 'expo-notifications';
import { ThemeProvider } from '../src/theme/ThemeContext';
import { AuthProvider, useAuth } from '../src/features/auth/AuthContext';
import { ConnectionBanner } from '../src/components/ConnectionBanner';
import { GlobalOfflineBanner } from '../src/components/GlobalOfflineBanner';
import { colors } from '../src/theme/tokens';
import {
  setupNotificationChannels,
  handleNotificationTapPayload,
  scheduleLocalNotification,
  NotificationBanner,
  BannerMessage,
  loadNotificationPreferences,
} from '../src/features/notifications';
import { useEventStream } from '../src/hooks/useEventStream';
import { canRoleDecideApprovals } from '../src/features/auth/roleMap';

function NavigationGuard({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (status === 'loading') return;

    const inAuthGroup = segments[0] === '(auth)';
    const isSettings = segments[1] === 'settings';

    if (status === 'unauthenticated' && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (status === 'authenticated' && inAuthGroup && !isSettings) {
      router.replace('/(tabs)');
    }
  }, [status, segments, router]);

  return <>{children}</>;
}

function NotificationBridge({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user } = useAuth();
  const [banner, setBanner] = useState<BannerMessage | null>(null);
  const seenEventsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (Platform.OS === 'web') return;
    void setupNotificationChannels();

    const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response?.notification?.request?.content?.data;
      if (data) {
        handleNotificationTapPayload(data, router);
      }
    });

    void Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) {
        const data = response?.notification?.request?.content?.data;
        if (data) {
          handleNotificationTapPayload(data, router);
        }
      }
    }).catch((error: unknown) => {
      console.warn('Unable to restore the last notification response:', error);
    });

    return () => {
      subscription.remove();
    };
  }, [router]);

  // Live SSE listener for real-time local push alerts
  const { lastEvent } = useEventStream('hitl,coldchain', { enabled: Boolean(user) });

  useEffect(() => {
    if (!lastEvent) return;
    const evtId = lastEvent.event_id || `${lastEvent.event_type}-${Date.now()}`;
    if (seenEventsRef.current.has(evtId)) return;
    seenEventsRef.current.add(evtId);

    const payload = lastEvent.payload || {};

    void (async () => {
      const prefs = await loadNotificationPreferences();

      // 1. HITL Approval Task Alert
      if (lastEvent.event_type === 'hitl.created' || lastEvent.event_type === 'hitl') {
        const isEligible = user?.permissions?.can_decide_approvals || canRoleDecideApprovals(user?.role);
        if (isEligible && prefs.approvalAlerts) {
          const taskId = payload.task_id || payload.id;
          const taskType = payload.task_type || 'approval';
          const title = '⚠️ Approval Required';
          const body = `New ${String(taskType).replace(/_/g, ' ')} requires review.`;

          void scheduleLocalNotification(
            title,
            body,
            { type: 'hitl.created', taskId, deepLink: `/approvals/${taskId}` },
            'mediflux-approvals'
          );

          setBanner({
            id: evtId,
            title,
            body,
            type: 'hitl',
            data: { type: 'hitl.created', taskId, deepLink: `/approvals/${taskId}` },
          });
        }
      }

      // 2. Cold-Chain Batch Quarantined Alert
      if (
        lastEvent.event_type === 'batch.quarantined' ||
        lastEvent.event_type === 'coldchain.quarantined' ||
        (lastEvent.topic === 'coldchain' && payload.quarantined)
      ) {
        if (prefs.coldchainAlerts) {
          const batchId = payload.batch_id || 'BIO-INS-01';
          const batchNo = payload.batch_no || batchId;
          const nodeName = payload.node_name || 'Supply Chain Hub';
          const title = '❄️ Cold-Chain Quarantined';
          const body = `Batch ${batchNo} was quarantined at ${nodeName}.`;

          void scheduleLocalNotification(
            title,
            body,
            { type: 'batch.quarantined', batchId, deepLink: `/cold-chain/${batchId}` },
            'mediflux-coldchain'
          );

          setBanner({
            id: evtId,
            title,
            body,
            type: 'coldchain',
            data: { type: 'batch.quarantined', batchId, deepLink: `/cold-chain/${batchId}` },
          });
        }
      }
    })();
  }, [lastEvent, user]);

  return (
    <>
      <NotificationBanner banner={banner} onDismiss={() => setBanner(null)} />
      {children}
    </>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <AuthProvider>
          <NotificationBridge>
            <NavigationGuard>
              <SafeAreaView style={styles.container} edges={['top']}>
                <StatusBar style="dark" backgroundColor={colors.canvas.primary} />
                <GlobalOfflineBanner />
                <ConnectionBanner />
                <View style={styles.stackWrapper}>
                  <Stack
                    screenOptions={{
                      headerStyle: {
                        backgroundColor: colors.canvas.primary,
                      },
                      headerTintColor: colors.text.primary,
                      headerTitleStyle: {
                        fontWeight: '700',
                        fontSize: 18,
                      },
                      contentStyle: {
                        backgroundColor: colors.canvas.primary,
                      },
                    }}
                  >
                    <Stack.Screen name="index" options={{ headerShown: false }} />
                    <Stack.Screen name="(auth)" options={{ headerShown: false }} />
                    <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
                  </Stack>
                </View>
              </SafeAreaView>
            </NavigationGuard>
          </NotificationBridge>
        </AuthProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
  },
  stackWrapper: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
  },
});
