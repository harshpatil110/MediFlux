/**
 * Backend Connection & Desktop Settings Modal.
 *
 * Implements Task 28:
 * - Runtime-configurable Backend API Base URL store.
 * - Live connection health probe measuring round-trip latency (ms).
 * - Desktop runtime badge (Electron / Tauri native shell vs Web browser).
 * - "🔔 Test Native Notification" button triggering both HITL and Quarantine alerts.
 * - Adheres strictly to Warm Editorial Minimalism design system (design.md).
 */

import React, { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Check,
  Monitor,
  RefreshCw,
  RotateCcw,
  Server,
  Sparkles,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { getApiBaseUrl, resetApiBaseUrl, setApiBaseUrl } from "../../config/env";
import { useDesktopNotifications } from "../../hooks/useDesktopNotifications";
import { api } from "../../lib/api";

interface BackendSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface HealthCheckResult {
  ok: boolean;
  latencyMs?: number;
  data?: any;
  error?: string;
}

export const BackendSettingsModal: React.FC<BackendSettingsModalProps> = ({ isOpen, onClose }) => {
  const queryClient = useQueryClient();
  const { testNotification } = useDesktopNotifications();

  const [currentUrl, setCurrentUrl] = useState<string>(getApiBaseUrl());
  const [candidateUrl, setCandidateUrl] = useState<string>(getApiBaseUrl());
  const [testingStatus, setTestingStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [healthResult, setHealthResult] = useState<HealthCheckResult | null>(null);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [isResettingDemo, setIsResettingDemo] = useState<boolean>(false);

  const handleResetDemoState = async () => {
    setIsResettingDemo(true);
    try {
      await api.demo.reset();
      queryClient.invalidateQueries();
      window.dispatchEvent(new CustomEvent("mediflux:backend-url-changed"));
    } catch (err) {
      console.warn("Failed to reset demo state:", err);
    } finally {
      setIsResettingDemo(false);
    }
  };

  // Detect desktop runtime shell
  const isDesktop =
    typeof window !== "undefined" && Boolean((window as any).medifluxDesktop?.isDesktop);
  const desktopRuntime =
    typeof window !== "undefined" ? (window as any).medifluxDesktop?.runtime || "web" : "web";

  // Synchronize on modal open
  useEffect(() => {
    if (isOpen) {
      const active = getApiBaseUrl();
      setCurrentUrl(active);
      setCandidateUrl(active);
      setSavedSuccess(false);
      pingCandidateUrl(active);
    }
  }, [isOpen]);

  // Ping backend /health probe and measure round-trip latency
  const pingCandidateUrl = async (targetUrl: string) => {
    setTestingStatus("testing");
    setHealthResult(null);

    const cleanUrl = targetUrl.trim().replace(/\/+$/, "");
    const startTime = performance.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      const resp = await fetch(`${cleanUrl}/health`, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      clearTimeout(timeoutId);

      const latencyMs = Math.round(performance.now() - startTime);

      if (resp.ok) {
        const data = await resp.json();
        setTestingStatus("success");
        setHealthResult({ ok: true, latencyMs, data });
      } else {
        setTestingStatus("error");
        setHealthResult({
          ok: false,
          latencyMs,
          error: `HTTP ${resp.status} ${resp.statusText}`,
        });
      }
    } catch (err: any) {
      const latencyMs = Math.round(performance.now() - startTime);
      setTestingStatus("error");
      setHealthResult({
        ok: false,
        latencyMs,
        error: err.name === "AbortError" ? "Connection timed out (4s)" : err.message || "Connection refused",
      });
    }
  };

  // Save new backend URL and reconnect
  const handleSaveAndReconnect = () => {
    setApiBaseUrl(candidateUrl);
    setCurrentUrl(candidateUrl);
    setSavedSuccess(true);

    // Invalidate all cached queries
    queryClient.invalidateQueries();

    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 900);
  };

  // Reset to default
  const handleResetDefault = () => {
    resetApiBaseUrl();
    const defaultUrl = "http://localhost:8000";
    setCandidateUrl(defaultUrl);
    setCurrentUrl(defaultUrl);
    pingCandidateUrl(defaultUrl);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-[var(--bg-surface)] border-2 border-[var(--border-subtle)] shadow-2xl space-y-5 p-6 relative">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[var(--border-subtle)] pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 bg-[var(--accent-teal)]/10 text-[var(--accent-teal)]">
                <Server className="w-4 h-4" />
              </span>
              <h3 className="text-sm font-serif font-bold text-[var(--text-primary)]">
                Backend Connection & Runtime Settings
              </h3>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              Configure FastAPI target URL, probe network latency, and inspect desktop runtime shell.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-canvas)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Runtime Badge Row */}
        <div className="flex items-center justify-between p-2.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono">
          <div className="flex items-center gap-2">
            <Monitor className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
            <span className="text-[var(--text-secondary)]">Active Environment:</span>
            <span className="font-bold text-[var(--text-primary)]">
              {isDesktop ? `Desktop App (${desktopRuntime.toUpperCase()} Shell)` : "Standard Web Browser"}
            </span>
          </div>

          <span
            className={`px-2 py-0.5 text-[10px] uppercase font-bold border ${
              isDesktop
                ? "bg-teal-50 text-teal-800 border-teal-300 dark:bg-teal-950/60 dark:text-teal-200"
                : "bg-stone-100 text-stone-800 border-stone-300 dark:bg-stone-900 dark:text-stone-300"
            }`}
          >
            {isDesktop ? "Native Desktop" : "Web Client"}
          </span>
        </div>

        {/* Live Status Indicator Bar */}
        <div className="p-3 border border-[var(--border-subtle)] bg-[var(--bg-canvas)] space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[var(--text-secondary)]">Live Probe Status:</span>
            {testingStatus === "testing" ? (
              <span className="text-amber-600 dark:text-amber-400 font-bold flex items-center gap-1.5">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> PROBING TARGET...
              </span>
            ) : healthResult?.ok ? (
              <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1.5">
                <Wifi className="w-3.5 h-3.5" /> ONLINE ({healthResult.latencyMs}ms)
              </span>
            ) : (
              <span className="text-coral-600 dark:text-coral-400 font-bold flex items-center gap-1.5">
                <WifiOff className="w-3.5 h-3.5" /> UNREACHABLE
              </span>
            )}
          </div>

          {healthResult && (
            <div className="text-[11px] font-mono text-[var(--text-secondary)] pt-1 border-t border-[var(--border-subtle)] flex flex-wrap justify-between gap-1">
              {healthResult.ok ? (
                <>
                  <span>Version: {healthResult.data?.version || "1.0.0"}</span>
                  <span>Service: {healthResult.data?.app || "MediFlux Backend"}</span>
                  <span>CORS: Enabled</span>
                </>
              ) : (
                <span className="text-coral-600">{healthResult.error}</span>
              )}
            </div>
          )}
        </div>

        {/* Target URL Input & Presets */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[var(--text-secondary)]">FastAPI Backend Target URL:</span>
            <span className="text-[10px] text-[var(--text-secondary)] truncate max-w-[200px]">
              Active: {currentUrl}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={candidateUrl}
              onChange={(e) => setCandidateUrl(e.target.value)}
              placeholder="http://localhost:8000"
              className="flex-1 px-3 py-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
            />
            <button
              type="button"
              disabled={testingStatus === "testing"}
              onClick={() => pingCandidateUrl(candidateUrl)}
              className="px-3 py-2 bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono text-[var(--text-primary)] font-semibold shrink-0 transition-colors"
            >
              Test Ping
            </button>
          </div>

          {/* Quick Presets */}
          <div className="flex items-center gap-2 pt-1 text-xs font-mono text-[var(--text-secondary)]">
            <span className="text-[10px]">Quick Presets:</span>
            <button
              type="button"
              onClick={() => {
                setCandidateUrl("http://localhost:8000");
                pingCandidateUrl("http://localhost:8000");
              }}
              className="px-2 py-0.5 text-[10px] bg-[var(--bg-canvas)] hover:border-[var(--accent-teal)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
            >
              localhost:8000
            </button>
            <button
              type="button"
              onClick={() => {
                setCandidateUrl("http://127.0.0.1:8000");
                pingCandidateUrl("http://127.0.0.1:8000");
              }}
              className="px-2 py-0.5 text-[10px] bg-[var(--bg-canvas)] hover:border-[var(--accent-teal)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
            >
              127.0.0.1:8000
            </button>
          </div>
        </div>

        {/* Native Notification Test Buttons */}
        <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[var(--text-secondary)] flex items-center gap-1.5 font-semibold">
              <Bell className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
              Native Desktop Notifications:
            </span>
            <span className="text-[10px] text-[var(--text-secondary)]">Click to test instant alert</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => testNotification("hitl")}
              className="flex-1 py-1.5 px-2 bg-[var(--bg-surface)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-xs font-mono text-[var(--text-primary)] flex items-center justify-center gap-1.5 transition-colors"
            >
              🔔 Test Approval Alert
            </button>
            <button
              type="button"
              onClick={() => testNotification("quarantine")}
              className="flex-1 py-1.5 px-2 bg-[var(--bg-surface)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-xs font-mono text-[var(--text-primary)] flex items-center justify-center gap-1.5 transition-colors"
            >
              ❄️ Test Quarantine Alert
            </button>
          </div>
        </div>

        {/* Demo State & Replay Controls */}
        <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-xs font-mono font-bold text-[var(--text-primary)] block">
              Demo Environment State
            </span>
            <span className="text-[11px] text-[var(--text-secondary)]">
              Deterministic 6-Act sequence, offline LLM replay cache, and clean baseline restore.
            </span>
          </div>
          <button
            type="button"
            disabled={isResettingDemo}
            onClick={handleResetDemoState}
            className="px-3 py-1.5 border border-[var(--border-subtle)] hover:bg-[var(--bg-surface)] text-xs font-mono flex items-center gap-1.5 transition-colors text-[var(--text-primary)] disabled:opacity-50"
          >
            <RotateCcw className={`w-3.5 h-3.5 text-[var(--accent-teal)] ${isResettingDemo ? "animate-spin" : ""}`} />
            <span>{isResettingDemo ? "Resetting..." : "Reset Demo"}</span>
          </button>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-[var(--border-subtle)]">
          <button
            type="button"
            onClick={handleResetDefault}
            className="inline-flex items-center gap-1.5 text-xs font-mono text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <RotateCcw className="w-3 h-3" /> Reset Default
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-xs font-mono text-[var(--text-primary)]"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleSaveAndReconnect}
              className="px-5 py-2 bg-[var(--accent-teal)] hover:opacity-90 text-[var(--bg-surface)] text-xs font-mono font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-xs"
            >
              {savedSuccess ? (
                <>
                  <Check className="w-3.5 h-3.5" /> Reconnected!
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" /> Save & Reconnect
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
