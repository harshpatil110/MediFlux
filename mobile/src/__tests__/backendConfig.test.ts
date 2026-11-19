import { Platform } from 'react-native';
import Constants from 'expo-constants';
import { storage } from '../lib/storage';
import { getDefaultBackendUrl, getBackendUrl, loadBackendUrl, setBackendUrl } from '../lib/config';

const storageKey = 'mediflux_mobile_backend_url';
const migrationKey = 'mediflux_migrated_to_vercel_v1';
const cloudUrl = 'https://mediflux-backend.vercel.app';
const oldLanUrl = 'http://172.20.10.4:8000';
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
const originalExtra = Constants.expoConfig!.extra;
const originalFetch = global.fetch;
const originalApiUrl = process.env.EXPO_PUBLIC_API_URL;
const originalLanUrl = process.env.EXPO_PUBLIC_LAN_API_URL;

function browserHost(hostname: string): void {
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { location: { hostname } },
  });
}

describe('Mobile backend URL selection', () => {
  beforeEach(async () => {
    Platform.OS = 'web';
    browserHost('localhost');
    Constants.expoConfig!.extra = { apiUrl: oldLanUrl, lanApiUrl: oldLanUrl };
    process.env.EXPO_PUBLIC_API_URL = oldLanUrl;
    process.env.EXPO_PUBLIC_LAN_API_URL = oldLanUrl;
    await storage.removeItem(storageKey);
    await storage.removeItem(migrationKey);
    global.fetch = jest.fn().mockRejectedValue(new Error('Unreachable'));
  });

  afterEach(async () => {
    await storage.removeItem(storageKey);
    await storage.removeItem(migrationKey);
    Constants.expoConfig!.extra = originalExtra;
    Platform.OS = 'web';
    global.fetch = originalFetch;
    if (originalApiUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = originalApiUrl;
    if (originalLanUrl === undefined) delete process.env.EXPO_PUBLIC_LAN_API_URL;
    else process.env.EXPO_PUBLIC_LAN_API_URL = originalLanUrl;
    if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow);
    else Reflect.deleteProperty(globalThis, 'window');
  });

  test.each(['web', 'android', 'ios'] as const)(
    'defaults %s to the configured cloud API', (platform) => {
      Platform.OS = platform;
      expect(getDefaultBackendUrl()).toBe(oldLanUrl);
      process.env.EXPO_PUBLIC_API_URL = cloudUrl;
      expect(getDefaultBackendUrl()).toBe(cloudUrl);
    });

  test('honors an explicitly configured separate API', () => {
    Constants.expoConfig!.extra = { apiUrl: 'https://api.example.test', lanApiUrl: oldLanUrl };
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(getDefaultBackendUrl()).toBe('https://api.example.test');
  });

  test('uses the cloud fallback when no environment or Expo extra is configured', () => {
    Platform.OS = 'android';
    Constants.expoConfig!.extra = {};
    delete process.env.EXPO_PUBLIC_API_URL;
    delete process.env.EXPO_PUBLIC_LAN_API_URL;
    expect(getDefaultBackendUrl()).toBe(cloudUrl);
  });

  test.each(['http://localhost:8000', 'http://127.0.0.1:8000', 'http://10.0.2.2:8000',
    'http://192.168.1.4:8000', oldLanUrl])('migrates stale local %s to cloud on first launch', async (localUrl) => {
    process.env.EXPO_PUBLIC_API_URL = cloudUrl;
    await storage.setItem(storageKey, localUrl);
    expect(await loadBackendUrl()).toBe(cloudUrl);
    expect(await storage.getItem(storageKey)).toBe(cloudUrl);
    expect(await storage.getItem(migrationKey)).toBe('1');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('honors an explicit local choice after migration in development', async () => {
    (globalThis as any).__DEV__ = true;
    await storage.setItem(storageKey, oldLanUrl);
    await storage.setItem(migrationKey, '1');
    expect(await loadBackendUrl()).toBe(oldLanUrl);
    delete (globalThis as any).__DEV__;
  });

  test('restores a user-selected remote API without probing or replacing it', async () => {
    await setBackendUrl(' https://custom.example.test/api/ ');
    expect(await loadBackendUrl()).toBe('https://custom.example.test/api');
    expect(getBackendUrl()).toBe('https://custom.example.test/api');
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
