import { Platform } from 'react-native';
import Constants from 'expo-constants';
import { storage } from '../lib/storage';
import { getDefaultBackendUrl, getBackendUrl, loadBackendUrl, setBackendUrl } from '../lib/config';

const storageKey = 'mediflux_mobile_backend_url';
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
    global.fetch = jest.fn().mockRejectedValue(new Error('Unreachable'));
  });

  afterEach(async () => {
    await storage.removeItem(storageKey);
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

  test.each(['localhost', '127.0.0.1', '192.168.1.20'])(
    'uses browser host %s instead of a stale generated phone address',
    (hostname) => {
      browserHost(hostname);
      expect(getDefaultBackendUrl()).toBe(`http://${hostname}:8000`);
    }
  );

  test('honors an explicitly configured separate API', () => {
    Constants.expoConfig!.extra = { apiUrl: 'https://api.example.test', lanApiUrl: oldLanUrl };
    expect(getDefaultBackendUrl()).toBe('https://api.example.test');
  });

  test.each(['android', 'ios'] as const)('keeps the LAN address for native %s', (platform) => {
    Platform.OS = platform;
    expect(getDefaultBackendUrl()).toBe(oldLanUrl);
  });

  test('uses the Android emulator alias when no API is configured', () => {
    Platform.OS = 'android';
    Constants.expoConfig!.extra = {};
    delete process.env.EXPO_PUBLIC_API_URL;
    delete process.env.EXPO_PUBLIC_LAN_API_URL;
    expect(getDefaultBackendUrl()).toBe('http://10.0.2.2:8000');
  });

  test('repairs a saved generated LAN preset when the local API responds', async () => {
    await storage.setItem(storageKey, oldLanUrl);
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) });
    expect(await loadBackendUrl()).toBe('http://localhost:8000');
    expect(await storage.getItem(storageKey)).toBe('http://localhost:8000');
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/health', expect.any(Object));
  });

  test('keeps the saved LAN preset when the local API is unavailable', async () => {
    await storage.setItem(storageKey, oldLanUrl);
    expect(await loadBackendUrl()).toBe(oldLanUrl);
    expect(await storage.getItem(storageKey)).toBe(oldLanUrl);
  });

  test('restores a user-selected remote API without probing or replacing it', async () => {
    await setBackendUrl(' https://custom.example.test/api/ ');
    expect(await loadBackendUrl()).toBe('https://custom.example.test/api');
    expect(getBackendUrl()).toBe('https://custom.example.test/api');
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
