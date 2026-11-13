/**
 * Regulatory Lab Page (/regulatory-lab)
 * Autonomous CDSCO notification ingestion, compliance rules hot-swapping, and audit verification.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Hash, RefreshCw, Scale } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { RegulatoryNotification } from "../types/api";

export const RegulatoryLabPage: React.FC = () => {
  const [selectedNotice, setSelectedNotice] = useState<RegulatoryNotification | null>(null);

  const {
    data: notifications = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["regulatory-notifications"],
    queryFn: () => api.regulatory.listNotifications(),
  });

  const columns: Column<RegulatoryNotification>[] = [
    {
      key: "title",
      header: "Regulatory Directive",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)]">{row.title}</div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">Authority: {row.source}</div>
        </div>
      ),
    },
    {
      key: "content_hash",
      header: "SHA-256 Hash",
      render: (row) => (
        <span className="font-mono text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
          <Hash className="w-3 h-3 opacity-50" />
          {row.content_hash ? row.content_hash.slice(0, 14) : "—"}...
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      render: (row) => <StatusBadge status={row.status || "active"} size="sm" />,
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            CDSCO Regulatory Lab & Hot-Swap Engine
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Real-time compliance monitoring, Gazette notifications, and dynamic Schedule H/H1 policy enforcement.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Notifications
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 space-y-2">
          <DataTable
            data={notifications}
            columns={columns}
            keyExtractor={(row) => row.id}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedNotice(row)}
            searchPlaceholder="Search gazette directive, title, or authority..."
            searchFilter={(row, q) =>
              row.title.toLowerCase().includes(q) ||
              row.source.toLowerCase().includes(q) ||
              row.content_hash.toLowerCase().includes(q)
            }
            emptyTitle="No regulatory notices ingested"
            emptyDescription="New notifications from CDSCO / NPPA will appear here automatically."
            pageSize={8}
          />
        </div>

        <div className="lg:col-span-5 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Directive Gazette Details
          </h3>
          {selectedNotice ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-xs text-[var(--text-primary)]">
                    {selectedNotice.title}
                  </h4>
                  <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                    Source: {selectedNotice.source}
                  </span>
                </div>
                <StatusBadge status={selectedNotice.status || "active"} size="sm" />
              </div>

              <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] leading-relaxed">
                <span className="font-semibold block mb-1 text-[10px] font-mono uppercase tracking-widest text-[var(--text-secondary)]">
                  Executive Summary:
                </span>
                {selectedNotice.summary}
              </div>

              {selectedNotice.affected_schedules && selectedNotice.affected_schedules.length > 0 && (
                <div className="flex items-center gap-1.5 text-xs font-mono">
                  <span className="text-[var(--text-secondary)]">Affected Schedules:</span>
                  {selectedNotice.affected_schedules.map((s) => (
                    <span key={s} className="px-1.5 py-0.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                      {s}
                    </span>
                  ))}
                </div>
              )}

              <JsonViewer data={selectedNotice} title="Full Notification Envelope" defaultExpanded={false} />
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <Scale className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Select any regulatory gazette notification to inspect rules and affected schedules.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
