/**
 * Adapter Forge Page (/adapter-forge)
 * Inspects self-evolving ERP translators, synthesized Python transformation code, and AST guardrails.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Code2, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { Adapter } from "../types/api";

export const AdapterForgePage: React.FC = () => {
  const [selectedAdapter, setSelectedAdapter] = useState<Adapter | null>(null);

  const {
    data: adapters = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["adapters"],
    queryFn: () => api.adapters.list(),
  });

  const columns: Column<Adapter>[] = [
    {
      key: "name",
      header: "Adapter Spec",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)]">{row.name}</div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">{row.erp_system}</div>
        </div>
      ),
    },
    {
      key: "version",
      header: "Version",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)]">
          v{row.version}
        </span>
      ),
    },
    {
      key: "status",
      header: "Deployment",
      sortable: true,
      render: (row) => <StatusBadge status={row.status} size="sm" />,
    },
    {
      key: "created_at",
      header: "Compiled",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)]">
          {row.created_at ? new Date(row.created_at).toLocaleDateString() : "Active"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            Adapter Forge & Legacy Ingestion
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Self-evolving Python AST-guarded translators adapting Marg, Tally, and SAP ERP payloads.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Adapters
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 space-y-2">
          <DataTable
            data={adapters}
            columns={columns}
            keyExtractor={(row) => row.id}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedAdapter(row)}
            searchPlaceholder="Search adapter or ERP system..."
            searchFilter={(row, q) =>
              row.name.toLowerCase().includes(q) ||
              row.erp_system.toLowerCase().includes(q)
            }
            emptyTitle="No registered adapters"
            emptyDescription="Generated adapters will be listed here after synthesis."
            pageSize={8}
          />
        </div>

        <div className="lg:col-span-5 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Transformation Source & AST Sandbox
          </h3>
          {selectedAdapter ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-xs text-[var(--text-primary)]">
                    {selectedAdapter.name}
                  </span>
                  <span className="block text-[10px] font-mono text-[var(--text-secondary)]">
                    Target ERP: {selectedAdapter.erp_system}
                  </span>
                </div>
                <StatusBadge status={selectedAdapter.status} size="sm" />
              </div>

              {selectedAdapter.source_code && (
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-secondary)] block mb-1">
                    Synthesized Python AST Code:
                  </span>
                  <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] max-h-56 overflow-auto font-mono text-[11px] leading-tight text-[var(--text-primary)]">
                    <pre>{selectedAdapter.source_code}</pre>
                  </div>
                </div>
              )}

              <JsonViewer
                data={selectedAdapter.transformation_rules}
                title="Transformation Rules Schema"
                defaultExpanded={!selectedAdapter.source_code}
              />
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <Code2 className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Select any adapter to inspect synthesized Python code and AST safety analysis.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
