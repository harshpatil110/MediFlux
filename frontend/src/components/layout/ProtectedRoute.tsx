/**
 * Protected Route wrapper enforcing authentication and role-based access.
 */

import React from "react";
import { Navigate, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import type { UserRole } from "../../types/api";
import { ShieldAlert, ArrowLeft } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-canvas)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--border-subtle)] border-t-[var(--accent-teal)] rounded-none animate-spin" />
          <span className="text-xs font-mono uppercase tracking-widest text-[var(--text-secondary)]">
            Authenticating Session...
          </span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role) && user.role !== "admin") {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-6">
        <div className="max-w-md w-full p-8 editorial-card bg-[var(--bg-surface)] text-center">
          <div className="w-12 h-12 mx-auto mb-4 bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-600 dark:text-amber-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)] mb-2">
            Access Restricted
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mb-6 leading-relaxed">
            Your current assigned role (
            <span className="font-mono font-semibold uppercase text-[var(--text-primary)]">
              {user.role}
            </span>
            ) does not have access permissions for this operational module.
          </p>
          <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs text-left mb-6 font-mono">
            <span className="text-[var(--text-secondary)] block mb-1">Permitted Roles:</span>
            <div className="flex flex-wrap gap-1.5">
              {allowedRoles.map((r) => (
                <span
                  key={r}
                  className="px-1.5 py-0.5 uppercase text-[10px] bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
                >
                  {r}
                </span>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-center gap-3">
            <Link
              to="/overview"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium bg-[var(--bg-canvas)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] transition-colors text-[var(--text-primary)]"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Return to Overview
            </Link>
            <Link
              to="/login"
              className="px-4 py-2 text-xs font-medium bg-[var(--accent-teal)] text-white hover:bg-[var(--accent-teal)]/90 transition-colors"
            >
              Switch Role
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
