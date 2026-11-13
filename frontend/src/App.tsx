/**
 * MediFlux Frontend Application Root.
 * Configures QueryClient, AuthProvider, ThemeProvider, and React Router routes.
 */

import { useEffect } from "react";
import { BrowserRouter, HashRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { CascadePage } from "./pages/CascadePage";
import { AgentsPage } from "./pages/AgentsPage";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { AdapterForgePage } from "./pages/AdapterForgePage";
import { RegulatoryLabPage } from "./pages/RegulatoryLabPage";
import { PrescriptionsPage } from "./pages/PrescriptionsPage";
import { ColdChainPage } from "./pages/ColdChainPage";
import { AuditPage } from "./pages/AuditPage";
import { CopilotPage } from "./pages/CopilotPage";
import { DeveloperPage } from "./pages/DeveloperPage";
import { NAVIGATION_ITEMS } from "./config/navigation";
import { useDesktopNotifications } from "./hooks/useDesktopNotifications";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 10000,
    },
  },
});

// Use HashRouter for packaged desktop environments running on file:// or desktop shells;
// use BrowserRouter for standard web hosting.
const isFileProtocol = typeof window !== "undefined" && (
  window.location.protocol === "file:" ||
  Boolean((window as any).medifluxDesktop?.isDesktop)
);
const RouterComponent = isFileProtocol ? HashRouter : BrowserRouter;

/**
 * Global bridge listener to handle system tray / app menu navigation
 * and desktop event dispatches.
 */
function DesktopBridgeListener() {
  const navigate = useNavigate();
  // Automatically activate desktop notification listener for HITL & cold-chain breaches
  useDesktopNotifications();

  useEffect(() => {
    const desktop = (window as any).medifluxDesktop;
    if (!desktop) return;

    if (desktop.onNavigate) {
      desktop.onNavigate((targetRoute: string) => {
        if (targetRoute) {
          navigate(targetRoute);
        }
      });
    }

    if (desktop.onOpenSettings) {
      desktop.onOpenSettings(() => {
        window.dispatchEvent(new CustomEvent("mediflux:open-settings"));
      });
    }
  }, [navigate]);

  return null;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <RouterComponent>
            <DesktopBridgeListener />
            <Routes>
              {/* Public Authentication Route */}
              <Route path="/login" element={<LoginPage />} />

              {/* Protected 11 Operational Routes */}
              <Route
                path="/"
                element={<Navigate to="/overview" replace />}
              />

              <Route
                path="/overview"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "overview")?.allowedRoles}>
                    <AppShell>
                      <OverviewPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/cascade"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "cascade")?.allowedRoles}>
                    <AppShell>
                      <CascadePage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/agents"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "agents")?.allowedRoles}>
                    <AppShell>
                      <AgentsPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/approvals"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "approvals")?.allowedRoles}>
                    <AppShell>
                      <ApprovalsPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/adapter-forge"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "adapter-forge")?.allowedRoles}>
                    <AppShell>
                      <AdapterForgePage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/regulatory-lab"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "regulatory-lab")?.allowedRoles}>
                    <AppShell>
                      <RegulatoryLabPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/prescriptions"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "prescriptions")?.allowedRoles}>
                    <AppShell>
                      <PrescriptionsPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/cold-chain"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "cold-chain")?.allowedRoles}>
                    <AppShell>
                      <ColdChainPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/audit"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "audit")?.allowedRoles}>
                    <AppShell>
                      <AuditPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/copilot"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "copilot")?.allowedRoles}>
                    <AppShell>
                      <CopilotPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              <Route
                path="/developer"
                element={
                  <ProtectedRoute allowedRoles={NAVIGATION_ITEMS.find((n) => n.id === "developer")?.allowedRoles}>
                    <AppShell>
                      <DeveloperPage />
                    </AppShell>
                  </ProtectedRoute>
                }
              />

              {/* Catch-all redirect to overview */}
              <Route path="*" element={<Navigate to="/overview" replace />} />
            </Routes>
          </RouterComponent>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
