import 'react-native-url-polyfill/auto';
import { AppState, AppStateStatus } from 'react-native';
import { createClient } from '@supabase/supabase-js';
import { supabaseStorageAdapter } from './storage';

export const supabaseUrl =
  process.env.EXPO_PUBLIC_SUPABASE_URL || 'https://drjyczgwntuibykxodgs.supabase.co';
export const supabaseAnonKey =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || 'sb_publishable_NEx8s6S7CR4eM4J5QuDifw_mCI1ezZ_';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: supabaseStorageAdapter,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

export function handleAppStateChange(state: AppStateStatus): void {
  if (state === 'active') {
    try {
      supabase.auth.startAutoRefresh();
    } catch {
      // Ignore if unsupported in environment
    }
  } else {
    try {
      supabase.auth.stopAutoRefresh();
    } catch {
      // Ignore if unsupported in environment
    }
  }
}

// Register AppState listener for foreground/background token auto-refresh
if (typeof AppState?.addEventListener === 'function') {
  AppState.addEventListener('change', handleAppStateChange);
}

