/**
 * Unified Typed API Client for MediFlux FastAPI Backend.
 * Automatically injects active Supabase session JWT, actor headers, and handles domain responses.
 */

import { API_BASE_URL } from "../config/env";
import type {
  Adapter,
  AgentMetrics,
  AgentRun,
  ApiKey,
  AuditLedgerEntry,
  CascadeSummary,
  CascadeTrace,
  ColdChainBatch,
  ComplianceLog,
  CopilotQueryResponse,
  DemoUser,
  HitlTask,
  InventoryItem,
  NetworkNode,
  OverviewKpis,
  Product,
  RegulatoryNotification,
  SearchResult,
  SystemEvent,
  UserProfile,
  WebhookSubscription,
} from "../types/api";

const TOKEN_STORAGE_KEY = "mediflux_token";
const USER_STORAGE_KEY = "mediflux_user";

export function getStoredToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(TOKEN_STORAGE_KEY) : null;
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function getStoredUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserProfile;
  } catch {
    return null;
  }
}

export function setStoredUser(user: UserProfile | null): void {
  if (typeof window === "undefined") return;
  if (user) {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_STORAGE_KEY);
  }
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Core HTTP request handler attaching auth and actor headers.
 */
export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const user = getStoredUser();

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (user) {
    if (user.role) headers["X-User-Role"] = user.role;
    if (user.node_id) headers["X-Node-Id"] = user.node_id;
    if (user.user_id) headers["X-User-Id"] = user.user_id;
    if (user.region) headers["X-User-Region"] = user.region;
  }

  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${API_BASE_URL}${cleanPath}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errorData: any = null;
    try {
      errorData = await response.json();
      if (errorData?.detail) {
        errorDetail = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
      }
    } catch {
      // response is not JSON
    }
    throw new ApiError(errorDetail, response.status, errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  // --------------------------------------------------------------------------
  // Authentication & Demo Users
  // --------------------------------------------------------------------------
  auth: {
    getDemoUsers: () => apiRequest<DemoUser[]>("/api/v1/auth/demo-users"),
    login: (credentials: { email?: string; password?: string; role?: string }) =>
      apiRequest<{ token: string; user: UserProfile }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
      }),
    getMe: () => apiRequest<UserProfile>("/api/v1/auth/me"),
  },

  // --------------------------------------------------------------------------
  // Nodes, Products, Inventory
  // --------------------------------------------------------------------------
  nodes: {
    list: (params?: { tier?: string; region?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.tier) q.set("tier", params.tier);
      if (params?.region) q.set("region", params.region);
      if (params?.limit) q.set("limit", String(params.limit));
      const qs = q.toString() ? `?${q.toString()}` : "";
      return apiRequest<{ items?: NetworkNode[]; total?: number } | NetworkNode[]>(`/api/v1/nodes${qs}`).then((res) => {
        if (Array.isArray(res)) return res;
        return res.items || [];
      });
    },
  },

  products: {
    list: (params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return apiRequest<{ items?: Product[]; total?: number } | Product[]>(`/api/v1/products${qs}`).then((res) => {
        if (Array.isArray(res)) return res;
        return res.items || [];
      });
    },
  },

  inventory: {
    list: (params?: { node_id?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.node_id) q.set("node_id", params.node_id);
      if (params?.limit) q.set("limit", String(params.limit));
      const qs = q.toString() ? `?${q.toString()}` : "";
      return apiRequest<{ items?: InventoryItem[]; total?: number } | InventoryItem[]>(`/api/v1/inventory${qs}`).then((res) => {
        if (Array.isArray(res)) return res;
        return res.items || [];
      });
    },
  },

  // --------------------------------------------------------------------------
  // Events & Demand Cascade
  // --------------------------------------------------------------------------
  events: {
    list: (params?: { topic?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.topic) q.set("topic", params.topic);
      if (params?.limit) q.set("limit", String(params.limit));
      const qs = q.toString() ? `?${q.toString()}` : "";
      return apiRequest<SystemEvent[]>(`/api/v1/events${qs}`);
    },
    postEvent: (payload: Record<string, any>) =>
      apiRequest<{ status: string; event_id: string; correlation_id?: string }>("/api/v1/events", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // --------------------------------------------------------------------------
  // Simulator & Demand Cascade
  // --------------------------------------------------------------------------
  simulator: {
    triggerPos: (payload: {
      mode: "single" | "steady" | "burst" | "stockout";
      product_id?: string;
      pharmacy_id?: string;
      quantity?: number;
    }) =>
      apiRequest<{
        correlation_id: string;
        mode: string;
        events_created: number;
        cascade: CascadeTrace;
      }>("/api/v1/simulator/pos", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  cascade: {
    list: (limit?: number) => {
      const qs = limit ? `?limit=${limit}` : "";
      return apiRequest<CascadeSummary[]>(`/api/v1/cascade${qs}`);
    },
    getTrace: (correlationId: string) =>
      apiRequest<CascadeTrace>(`/api/v1/cascade/${correlationId}`),
    trigger: (payload: {
      mode?: "single" | "steady" | "burst" | "stockout";
      product_id?: string;
      node_id?: string;
      quantity?: number;
    }) =>
      apiRequest<{
        correlation_id: string;
        mode: string;
        events_created: number;
        cascade: CascadeTrace;
      }>("/api/v1/cascade/trigger", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // --------------------------------------------------------------------------
  // Agents & Graph Traces
  // --------------------------------------------------------------------------
  agents: {
    listRuns: (params?: {
      graph?: string;
      agent?: string;
      status?: string;
      correlation_id?: string;
      limit?: number;
    }) => {
      const q = new URLSearchParams();
      if (params?.graph) q.set("graph", params.graph);
      if (params?.agent) q.set("agent", params.agent);
      if (params?.status) q.set("status", params.status);
      if (params?.correlation_id) q.set("correlation_id", params.correlation_id);
      if (params?.limit) q.set("limit", String(params.limit));
      const qs = q.toString() ? `?${q.toString()}` : "";
      return apiRequest<AgentRun[]>(`/api/v1/agents/runs${qs}`);
    },
    getMetrics: () => apiRequest<AgentMetrics>("/api/v1/agents/metrics"),
  },

  // --------------------------------------------------------------------------
  // Human-in-the-Loop (HITL) Approvals
  // --------------------------------------------------------------------------
  hitl: {
    listTasks: (params?: { status?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set("status", params.status);
      if (params?.limit) q.set("limit", String(params.limit));
      const qs = q.toString() ? `?${q.toString()}` : "";
      return apiRequest<HitlTask[]>(`/api/v1/hitl/tasks${qs}`);
    },
    getTask: (taskId: string) => apiRequest<HitlTask>(`/api/v1/hitl/tasks/${taskId}`),
    decide: (taskId: string, decision: { decision: "approved" | "rejected"; reason?: string }) =>
      apiRequest<{ status: string; task_id: string }>(`/api/v1/hitl/tasks/${taskId}/decide`, {
        method: "POST",
        body: JSON.stringify(decision),
      }),
  },

  // --------------------------------------------------------------------------
  // Adapters & Regulatory Lab
  // --------------------------------------------------------------------------
  adapters: {
    list: () => apiRequest<Adapter[]>("/api/v1/adapters"),
  },

  regulatory: {
    listNotifications: () => apiRequest<RegulatoryNotification[]>("/api/v1/regulatory/notifications"),
  },

  // --------------------------------------------------------------------------
  // Prescriptions & Compliance
  // --------------------------------------------------------------------------
  compliance: {
    listLogs: (params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return apiRequest<ComplianceLog[]>(`/api/v1/compliance/logs${qs}`);
    },
  },

  // --------------------------------------------------------------------------
  // Cold Chain Telemetry
  // --------------------------------------------------------------------------
  coldchain: {
    listBatches: () => apiRequest<ColdChainBatch[]>("/api/v1/coldchain/batches"),
  },

  // --------------------------------------------------------------------------
  // Cryptographic Audit Ledger
  // --------------------------------------------------------------------------
  audit: {
    listLedger: (params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return apiRequest<AuditLedgerEntry[]>(`/api/v1/audit${qs}`);
    },
    verifyChain: () =>
      apiRequest<{ valid: boolean; verified_count: number; message: string }>("/api/v1/audit/verify"),
  },

  // --------------------------------------------------------------------------
  // Network Copilot & Semantic Search
  // --------------------------------------------------------------------------
  copilot: {
    query: (queryText: string) =>
      apiRequest<CopilotQueryResponse>("/api/v1/copilot/query", {
        method: "POST",
        body: JSON.stringify({ query: queryText }),
      }),
    search: (q: string) => apiRequest<SearchResult[]>(`/api/v1/search?q=${encodeURIComponent(q)}`),
  },

  // --------------------------------------------------------------------------
  // Developer Platform
  // --------------------------------------------------------------------------
  developer: {
    listKeys: () => apiRequest<ApiKey[]>("/api/v1/developer/keys"),
    listWebhooks: () => apiRequest<WebhookSubscription[]>("/api/v1/developer/webhooks"),
  },

  // --------------------------------------------------------------------------
  // Overview Aggregations
  // --------------------------------------------------------------------------
  overview: {
    getKpis: () => apiRequest<OverviewKpis>("/api/v1/overview/kpis"),
  },
};
