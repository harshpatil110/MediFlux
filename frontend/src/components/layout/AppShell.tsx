/**
 * App Shell Layout implementing Warm Editorial Minimalism per design.md.
 * Features role-filtered sidebar, top header with node topology badges, SSE stream pill, and theme toggle.
 */

import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  LogOut,
  Moon,
  Radio,
  Settings,
  Sun,
  UserCheck,
  Building2,
  Menu,
  X,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import { getFilteredNavigation } from "../../config/navigation";
import { StatusBadge } from "../shared/StatusBadge";
import { SseDebugPanel } from "./SseDebugPanel";
import { BackendSettingsModal } from "./BackendSettingsModal";
import { useEventStream } from "../../hooks/useEventStream";

interface AppShellProps {
  children?: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const [isSseDebugOpen, setIsSseDebugOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    const handleOpenSettings = () => setIsSettingsOpen(true);
    window.addEventListener("mediflux:open-settings", handleOpenSettings);
    return () => window.removeEventListener("mediflux:open-settings", handleOpenSettings);
  }, []);

  // Background stream for live status pill in top header
  const { events, connectionState } = useEventStream({
    topics: ["*"],
    enabled: true,
  });

  const navItems = getFilteredNavigation(user?.role);

  const activeNav = navItems.find((item) => item.path === location.pathname);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] flex font-sans antialiased">
      {/* Mobile Sidebar Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-64 bg-[var(--bg-surface)] border-r border-[var(--border-subtle)] flex flex-col transition-transform duration-200 ease-in-out ${
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Brand Banner */}
        <div className="h-16 px-6 border-b border-[var(--border-subtle)] flex items-center justify-between">
          <Link to="/overview" className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-[var(--accent-teal)] text-white flex items-center justify-center font-serif font-black text-lg">
              M
            </div>
            <div>
              <span className="font-serif font-bold text-base tracking-tight text-[var(--text-primary)] block leading-none">
                MEDIFLUX
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-secondary)]">
                Pharma 4-Tier OS
              </span>
            </div>
          </Link>
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen(false)}
            className="lg:hidden p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Role Notice */}
        <div className="px-5 py-2.5 bg-[var(--bg-canvas)]/50 border-b border-[var(--border-subtle)] flex items-center justify-between text-xs">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Active Role:
          </span>
          <StatusBadge status="active" label={user?.role || "GUEST"} size="sm" />
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.id}
                to={item.path}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center gap-3 px-3 py-2 text-xs font-medium border transition-colors ${
                  isActive
                    ? "bg-[var(--bg-canvas)] border-[var(--border-subtle)] text-[var(--accent-teal)] font-semibold shadow-sm"
                    : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-canvas)]/60"
                }`}
              >
                <Icon
                  className={`w-4 h-4 ${
                    isActive ? "text-[var(--accent-teal)]" : "text-[var(--text-secondary)]"
                  }`}
                />
                <span className="truncate">{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Pill & Quick Actions */}
        <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-canvas)]/40 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex items-center justify-center text-[var(--text-primary)]">
              <UserCheck className="w-4 h-4 text-[var(--accent-teal)]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-[var(--text-primary)] truncate">
                {user?.full_name || "Demo User"}
              </p>
              <p className="text-[10px] font-mono text-[var(--text-secondary)] truncate">
                {user?.email || "user@mediflux.in"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Link
              to="/login"
              className="flex-1 py-1 px-2 text-[11px] text-center font-mono border border-[var(--border-subtle)] hover:bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              Switch Role
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              className="p-1 border border-[var(--border-subtle)] hover:bg-rose-500/10 text-[var(--text-secondary)] hover:text-rose-600 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="h-16 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-6 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="lg:hidden p-1.5 border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            >
              <Menu className="w-4 h-4" />
            </button>

            <div>
              <h1 className="font-serif font-bold text-lg text-[var(--text-primary)] leading-tight">
                {activeNav?.name || "Dashboard"}
              </h1>
              <span className="text-[10px] font-mono text-[var(--text-secondary)] hidden sm:inline">
                {activeNav?.description || "MediFlux Autonomous Supply Chain Operations"}
              </span>
            </div>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-3">
            {/* Node Topology Badge */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono">
              <Building2 className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
              <span className="text-[var(--text-primary)] font-semibold truncate max-w-[200px]">
                {user?.node_name || (user?.role === "admin" ? "All Network Nodes" : "Network Node")}
              </span>
              {user?.region && (
                <span className="text-[10px] text-[var(--text-secondary)] border-l border-[var(--border-subtle)] pl-2">
                  {user.region}
                </span>
              )}
            </div>

            {/* Live SSE Stream Status Pill */}
            <button
              type="button"
              onClick={() => setIsSseDebugOpen(true)}
              className="flex items-center gap-2 px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] transition-colors text-xs font-mono"
              title="Open Live SSE Stream Telemetry Panel"
            >
              <Radio
                className={`w-3.5 h-3.5 ${
                  connectionState === "connected"
                    ? "text-teal-600 dark:text-teal-400 animate-pulse"
                    : "text-amber-600"
                }`}
              />
              <span className="text-[11px] text-[var(--text-primary)] hidden sm:inline">
                SSE: {connectionState}
              </span>
              <span className="px-1 py-0.2 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[10px] text-[var(--text-secondary)]">
                {events.length}
              </span>
            </button>

            {/* Backend Connection Settings Pill */}
            <button
              type="button"
              onClick={() => setIsSettingsOpen(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] transition-colors text-xs font-mono"
              title="Configure Backend Connection & Test Native Notifications"
            >
              <Settings className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
              <span className="text-[11px] text-[var(--text-primary)] hidden sm:inline">
                Backend
              </span>
            </button>

            {/* Theme Toggle Button */}
            <button
              type="button"
              onClick={toggleTheme}
              className="p-1.5 border border-[var(--border-subtle)] bg-[var(--bg-canvas)] hover:bg-[var(--border-subtle)] text-[var(--text-primary)] transition-colors"
              title={`Switch to ${theme === "light" ? "Dark" : "Light"} mode`}
            >
              {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
            </button>
          </div>
        </header>

        {/* Page Content Body */}
        <main className="flex-1 p-6 md:p-8 overflow-y-auto">{children}</main>
      </div>

      {/* Docked Live SSE Debug Panel */}
      <SseDebugPanel
        isOpen={isSseDebugOpen}
        onClose={() => setIsSseDebugOpen(false)}
      />

      {/* Backend Settings & Telemetry Modal */}
      <BackendSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
