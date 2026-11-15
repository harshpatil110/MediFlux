import { useState, useEffect, useRef, useCallback } from 'react';
import { AppState, AppStateStatus, Platform } from 'react-native';
import EventSource from 'react-native-sse';
import { apiClient } from '../api/client';
import { getBackendUrl } from '../lib/config';
import { useNetworkStatus } from './useNetworkStatus';

export type StreamConnectionStatus = 'connecting' | 'open' | 'retrying' | 'failed';

export interface MobileStreamEvent {
  id: string;
  event_id: string;
  event_type: string;
  topic?: string;
  agent_name: string;
  tier: string;
  summary: string;
  correlation_id: string;
  node_id?: string | null;
  node_name?: string | null;
  created_at: string;
  payload?: any;
}

export interface UseEventStreamOptions {
  enabled?: boolean;
  maxBufferSize?: number; // default: 100
  initialBackoffMs?: number; // default: 1000
  maxBackoffMs?: number; // default: 15000
  maxFailuresBeforePolling?: number; // default: 3
  pollingIntervalMs?: number; // default: 3000
  streamRecoveryProbeMs?: number; // default: 10000
  eventSourceFactory?: (url: string, options: any) => any;
}

export interface UseEventStreamResult {
  status: StreamConnectionStatus;
  isPollingFallback: boolean;
  events: MobileStreamEvent[];
  lastEvent: MobileStreamEvent | null;
  lastEventId: string | null;
  reconnect: () => void;
  refreshRecent: () => Promise<void>;
  clearEvents: () => void;
}

export function useEventStream(
  topics: string = '*',
  options: UseEventStreamOptions = {}
): UseEventStreamResult {
  const {
    enabled = true,
    maxBufferSize = 100,
    initialBackoffMs = 1000,
    maxBackoffMs = 15000,
    maxFailuresBeforePolling = 3,
    pollingIntervalMs = 3000,
    streamRecoveryProbeMs = 10000,
    eventSourceFactory,
  } = options;

  const { isOnline } = useNetworkStatus();

  const [status, setStatus] = useState<StreamConnectionStatus>('connecting');
  const [isPollingFallback, setIsPollingFallback] = useState<boolean>(false);
  const [events, setEvents] = useState<MobileStreamEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<MobileStreamEvent | null>(null);

  const seenEventIdsRef = useRef<Set<string>>(new Set());
  const lastEventIdRef = useRef<string | null>(null);
  const consecutiveFailuresRef = useRef<number>(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const recoveryProbeTimerRef = useRef<NodeJS.Timeout | null>(null);
  const eventSourceRef = useRef<any>(null);
  const isComponentMountedRef = useRef<boolean>(true);
  const appStateRef = useRef<AppStateStatus>(AppState.currentState);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
    if (recoveryProbeTimerRef.current) {
      clearInterval(recoveryProbeTimerRef.current);
      recoveryProbeTimerRef.current = null;
    }
  }, []);

  const closeEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      try {
        eventSourceRef.current.close();
      } catch {
        // Ignore close errors
      }
      eventSourceRef.current = null;
    }
  }, []);

  const addEvents = useCallback(
    (newEvents: MobileStreamEvent[]) => {
      if (!isComponentMountedRef.current || newEvents.length === 0) return;

      const unseen: MobileStreamEvent[] = [];
      for (const ev of newEvents) {
        const key = ev.id || ev.event_id;
        if (key && !seenEventIdsRef.current.has(key)) {
          seenEventIdsRef.current.add(key);
          unseen.push(ev);
        }
      }

      if (unseen.length === 0) return;

      const latest = unseen[unseen.length - 1];
      const latestId = latest.id || latest.event_id;
      if (latestId) {
        lastEventIdRef.current = latestId;
      }
      setLastEvent(latest);

      setEvents((prev) => {
        // Prepend newer events
        const combined = [...unseen.reverse(), ...prev];
        return combined.slice(0, maxBufferSize);
      });
    },
    [maxBufferSize]
  );

  const pollRecentEvents = useCallback(async () => {
    if (!isComponentMountedRef.current) return;
    try {
      const auth = apiClient.getAuth();
      const baseUrl = getBackendUrl().replace(/\/+$/, '');
      const params = new URLSearchParams();
      if (lastEventIdRef.current) {
        params.append('since', lastEventIdRef.current);
      }
      if (topics && topics !== '*') {
        params.append('topics', topics);
      }
      params.append('limit', '50');

      const headers: Record<string, string> = {
        Accept: 'application/json',
      };
      if (auth.token) {
        headers['Authorization'] = `Bearer ${auth.token}`;
      }
      if (auth.role) headers['X-User-Role'] = auth.role;
      if (auth.nodeId) headers['X-Node-Id'] = auth.nodeId;

      const res = await fetch(`${baseUrl}/api/v1/events/recent?${params.toString()}`, {
        method: 'GET',
        headers,
      });

      if (res.ok) {
        const data = await res.json();
        if (data.events && Array.isArray(data.events) && data.events.length > 0) {
          addEvents(data.events);
        }
      }
    } catch {
      // Ignore polling blips
    }
  }, [topics, addEvents]);

  const startPollingFallback = useCallback(() => {
    setIsPollingFallback(true);
    setStatus('retrying');
    clearTimers();

    // Immediate first poll
    pollRecentEvents();

    // Recurring poll
    pollingTimerRef.current = setInterval(() => {
      pollRecentEvents();
    }, pollingIntervalMs);

    // Periodic stream recovery probe
    recoveryProbeTimerRef.current = setInterval(() => {
      if (isOnline && appStateRef.current === 'active') {
        connectStream(true);
      }
    }, streamRecoveryProbeMs);
  }, [clearTimers, pollRecentEvents, pollingIntervalMs, isOnline, streamRecoveryProbeMs]);

  const connectStream = useCallback(
    (isRecoveryProbe = false) => {
      if (!enabled || !isOnline || appStateRef.current !== 'active') {
        return;
      }

      if (!isRecoveryProbe) {
        setStatus(consecutiveFailuresRef.current === 0 ? 'connecting' : 'retrying');
      }

      closeEventSource();

      const auth = apiClient.getAuth();
      const baseUrl = getBackendUrl().replace(/\/+$/, '');
      const url = new URL(`${baseUrl}/api/v1/stream`);
      url.searchParams.append('topics', topics);
      if (lastEventIdRef.current) {
        url.searchParams.append('last_event_id', lastEventIdRef.current);
      }
      if (auth.token) {
        url.searchParams.append('token', auth.token);
      }

      const headers: Record<string, any> = {
        Accept: 'text/event-stream',
      };
      if (auth.token) {
        headers['Authorization'] = `Bearer ${auth.token}`;
      }
      if (auth.role) headers['X-User-Role'] = auth.role;
      if (auth.nodeId) headers['X-Node-Id'] = auth.nodeId;
      if (lastEventIdRef.current) {
        headers['Last-Event-ID'] = lastEventIdRef.current;
      }

      const sourceOptions = {
        headers,
        lineEndingCharacter: '\n',
      };

      try {
        let es: any;
        if (eventSourceFactory) {
          es = eventSourceFactory(url.toString(), sourceOptions);
        } else {
          es = new EventSource(url.toString(), sourceOptions);
        }

        eventSourceRef.current = es;

        es.addEventListener('open', () => {
          if (!isComponentMountedRef.current) return;
          consecutiveFailuresRef.current = 0;
          setStatus('open');
          setIsPollingFallback(false);
          clearTimers();
        });

        es.addEventListener('message', (event: any) => {
          if (!isComponentMountedRef.current) return;
          if (!event.data) return;

          try {
            const parsed = JSON.parse(event.data);
            if (parsed.status === 'connected') return;

            const normalized: MobileStreamEvent = {
              id: parsed.id || parsed.event_id || `evt-${Date.now()}`,
              event_id: parsed.event_id || parsed.id || `evt-${Date.now()}`,
              event_type: parsed.event_type || parsed.type || 'domain.event',
              topic: parsed.topic || parsed.type,
              agent_name: parsed.agent_name || 'Supply Chain Node Agent',
              tier: parsed.tier || 'PHARMACY',
              summary: parsed.summary || parsed.payload?.summary || 'Operational event received.',
              correlation_id: parsed.correlation_id || parsed.payload?.correlation_id || 'unknown',
              node_id: parsed.node_id || parsed.payload?.node_id,
              node_name: parsed.node_name || parsed.payload?.node_name,
              created_at: parsed.created_at || parsed.ts || new Date().toISOString(),
              payload: parsed.payload || parsed,
            };

            addEvents([normalized]);
          } catch {
            // Ignore non-json comments/heartbeats
          }
        });

        es.addEventListener('error', () => {
          if (!isComponentMountedRef.current) return;
          closeEventSource();
          consecutiveFailuresRef.current += 1;

          if (consecutiveFailuresRef.current >= maxFailuresBeforePolling) {
            startPollingFallback();
          } else {
            setStatus('retrying');
            const attempt = consecutiveFailuresRef.current;
            const backoff = Math.min(maxBackoffMs, initialBackoffMs * Math.pow(2, attempt - 1));
            clearTimers();
            reconnectTimerRef.current = setTimeout(() => {
              connectStream();
            }, backoff);
          }
        });
      } catch {
        consecutiveFailuresRef.current += 1;
        startPollingFallback();
      }
    },
    [
      enabled,
      isOnline,
      topics,
      eventSourceFactory,
      closeEventSource,
      clearTimers,
      addEvents,
      maxFailuresBeforePolling,
      startPollingFallback,
      maxBackoffMs,
      initialBackoffMs,
    ]
  );

  const reconnect = useCallback(() => {
    consecutiveFailuresRef.current = 0;
    setIsPollingFallback(false);
    clearTimers();
    connectStream();
  }, [clearTimers, connectStream]);

  const refreshRecent = useCallback(async () => {
    await pollRecentEvents();
    if (status !== 'open') {
      reconnect();
    }
  }, [pollRecentEvents, status, reconnect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setLastEvent(null);
    seenEventIdsRef.current.clear();
  }, []);

  // Initial stream setup & teardown
  useEffect(() => {
    isComponentMountedRef.current = true;

    // Load initial events from recent endpoint immediately
    pollRecentEvents();

    if (enabled && isOnline) {
      connectStream();
    } else if (!isOnline) {
      setStatus('failed');
    }

    return () => {
      isComponentMountedRef.current = false;
      clearTimers();
      closeEventSource();
    };
  }, [enabled, isOnline, connectStream, pollRecentEvents, clearTimers, closeEventSource]);

  // AppState background / foreground handling
  useEffect(() => {
    const handleAppStateChange = (nextState: AppStateStatus) => {
      const prev = appStateRef.current;
      appStateRef.current = nextState;

      if (nextState !== 'active') {
        // App in background / inactive: pause connection to save battery & data
        closeEventSource();
        clearTimers();
      } else if (prev !== 'active' && nextState === 'active') {
        // App returned to foreground: reconnect with Last-Event-ID
        reconnect();
      }
    };

    const sub = AppState.addEventListener('change', handleAppStateChange);
    return () => {
      sub.remove();
    };
  }, [closeEventSource, clearTimers, reconnect]);

  // Network recovery handling (offline -> online)
  useEffect(() => {
    if (isOnline) {
      if (status === 'failed') {
        reconnect();
      }
    } else {
      setStatus('failed');
      closeEventSource();
      clearTimers();
    }
  }, [isOnline, status, reconnect, closeEventSource, clearTimers]);

  return {
    status,
    isPollingFallback,
    events,
    lastEvent,
    lastEventId: lastEventIdRef.current,
    reconnect,
    refreshRecent,
    clearEvents,
  };
}
