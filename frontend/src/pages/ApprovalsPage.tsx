/**
 * HITL Approvals Page (/approvals)
 * Operator review queue for Human-in-the-Loop decision checkpoints.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, RefreshCw, ShieldAlert, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { HitlTask } from "../types/api";

export const ApprovalsPage: React.FC = () => {
  const [selectedTask, setSelectedTask] = useState<HitlTask | null>(null);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [isDeciding, setIsDeciding] = useState<boolean>(false);

  const {
    data: tasks = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["hitl-tasks"],
    queryFn: () => api.hitl.listTasks({ limit: 50 }),
  });

  const handleDecide = async (decision: "approved" | "rejected") => {
    if (!selectedTask) return;
    const taskId = selectedTask.task_id || selectedTask.id;
    if (!taskId) return;

    setIsDeciding(true);
    setActionStatus(null);
    try {
      await api.hitl.decide(taskId, {
        decision,
        reason: `Operator decision via UI shell: ${decision}`,
      });
      setActionStatus(`Task ${taskId.slice(0, 8)} successfully ${decision}!`);
      refetch();
      setSelectedTask(null);
    } catch (err: any) {
      setActionStatus(`Decision error: ${err.message || "Failed"}`);
    } finally {
      setIsDeciding(false);
    }
  };

  const columns: Column<HitlTask>[] = [
    {
      key: "task_type",
      header: "Intervention Type",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)]">{row.task_type}</div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">{row.workflow_name}</div>
        </div>
      ),
    },
    {
      key: "node_id",
      header: "Target Node",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-secondary)]">
          {row.node_id ? `${row.node_id.slice(0, 12)}...` : "Network"}
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
      header: "Created",
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
            Human-in-the-Loop Decision Queue
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Intervention checkpoints for credit overrides, regulatory hot-swaps, and high-value orders.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Queue
        </button>
      </div>

      {actionStatus && (
        <div className="p-3 bg-teal-500/10 border border-teal-500/30 text-teal-800 dark:text-teal-200 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[var(--accent-teal)]" />
          <span>{actionStatus}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 space-y-2">
          <DataTable
            data={tasks}
            columns={columns}
            keyExtractor={(row) => row.task_id || row.id || `task-${Math.random()}`}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedTask(row)}
            searchPlaceholder="Search task type or workflow..."
            searchFilter={(row, q) =>
              row.task_type.toLowerCase().includes(q) ||
              row.workflow_name.toLowerCase().includes(q)
            }
            emptyTitle="No open approval tasks"
            emptyDescription="All critical checkpoints are resolved. Agent graphs are running autonomously."
            pageSize={8}
          />
        </div>

        <div className="lg:col-span-5 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Task Decision Details
          </h3>
          {selectedTask ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-sm text-[var(--text-primary)]">
                    {selectedTask.task_type}
                  </h4>
                  <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                    workflow: {selectedTask.workflow_name}
                  </span>
                </div>
                <StatusBadge status={selectedTask.status} size="sm" />
              </div>

              {selectedTask.expires_at && (
                <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400 font-mono">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Expires: {new Date(selectedTask.expires_at).toLocaleString()}</span>
                </div>
              )}

              <JsonViewer data={selectedTask.payload} title="Intervention Context" defaultExpanded={true} />

              {selectedTask.status === "pending" && (
                <div className="pt-2 flex items-center gap-3">
                  <button
                    type="button"
                    disabled={isDeciding}
                    onClick={() => handleDecide("approved")}
                    className="flex-1 py-2 px-3 text-xs font-medium bg-teal-600 hover:bg-teal-700 text-white flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" /> Approve Action
                  </button>
                  <button
                    type="button"
                    disabled={isDeciding}
                    onClick={() => handleDecide("rejected")}
                    className="flex-1 py-2 px-3 text-xs font-medium bg-rose-600 hover:bg-rose-700 text-white flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-3.5 h-3.5" /> Reject Action
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <ShieldAlert className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Select any pending task in the table to review contextual data and sign off.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
