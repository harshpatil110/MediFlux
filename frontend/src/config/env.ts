/**
 * Environment configuration for MediFlux frontend.
 * Provides dynamic runtime-configurable Backend API URL store with localStorage persistence.
 */

const BACKEND_URL_STORAGE_KEY = "mediflux_backend_url";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    try {
      const stored = localStorage.getItem(BACKEND_URL_STORAGE_KEY);
      if (stored && stored.trim()) {
        return stored.trim().replace(/\/+$/, "");
      }
    } catch {
      // localStorage may fail in restricted sandboxes
    }
  }

  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, "");
  }

  return "http://localhost:8000";
}

export function setApiBaseUrl(url: string): void {
  if (typeof window === "undefined") return;
  const clean = url.trim().replace(/\/+$/, "");
  try {
    localStorage.setItem(BACKEND_URL_STORAGE_KEY, clean);
  } catch {
    // Ignore storage quota errors
  }
  window.dispatchEvent(
    new CustomEvent("mediflux:backend-url-changed", { detail: { url: clean } })
  );
}

export function resetApiBaseUrl(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(BACKEND_URL_STORAGE_KEY);
  } catch {
    // Ignore
  }
  const defaultUrl = "http://localhost:8000";
  window.dispatchEvent(
    new CustomEvent("mediflux:backend-url-changed", { detail: { url: defaultUrl } })
  );
}

// Backward-compatible constant returning current evaluated base URL
export const API_BASE_URL = getApiBaseUrl();

export const SUPABASE_URL =
  import.meta.env.VITE_SUPABASE_URL || "https://drjyczgwntuibykxodgs.supabase.co";

export const SUPABASE_ANON_KEY =
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRyanljend3bnR1aWJ5a3hvZGdzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDk4NTYwMDAsImV4cCI6MjAyNTQzMjAwMH0.mock";

export const IS_PRODUCTION = import.meta.env.PROD;
