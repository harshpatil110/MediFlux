/**
 * Developer Platform Page (/developer)
 * API keys management, HMAC-SHA256 webhooks, and rate limit telemetry.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Key, RefreshCw, Webhook } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import type { ApiKey, WebhookSubscription } from "../types/api";

export const DeveloperPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"keys" | "webhooks">("keys");

  const {
    data: apiKeys = [],
    isLoading: keysLoading,
    refetch: refetchKeys,
  } = useQuery({
    queryKey: ["developer-keys"],
    queryFn: () => api.developer.listKeys(),
  });

  const {
    data: webhooks = [],
    isLoading: webhooksLoading,
    refetch: refetchWebhooks,
  } = useQuery({
    queryKey: ["developer-webhooks"],
    queryFn: () => api.developer.listWebhooks(),
  });

  const keyColumns: Column<ApiKey>[] = [
    {
      key: "key_id",
      header: "Key Identifier",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--accent-teal)] font-semibold flex items-center gap-1.5">
          <Key className="w-3.5 h-3.5" />
          {row.key_id}
        </span>
      ),
    },
    {
      key: "role",
      header: "Scoped Role",
      render: (row) => <StatusBadge status="active" label={row.role} size="sm" />,
    },
    {
      key: "scopes",
      header: "Granted Scopes",
      render: (row) => (
        <div className="flex flex-wrap gap-1 font-mono text-[10px]">
          {row.scopes?.map((s) => (
            <span key={s} className="px-1 py-0.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
              {s}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: "rate_limit_per_minute",
      header: "Rate Limit",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-secondary)]">
          {row.rate_limit_per_minute} req/min
        </span>
      ),
    },
    {
      key: "is_active",
      header: "Status",
      render: (row) => (
        <StatusBadge
          status={row.is_active ? "active" : "archived"}
          label={row.is_active ? "Active" : "Revoked"}
          size="sm"
        />
      ),
    },
  ];

  const webhookColumns: Column<WebhookSubscription>[] = [
    {
      key: "target_url",
      header: "Target Endpoint URL",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)] font-medium truncate block max-w-sm">
          {row.target_url}
        </span>
      ),
    },
    {
      key: "event_types",
      header: "Subscribed Topics",
      render: (row) => (
        <div className="flex flex-wrap gap-1 font-mono text-[10px]">
          {row.event_types?.map((evt) => (
            <span key={evt} className="px-1 py-0.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
              {evt}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: "consecutive_failures",
      header: "Failure Count",
      render: (row) => (
        <span
          className={`font-mono text-xs ${
            row.consecutive_failures > 0 ? "text-rose-600 font-bold" : "text-[var(--text-secondary)]"
          }`}
        >
          {row.consecutive_failures} fails
        </span>
      ),
    },
    {
      key: "is_active",
      header: "Status",
      render: (row) => (
        <StatusBadge
          status={row.is_active ? "active" : "archived"}
          label={row.is_active ? "Active" : "Disabled"}
          size="sm"
        />
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            Developer Platform & Integration Engine
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Scoped SHA-256 API key authentication, Token-Bucket rate limits, and HMAC-SHA256 signed webhooks.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            refetchKeys();
            refetchWebhooks();
          }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Platform
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--border-subtle)] gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("keys")}
          className={`px-4 py-2 text-xs font-mono font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "keys"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Key className="w-3.5 h-3.5" /> Scoped API Keys ({apiKeys.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("webhooks")}
          className={`px-4 py-2 text-xs font-mono font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "webhooks"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Webhook className="w-3.5 h-3.5" /> Outbound Webhooks ({webhooks.length})
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "keys" ? (
        <DataTable
          data={apiKeys}
          columns={keyColumns}
          keyExtractor={(row) => row.key_id}
          isLoading={keysLoading}
          searchPlaceholder="Search key identifier, role, or scope..."
          searchFilter={(row, q) =>
            row.key_id.toLowerCase().includes(q) ||
            row.role.toLowerCase().includes(q) ||
            row.scopes?.some((s) => s.toLowerCase().includes(q))
          }
          emptyTitle="No API keys registered"
          emptyDescription="Developer API keys will be displayed here."
          pageSize={8}
        />
      ) : (
        <DataTable
          data={webhooks}
          columns={webhookColumns}
          keyExtractor={(row) => row.id}
          isLoading={webhooksLoading}
          searchPlaceholder="Search target URL or subscribed topic..."
          searchFilter={(row, q) =>
            row.target_url.toLowerCase().includes(q) ||
            row.event_types?.some((e) => e.toLowerCase().includes(q))
          }
          emptyTitle="No webhook subscriptions"
          emptyDescription="Outbound HMAC webhooks will be displayed here."
          pageSize={8}
        />
      )}
    </div>
  );
};
