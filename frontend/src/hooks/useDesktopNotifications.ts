import { useCallback, useEffect, useState } from "react";
import { useEventStream } from "./useEventStream";

const MUTE_STORAGE_KEY = "mediflux_notifications_muted";

export interface DesktopNotificationState {
  permission: NotificationPermission;
  isSupported: boolean;
  isMuted: boolean;
  requestPermission: () => Promise<NotificationPermission>;
  toggleMute: () => void;
  notify: (title: string, options?: NotificationOptions & { route?: string }) => void;
  testNotification: (type?: "hitl" | "quarantine") => void;
}

export function useDesktopNotifications(onEvent?: (event: any) => void): DesktopNotificationState {
  const isDesktopShell =
    typeof window !== "undefined" && Boolean((window as any).medifluxDesktop?.isDesktop);

  const isBrowserNotificationSupported = typeof window !== "undefined" && "Notification" in window;
  const isSupported = isDesktopShell || isBrowserNotificationSupported;

  const [permission, setPermission] = useState<NotificationPermission>(() => {
    if (isDesktopShell) return "granted";
    if (!isBrowserNotificationSupported) return "denied";
    return Notification.permission;
  });

  const [isMuted, setIsMuted] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(MUTE_STORAGE_KEY) === "true";
  });

  const requestPermission = useCallback(async () => {
    if (isDesktopShell) {
      setPermission("granted");
      return "granted";
    }
    if (!isBrowserNotificationSupported) return "denied";
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      return result;
    } catch {
      return "denied";
    }
  }, [isDesktopShell, isBrowserNotificationSupported]);

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
    (title: string, options?: NotificationOptions & { route?: string }) => {
      if (isMuted) return;

      // 1. Prioritize native desktop bridge if running in Electron / Tauri
      if (typeof window !== "undefined" && (window as any).medifluxDesktop?.showNotification) {
        try {
          (window as any).medifluxDesktop.showNotification({
            title,
            body: options?.body || "",
            route: options?.route,
          });
          return;
        } catch (err) {
          console.warn("Desktop native notification bridge error:", err);
        }
      }

      // 2. Standard Web Notification API fallback
      if (isBrowserNotificationSupported && permission === "granted") {
        try {
          const notif = new Notification(title, {
            icon: "/favicon.ico",
            badge: "/favicon.ico",
            ...options,
          });

          if (options?.route && typeof window !== "undefined") {
            notif.onclick = () => {
              window.focus();
              window.location.hash = options.route || "#/";
            };
          }
        } catch (err) {
          console.warn("Web Notification API error:", err);
        }
      }
    },
    [isMuted, isBrowserNotificationSupported, permission]
  );

  // One-click test notification dispatcher
  const testNotification = useCallback(
    (type: "hitl" | "quarantine" = "hitl") => {
      if (type === "quarantine") {
        notify("❄️ Cold-Chain Batch Auto-Quarantined", {
          body: "Batch B26-INS-REG-01 quarantined at Bangalore Hub (excursion 16.5°C). Dynamic balancing initiated.",
          route: "/cold-chain",
        });
      } else {
        notify("⚠️ MediFlux Approval Required", {
          body: "High-risk task awaiting review: Schedule H Dual Authorization at Apollo Pharmacy #4.",
          route: "/approvals",
        });
      }
    },
    [notify]
  );

  // Listen to live SSE event streams for HITL tasks and Cold-Chain Quarantines
  const { events } = useEventStream({
    topics: ["hitl", "hitl.*", "coldchain", "coldchain.*", "batch.*"],
    maxEvents: 25,
    enabled: true,
  });

  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[0];
    const eventType = (latest.type || latest.event_type || latest.topic || "").toLowerCase();

    if (onEvent) {
      onEvent(latest);
    }

    // 1. HITL Approval Task Created
    if (eventType.includes("hitl") || eventType.includes("task.created")) {
      const taskType =
        latest.data?.task_type ||
        latest.payload?.task_type ||
        latest.data?.title ||
        "Human Approval Required";
      const nodeName = latest.data?.node_name || latest.payload?.node_name || "Regional Node";

      notify("⚠️ MediFlux Approval Required", {
        body: `High-risk task awaiting review: ${taskType} at ${nodeName}.`,
        route: "/approvals",
        tag: latest.id || latest.event_id,
      });
    }

    // 2. Cold-Chain Batch Quarantined
    else if (
      eventType.includes("quarantine") ||
      (eventType.includes("coldchain") && (latest.data?.decision === "quarantine" || latest.payload?.decision === "quarantine"))
    ) {
      const batchNo =
        latest.data?.batch_no ||
        latest.data?.batch_id ||
        latest.payload?.batch_no ||
        "Biologic Batch";
      const nodeName = latest.data?.node_name || latest.payload?.node_name || "Cold Storage Hub";

      notify("❄️ Cold-Chain Batch Auto-Quarantined", {
        body: `Batch ${batchNo} auto-quarantined at ${nodeName} due to environmental breach. Restock cascade active.`,
        route: "/cold-chain",
        tag: latest.id || latest.event_id,
      });
    }
  }, [events, notify, onEvent]);

  return {
    permission,
    isSupported,
    isMuted,
    requestPermission,
    toggleMute,
    notify,
    testNotification,
  };
}
