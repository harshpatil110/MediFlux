import { useState, useEffect } from 'react';
import { Platform } from 'react-native';
import { checkBackendHealth, HealthCheckResult } from '../lib/config';

export interface NetworkStatus {
  isOnline: boolean;
  backend: HealthCheckResult;
  checkNow: () => Promise<HealthCheckResult>;
}

export function useNetworkStatus(intervalMs: number = 20000): NetworkStatus {
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [backendHealth, setBackendHealth] = useState<HealthCheckResult>({
    reachable: false,
    latencyMs: null,
    status: 'checking',
    url: '',
  });

  const checkNow = async (): Promise<HealthCheckResult> => {
    if (Platform.OS === 'web' && typeof navigator !== 'undefined') {
      setIsOnline(navigator.onLine);
    }
    const health = await checkBackendHealth();
    setBackendHealth(health);
    return health;
  };

  useEffect(() => {
    checkNow();

    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const handleOnline = () => setIsOnline(true);
      const handleOffline = () => setIsOnline(false);
      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);

      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }

    const timer = setInterval(checkNow, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);

  return { isOnline, backend: backendHealth, checkNow };
}

