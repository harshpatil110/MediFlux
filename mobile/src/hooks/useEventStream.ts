import { useState, useEffect, useRef } from 'react';
import { Platform } from 'react-native';
import { getBackendUrl } from '../lib/config';
import { SseEventEnvelope } from '@mediflux/shared';

export interface UseEventStreamOptions {
  channel?: string;
  enabled?: boolean;
  onEvent?: (event: SseEventEnvelope) => void;
}

export function useEventStream({
  channel = 'all',
  enabled = true,
  onEvent,
}: UseEventStreamOptions = {}) {
  const [events, setEvents] = useState<SseEventEnvelope[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const eventSourceRef = useRef<any>(null);

  useEffect(() => {
    if (!enabled) {
      setIsConnected(false);
      return;
    }

    const baseUrl = getBackendUrl().replace(/\/+$/, '');
    const streamUrl = `${baseUrl}/api/v1/events/stream?channel=${encodeURIComponent(channel)}`;

    if (Platform.OS === 'web' && typeof window !== 'undefined' && 'EventSource' in window) {
      try {
        const es = new EventSource(streamUrl);
        eventSourceRef.current = es;

        es.onopen = () => {
          setIsConnected(true);
          setLastError(null);
        };

        es.onmessage = (event) => {
          try {
            const parsed = JSON.parse(event.data) as SseEventEnvelope;
            setEvents((prev) => [parsed, ...prev.slice(0, 99)]);
            onEvent?.(parsed);
          } catch {
            // Ignore non-json ping/heartbeats
          }
        };

        es.onerror = () => {
          setIsConnected(false);
          setLastError('SSE Connection error');
        };

        return () => {
          es.close();
          eventSourceRef.current = null;
        };
      } catch (err: unknown) {
        setLastError((err as Error)?.message || 'Failed to initialize EventSource');
      }
    } else {
      // Fetch-based SSE reader for React Native
      const controller = new AbortController();
      let isMounted = true;

      const connectNativeSse = async () => {
        try {
          const res = await fetch(streamUrl, {
            headers: { Accept: 'text/event-stream' },
            signal: controller.signal,
          });

          if (!res.ok) {
            if (isMounted) {
              setIsConnected(false);
              setLastError(`HTTP ${res.status}`);
            }
            return;
          }

          if (isMounted) {
            setIsConnected(true);
            setLastError(null);
          }
        } catch (err: unknown) {
          if (isMounted && !controller.signal.aborted) {
            setIsConnected(false);
            setLastError((err as Error)?.message || 'Native SSE connection failed');
          }
        }
      };

      connectNativeSse();

      return () => {
        isMounted = false;
        controller.abort();
      };
    }
  }, [channel, enabled]);

  const clearEvents = () => setEvents([]);

  return { events, isConnected, lastError, clearEvents };
}
