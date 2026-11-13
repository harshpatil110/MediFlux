import { useCallback, useEffect, useState } from "react";
import { useEventStream } from "./useEventStream";

const MUTE_STORAGE_KEY = "mediflux_hitl_notifications_muted";

export interface DesktopNotificationState {
  permission: NotificationPermission;
  isSupported: boolean;
  isMuted: boolean;
  requestPermission: () => Promise<NotificationPermission>;
  toggleMute: () => void;
  notify: (title: string, options?: NotificationOptions) => void;
}

export function useDesktopNotifications(onNewTask?: (event: any) => void): DesktopNotificationState {
  const isSupported = typeof window !== "undefined" && "Notification" in window;
  const [permission, setPermission] = useState<NotificationPermission>(() => {
    if (!isSupported) return "denied";
    return Notification.permission;
  });

  const [isMuted, setIsMuted] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(MUTE_STORAGE_KEY) === "true";
  });

  const requestPermission = useCallback(async () => {
    if (!isSupported) return "denied";
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      return result;
    } catch {
      return "denied";
    }
  }, [isSupported]);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        localStorage.setItem(MUTE_STORAGE_KEY, String(next));
      }
      return next;
    });
  }, []);

  const notify = useCallback(
    (title: string, options?: NotificationOptions) => {
      if (!isSupported || isMuted || permission !== "granted") return;
      try {
        new Notification(title, {
          icon: "/favicon.ico",
          badge: "/favicon.ico",
          ...options,
        });
      } catch (err) {
        console.warn("Desktop notification error:", err);
      }
    },
    [isSupported, isMuted, permission]
  );

  // Listen to HITL events from the live SSE stream
  const { events } = useEventStream({
    topics: ["hitl", "hitl.*"],
    maxEvents: 20,
    enabled: true,
  });

  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[0];
    if (
      latest.topic?.startsWith("hitl") ||
      latest.event_type?.includes("hitl") ||
      latest.event_type?.includes("task")
    ) {
      if (onNewTask) {
        onNewTask(latest);
      }
      const title = `🚨 Action Required: ${latest.payload?.task_type || latest.event_type || "Approval Requested"}`;
      const body =
        latest.payload?.summary ||
        latest.payload?.reasoning ||
        `Risk: ${latest.payload?.risk_level || "HIGH"}. Click to review in Approvals Inbox.`;
      notify(title, {
        body,
        tag: latest.event_id,
      });
    }
  }, [events, notify, onNewTask]);

  return {
    permission,
    isSupported,
    isMuted,
    requestPermission,
    toggleMute,
    notify,
  };
}
