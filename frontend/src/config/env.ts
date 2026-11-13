/**
 * Environment configuration for MediFlux frontend.
 * Reads Vite environment variables or falls back to local development defaults.
 */

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "http://localhost:8000")
).replace(/\/+$/, "");

export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "https://drjyczgwntuibykxodgs.supabase.co";

export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRyanljend3bnR1aWJ5a3hvZGdzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDk4NTYwMDAsImV4cCI6MjAyNTQzMjAwMH0.mock";

export const IS_PRODUCTION = import.meta.env.PROD;
