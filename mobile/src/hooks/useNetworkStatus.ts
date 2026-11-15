import { useState, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';

export interface NetworkStatus {
  isOnline: boolean;
  setOnlineForTesting?: (online: boolean) => void;
}

// Global state so multiple hooks share the status
let globalIsOnline = true;
const listeners = new Set<(online: boolean) => void>();

export function setSimulatedOnline(online: boolean) {
  globalIsOnline = online;
  listeners.forEach((cb) => cb(online));
}

export function useNetworkStatus(): NetworkStatus {
  const [isOnline, setIsOnline] = useState<boolean>(globalIsOnline);

  useEffect(() => {
    const handleStatusChange = (status: boolean) => {
      setIsOnline(status);
    };

    listeners.add(handleStatusChange);

    // Browser online/offline event support
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const handleOnline = () => setSimulatedOnline(true);
      const handleOffline = () => setSimulatedOnline(false);

      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);

      return () => {
        listeners.delete(handleStatusChange);
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }

    return () => {
      listeners.delete(handleStatusChange);
    };
  }, []);

  const setOnlineForTesting = useCallback((online: boolean) => {
    setSimulatedOnline(online);
  }, []);

  return { isOnline, setOnlineForTesting };
}
