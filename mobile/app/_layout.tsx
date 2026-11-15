import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StyleSheet, View } from 'react-native';
import { ThemeProvider } from '../src/theme/ThemeContext';
import { ConnectionBanner } from '../src/components/ConnectionBanner';
import { colors } from '../src/theme/tokens';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
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

