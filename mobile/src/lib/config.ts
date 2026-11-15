import { Platform } from 'react-native';
import Constants from 'expo-constants';
import { storage } from './storage';
import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY_BACKEND_URL = 'mediflux_mobile_backend_url';

export function getDefaultBackendUrl(): string {
  // 1. Check Expo extra configuration
  const extra = Constants.expoConfig?.extra as { apiUrl?: string; lanApiUrl?: string } | undefined;
  if (extra?.apiUrl && extra.apiUrl !== 'http://localhost:8000') {
    return extra.apiUrl;
  }

  // 2. Check environment variables
  if (process.env.EXPO_PUBLIC_LAN_API_URL) {
    return process.env.EXPO_PUBLIC_LAN_API_URL;
  }
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }

  // 3. Platform-specific defaults
  if (Platform.OS === 'android') {
    // Android Emulator host loopback alias
    return 'http://10.0.2.2:8000';
  }

  // Web and iOS simulator default
  return 'http://localhost:8000';
}

let currentBackendUrl: string = getDefaultBackendUrl();

export async function loadBackendUrl(): Promise<string> {
  try {
    const saved = await storage.getItem(STORAGE_KEY_BACKEND_URL);
    if (saved && saved.trim()) {
      currentBackendUrl = saved.trim().replace(/\/+$/, '');
      return currentBackendUrl;
    }
  } catch {
    // Keep default
  }
  currentBackendUrl = getDefaultBackendUrl();
  return currentBackendUrl;
}

export function getBackendUrl(): string {
  return currentBackendUrl;
}

export async function setBackendUrl(url: string): Promise<void> {
  const sanitized = url.trim().replace(/\/+$/, '');
  currentBackendUrl = sanitized;
  await storage.setItem(STORAGE_KEY_BACKEND_URL, sanitized);
}

export function getLanPresetUrls(): Array<{ label: string; url: string; description: string }> {
  const presets: Array<{ label: string; url: string; description: string }> = [
    {
      label: 'Localhost (Web / PC)',
      url: 'http://localhost:8000',
      description: 'Standard loopback for Expo Web or browser preview',
    },
    {
      label: 'Android Emulator',
      url: 'http://10.0.2.2:8000',
      description: 'Android Studio / AVD loopback mapping',
    },
  ];

  const detectedLan =
    process.env.EXPO_PUBLIC_LAN_API_URL ||
    (Constants.expoConfig?.extra as { lanApiUrl?: string } | undefined)?.lanApiUrl;

  if (detectedLan) {
    presets.unshift({
      label: 'Host LAN Wi-Fi (Auto-Detected)',
      url: detectedLan,
      description: 'Physical phone, Expo Go, or local network device',
    });
  }

  return presets;
}

export interface HealthCheckResult {
  reachable: boolean;
  latencyMs: number | null;
  status: 'reachable' | 'unreachable' | 'checking';
  url: string;
  serverInfo?: {
    status?: string;
    app?: string;
    version?: string;
    environment?: string;
  };
  error?: string;
}

export async function checkBackendHealth(targetUrl?: string): Promise<HealthCheckResult> {
  const url = (targetUrl || getBackendUrl()).replace(/\/+$/, '');
  const startTime = Date.now();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${url}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const latencyMs = Date.now() - startTime;

    if (response.ok) {
      const data = await response.json();
      return {
        reachable: true,
        latencyMs,
        status: 'reachable',
        url,
        serverInfo: data,
      };
    } else {
      return {
        reachable: false,
        latencyMs,
        status: 'unreachable',
        url,
        error: `HTTP ${response.status}: ${response.statusText}`,
      };
    }
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    const latencyMs = Date.now() - startTime;
    const msg = err instanceof Error ? err.message : 'Connection failed';
    return {
      reachable: false,
      latencyMs: null,
      status: 'unreachable',
      url,
      error: msg,
    };
  }
}

export function useBackendHealth(pollIntervalMs: number = 30000) {
  const [health, setHealth] = useState<HealthCheckResult>({
    reachable: false,
    latencyMs: null,
    status: 'checking',
    url: getBackendUrl(),
  });

  const refresh = useCallback(async (customUrl?: string) => {
    setHealth((prev) => ({ ...prev, status: 'checking' }));
    const result = await checkBackendHealth(customUrl);
    setHealth(result);
    return result;
  }, []);

  useEffect(() => {
    // Initial load and check
    loadBackendUrl().then((url) => {
      refresh(url);
    });

    if (pollIntervalMs > 0) {
      const interval = setInterval(() => {
        refresh();
      }, pollIntervalMs);
      return () => clearInterval(interval);
    }
  }, [refresh, pollIntervalMs]);

  return { health, refresh, setUrl: setBackendUrl };
}

