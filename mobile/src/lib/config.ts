import Constants from 'expo-constants';
import { storage } from './storage';
import { useState, useEffect, useCallback, useSyncExternalStore } from 'react';

const STORAGE_KEY_BACKEND_URL = 'mediflux_mobile_backend_url';
const STORAGE_KEY_CLOUD_MIGRATION = 'mediflux_migrated_to_vercel_v1';
export const DEFAULT_CLOUD_BACKEND_URL = 'https://mediflux-backend.vercel.app';

function isLegacyLocalUrl(value: string): boolean {
  try {
    const host = new URL(value).hostname.toLowerCase();
    return host === 'localhost' || host === '127.0.0.1' || host === '10.0.2.2' ||
      /^192\.168\./.test(host) || /^10\./.test(host) ||
      /^172\.(1[6-9]|2\d|3[01])\./.test(host);
  } catch {
    return false;
  }
}

export function getDefaultBackendUrl(): string {
  const extra = Constants.expoConfig?.extra as { apiUrl?: string } | undefined;
  return (process.env.EXPO_PUBLIC_API_URL || extra?.apiUrl || DEFAULT_CLOUD_BACKEND_URL).replace(/\/+$/, '');
}

let currentBackendUrl: string = getDefaultBackendUrl();
const backendUrlListeners = new Set<() => void>();

function updateBackendUrl(url: string): void {
  currentBackendUrl = url.trim().replace(/\/+$/, '');
  backendUrlListeners.forEach((listener) => listener());
}

function subscribeBackendUrl(listener: () => void): () => void {
  backendUrlListeners.add(listener);
  return () => { backendUrlListeners.delete(listener); };
}

export function useBackendUrl(): string {
  return useSyncExternalStore(subscribeBackendUrl, getBackendUrl, getDefaultBackendUrl);
}

export async function loadBackendUrl(): Promise<string> {
  try {
    const saved = await storage.getItem(STORAGE_KEY_BACKEND_URL);
    const migrated = await storage.getItem(STORAGE_KEY_CLOUD_MIGRATION);
    if (saved?.trim()) {
      const sanitized = saved.trim().replace(/\/+$/, '');
      const devMode = typeof __DEV__ !== 'undefined' && __DEV__;
      if (isLegacyLocalUrl(sanitized) && (!devMode || migrated !== '1')) {
        updateBackendUrl(DEFAULT_CLOUD_BACKEND_URL);
        await storage.setItem(STORAGE_KEY_BACKEND_URL, currentBackendUrl);
      } else {
        updateBackendUrl(sanitized);
      }
    } else {
      updateBackendUrl(getDefaultBackendUrl());
    }
    if (migrated !== '1') await storage.setItem(STORAGE_KEY_CLOUD_MIGRATION, '1');
    return currentBackendUrl;
  } catch {
    updateBackendUrl(getDefaultBackendUrl());
    return currentBackendUrl;
  }
}

export function getBackendUrl(): string {
  return currentBackendUrl;
}

export async function setBackendUrl(url: string): Promise<void> {
  updateBackendUrl(url);
  await storage.setItem(STORAGE_KEY_BACKEND_URL, currentBackendUrl);
  await storage.setItem(STORAGE_KEY_CLOUD_MIGRATION, '1');
}

export function getLanPresetUrls(): Array<{ label: string; url: string; description: string }> {
  const presets: Array<{ label: string; url: string; description: string }> = [
    {
      label: 'Cloud Backend (Vercel)',
      url: DEFAULT_CLOUD_BACKEND_URL,
      description: 'Hosted API available from any network',
    },
    {
      label: 'Local PC (Web)',
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
    presets.push({
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
  const timeoutId = setTimeout(() => controller.abort(), 15000);

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
  const backendUrl = useBackendUrl();
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
    void refresh(backendUrl);

    if (pollIntervalMs > 0) {
      const interval = setInterval(() => {
        refresh();
      }, pollIntervalMs);
      return () => clearInterval(interval);
    }
  }, [backendUrl, refresh, pollIntervalMs]);

  return { health, refresh, setUrl: setBackendUrl };
}

