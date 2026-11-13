/**
 * Authentication Context for MediFlux.
 * Manages Supabase Auth session, JWT tokens, active actor profile, and seeded demo user switching.
 */

import React, { createContext, useContext, useEffect, useState } from "react";
import { api, getStoredToken, getStoredUser, setStoredToken, setStoredUser } from "../lib/api";
import type { DemoUser, UserProfile, UserRole } from "../types/api";

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  demoUsers: DemoUser[];
  login: (credentials: { email?: string; password?: string; role?: string }) => Promise<void>;
  loginAsDemoRole: (role: UserRole) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(getStoredUser());
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [loading, setLoading] = useState<boolean>(true);
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);

  // Fetch seeded demo users on initialization
  useEffect(() => {
    let isMounted = true;
    api.auth
      .getDemoUsers()
      .then((users) => {
        if (isMounted && users && users.length > 0) {
          setDemoUsers(users);
        }
      })
      .catch((err) => {
        console.warn("Failed fetching demo users from backend:", err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Validate or restore session
  useEffect(() => {
    let isMounted = true;
    const initializeAuth = async () => {
      const storedToken = getStoredToken();
      if (storedToken) {
        try {
          const profile = await api.auth.getMe();
          if (isMounted) {
            setUser(profile);
            setStoredUser(profile);
          }
        } catch {
          // If token expired, fall back to cached user or clear
          const cached = getStoredUser();
          if (isMounted) setUser(cached);
        }
      }
      if (isMounted) setLoading(false);
    };

    initializeAuth();
    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (credentials: { email?: string; password?: string; role?: string }) => {
    setLoading(true);
    try {
      const res = await api.auth.login(credentials);
      setToken(res.token);
      setUser(res.user);
      setStoredToken(res.token);
      setStoredUser(res.user);
    } finally {
      setLoading(false);
    }
  };

  const loginAsDemoRole = async (role: UserRole) => {
    await login({ role });
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setStoredToken(null);
    setStoredUser(null);
  };

  const refreshProfile = async () => {
    if (!token) return;
    try {
      const profile = await api.auth.getMe();
      setUser(profile);
      setStoredUser(profile);
    } catch (err) {
      console.warn("Failed refreshing profile:", err);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        demoUsers,
        login,
        loginAsDemoRole,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
