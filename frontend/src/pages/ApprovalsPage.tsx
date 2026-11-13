/**
 * HITL Approvals Inbox (/approvals)
 * Operator review queue for Human-in-the-Loop decision checkpoints.
 * Features desktop notification integration, split-pane inspection,
 * agent reasoning explanation, context-aware payload diff, and immediate graph resumption.
 */

import React, { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  Clock,
  RefreshCw,
  Bell,
  BellOff,
  FileCode,
  UserCheck,
  ThermometerSnowflake,
  Sparkles,
} from "lucide-react";
import { api } from "../lib/api";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import { useDesktopNotifications } from "../hooks/useDesktopNotifications";
import type { HitlTask } from "../types/api";

type StatusTab = "pending" | "approved" | "rejected" | "all";
type RiskFilter = "all" | "critical" | "high" | "medium" | "low";

export const ApprovalsPage: React.FC = () => {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [statusTab, setStatusTab] = useState<StatusTab>("pending");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [decisionNote, setDecisionNote] = useState<string>("");
  const [isDeciding, setIsDeciding] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
    details?: any;
  } | null>(null);

  // Desktop notifications hook
  const {
    permission,
    isSupported: notificationsSupported,
    isMuted,
    requestPermission,
    toggleMute,
  } = useDesktopNotifications();

  // Query all tasks
  const {
    data: tasks = [],
    isLoading,
    refetch,
  } = useQuery<HitlTask[]>({
    queryKey: ["hitl-tasks", statusTab, riskFilter, typeFilter],
    queryFn: async () => {
      const params: any = { limit: 100 };
      if (statusTab !== "all") params.status = statusTab;
      if (riskFilter !== "all") params.risk_level = riskFilter;
      if (typeFilter !== "all") params.task_type = typeFilter;
      return api.hitl.listTasks(params);
    },
    refetchInterval: 10000,
  });

  // Keep selected task synced with tasks list
  const selectedTask = useMemo(() => {
    if (!tasks || tasks.length === 0) return null;
    if (selectedTaskId) {
      const found = tasks.find(
        (t) => (t.task_id || t.id) === selectedTaskId
      );
      if (found) return found;
    }
    // Default to first pending task or first task
    const firstPending = tasks.find((t) => t.status === "pending");
    return firstPending || tasks[0];
  }, [tasks, selectedTaskId]);

  // Unique task types for filter dropdown
  const uniqueTaskTypes = useMemo(() => {
    const set = new Set<string>();
    tasks.forEach((t) => {
      if (t.task_type) set.add(t.task_type);
    });
    return Array.from(set);
  }, [tasks]);

  // Filtered tasks by search query
  const filteredTasks = useMemo(() => {
    if (!searchQuery.trim()) return tasks;
    const q = searchQuery.toLowerCase();
    return tasks.filter((t) => {
      const title = (t.title || t.task_type || "").toLowerCase();
      const node = (t.node_name || t.node_id || "").toLowerCase();
      const summary = (t.summary || "").toLowerCase();
      const workflow = (t.workflow_name || "").toLowerCase();
      return (
        title.includes(q) ||
        node.includes(q) ||
        summary.includes(q) ||
        workflow.includes(q)
      );
    });
  }, [tasks, searchQuery]);

  const handleDecide = async (decision: "approved" | "rejected") => {
    if (!selectedTask) return;
    const taskId = selectedTask.task_id || selectedTask.id;
    if (!taskId) return;

    setIsDeciding(true);
    setFeedback(null);
    try {
      const res = await api.hitl.decide(taskId, {
        decision,
        note: decisionNote || `Operator decision via UI shell: ${decision}`,
        reason: decisionNote || `Operator decision via UI shell: ${decision}`,
      });

      const actionWord = decision === "approved" ? "Approved & Resumed" : "Rejected & Aborted";
      let detailMsg = `Task ${taskId.slice(0, 8)} successfully ${actionWord}. Recorded in cryptographic audit ledger.`;
      if (res.resumed_workflow) {
        if (res.resumed_workflow.action === "activated_module") {
          detailMsg += ` Module '${res.resumed_workflow.module_name}' hot-swapped to v${res.resumed_workflow.version} with zero downtime!`;
        }
      }

      setFeedback({
        type: "success",
        message: detailMsg,
        details: res.resumed_workflow,
      });

      setDecisionNote("");
      refetch();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: `Decision submission failed: ${err.message || "Unknown error"}`,
      });
    } finally {
      setIsDeciding(false);
    }
  };

  const getRiskBadge = (risk?: string) => {
    const r = (risk || "medium").toLowerCase();
    if (r === "critical") {
      return (
        <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30">
          CRITICAL
        </span>
      );
    }
    if (r === "high") {
      return (
        <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">
          HIGH
        </span>
      );
    }
    if (r === "medium") {
      return (
        <span className="px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wider bg-blue-500/15 text-blue-700 dark:text-blue-300 border border-blue-500/30">
          MEDIUM
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 text-[10px] font-mono font-normal uppercase tracking-wider bg-stone-500/15 text-stone-700 dark:text-stone-300 border border-stone-500/30">
        LOW
      </span>
    );
  };

  const getTaskIcon = (type?: string) => {
    const t = (type || "").toLowerCase();
    if (t.includes("regulatory") || t.includes("swap") || t.includes("code")) {
      return <FileCode className="w-4 h-4 text-[var(--accent-teal)]" />;
    }
    if (t.includes("prescription") || t.includes("doctor") || t.includes("compliance")) {
      return <UserCheck className="w-4 h-4 text-amber-500" />;
    }
    if (t.includes("coldchain") || t.includes("temp") || t.includes("batch")) {
      return <ThermometerSnowflake className="w-4 h-4 text-cyan-500" />;
    }
    return <AlertTriangle className="w-4 h-4 text-rose-500" />;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header & Desktop Notification Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
              Human-in-the-Loop Approvals Inbox
            </h2>
            <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-[var(--accent-teal)]/10 text-[var(--accent-teal)] border border-[var(--accent-teal)]/30 font-semibold">
              Live Gateway
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Supervisory decision gate for regulatory hot-swaps, Schedule H1 drug verification, cold-chain excursions, and credit overrides.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Notification control button */}
          {notificationsSupported && (
            <button
              type="button"
              onClick={permission === "granted" ? toggleMute : requestPermission}
              title={
                permission === "granted"
                  ? isMuted
                    ? "Notifications muted (click to unmute)"
                    : "Notifications active (click to mute)"
                  : "Enable desktop push notifications for urgent checkpoints"
              }
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border transition-colors ${
                permission === "granted"
                  ? isMuted
                    ? "border-amber-500/40 text-amber-600 bg-amber-500/5 hover:bg-amber-500/10"
                    : "border-teal-500/40 text-[var(--accent-teal)] bg-teal-500/5 hover:bg-teal-500/10"
                  : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-canvas)]"
              }`}
            >
              {permission === "granted" ? (
                isMuted ? (
                  <>
                    <BellOff className="w-3.5 h-3.5 text-amber-500" />
                    <span>Muted</span>
                  </>
                ) : (
                  <>
                    <Bell className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                    <span>Desktop Alerts On</span>
                  </>
                )
              ) : (
                <>
                  <Bell className="w-3.5 h-3.5" />
                  <span>Enable Push Alerts</span>
                </>
              )}
            </button>
          )}

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Status Tabs */}
        <div className="flex items-center gap-1">
          {(["pending", "approved", "rejected", "all"] as StatusTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setStatusTab(tab)}
              className={`px-3 py-1 text-xs font-mono uppercase tracking-wide transition-all ${
                statusTab === tab
                  ? "bg-[var(--accent-teal)] text-white font-bold"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-canvas)]"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Filters and search */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Risk Level */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value as RiskFilter)}
            className="px-2 py-1 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
          >
            <option value="all">Risk: All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          {/* Type Filter */}
          {uniqueTaskTypes.length > 0 && (
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-2 py-1 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
            >
              <option value="all">Type: All</option>
              {uniqueTaskTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          )}

          {/* Search box */}
          <input
            type="text"
            placeholder="Search tasks, nodes, reasoning..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-2.5 py-1 text-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent-teal)] min-w-[200px]"
          />
        </div>
      </div>

      {/* Global Action Feedback Banner */}
      {feedback && (
        <div
          className={`p-3.5 border flex items-start gap-3 transition-all ${
            feedback.type === "success"
              ? "bg-teal-500/10 border-teal-500/40 text-teal-900 dark:text-teal-100"
              : "bg-rose-500/10 border-rose-500/40 text-rose-900 dark:text-rose-100"
          }`}
        >
          {feedback.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 text-[var(--accent-teal)] shrink-0 mt-0.5" />
          ) : (
            <XCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          )}
          <div className="space-y-1 text-xs">
            <div className="font-semibold">{feedback.message}</div>
            {feedback.details && (
              <pre className="font-mono text-[11px] bg-[var(--bg-surface)] p-2 border border-[var(--border-subtle)] overflow-x-auto">
                {JSON.stringify(feedback.details, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Split-Pane Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Pane: Task Queue */}
        <div className="lg:col-span-5 space-y-2">
          <div className="flex items-center justify-between pb-1">
            <span className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
              Task Queue ({filteredTasks.length})
            </span>
            <span className="text-[10px] font-mono text-[var(--text-secondary)]">
              Auto-polled 10s
            </span>
          </div>

          {filteredTasks.length === 0 ? (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <ShieldAlert className="w-8 h-8 opacity-25 mx-auto mb-2 text-[var(--accent-teal)]" />
              <p className="font-medium text-[var(--text-primary)]">No tasks match current filter</p>
              <p className="mt-1 text-[11px]">All workflows are executing without manual hold.</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[720px] overflow-y-auto pr-1">
              {filteredTasks.map((t) => {
                const taskId = t.task_id || t.id || "";
                const isSelected = selectedTask && (selectedTask.task_id || selectedTask.id) === taskId;

                return (
                  <div
                    key={taskId}
                    onClick={() => {
                      setSelectedTaskId(taskId);
                      setFeedback(null);
                    }}
                    className={`p-3 border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-[var(--bg-surface)] border-[var(--accent-teal)] shadow-sm"
                        : "bg-[var(--bg-surface)]/70 border-[var(--border-subtle)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-surface)]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {getTaskIcon(t.task_type)}
                        <span className="font-semibold text-xs text-[var(--text-primary)]">
                          {t.title || t.task_type}
                        </span>
                      </div>
                      {getRiskBadge(t.risk_level)}
                    </div>

                    <p className="text-xs text-[var(--text-secondary)] line-clamp-2 mt-1.5">
                      {t.summary || t.reasoning || "Intervention requested by supervisor agent."}
                    </p>

                    <div className="mt-2.5 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] font-mono text-[var(--text-secondary)]">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={t.status} size="sm" />
                        <span>{t.node_name || (t.node_id ? t.node_id.slice(0, 10) : "Network")}</span>
                      </div>
                      <div className="flex items-center gap-1 text-[10px]">
                        <Clock className="w-3 h-3" />
                        <span>{t.created_at ? new Date(t.created_at).toLocaleTimeString() : "Recent"}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Pane: Deep Inspection Console */}
        <div className="lg:col-span-7 space-y-4">
          {selectedTask ? (
            <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-5">
              {/* Task Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[var(--border-subtle)]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
                      ID: {selectedTask.task_id || selectedTask.id}
                    </span>
                    {getRiskBadge(selectedTask.risk_level)}
                  </div>
                  <h3 className="text-base font-serif font-bold text-[var(--text-primary)] mt-1">
                    {selectedTask.title || selectedTask.task_type}
                  </h3>
                  <div className="flex items-center gap-3 text-xs font-mono text-[var(--text-secondary)] mt-0.5">
                    <span>workflow: <strong>{selectedTask.workflow_name || selectedTask.task_type}</strong></span>
                    {selectedTask.node_name && (
                      <span>• node: <strong>{selectedTask.node_name}</strong></span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <StatusBadge status={selectedTask.status} size="sm" />
                </div>
              </div>

              {/* Agent Reasoning Box */}
              <div className="p-3.5 bg-amber-500/5 border border-amber-500/25 rounded-none space-y-1.5">
                <div className="flex items-center gap-2 text-xs font-semibold text-amber-800 dark:text-amber-200">
                  <Sparkles className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                  <span>Agent Reasoning & Trigger Diagnosis</span>
                </div>
                <p className="text-xs text-[var(--text-primary)] leading-relaxed">
                  {selectedTask.reasoning ||
                    selectedTask.summary ||
                    "This checkpoint was paused by the autonomous supervisor graph. An authorized human operator must inspect the attached diff or compliance payload before demand propagation or code activation can proceed."}
                </p>
                {selectedTask.expires_at && (
                  <div className="pt-1 flex items-center gap-1.5 text-[11px] font-mono text-amber-700 dark:text-amber-300">
                    <Clock className="w-3.5 h-3.5" />
                    <span>SLA Expiration: {new Date(selectedTask.expires_at).toLocaleString()}</span>
                  </div>
                )}
              </div>

              {/* Code Diff or Context-Aware Inspection */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
                    <FileCode className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                    <span>Intervention Context & Payload Inspection</span>
                  </h4>
                  {selectedTask.correlation_id && (
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                      corr: {selectedTask.correlation_id.slice(0, 12)}...
                    </span>
                  )}
                </div>

                {/* Specific diff rendering if available */}
                {selectedTask.payload?.diff ? (
                  <div className="border border-[var(--border-subtle)] bg-[var(--bg-canvas)] font-mono text-xs overflow-x-auto max-h-[300px]">
                    <div className="p-2 border-b border-[var(--border-subtle)] text-[10px] font-mono text-[var(--text-secondary)] bg-[var(--bg-surface)] flex justify-between">
                      <span>Module Hot-Swap Diff</span>
                      <span>Unified Diff Format</span>
                    </div>
                    <pre className="p-3 leading-relaxed whitespace-pre-wrap">
                      {selectedTask.payload.diff}
                    </pre>
                  </div>
                ) : (
                  <JsonViewer
                    data={selectedTask.payload || selectedTask.details || {}}
                    title="Payload Snapshot"
                    defaultExpanded={true}
                  />
                )}
              </div>

              {/* Decision Section */}
              <div className="pt-2 border-t border-[var(--border-subtle)] space-y-3">
                {selectedTask.status === "pending" ? (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-mono text-[var(--text-secondary)] uppercase tracking-wider mb-1">
                        Operator Decision Note / Justification
                      </label>
                      <textarea
                        value={decisionNote}
                        onChange={(e) => setDecisionNote(e.target.value)}
                        placeholder="Provide mandatory compliance note or rationale for sign-off..."
                        rows={2}
                        className="w-full p-2.5 text-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent-teal)] resize-none"
                      />
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        disabled={isDeciding}
                        onClick={() => handleDecide("approved")}
                        className="flex-1 py-2.5 px-4 text-xs font-semibold bg-[var(--accent-teal)] hover:opacity-90 text-white flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        <span>{isDeciding ? "Resuming Graph..." : "✓ Approve & Resume Graph"}</span>
                      </button>

                      <button
                        type="button"
                        disabled={isDeciding}
                        onClick={() => handleDecide("rejected")}
                        className="flex-1 py-2.5 px-4 text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                      >
                        <XCircle className="w-4 h-4" />
                        <span>{isDeciding ? "Aborting..." : "✕ Reject & Abort"}</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs space-y-1">
                    <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                      <StatusBadge status={selectedTask.status} size="sm" />
                      <span>This checkpoint has already been resolved.</span>
                    </div>
                    {selectedTask.decision_note && (
                      <p className="text-[var(--text-secondary)] italic">
                        "{selectedTask.decision_note}"
                      </p>
                    )}
                    <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                      Decided by {selectedTask.decided_by || "Operator"} at{" "}
                      {selectedTask.decided_at ? new Date(selectedTask.decided_at).toLocaleString() : "N/A"}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)] space-y-3">
              <ShieldAlert className="w-10 h-10 opacity-30 mx-auto text-[var(--accent-teal)]" />
              <h4 className="font-semibold text-sm text-[var(--text-primary)]">Select a Checkpoint to Inspect</h4>
              <p className="max-w-md mx-auto text-xs">
                Pick any task from the queue to view real-time agent diagnostics, code diffs, and resume paused LangGraph workflows.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
