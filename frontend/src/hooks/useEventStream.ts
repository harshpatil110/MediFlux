/**
 * Resilient Server-Sent Events (SSE) hook with topic filtering,
 * Last-Event-ID tracking, auto-reconnect with exponential backoff, and ring buffer.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { getApiBaseUrl } from "../config/env";
import { getStoredToken, getStoredUser } from "../lib/api";
import type { SystemEvent } from "../types/api";

export type SseConnectionState = "connecting" | "connected" | "reconnecting" | "closed";

interface UseEventStreamOptions {
  topics?: string[];
  maxEvents?: number;
  enabled?: boolean;
}

export function useEventStream(options: UseEventStreamOptions = {}) {
  const { topics = ["*"], maxEvents = 100, enabled = true } = options;

  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [connectionState, setConnectionState] = useState<SseConnectionState>("closed");
  const [lastEventId, setLastEventId] = useState<string | null>(null);

  const lastEventIdRef = useRef<string | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    // Abort existing connection if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const token = getStoredToken();
    const user = getStoredUser();

    // Build URL with query params
    const query = new URLSearchParams();
    const joinedTopics = topics.length > 0 ? topics.join(",") : "*";
    query.set("topics", joinedTopics);

    if (lastEventIdRef.current) {
      query.set("last_event_id", lastEventIdRef.current);
    }

    if (token) {
      query.set("token", token);
    }

    if (user?.role) {
      query.set("role", user.role);
    }

    const baseUrl = getApiBaseUrl();
    const sseUrl = `${baseUrl}/api/v1/events/stream?${query.toString()}`;

    setConnectionState((prev) => (prev === "closed" ? "connecting" : "reconnecting"));

    const headers: Record<string, string> = {
      Accept: "text/event-stream",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    if (lastEventIdRef.current) {
      headers["Last-Event-ID"] = lastEventIdRef.current;
    }
    if (user?.role) {
      headers["X-User-Role"] = user.role;
    }
    if (user?.node_id) {
      headers["X-Node-Id"] = user.node_id;
    }

    fetch(sseUrl, {
      method: "GET",
      headers,
      signal: abortController.signal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          throw new Error(`SSE stream failed with status ${response.status}`);
        }

        setConnectionState("connected");
        reconnectAttemptsRef.current = 0;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        let currentId = "";
        let currentEvent = "";
        let currentData = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith(":")) {
              // Heartbeat comment or empty line
              if (trimmed === "" && (currentData || currentEvent)) {
                // Dispatch completed event
                let parsedPayload: Record<string, any> = {};
                try {
                  parsedPayload = JSON.parse(currentData);
                } catch {
                  parsedPayload = { raw: currentData };
                }

                const newEvent: SystemEvent = {
                  event_id: currentId || parsedPayload.event_id || `evt-${Date.now()}`,
                  type: currentEvent || parsedPayload.type || "system.event",
                  node_id: parsedPayload.node_id || "network",
                  correlation_id: parsedPayload.correlation_id || "",
                  timestamp: parsedPayload.timestamp || new Date().toISOString(),
                  payload: parsedPayload.payload || parsedPayload,
                };

                if (currentId) {
                  lastEventIdRef.current = currentId;
                  setLastEventId(currentId);
                }

                setEvents((prev) => [newEvent, ...prev].slice(0, maxEvents));

                // Reset per-event fields
                currentId = "";
                currentEvent = "";
                currentData = "";
              }
              continue;
            }

            if (trimmed.startsWith("id:")) {
              currentId = trimmed.slice(3).trim();
            } else if (trimmed.startsWith("event:")) {
              currentEvent = trimmed.slice(6).trim();
            } else if (trimmed.startsWith("data:")) {
              const dataContent = trimmed.slice(5).trim();
              currentData = currentData ? `${currentData}\n${dataContent}` : dataContent;
            }
          }
        }
      })
      .catch((err) => {
        if (err.name === "AbortError") {
          return;
        }
        console.warn("SSE connection encountered error:", err);
        setConnectionState("reconnecting");

        // Exponential backoff reconnect
        const attempt = reconnectAttemptsRef.current;
        const delay = Math.min(1000 * Math.pow(2, attempt), 15000);
        reconnectAttemptsRef.current += 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      });
  }, [enabled, maxEvents, topics]);

  useEffect(() => {
    connect();

    const handleUrlChanged = () => {
      reconnectAttemptsRef.current = 0;
      connect();
    };
    window.addEventListener("mediflux:backend-url-changed", handleUrlChanged);

    return () => {
      window.removeEventListener("mediflux:backend-url-changed", handleUrlChanged);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      setConnectionState("closed");
    };
  }, [connect]);

  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  return {
    events,
    connectionState,
    lastEventId,
    clearEvents,
    reconnect,
  };
}
