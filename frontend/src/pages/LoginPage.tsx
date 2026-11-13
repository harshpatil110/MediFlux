/**
 * Login Page with standard Email/Password authentication and
 * 1-click Seeded Demo Users selector for all 7 supply chain roles.
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Lock,
  Mail,
  RefreshCw,
  Settings,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { StatusBadge } from "../components/shared/StatusBadge";
import { BackendSettingsModal } from "../components/layout/BackendSettingsModal";
import type { UserRole } from "../types/api";

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, loginAsDemoRole, demoUsers } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submittingRole, setSubmittingRole] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    const handleOpenSettings = () => setIsSettingsOpen(true);
    window.addEventListener("mediflux:open-settings", handleOpenSettings);
    return () => window.removeEventListener("mediflux:open-settings", handleOpenSettings);
  }, []);

  const handleStandardLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmittingRole("standard");
    try {
      await login({ email, password });
      navigate("/overview");
    } catch (err: any) {
      setError(err.message || "Authentication failed. Check credentials.");
    } finally {
      setSubmittingRole(null);
    }
  };

  const handleQuickDemoLogin = async (role: UserRole) => {
    setError(null);
    setSubmittingRole(role);
    try {
      await loginAsDemoRole(role);
      navigate("/overview");
    } catch (err: any) {
      setError(err.message || `Failed to sign in as ${role}`);
    } finally {
      setSubmittingRole(null);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] flex flex-col justify-between p-6 md:p-12 font-sans">
      {/* Brand Top Header */}
      <header className="max-w-6xl w-full mx-auto flex items-center justify-between pb-8 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[var(--accent-teal)] text-white flex items-center justify-center font-serif font-black text-xl">
            M
          </div>
          <div>
            <span className="font-serif font-bold text-xl tracking-tight text-[var(--text-primary)] block">
              MEDIFLUX
            </span>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-secondary)]">
              Pharma 4-Tier Autonomous Supply Chain
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] transition-colors text-xs font-mono text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            title="Configure Backend Connection & Test Native Notifications"
          >
            <Settings className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
            <span>Server Settings</span>
          </button>
          <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-secondary)]">
            <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
            <span className="hidden sm:inline">FastAPI v0.1.0 Ready</span>
          </div>
        </div>
      </header>

      {/* Main Content: 2-Column Split */}
      <main className="max-w-6xl w-full mx-auto py-10 grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
        {/* Left Column: Standard Credentials Login */}
        <div className="lg:col-span-5 space-y-6">
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-[var(--text-secondary)] mb-1">
              Supply Chain Access Portal
            </p>
            <h2 className="text-2xl md:text-3xl font-serif font-bold text-[var(--text-primary)] tracking-tight">
              Sign In to MediFlux
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-2 leading-relaxed">
              Authenticate via Supabase Auth or select a seeded demo role to inspect tier-scoped operations.
            </p>
          </div>

          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleStandardLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@mediflux.in"
                  className="w-full pl-9 pr-3 py-2 text-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent-teal)]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3 py-2 text-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent-teal)]"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submittingRole === "standard"}
              className="w-full py-2.5 px-4 text-xs font-medium uppercase tracking-wider bg-[var(--accent-teal)] text-white hover:bg-[var(--accent-teal)]/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {submittingRole === "standard" ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Verifying...
                </>
              ) : (
                <>
                  Authenticate <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>

          {/* Technical Compliance Checklist */}
          <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2 text-xs text-[var(--text-secondary)]">
            <div className="font-semibold text-[var(--text-primary)] flex items-center gap-2 text-xs font-mono">
              <ShieldCheck className="w-4 h-4 text-[var(--accent-teal)]" />
              Production Security Directives
            </div>
            <p className="text-[11px] leading-relaxed">
              Row-Level Security (RLS) restricts database operations strictly to the caller&apos;s node_id and role scopes.
            </p>
          </div>
        </div>

        {/* Right Column: Seeded Demo Users Selector */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
            <div>
              <h3 className="text-sm font-mono uppercase tracking-wider font-semibold text-[var(--text-primary)] flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-[var(--accent-teal)]" />
                Seeded Demo Users (7 Roles)
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                Instant one-click evaluation logins mapped to real Supabase profiles and node topology.
              </p>
            </div>
            <span className="text-[10px] font-mono text-[var(--text-secondary)]">
              {demoUsers.length || 7} Seeded Roles
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {demoUsers.map((demo) => {
              const isLoading = submittingRole === demo.role;
              return (
                <div
                  key={demo.role}
                  className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-[var(--accent-teal)] transition-all flex flex-col justify-between space-y-3 group"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <StatusBadge status="active" label={demo.role} size="sm" />
                      <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                        {demo.allowed_routes?.length || 0} screens
                      </span>
                    </div>

                    <h4 className="font-semibold text-xs text-[var(--text-primary)] group-hover:text-[var(--accent-teal)] transition-colors">
                      {demo.label}
                    </h4>
                    <p className="text-[11px] text-[var(--text-secondary)] line-clamp-2 mt-1">
                      {demo.description}
                    </p>

                    <div className="mt-2.5 pt-2 border-t border-[var(--border-subtle)] text-[10px] font-mono text-[var(--text-secondary)] truncate">
                      Node:{" "}
                      <span className="text-[var(--text-primary)] font-medium">
                        {demo.node_name || "Global Network"}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    disabled={submittingRole !== null}
                    onClick={() => handleQuickDemoLogin(demo.role)}
                    className="w-full py-1.5 px-3 text-xs font-mono font-medium border border-[var(--border-subtle)] bg-[var(--bg-canvas)] hover:bg-[var(--accent-teal)] hover:text-white hover:border-[var(--accent-teal)] text-[var(--text-primary)] transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
                  >
                    {isLoading ? (
                      <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                      <>
                        Sign In as {demo.role.toUpperCase()}
                        <ArrowRight className="w-3 h-3" />
                      </>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="max-w-6xl w-full mx-auto pt-6 border-t border-[var(--border-subtle)] flex flex-col sm:flex-row items-center justify-between text-xs text-[var(--text-secondary)] gap-2">
        <span>© 2026 MediFlux India. Spec-driven Autonomous Supply Chain.</span>
        <div className="flex items-center gap-3 font-mono text-[11px]">
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-[var(--accent-teal)]" /> 7 Roles Seeded
          </span>
          <span>•</span>
          <span>FastAPI + Vite</span>
          <span>•</span>
          <span>Supabase Auth</span>
        </div>
      </footer>

      {/* Backend Settings & Telemetry Modal */}
      <BackendSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
