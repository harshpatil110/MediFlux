/**
 * Central Navigation and RBAC Route Access Matrix for MediFlux.
 * Strictly implements the 11 operational routes and their role permissions.
 */

import {
  Activity,
  Bot,
  Boxes,
  CheckSquare,
  Code2,
  FileCheck2,
  FileText,
  LayoutDashboard,
  ScrollText,
  Sparkles,
  Thermometer,
} from "lucide-react";
import type { ComponentType } from "react";
import type { UserRole } from "../types/api";

export interface NavigationItem {
  id: string;
  name: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
  allowedRoles: UserRole[];
  description: string;
}

export const NAVIGATION_ITEMS: NavigationItem[] = [
  {
    id: "overview",
    name: "Overview",
    path: "/overview",
    icon: LayoutDashboard,
    allowedRoles: [
      "admin",
      "regulator",
      "manufacturer",
      "distributor",
      "stockist",
      "pharmacy",
      "developer",
    ],
    description: "Network telemetry, KPIs, topological nodes, and system health.",
  },
  {
    id: "cascade",
    name: "Demand Cascade",
    path: "/cascade",
    icon: Activity,
    allowedRoles: [
      "admin",
      "regulator",
      "manufacturer",
      "distributor",
      "stockist",
      "pharmacy",
    ],
    description: "Single-unit POS demand propagation and multi-tier cascade traces.",
  },
  {
    id: "agents",
    name: "AI Agents",
    path: "/agents",
    icon: Bot,
    allowedRoles: ["admin", "manufacturer", "distributor", "stockist", "developer"],
    description: "Autonomous supply chain agent graph executions and LLM telemetry.",
  },
  {
    id: "approvals",
    name: "HITL Approvals",
    path: "/approvals",
    icon: CheckSquare,
    allowedRoles: [
      "admin",
      "regulator",
      "manufacturer",
      "distributor",
      "stockist",
      "pharmacy",
    ],
    description: "Human-in-the-Loop decision queues, timeout guards, and approvals.",
  },
  {
    id: "adapter-forge",
    name: "Adapter Forge",
    path: "/adapter-forge",
    icon: Boxes,
    allowedRoles: ["admin", "manufacturer", "pharmacy", "developer"],
    description: "Self-evolving legacy ERP translators and code generation sandbox.",
  },
  {
    id: "regulatory-lab",
    name: "Regulatory Lab",
    path: "/regulatory-lab",
    icon: FileCheck2,
    allowedRoles: ["admin", "regulator"],
    description: "CDSCO notification parsing, compliance mutations, and staging hot-swaps.",
  },
  {
    id: "prescriptions",
    name: "Prescriptions",
    path: "/prescriptions",
    icon: FileText,
    allowedRoles: ["admin", "regulator", "pharmacy"],
    description: "Sovereign multimodal prescription scanning and Schedule H ledger.",
  },
  {
    id: "cold-chain",
    name: "Cold Chain",
    path: "/cold-chain",
    icon: Thermometer,
    allowedRoles: [
      "admin",
      "regulator",
      "manufacturer",
      "distributor",
      "stockist",
      "pharmacy",
    ],
    description: "IoT environmental sensors, Arrhenius degradation, and batch quarantines.",
  },
  {
    id: "audit",
    name: "Audit Ledger",
    path: "/audit",
    icon: ScrollText,
    allowedRoles: ["admin", "regulator", "developer"],
    description: "Tamper-evident, hash-chained immutable cryptographic audit trail.",
  },
  {
    id: "copilot",
    name: "Network Copilot",
    path: "/copilot",
    icon: Sparkles,
    allowedRoles: [
      "admin",
      "regulator",
      "manufacturer",
      "distributor",
      "stockist",
      "pharmacy",
      "developer",
    ],
    description: "RLS-scoped conversational AI agent with grounded supply chain citations.",
  },
  {
    id: "developer",
    name: "Developer",
    path: "/developer",
    icon: Code2,
    allowedRoles: ["admin", "developer"],
    description: "API keys, HMAC webhooks, rate limiting, and system endpoints.",
  },
];

export function isRouteAllowed(path: string, role: UserRole | undefined): boolean {
  if (!role) return false;
  if (role === "admin") return true;
  const item = NAVIGATION_ITEMS.find((nav) => nav.path === path);
  if (!item) return true;
  return item.allowedRoles.includes(role);
}

export function getFilteredNavigation(role: UserRole | undefined): NavigationItem[] {
  if (!role) return [];
  if (role === "admin") return NAVIGATION_ITEMS;
  return NAVIGATION_ITEMS.filter((item) => item.allowedRoles.includes(role));
}
