/**
 * AI Agents Observability Page (/agents)
 * Inspects execution traces, graph workflows, model routing, and execution latencies.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bot, Cpu, RefreshCw, Zap } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { AgentRun } from "../types/api";

export const AgentsPage: React.FC = () => {
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);

  const {
    data: runs = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["agent-runs"],
    queryFn: () => api.agents.listRuns({ limit: 50 }),
  });

  const columns: Column<AgentRun>[] = [
    {
      key: "agent_name",
      header: "Agent Identity",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
            <Bot className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
            {row.agent_name}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">{row.graph}</div>
        </div>
      ),
    },
    {
      key: "model",
      header: "Inference Model",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)]">
          {row.model}
        </span>
      ),
    },
    {
      key: "duration_ms",
      header: "Latency",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-secondary)] flex items-center gap-1">
          <Zap className="w-3 h-3 text-amber-500" />
          {row.duration_ms ? `${row.duration_ms.toFixed(1)}ms` : "—"}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      render: (row) => <StatusBadge status={row.status} size="sm" />,
    },
    {
      key: "created_at",
      header: "Executed At",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)]">
          {row.created_at ? new Date(row.created_at).toLocaleTimeString() : "Recent"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            Autonomous Agent Orchestration
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            LangGraph execution traces, tool invocations, and deterministic LLM routing telemetry.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Traces
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 space-y-2">
          <DataTable
            data={runs}
            columns={columns}
            keyExtractor={(row) => row.run_id || row.id || `${row.agent_name}-${row.created_at}`}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedRun(row)}
            searchPlaceholder="Search agent name, graph workflow, or model..."
            searchFilter={(row, q) =>
              row.agent_name.toLowerCase().includes(q) ||
              row.graph.toLowerCase().includes(q) ||
              row.model.toLowerCase().includes(q)
            }
            emptyTitle="No agent runs recorded"
            emptyDescription="Agent traces will appear here once replenishment or demand cascade pipelines execute."
            pageSize={10}
          />
        </div>

        <div className="lg:col-span-4 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Trace Execution Detail
          </h3>
          {selectedRun ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs text-[var(--text-primary)]">{selectedRun.agent_name}</span>
                <StatusBadge status={selectedRun.status} size="sm" />
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                {selectedRun.summary || "Agent step execution completed within SLA bounds."}
              </p>
              <div className="pt-2 border-t border-[var(--border-subtle)]">
                <JsonViewer data={selectedRun} title="Raw Run Metadata" defaultExpanded={true} />
              </div>
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <Cpu className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Select any agent run to inspect model decisions and trace metadata.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
