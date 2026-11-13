/**
 * Developer Platform & MCP Server Hub Screen (/developer)
 *
 * Implements Task 22, Task 23 & Task 27:
 * - Tab 1: Scoped API Key Management (create key modal with show-once plaintext secret, granular scopes, revocation).
 * - Tab 2: Webhooks & Delivery Logs (subscription studio, HMAC-SHA256 test triggers, delivery history with latency).
 * - Tab 3: Interactive Code Snippets & OpenAPI Hub (Swagger UI, ReDoc, cURL/Python/JS tabs interpolating active key).
 * - Tab 4: MCP Server Hub (Task 23 tool registry, Claude/Cursor/Antigravity JSON configs, live tool tester calling /mcp/call).
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Check,
  CheckCircle2,
  Clock,
  Code,
  Copy,
  ExternalLink,
  Globe,
  Key,
  Layers,
  Play,
  RefreshCw,
  Server,
  ShieldCheck,
  Terminal,
  Trash2,
  Webhook,
  Zap,
} from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { DeveloperApiKey, McpToolMetadata, WebhookDeliveryLog } from "../types/api";

const AVAILABLE_SCOPES = [
  { id: "read:inventory", label: "Read Inventory & Stock Balances" },
  { id: "write:events", label: "Submit Retail POS Sales & Supply Events" },
  { id: "read:stream", label: "Subscribe to Real-time SSE Event Stream" },
  { id: "read:audit", label: "Verify Cryptographic Audit Hash Ledger" },
  { id: "use:copilot", label: "Ask Natural-Language Operational Copilot" },
  { id: "manage:adapters", label: "Deploy & Test Legacy System Adapters" },
  { id: "manage:hitl", label: "Authorize Operator Approval Workflows" },
  { id: "*", label: "Superuser Full Platform Access (*)" },
];

const WEBHOOK_EVENT_TYPES = [
  "order.created",
  "shipment.dispatched",
  "batch.quarantined",
  "hitl.created",
  "hitl.decided",
  "module.activated",
  "*",
];

export const DeveloperPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"keys" | "webhooks" | "snippets" | "mcp">("keys");
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<"curl" | "python" | "js">("curl");

  // Show-once created key modal state
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<{ key: string; name: string } | null>(null);

  // New Key Form State
  const [keyName, setKeyName] = useState("");
  const [keyRateLimit, setKeyRateLimit] = useState(100);
  const [keyNodeId, setKeyNodeId] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["read:inventory", "write:events"]);

  // New Webhook Form State
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEvents, setWebhookEvents] = useState<string[]>(["*"]);
  const [webhookSecret, setWebhookSecret] = useState("");

  // MCP Tool Tester State
  const [selectedMcpTool, setSelectedMcpTool] = useState<string>("get_inventory");
  const [mcpArgumentsText, setMcpArgumentsText] = useState<string>('{\n  "product": "Amoxicillin",\n  "limit": 5\n}');
  const [mcpResult, setMcpResult] = useState<any>(null);

  // Selected delivery log inspector
  const [inspectedDelivery, setInspectedDelivery] = useState<WebhookDeliveryLog | null>(null);

  // Queries
  const {
    data: apiKeys = [],
    isLoading: keysLoading,
    refetch: refetchKeys,
  } = useQuery({
    queryKey: ["developer-keys"],
    queryFn: () => api.developer.listKeys(),
  });

  const { data: webhooks = [] } = useQuery({
    queryKey: ["developer-webhooks"],
    queryFn: () => api.developer.listWebhooks(),
  });

  const {
    data: deliveries = [],
    isLoading: deliveriesLoading,
    refetch: refetchDeliveries,
  } = useQuery({
    queryKey: ["developer-deliveries"],
    queryFn: () => api.developer.listDeliveries({ limit: 25 }),
  });

  const {
    data: mcpToolsData,
    isLoading: mcpToolsLoading,
  } = useQuery({
    queryKey: ["developer-mcp-tools"],
    queryFn: () => api.developer.getMcpTools(),
  });

  const mcpTools: McpToolMetadata[] = mcpToolsData?.tools || [];

  // Key Mutation
  const createKeyMutation = useMutation({
    mutationFn: async () => {
      if (!keyName.trim()) throw new Error("Key name is required");
      return await api.developer.createKey({
        name: keyName.trim(),
        scopes: selectedScopes,
        node_id: keyNodeId.trim() || null,
        rate_limit: keyRateLimit,
      });
    },
    onSuccess: (res) => {
      setNewlyCreatedKey({
        key: res.key || res.api_key || "",
        name: res.name,
      });
      setKeyName("");
      setKeyNodeId("");
      queryClient.invalidateQueries({ queryKey: ["developer-keys"] });
    },
  });

  const revokeKeyMutation = useMutation({
    mutationFn: async (keyId: string) => {
      return await api.developer.revokeKey(keyId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer-keys"] });
    },
  });

  // Webhook Mutations
  const createWebhookMutation = useMutation({
    mutationFn: async () => {
      if (!webhookUrl.trim()) throw new Error("Target URL is required");
      return await api.developer.createWebhook({
        url: webhookUrl.trim(),
        events: webhookEvents,
        secret: webhookSecret.trim() || undefined,
      });
    },
    onSuccess: () => {
      setWebhookUrl("");
      setWebhookSecret("");
      queryClient.invalidateQueries({ queryKey: ["developer-webhooks"] });
    },
  });

  const deleteWebhookMutation = useMutation({
    mutationFn: async (id: string) => {
      return await api.developer.deleteWebhook(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer-webhooks"] });
    },
  });

  const testWebhookMutation = useMutation({
    mutationFn: async (subId: string) => {
      return await api.developer.testWebhook(subId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer-deliveries"] });
    },
  });

  // MCP Tool Execution Mutation
  const executeMcpMutation = useMutation({
    mutationFn: async () => {
      let argsObj = {};
      try {
        argsObj = JSON.parse(mcpArgumentsText);
      } catch (e: any) {
        throw new Error(`Invalid JSON arguments: ${e.message}`);
      }
      return await api.developer.callMcpTool({
        tool: selectedMcpTool,
        arguments: argsObj,
        api_key: newlyCreatedKey?.key || undefined,
      });
    },
    onSuccess: (data) => {
      setMcpResult(data);
    },
  });

  // Scope checkbox toggle helper
  const handleToggleScope = (scopeId: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scopeId) ? prev.filter((s) => s !== scopeId) : [...prev, scopeId]
    );
  };

  // Active Key representation for snippet generation
  const activeSecretSnippet = newlyCreatedKey?.key || "mediflux_live_sk_example123456789";

  // Code Snippet generators
  const getCodeSnippet = (lang: "curl" | "python" | "js"): string => {
    if (lang === "curl") {
      return `# 1. Query Real-Time Inventory Balance with Scoped API Key\ncurl -X GET "http://localhost:8000/api/v1/inventory" \\\n  -H "X-API-Key: ${activeSecretSnippet}" \\\n  -H "Accept: application/json"\n\n# 2. Ingest Single-Unit Retail POS Sale with Rx Verification\ncurl -X POST "http://localhost:8000/api/v1/events" \\\n  -H "X-API-Key: ${activeSecretSnippet}" \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "event_type": "retail.sale",\n    "product_id": "p-001-azithromycin",\n    "sku": "MED-AZI-500",\n    "quantity": 1,\n    "prescription_id": "rx-2026-0891",\n    "unit_price": 14.50\n  }'`;
    }
    if (lang === "python") {
      return `import httpx\n\nAPI_KEY = "${activeSecretSnippet}"\nBASE_URL = "http://localhost:8000/api/v1"\n\nheaders = {\n    "X-API-Key": API_KEY,\n    "Accept": "application/json",\n}\n\n# Query inventory\nwith httpx.Client(base_url=BASE_URL, headers=headers) as client:\n    response = client.get("/inventory")\n    print("Stock Balances:", response.json())\n\n    # Trigger POS demand cascade\n    sale_resp = client.post("/events", json={\n        "event_type": "retail.sale",\n        "product_id": "p-001-azithromycin",\n        "sku": "MED-AZI-500",\n        "quantity": 1,\n        "unit_price": 14.50,\n    })\n    print("Cascade Correlation ID:", sale_resp.json().get("correlation_id"))`;
    }
    return `// Node.js / Browser ESM\nconst API_KEY = "${activeSecretSnippet}";\nconst BASE_URL = "http://localhost:8000/api/v1";\n\nasync function queryMediFlux() {\n  // 1. Fetch real-time stock balances\n  const invRes = await fetch(\`\${BASE_URL}/inventory\`, {\n    headers: { "X-API-Key": API_KEY }\n  });\n  console.log("Inventory:", await invRes.json());\n\n  // 2. Dispatch retail demand propagation\n  const saleRes = await fetch(\`\${BASE_URL}/events\`, {\n    method: "POST",\n    headers: {\n      "X-API-Key": API_KEY,\n      "Content-Type": "application/json"\n    },\n    body: JSON.stringify({\n      event_type: "retail.sale",\n      sku: "MED-AZI-500",\n      quantity: 1\n    })\n  });\n  console.log("Propagation Result:", await saleRes.json());\n}\n\nqueryMediFlux();`;
  };

  // Table columns for API keys
  const keyColumns: Column<DeveloperApiKey>[] = [
    {
      key: "name",
      header: "Key Label & Prefix",
      sortable: true,
      render: (row) => (
        <div>
          <span className="font-semibold text-xs text-[var(--text-primary)] flex items-center gap-1.5">
            <Key className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
            {row.name}
          </span>
          <span className="font-mono text-[10px] text-[var(--text-secondary)]">
            Prefix: <code className="text-[var(--text-primary)]">{row.key_prefix}...</code>
          </span>
        </div>
      ),
    },
    {
      key: "scopes",
      header: "Permissions / Scopes",
      render: (row) => (
        <div className="flex flex-wrap gap-1 max-w-xs">
          {row.scopes.map((s) => (
            <span
              key={s}
              className={`px-1.5 py-0.2 text-[9px] font-mono border ${
                s === "*"
                  ? "bg-coral-50 text-coral-800 border-coral-300 dark:bg-coral-950/40 dark:text-coral-200"
                  : "bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-[var(--border-subtle)]"
              }`}
            >
              {s}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: "rate_limit",
      header: "Rate Limit",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)]">
          {row.rate_limit || 100} req/min
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Provisioned",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)]">
          {new Date(row.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: "id",
      header: "Action",
      render: (row) => (
        <button
          type="button"
          disabled={revokeKeyMutation.isPending}
          onClick={(e) => {
            e.stopPropagation();
            if (confirm(`Revoke API key "${row.name}"? This action cannot be undone.`)) {
              revokeKeyMutation.mutate(row.id);
            }
          }}
          className="px-2 py-1 text-[10px] font-mono border border-coral-300 text-coral-700 dark:text-coral-300 hover:bg-coral-50 dark:hover:bg-coral-950/40 flex items-center gap-1 transition-all"
        >
          <Trash2 className="w-3 h-3" /> Revoke
        </button>
      ),
    },
  ];

  // Table columns for Webhook Deliveries
  const deliveryColumns: Column<WebhookDeliveryLog>[] = [
    {
      key: "event_type",
      header: "Event Type",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs font-semibold text-[var(--accent-teal)]">
          {row.event_type}
        </span>
      ),
    },
    {
      key: "status_code",
      header: "Response Code",
      sortable: true,
      render: (row) => {
        const isSuccess = row.status_code >= 200 && row.status_code < 300;
        return (
          <span
            className={`font-mono text-xs font-bold px-1.5 py-0.5 border ${
              isSuccess
                ? "bg-teal-50 text-teal-800 border-teal-300 dark:bg-teal-950/40 dark:text-teal-200"
                : "bg-coral-50 text-coral-800 border-coral-300 dark:bg-coral-950/40 dark:text-coral-200"
            }`}
          >
            {row.status_code || "FAIL"}
          </span>
        );
      },
    },
    {
      key: "target_url",
      header: "Destination URL",
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)] truncate max-w-xs block">
          {row.target_url}
        </span>
      ),
    },
    {
      key: "latency_ms",
      header: "Latency",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-secondary)]">
          {row.latency_ms ? `${row.latency_ms.toFixed(0)} ms` : "< 15 ms"}
        </span>
      ),
    },
    {
      key: "attempted_at",
      header: "Timestamp",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)]">
          {new Date(row.attempted_at).toLocaleTimeString()}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Header & Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Terminal className="w-5 h-5 text-[var(--accent-teal)]" />
            Developer Platform & Model Context Protocol (MCP) Hub
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Provision cryptographically random scoped API keys, inspect HMAC-SHA256 webhooks, and integrate AI IDE agents via official MCP tools.
          </p>
        </div>

        {/* OpenAPI Hub Quick Links */}
        <div className="flex flex-wrap items-center gap-2">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
          >
            <BookOpen className="w-3.5 h-3.5 text-[var(--accent-teal)]" /> Swagger UI
            <ExternalLink className="w-3 h-3 text-[var(--text-secondary)]" />
          </a>

          <a
            href="http://localhost:8000/redoc"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
          >
            <Globe className="w-3.5 h-3.5 text-[var(--accent-teal)]" /> ReDoc
            <ExternalLink className="w-3 h-3 text-[var(--text-secondary)]" />
          </a>
        </div>
      </div>

      {/* 2. Four Main Navigation Tabs */}
      <div className="flex border-b border-[var(--border-subtle)] gap-2 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab("keys")}
          className={`px-4 py-2 text-xs font-mono uppercase tracking-wider font-semibold border-b-2 transition-all flex items-center gap-2 shrink-0 ${
            activeTab === "keys"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)] bg-[var(--bg-surface)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Key className="w-3.5 h-3.5" />
          1. Scoped API Keys ({apiKeys.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("webhooks")}
          className={`px-4 py-2 text-xs font-mono uppercase tracking-wider font-semibold border-b-2 transition-all flex items-center gap-2 shrink-0 ${
            activeTab === "webhooks"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)] bg-[var(--bg-surface)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Webhook className="w-3.5 h-3.5" />
          2. Webhooks & Deliveries ({webhooks.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("snippets")}
          className={`px-4 py-2 text-xs font-mono uppercase tracking-wider font-semibold border-b-2 transition-all flex items-center gap-2 shrink-0 ${
            activeTab === "snippets"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)] bg-[var(--bg-surface)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Code className="w-3.5 h-3.5" />
          3. Code Snippets & OpenAPI
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("mcp")}
          className={`px-4 py-2 text-xs font-mono uppercase tracking-wider font-semibold border-b-2 transition-all flex items-center gap-2 shrink-0 ${
            activeTab === "mcp"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)] bg-[var(--bg-surface)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Server className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
          4. MCP Server Hub ({mcpTools.length} Tools)
        </button>
      </div>

      {/* 3. SHOW-ONCE API KEY NOTIFICATION MODAL */}
      {newlyCreatedKey && (
        <div className="p-4 bg-teal-50 dark:bg-teal-950/60 border-2 border-[var(--accent-teal)] space-y-3 shadow-md animate-in fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-[var(--accent-teal)]" />
              <h4 className="text-xs font-mono uppercase tracking-wider font-bold text-[var(--text-primary)]">
                API Key Provisioned: "{newlyCreatedKey.name}"
              </h4>
            </div>
            <button
              type="button"
              onClick={() => setNewlyCreatedKey(null)}
              className="text-xs font-mono text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            >
              Dismiss ✕
            </button>
          </div>

          <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] flex items-center justify-between gap-3">
            <code className="font-mono text-xs font-bold text-[var(--accent-teal)] break-all select-all">
              {newlyCreatedKey.key}
            </code>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(newlyCreatedKey.key);
                setCopiedKey(true);
                setTimeout(() => setCopiedKey(false), 2000);
              }}
              className="px-3 py-1.5 text-xs font-mono bg-[var(--accent-teal)] text-[var(--bg-surface)] font-semibold flex items-center gap-1 shrink-0 hover:opacity-90 transition-all"
            >
              {copiedKey ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedKey ? "Copied!" : "Copy Key"}
            </button>
          </div>

          <p className="text-[11px] font-mono text-[var(--text-secondary)]">
            ⚠️ <strong>Security Notice:</strong> Copy and store this secret key safely now. For your security, this
            plaintext value will <em>never be displayed again</em> (only the SHA-256 hash is persisted).
          </p>
        </div>
      )}

      {/* 4. TAB 1: Scoped API Keys Management */}
      {activeTab === "keys" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left: Provision New Key Form (5 cols) */}
          <div className="lg:col-span-5 p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
            <div className="border-b border-[var(--border-subtle)] pb-2.5">
              <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                <Key className="w-4 h-4 text-[var(--accent-teal)]" />
                Provision Scoped API Key
              </h3>
              <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                Generate cryptographically secure 256-bit token with fine-grained RBAC scopes.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                  Key Name / Label *
                </label>
                <input
                  type="text"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  placeholder="e.g. Apollo Pharmacy POS Integration"
                  className="w-full px-3 py-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                  Rate Limit (Requests / Minute)
                </label>
                <input
                  type="number"
                  value={keyRateLimit}
                  onChange={(e) => setKeyRateLimit(Number(e.target.value))}
                  min={1}
                  max={10000}
                  className="w-full px-3 py-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                  Node UUID Binding (Optional RLS Restriction)
                </label>
                <input
                  type="text"
                  value={keyNodeId}
                  onChange={(e) => setKeyNodeId(e.target.value)}
                  placeholder="Leave blank for unconstrained admin scope"
                  className="w-full px-3 py-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
                />
              </div>

              {/* Scopes Selector */}
              <div>
                <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1.5">
                  Granular Permissions / Scopes:
                </label>
                <div className="space-y-1.5 max-h-48 overflow-y-auto p-2 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  {AVAILABLE_SCOPES.map((sc) => {
                    const isChecked = selectedScopes.includes(sc.id);
                    return (
                      <label
                        key={sc.id}
                        className="flex items-center gap-2 text-xs font-mono cursor-pointer hover:text-[var(--text-primary)] text-[var(--text-secondary)]"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleScope(sc.id)}
                          className="accent-[var(--accent-teal)]"
                        />
                        <code className="text-[var(--accent-teal)]">{sc.id}</code>
                        <span className="text-[10px] truncate">— {sc.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <button
                type="button"
                disabled={createKeyMutation.isPending || !keyName.trim()}
                onClick={() => createKeyMutation.mutate()}
                className="w-full py-2.5 px-4 bg-[var(--accent-teal)] hover:opacity-90 disabled:opacity-50 text-[var(--bg-surface)] font-mono text-xs uppercase tracking-wider font-semibold flex items-center justify-center gap-2 transition-all"
              >
                {createKeyMutation.isPending ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" /> Provisioning Key...
                  </>
                ) : (
                  <>
                    <Key className="w-4 h-4" /> Provision New Developer Key
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Right: Active Keys Table (7 cols) */}
          <div className="lg:col-span-7 space-y-3">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
              <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-[var(--accent-teal)]" />
                Active Provisioned Keys ({apiKeys.length})
              </h3>
              <button
                type="button"
                onClick={() => refetchKeys()}
                className="text-xs font-mono text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" /> Refresh
              </button>
            </div>

            <DataTable
              data={apiKeys}
              columns={keyColumns}
              keyExtractor={(row) => row.id}
              isLoading={keysLoading}
              searchPlaceholder="Filter key by name, prefix, or scope..."
              searchFilter={(row, q) =>
                row.name.toLowerCase().includes(q) ||
                row.key_prefix.toLowerCase().includes(q) ||
                row.scopes.some((s) => s.toLowerCase().includes(q))
              }
              emptyTitle="No API keys provisioned"
              emptyDescription="Generate a scoped key using the form on the left to start integrating."
              pageSize={6}
            />
          </div>
        </div>
      )}

      {/* 5. TAB 2: Webhooks & Delivery Logs */}
      {activeTab === "webhooks" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left: Register Webhook (5 cols) */}
          <div className="lg:col-span-5 p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
            <div className="border-b border-[var(--border-subtle)] pb-2.5">
              <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                <Webhook className="w-4 h-4 text-[var(--accent-teal)]" />
                Register Outbound Webhook
              </h3>
              <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                Receive signed HMAC-SHA256 HTTP POST notifications when system events fire.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                  Destination HTTPS / HTTP URL *
                </label>
                <input
                  type="url"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                  placeholder="https://client-erp.internal/webhook/mediflux"
                  className="w-full px-3 py-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                  Shared HMAC Secret (Optional, auto-generated if blank)
                </label>
                <input
                  type="text"
                  value={webhookSecret}
                  onChange={(e) => setWebhookSecret(e.target.value)}
                  placeholder="whsec_custom_secret_key"
                  className="w-full px-3 py-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                  Subscribed Event Topics:
                </label>
                <div className="flex flex-wrap gap-1.5 p-2 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  {WEBHOOK_EVENT_TYPES.map((evType) => {
                    const isSelected = webhookEvents.includes(evType);
                    return (
                      <button
                        key={evType}
                        type="button"
                        onClick={() =>
                          setWebhookEvents((prev) =>
                            prev.includes(evType) ? prev.filter((e) => e !== evType) : [...prev, evType]
                          )
                        }
                        className={`px-2 py-0.5 text-xs font-mono border transition-all ${
                          isSelected
                            ? "bg-[var(--accent-teal)] text-[var(--bg-surface)] border-[var(--accent-teal)] font-semibold"
                            : "bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-subtle)]"
                        }`}
                      >
                        {evType}
                      </button>
                    );
                  })}
                </div>
              </div>

              <button
                type="button"
                disabled={createWebhookMutation.isPending || !webhookUrl.trim()}
                onClick={() => createWebhookMutation.mutate()}
                className="w-full py-2.5 px-4 bg-[var(--accent-teal)] hover:opacity-90 disabled:opacity-50 text-[var(--bg-surface)] font-mono text-xs uppercase tracking-wider font-semibold flex items-center justify-center gap-2 transition-all"
              >
                {createWebhookMutation.isPending ? "Subscribing..." : "Subscribe Webhook"}
              </button>
            </div>

            {/* Subscriptions List */}
            <div className="pt-3 border-t border-[var(--border-subtle)] space-y-2">
              <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold">
                Active Subscriptions ({webhooks.length})
              </h4>
              {webhooks.map((sub) => (
                <div
                  key={sub.id}
                  className="p-2.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-1 text-xs font-mono"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[var(--text-primary)] truncate max-w-[200px]">
                      {sub.target_url}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        disabled={testWebhookMutation.isPending}
                        onClick={() => testWebhookMutation.mutate(sub.id)}
                        className="px-2 py-0.5 text-[10px] bg-teal-50 border border-teal-300 text-teal-800 dark:bg-teal-950/40 dark:text-teal-200 hover:bg-teal-100 flex items-center gap-1"
                      >
                        <Play className="w-2.5 h-2.5" /> Test
                      </button>
                      <button
                        type="button"
                        disabled={deleteWebhookMutation.isPending}
                        onClick={() => deleteWebhookMutation.mutate(sub.id)}
                        className="px-1.5 py-0.5 text-[10px] border border-coral-300 text-coral-600 hover:bg-coral-50"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  <div className="text-[10px] text-[var(--text-secondary)]">
                    Events: {sub.event_types.join(", ")}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Deliveries Log & HMAC Inspector (7 cols) */}
          <div className="lg:col-span-7 space-y-3">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
              <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-[var(--accent-teal)]" />
                Recent Webhook Delivery Logs
              </h3>
              <button
                type="button"
                onClick={() => refetchDeliveries()}
                className="text-xs font-mono text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" /> Refresh
              </button>
            </div>

            <DataTable
              data={deliveries}
              columns={deliveryColumns}
              keyExtractor={(row) => row.id}
              isLoading={deliveriesLoading}
              onRowClick={(row) => setInspectedDelivery(row)}
              emptyTitle="No webhook deliveries attempted yet"
              emptyDescription="Click 'Test' on any registered subscription on the left to fire a signed event."
              pageSize={6}
            />

            {inspectedDelivery && (
              <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
                <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-1.5">
                  <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                    Delivery Inspection: {inspectedDelivery.event_type}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--text-secondary)]">
                    HMAC: {inspectedDelivery.hmac_signature ? `${inspectedDelivery.hmac_signature.slice(0, 16)}...` : "SHA256"}
                  </span>
                </div>
                <JsonViewer data={inspectedDelivery} title="Full Webhook Delivery Record" defaultExpanded={false} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* 6. TAB 3: Interactive Code Snippets & OpenAPI Hub */}
      {activeTab === "snippets" && (
        <div className="p-5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-3">
            <div>
              <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Code className="w-4 h-4 text-[var(--accent-teal)]" />
                Interactive Client Integration Snippets
              </h3>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Ready-to-run copyable code blocks with your active credentials interpolated.
              </p>
            </div>

            {/* Language Selector Pills */}
            <div className="flex items-center gap-1 bg-[var(--bg-canvas)] p-1 border border-[var(--border-subtle)]">
              {(["curl", "python", "js"] as const).map((lang) => (
                <button
                  key={lang}
                  type="button"
                  onClick={() => setSelectedLanguage(lang)}
                  className={`px-3 py-1 text-xs font-mono uppercase tracking-wider font-semibold transition-all ${
                    selectedLanguage === lang
                      ? "bg-[var(--accent-teal)] text-[var(--bg-surface)]"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {lang === "js" ? "JavaScript" : lang === "python" ? "Python" : "cURL"}
                </button>
              ))}
            </div>
          </div>

          {/* Code Canvas Container */}
          <div className="relative">
            <pre className="p-4 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] overflow-x-auto leading-relaxed">
              {getCodeSnippet(selectedLanguage)}
            </pre>

            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(getCodeSnippet(selectedLanguage));
                setCopiedSnippet(true);
                setTimeout(() => setCopiedSnippet(false), 2000);
              }}
              className="absolute top-3 right-3 px-3 py-1.5 bg-[var(--bg-surface)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-xs font-mono font-semibold text-[var(--text-primary)] flex items-center gap-1.5 transition-all shadow-xs"
            >
              {copiedSnippet ? <Check className="w-3.5 h-3.5 text-teal-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedSnippet ? "Copied!" : "Copy Code"}
            </button>
          </div>

          <div className="p-3.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] flex items-center justify-between text-xs font-mono text-[var(--text-secondary)]">
            <span>
              Key in use: <code className="text-[var(--accent-teal)]">{activeSecretSnippet.slice(0, 16)}...</code>
            </span>
            <span className="text-[10px]">
              Tip: Provision a new key in Tab 1 to auto-update snippets with your private token.
            </span>
          </div>
        </div>
      )}

      {/* 7. TAB 4: MCP Server Hub (Task 23 Model Context Protocol) */}
      {activeTab === "mcp" && (
        <div className="space-y-6">
          {/* Top Banner explaining MCP Server */}
          <div className="p-4 bg-[var(--bg-surface)] border-l-4 border-l-[var(--accent-teal)] border border-[var(--border-subtle)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase tracking-wider font-bold text-[var(--accent-teal)]">
                  MODEL CONTEXT PROTOCOL (MCP 2.3.0) COMPLIANT SERVER
                </span>
                <span className="px-1.5 py-0.5 text-[9px] font-mono bg-teal-100 text-teal-900 border border-teal-300">
                  7 Tools Registered
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                External coding and reasoning agents (Claude Desktop, Cursor, Antigravity, VS Code) can natively inspect
                network inventory, evaluate stockouts, and dispatch cascade sales via MCP over stdio or HTTP/SSE.
              </p>
            </div>

            <div className="font-mono text-xs text-[var(--text-secondary)] bg-[var(--bg-canvas)] px-3 py-1.5 border border-[var(--border-subtle)]">
              SSE Endpoint: <code>/api/v1/mcp/sse</code>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left: 7 Tools Registry List (6 cols) */}
            <div className="lg:col-span-6 space-y-3">
              <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-[var(--accent-teal)]" />
                Registered MediFlux Domain Tools
              </h3>

              <div className="space-y-2 max-h-[540px] overflow-y-auto">
                {mcpToolsLoading ? (
                  <div className="text-xs font-mono text-[var(--text-secondary)] p-4">Loading tools...</div>
                ) : (
                  mcpTools.map((t) => {
                    const isSelected = selectedMcpTool === t.name;
                    return (
                      <div
                        key={t.name}
                        onClick={() => {
                          setSelectedMcpTool(t.name);
                          setMcpResult(null);
                        }}
                        className={`p-3 bg-[var(--bg-surface)] border cursor-pointer transition-all space-y-1.5 ${
                          isSelected
                            ? "border-[var(--accent-teal)] shadow-xs"
                            : "border-[var(--border-subtle)] hover:border-[var(--text-secondary)]"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <code className="text-xs font-bold text-[var(--accent-teal)]">{t.name}</code>
                          <span className="px-1.5 py-0.2 text-[9px] font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                            Scope: {t.required_scope}
                          </span>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] leading-snug">{t.description}</p>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right: Live Interactive MCP Tool Tester (6 cols) */}
            <div className="lg:col-span-6 p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <div className="border-b border-[var(--border-subtle)] pb-2">
                <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                  <Play className="w-4 h-4 text-[var(--accent-teal)]" />
                  Live MCP Tool Tester (POST /api/v1/mcp/call)
                </h3>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                  Execute selected MCP tool protected by token bucket rate limiter and scope enforcement.
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                    Selected Tool Name:
                  </label>
                  <input
                    type="text"
                    value={selectedMcpTool}
                    readOnly
                    className="w-full px-3 py-1.5 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--accent-teal)] font-bold"
                  />
                </div>

                <div>
                  <label className="text-xs font-mono text-[var(--text-secondary)] block mb-1">
                    Arguments (JSON Object):
                  </label>
                  <textarea
                    rows={4}
                    value={mcpArgumentsText}
                    onChange={(e) => setMcpArgumentsText(e.target.value)}
                    className="w-full p-2.5 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
                  />
                </div>

                <button
                  type="button"
                  disabled={executeMcpMutation.isPending}
                  onClick={() => executeMcpMutation.mutate()}
                  className="w-full py-2.5 bg-[var(--accent-teal)] hover:opacity-90 disabled:opacity-50 text-[var(--bg-surface)] font-mono text-xs uppercase tracking-wider font-semibold flex items-center justify-center gap-2 transition-all"
                >
                  {executeMcpMutation.isPending ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" /> Executing Tool Call...
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" /> Run Tool: {selectedMcpTool}()
                    </>
                  )}
                </button>

                {executeMcpMutation.isError && (
                  <div className="p-2.5 text-xs font-mono bg-coral-50 border border-coral-200 text-coral-800 dark:bg-coral-950/40 dark:text-coral-200">
                    Execution Error: {(executeMcpMutation.error as any)?.message || "Failed to call MCP tool."}
                  </div>
                )}

                {/* Structured Result Viewer */}
                {mcpResult && (
                  <div className="space-y-1.5 pt-2 border-t border-[var(--border-subtle)]">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)] block">
                      MCP Output Response:
                    </span>
                    <JsonViewer data={mcpResult} title={`Output from ${selectedMcpTool}`} defaultExpanded={true} />
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Client JSON Configurations Box (Claude, Cursor, Antigravity) */}
          <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
            <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
              Ready-to-Paste Client Configuration (Claude Desktop / Cursor / Antigravity)
            </h4>

            <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] overflow-x-auto">
              <pre>{`{
  "mcpServers": {
    "mediflux": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "env": {
        "MEDIFLUX_API_KEY": "${activeSecretSnippet}"
      }
    }
  }
}`}</pre>
            </div>
            <p className="text-[11px] font-mono text-[var(--text-secondary)]">
              Paste this block into <code>~/AppData/Roaming/Claude/claude_desktop_config.json</code> or your Cursor MCP settings.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
