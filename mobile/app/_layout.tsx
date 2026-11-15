import React, { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StyleSheet, View } from 'react-native';
import { ThemeProvider } from '../src/theme/ThemeContext';
import { AuthProvider, useAuth } from '../src/features/auth/AuthContext';
import { ConnectionBanner } from '../src/components/ConnectionBanner';
import { colors } from '../src/theme/tokens';

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

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <AuthProvider>
          <NavigationGuard>
            <SafeAreaView style={styles.container} edges={['top']}>
              <StatusBar style="dark" backgroundColor={colors.canvas.primary} />
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
