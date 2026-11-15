import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { storage } from '../../lib/storage';
import { supabase } from '../../lib/supabase';
import { apiClient } from '../../api/client';
import { UserRole } from '../../api/generated';
import { getBackendUrl } from '../../lib/config';

export const AUTH_STORAGE_KEY = 'mediflux_auth_session_v1';

export interface SessionData {
  accessToken: string;
  refreshToken: string;
  expiresAt?: number;
}

export interface UserData {
  id?: string;
  user_id: string;
  email: string;
  full_name?: string;
  role: UserRole;
  role_name?: string;
  node_id: string | null;
  node_name: string | null;
  tier?: string;
  region?: string;
  permissions?: {
    can_view_approvals: boolean;
    can_decide_approvals: boolean;
  };
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export interface StoredSessionPayload {
  session: SessionData;
  user: UserData;
}

export interface AuthContextValue {
  status: AuthStatus;
  session: SessionData | null;
  user: UserData | null;
  error: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginAsDemoRole: (role: string) => Promise<void>;
  logout: () => Promise<void>;
  forceLogout: (reason?: string) => Promise<void>;
  refreshSessionOnce: () => Promise<string | null>;
  reloadProfile: () => Promise<UserData | null>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [session, setSession] = useState<SessionData | null>(null);
  const [user, setUser] = useState<UserData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const clearSessionStorage = useCallback(async () => {
    try {
      await storage.removeItem(AUTH_STORAGE_KEY);
      apiClient.clearAuth();
      try {
        await supabase.auth.signOut();
      } catch {
        // Ignore supabase signout issues
      }
    } catch {
      // Ignore
    }
  }, []);

  const forceLogout = useCallback(
    async (reason?: string) => {
      await clearSessionStorage();
      setSession(null);
      setUser(null);
      setStatus('unauthenticated');
      if (reason) {
        setError(reason);
      }
    },
    [clearSessionStorage]
  );

  const updateStoredSession = useCallback(
    async (newSession: SessionData, newUser: UserData) => {
      setSession(newSession);
      setUser(newUser);
      setStatus('authenticated');
      apiClient.setAuth({
        token: newSession.accessToken,
        role: newUser.role,
        nodeId: newUser.node_id,
        userId: newUser.user_id,
      });
      await storage.setItem(
        AUTH_STORAGE_KEY,
        JSON.stringify({ session: newSession, user: newUser })
      );
    },
    []
  );

  const fetchEnrichedProfile = useCallback(async (token: string): Promise<UserData> => {
    const baseUrl = getBackendUrl().replace(/\/+$/, '');
    const res = await fetch(`${baseUrl}/api/v1/me`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const code = errBody?.error?.code || errBody?.detail?.code || `HTTP_${res.status}`;
      const msg = errBody?.error?.message || errBody?.detail || 'Failed to fetch user profile';
      const err = new Error(msg);
      (err as any).code = code;
      (err as any).status = res.status;
      throw err;
    }

    const data = await res.json();
    return {
      id: data.id || data.user_id,
      user_id: data.user_id || data.id,
      email: data.email,
      full_name: data.full_name,
      role: (data.role || 'pharmacy').toLowerCase() as UserRole,
      role_name: data.role_name,
      node_id: data.node_id || null,
      node_name: data.node_name || null,
      tier: data.tier,
      region: data.region,
      permissions: data.permissions || {
        can_view_approvals: true,
        can_decide_approvals: ['admin', 'stockist', 'distributor', 'manufacturer', 'regulator'].includes(
          (data.role || '').toLowerCase()
        ),
      },
    };
  }, []);

  const refreshSessionOnce = useCallback(async (): Promise<string | null> => {
    try {
      // 1. Try Supabase refresh
      const { data: supaData } = await supabase.auth.refreshSession();
      if (supaData?.session?.access_token) {
        const newSession: SessionData = {
          accessToken: supaData.session.access_token,
          refreshToken: supaData.session.refresh_token,
          expiresAt: supaData.session.expires_at,
        };
        if (user) {
          await updateStoredSession(newSession, user);
        }
        return newSession.accessToken;
      }
    } catch {
      // Continue to backend refresh
    }

    try {
      // 2. Try Backend refresh endpoint
      const rawStored = await storage.getItem(AUTH_STORAGE_KEY);
      if (rawStored) {
        const parsed: StoredSessionPayload = JSON.parse(rawStored);
        const refToken = parsed.session?.refreshToken || parsed.session?.accessToken;
        if (refToken) {
          const baseUrl = getBackendUrl().replace(/\/+$/, '');
          const res = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'application/json',
            },
            body: JSON.stringify({ refresh_token: refToken }),
          });

          if (res.ok) {
            const data = await res.json();
            const newSession: SessionData = {
              accessToken: data.access_token,
              refreshToken: data.refresh_token || refToken,
              expiresAt: Math.floor(Date.now() / 1000) + (data.expires_in || 3600),
            };
            const currentUser = user || parsed.user;
            await updateStoredSession(newSession, currentUser);
            return newSession.accessToken;
          }
        }
      }
    } catch {
      // Refresh failed
    }

    return null;
  }, [user, updateStoredSession]);

  const reloadProfile = useCallback(async (): Promise<UserData | null> => {
    if (!session?.accessToken) return null;
    try {
      const updatedUser = await fetchEnrichedProfile(session.accessToken);
      await updateStoredSession(session, updatedUser);
      return updatedUser;
    } catch {
      return user;
    }
  }, [session, fetchEnrichedProfile, updateStoredSession, user]);

  // Initial session restoration on mount
  useEffect(() => {
    let isMounted = true;

    async function restoreSession() {
      try {
        const raw = await storage.getItem(AUTH_STORAGE_KEY);
        if (!raw) {
          if (isMounted) setStatus('unauthenticated');
          return;
        }

        const parsed: StoredSessionPayload = JSON.parse(raw);
        if (!parsed.session?.accessToken) {
          if (isMounted) setStatus('unauthenticated');
          return;
        }

        // Optimistically restore in-memory auth
        apiClient.setAuth({
          token: parsed.session.accessToken,
          role: parsed.user?.role,
          nodeId: parsed.user?.node_id,
          userId: parsed.user?.user_id,
        });

        // Verify with /api/v1/me
        try {
          const verifiedUser = await fetchEnrichedProfile(parsed.session.accessToken);
          if (isMounted) {
            setSession(parsed.session);
            setUser(verifiedUser);
            setStatus('authenticated');
            await updateStoredSession(parsed.session, verifiedUser);
          }
        } catch (verErr: any) {
          // If token expired (401), try one refresh
          if (verErr?.status === 401 || verErr?.code === 'TOKEN_EXPIRED') {
            const newToken = await refreshSessionOnce();
            if (newToken && isMounted) {
              const freshUser = await fetchEnrichedProfile(newToken);
              setUser(freshUser);
              setStatus('authenticated');
              return;
            }
          }
          // If unreachable / network error, retain cached session
          if (isMounted) {
            setSession(parsed.session);
            setUser(parsed.user);
            setStatus('authenticated');
          }
        }
      } catch {
        if (isMounted) setStatus('unauthenticated');
      }
    }

    restoreSession();

    // Register apiClient interceptor handlers
    apiClient.setAuthHandlers({
      onRefresh: refreshSessionOnce,
      onForceLogout: forceLogout,
    });

    return () => {
      isMounted = false;
    };
  }, [fetchEnrichedProfile, refreshSessionOnce, forceLogout, updateStoredSession]);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      setIsLoading(true);
      setError(null);
      const baseUrl = getBackendUrl().replace(/\/+$/, '');

      try {
        const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
          body: JSON.stringify({ email: email.trim(), password }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          const msg =
            errData?.error?.message ||
            errData?.detail ||
            'Invalid credentials or unauthorized access.';
          throw new Error(msg);
        }

        const loginData = await res.json();
        const token = loginData.access_token;
        const refreshToken = loginData.refresh_token || token;

        // Hydrate enriched profile with permissions & node bindings
        const profile = await fetchEnrichedProfile(token);
        const newSession: SessionData = {
          accessToken: token,
          refreshToken,
          expiresAt: Math.floor(Date.now() / 1000) + 3600,
        };

        await updateStoredSession(newSession, profile);
      } catch (err: any) {
        setError(err.message || 'Login failed. Please check your credentials and server status.');
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [fetchEnrichedProfile, updateStoredSession]
  );

  const loginAsDemoRole = useCallback(
    async (role: string): Promise<void> => {
      setIsLoading(true);
      setError(null);
      const baseUrl = getBackendUrl().replace(/\/+$/, '');

      try {
        const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
          body: JSON.stringify({ role: role.toLowerCase() }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(
            errData?.error?.message || errData?.detail || `Failed to sign in as ${role}`
          );
        }

        const loginData = await res.json();
        const token = loginData.access_token;
        const refreshToken = loginData.refresh_token || token;

        const profile = await fetchEnrichedProfile(token);
        const newSession: SessionData = {
          accessToken: token,
          refreshToken,
          expiresAt: Math.floor(Date.now() / 1000) + 3600,
        };

        await updateStoredSession(newSession, profile);
      } catch (err: any) {
        setError(err.message || `Failed to sign in as ${role}`);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [fetchEnrichedProfile, updateStoredSession]
  );

  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      await clearSessionStorage();
      setSession(null);
      setUser(null);
      setStatus('unauthenticated');
      setError(null);
    } finally {
      setIsLoading(false);
    }
  }, [clearSessionStorage]);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({
      status,
      session,
      user,
      error,
      isLoading,
      login,
      loginAsDemoRole,
      logout,
      forceLogout,
      refreshSessionOnce,
      reloadProfile,
      clearError,
    }),
    [
      status,
      session,
      user,
      error,
      isLoading,
      login,
      loginAsDemoRole,
      logout,
      forceLogout,
      refreshSessionOnce,
      reloadProfile,
      clearError,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
