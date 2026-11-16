import { useState, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';

export interface NetworkStatus {
  isConnected: boolean;
  isInternetReachable: boolean;
  isOffline: boolean;
  isOnline: boolean;
  connectionType: string;
  lastChangedAt: number;
  setSimulatedOffline: (offline: boolean) => void;
  setOnlineForTesting?: (online: boolean) => void;
}

// Global shared state for deterministic multi-component coordination & dev failure-injection
let simulatedOffline: boolean | null = null;
let currentConnected = true;
let currentReachable = true;
let currentType = 'unknown';
let currentLastChangedAt = Date.now();

type StatusListener = (status: {
  isConnected: boolean;
  isInternetReachable: boolean;
  isOffline: boolean;
  isOnline: boolean;
  connectionType: string;
  lastChangedAt: number;
}) => void;

const listeners = new Set<StatusListener>();

function notifyListeners() {
  const isOffline = simulatedOffline === true || (!currentConnected && simulatedOffline === null);
  const isOnline = !isOffline;
  const isConnected = simulatedOffline !== null ? !simulatedOffline : currentConnected;
  const isInternetReachable = simulatedOffline !== null ? !simulatedOffline : currentReachable;
  const payload = {
    isConnected,
    isInternetReachable,
    isOffline,
    isOnline,
    connectionType: simulatedOffline ? 'none' : currentType,
    lastChangedAt: currentLastChangedAt,
  };
  listeners.forEach((cb) => {
    try {
      cb(payload);
    } catch {
      // Safe listener invocation
    }
  });
}

/**
 * Programmatically simulate offline/online state for tests and dev failure injection.
 * When called with true, forces isOffline=true, isOnline=false, connectionType='none'.
 * When called with false, returns to real or forced online state.
 */
export function setSimulatedOffline(offline: boolean) {
  simulatedOffline = offline;
  currentLastChangedAt = Date.now();
  notifyListeners();
}

/**
 * Backward compatibility alias for existing tests / callers.
 */
export function setSimulatedOnline(online: boolean) {
  setSimulatedOffline(!online);
}

/**
 * Reset simulated offline override back to actual hardware status.
 */
export function resetSimulatedNetwork() {
  simulatedOffline = null;
  currentLastChangedAt = Date.now();
  notifyListeners();
}

export function useNetworkStatus(): NetworkStatus {
  const isOfflineInitial = simulatedOffline === true || (!currentConnected && simulatedOffline === null);
  const [status, setStatus] = useState({
    isConnected: simulatedOffline !== null ? !simulatedOffline : currentConnected,
    isInternetReachable: simulatedOffline !== null ? !simulatedOffline : currentReachable,
    isOffline: isOfflineInitial,
    isOnline: !isOfflineInitial,
    connectionType: simulatedOffline ? 'none' : currentType,
    lastChangedAt: currentLastChangedAt,
  });

  useEffect(() => {
    const handleStatusUpdate: StatusListener = (newStatus) => {
      setStatus(newStatus);
    };

    listeners.add(handleStatusUpdate);

    // 1. Subscribe to NetInfo (works on native iOS/Android, and web if supported)
    let unsubscribeNetInfo: (() => void) | null = null;
    try {
      if (NetInfo && typeof NetInfo.addEventListener === 'function') {
        unsubscribeNetInfo = NetInfo.addEventListener((netState: NetInfoState) => {
          currentConnected = netState.isConnected ?? true;
          currentReachable = netState.isInternetReachable ?? true;
          currentType = netState.type ?? 'unknown';
          currentLastChangedAt = Date.now();
          notifyListeners();
        });
      }
    } catch {
      // Fallback in non-native / test environments
    }

    // 2. Browser online/offline event support on Web
    let removeWebListeners: (() => void) | null = null;
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const handleOnline = () => {
        currentConnected = true;
        currentReachable = true;
        currentLastChangedAt = Date.now();
        notifyListeners();
      };
      const handleOffline = () => {
        currentConnected = false;
        currentReachable = false;
        currentType = 'none';
        currentLastChangedAt = Date.now();
        notifyListeners();
      };

      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);

      removeWebListeners = () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }

    return () => {
      listeners.delete(handleStatusUpdate);
      if (unsubscribeNetInfo) {
        unsubscribeNetInfo();
      }
      if (removeWebListeners) {
        removeWebListeners();
      }
    };
  }, []);

  const handleSetSimulatedOffline = useCallback((offline: boolean) => {
    setSimulatedOffline(offline);
  }, []);

  const handleSetOnlineForTesting = useCallback((online: boolean) => {
    setSimulatedOffline(!online);
  }, []);

  return {
    ...status,
    setSimulatedOffline: handleSetSimulatedOffline,
    setOnlineForTesting: handleSetOnlineForTesting,
  };
}
