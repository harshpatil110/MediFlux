/**
 * Strip Cascade Replay Page (/cascade)
 * Interactive 4-Tier React Flow canvas with live and historical demand propagation:
 * Tier 4 Retail Pharmacy -> Tier 3 Regional Stockist -> Tier 2 Logistics Distributor -> Tier 1 Formulation Plant
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Layers,
  Pause,
  Play,
  Radio,
  RotateCcw,
  Sparkles,
  Zap,
} from "lucide-react";
import { api } from "../lib/api";
import { JsonViewer } from "../components/shared/JsonViewer";
import { StatusBadge } from "../components/shared/StatusBadge";
import type { CascadeStep, CascadeSummary } from "../types/api";

// -----------------------------------------------------------------------------
// Custom Node Component for the 4 Supply Chain Tiers
// -----------------------------------------------------------------------------
type TierNodeData = {
  tier: number;
  tierLabel: string;
  agentName: string;
  nodeName: string;
  state: "idle" | "active" | "completed";
  durationMs?: number;
  totalTokens?: number;
  decisionSnippet?: string;
  isSelected?: boolean;
  [key: string]: unknown;
};

const CascadeTierNode: React.FC<NodeProps<Node<TierNodeData>>> = ({ data }) => {
  const isTarget = data.tier < 4;
  const isSource = data.tier > 1;

  const stateColors = {
    idle: "border-dashed border-[var(--border)] bg-[var(--surface-muted)] opacity-60",
    active: "border-2 border-[#00AEBB] ring-4 ring-[#00AEBB]/20 bg-[var(--surface)] shadow-md",
    completed: data.isSelected
      ? "border-2 border-[#00AEBB] bg-[var(--surface)] shadow-sm"
      : "border border-[var(--border)] bg-[var(--surface)] hover:border-[#00AEBB]/60",
  };

  return (
    <div
      className={`w-72 p-3.5 transition-all text-left ${stateColors[data.state]} cursor-pointer`}
      style={{ minHeight: "130px" }}
    >
      {/* React Flow Connection Handles */}
      {isTarget && (
        <Handle
          type="target"
          position={Position.Left}
          className="w-2.5 h-2.5 !bg-[#00AEBB] !border-2 !border-white"
        />
      )}
      {isSource && (
        <Handle
          type="source"
          position={Position.Right}
          className="w-2.5 h-2.5 !bg-[#00AEBB] !border-2 !border-white"
        />
      )}

      {/* Tier Badge & Execution State */}
      <div className="flex items-center justify-between gap-1 mb-2">
        <span className="font-mono text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink)]">
          Tier {data.tier}: {data.tierLabel}
        </span>

        {data.state === "active" ? (
          <span className="flex items-center gap-1 font-mono text-[10px] text-[#00AEBB] font-semibold animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00AEBB] animate-ping" />
            EXECUTING...
          </span>
        ) : data.state === "completed" ? (
          <span className="flex items-center gap-1 font-mono text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
            <CheckCircle2 className="w-3 h-3" />
            DONE
          </span>
        ) : (
          <span className="font-mono text-[10px] text-[var(--ink-muted)]">PENDING</span>
        )}
      </div>

      {/* Facility Name & Agent */}
      <div className="space-y-0.5">
        <div className="font-sans font-semibold text-xs text-[var(--ink)] line-clamp-1">
          {data.nodeName || "Network Facility"}
        </div>
        <div className="font-mono text-[10px] text-[var(--ink-secondary)]">
          {data.agentName}
        </div>
      </div>

      {/* Output / Decision Snippet */}
      {data.state === "completed" && (
        <div className="mt-2 pt-2 border-t border-[var(--border-subtle)] space-y-1">
          <p className="text-[10px] text-[var(--ink-secondary)] line-clamp-1 italic">
            "{data.decisionSnippet || "Action confirmed"}"
          </p>
          <div className="flex items-center gap-2 font-mono text-[9px] text-[var(--ink-muted)]">
            <span>{data.durationMs ? `${data.durationMs.toFixed(0)}ms` : "—"}</span>
            <span>•</span>
            <span>{data.totalTokens ? `${data.totalTokens} tok` : "—"}</span>
          </div>
        </div>
      )}
    </div>
  );
};

const nodeTypes = {
  tierNode: CascadeTierNode,
};

// -----------------------------------------------------------------------------
// Cascade Replay Page Component
// -----------------------------------------------------------------------------
export const CascadePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlCorrelationId = searchParams.get("correlation_id");

  // Replay State
  const [selectedCorrelationId, setSelectedCorrelationId] = useState<string>(
    urlCorrelationId || ""
  );
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(3); // 0=Tier4, 1=Tier3, 2=Tier2, 3=Tier1
  const [selectedStepIndex, setSelectedStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1); // 0.5, 1, 2, 4
  const [isTriggeringLive, setIsTriggeringLive] = useState<boolean>(false);
  const [manualInputId, setManualInputId] = useState<string>("");

  // ---------------------------------------------------------------------------
  // Queries
  // ---------------------------------------------------------------------------
  const { data: recentCascades = [], refetch: refetchCascadeList } = useQuery({
    queryKey: ["cascade-recent-list"],
    queryFn: () => api.cascade.list(20),
  });

  // Pick first available correlation ID if none specified
  useEffect(() => {
    if (!selectedCorrelationId && recentCascades.length > 0) {
      const firstId = recentCascades[0].correlation_id;
      setSelectedCorrelationId(firstId);
      setSearchParams({ correlation_id: firstId });
    }
  }, [recentCascades, selectedCorrelationId, setSearchParams]);

  // Sync URL changes
  useEffect(() => {
    if (urlCorrelationId && urlCorrelationId !== selectedCorrelationId) {
      setSelectedCorrelationId(urlCorrelationId);
    }
  }, [urlCorrelationId, selectedCorrelationId]);

  // Fetch full deterministic trace for current correlation_id
  const {
    data: cascadeTrace,
    isLoading: traceLoading,
    refetch: refetchTrace,
  } = useQuery({
    queryKey: ["cascade-trace", selectedCorrelationId],
    queryFn: () => api.cascade.getTrace(selectedCorrelationId),
    enabled: Boolean(selectedCorrelationId),
  });

  // Sort trace steps deterministically (Tier 4 -> Tier 3 -> Tier 2 -> Tier 1)
  const orderedSteps: CascadeStep[] = useMemo(() => {
    if (!cascadeTrace?.steps) return [];
    return [...cascadeTrace.steps].sort((a, b) => b.tier - a.tier);
  }, [cascadeTrace]);

  // ---------------------------------------------------------------------------
  // Step Replay Animation Timer
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!isPlaying) return;

    const baseDelay = 1200;
    const intervalMs = Math.max(250, Math.round(baseDelay / playbackSpeed));

    const timer = setInterval(() => {
      setCurrentStepIndex((prev) => {
        if (prev < orderedSteps.length - 1) {
          const next = prev + 1;
          setSelectedStepIndex(next);
          return next;
        } else {
          setIsPlaying(false);
          return prev;
        }
      });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, playbackSpeed, orderedSteps.length]);

  // Handle Play/Pause
  const togglePlay = () => {
    if (currentStepIndex >= orderedSteps.length - 1) {
      // Reached the end, restart from step 0
      setCurrentStepIndex(0);
      setSelectedStepIndex(0);
      setIsPlaying(true);
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const handleRestart = () => {
    setCurrentStepIndex(0);
    setSelectedStepIndex(0);
    setIsPlaying(true);
  };

  const handleStepBack = () => {
    setIsPlaying(false);
    setCurrentStepIndex((prev) => {
      const next = Math.max(0, prev - 1);
      setSelectedStepIndex(next);
      return next;
    });
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    setCurrentStepIndex((prev) => {
      const next = Math.min(orderedSteps.length - 1, prev + 1);
      setSelectedStepIndex(next);
      return next;
    });
  };

  // ---------------------------------------------------------------------------
  // "⚡ Sell 1 Strip & Watch Live" Handler
  // ---------------------------------------------------------------------------
  const handleTriggerSellOneStrip = async () => {
    setIsTriggeringLive(true);
    try {
      const res = await api.simulator.triggerPos({
        mode: "single",
        quantity: 1,
      });

      setSelectedCorrelationId(res.correlation_id);
      setSearchParams({ correlation_id: res.correlation_id });
      await refetchCascadeList();
      await refetchTrace();

      // Start animation from beginning
      setCurrentStepIndex(0);
      setSelectedStepIndex(0);
      setIsPlaying(true);
    } catch (err: any) {
      console.error("Live trigger error:", err);
    } finally {
      setIsTriggeringLive(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Build React Flow Nodes & Edges
  // ---------------------------------------------------------------------------
  const tiersConfig = useMemo(
    () => [
      { tier: 4, label: "Retail Pharmacy", x: 40, y: 120 },
      { tier: 3, label: "Regional Stockist", x: 370, y: 120 },
      { tier: 2, label: "Logistics Distributor", x: 700, y: 120 },
      { tier: 1, label: "Formulation Plant", x: 1030, y: 120 },
    ],
    []
  );

  const nodes: Node<TierNodeData>[] = useMemo(() => {
    return tiersConfig.map((cfg, idx) => {
      const step = orderedSteps[idx];
      let state: "idle" | "active" | "completed" = "idle";

      if (idx < currentStepIndex) {
        state = "completed";
      } else if (idx === currentStepIndex) {
        state = isPlaying ? "active" : "completed";
      } else {
        state = "idle";
      }

      return {
        id: `tier-${cfg.tier}`,
        type: "tierNode",
        position: { x: cfg.x, y: cfg.y },
        data: {
          tier: cfg.tier,
          tierLabel: cfg.label,
          agentName: step?.agent_name || `tier_${cfg.tier}_agent`,
          nodeName: step?.node_name || `${cfg.label} Hub`,
          state,
          durationMs: step?.duration_ms,
          totalTokens: step?.total_tokens,
          decisionSnippet: step?.reasoning,
          isSelected: selectedStepIndex === idx,
        },
      };
    });
  }, [tiersConfig, orderedSteps, currentStepIndex, isPlaying, selectedStepIndex]);

  const edges: Edge[] = useMemo(() => {
    return [
      {
        id: "e4-3",
        source: "tier-4",
        target: "tier-3",
        animated: currentStepIndex >= 1,
        style: {
          stroke: currentStepIndex >= 1 ? "#00AEBB" : "var(--border)",
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: currentStepIndex >= 1 ? "#00AEBB" : "var(--border)",
        },
      },
      {
        id: "e3-2",
        source: "tier-3",
        target: "tier-2",
        animated: currentStepIndex >= 2,
        style: {
          stroke: currentStepIndex >= 2 ? "#00AEBB" : "var(--border)",
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: currentStepIndex >= 2 ? "#00AEBB" : "var(--border)",
        },
      },
      {
        id: "e2-1",
        source: "tier-2",
        target: "tier-1",
        animated: currentStepIndex >= 3,
        style: {
          stroke: currentStepIndex >= 3 ? "#00AEBB" : "var(--border)",
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: currentStepIndex >= 3 ? "#00AEBB" : "var(--border)",
        },
      },
    ];
  }, [currentStepIndex]);

  // Click on node in React Flow canvas selects step in side panel
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const clickedTier = Number(node.id.replace("tier-", ""));
      const stepIdx = tiersConfig.findIndex((t) => t.tier === clickedTier);
      if (stepIdx !== -1) {
        setSelectedStepIndex(stepIdx);
      }
    },
    [tiersConfig]
  );

  // Active step details for inspector panel
  const activeStep: CascadeStep | undefined = orderedSteps[selectedStepIndex];

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-12">
      {/* --------------------------------------------------------------------- */}
      {/* Top Header & Fast Live Action Trigger                                 */}
      {/* --------------------------------------------------------------------- */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-serif font-bold text-[var(--ink)] tracking-tight">
              Single-Unit Strip Demand Cascade Replay
            </h1>
            <span className="font-mono text-[10px] px-2 py-0.5 border border-[#00AEBB] bg-[#00AEBB]/10 text-[#00AEBB] font-semibold">
              LANGGRAPH
            </span>
          </div>
          <p className="text-xs text-[var(--ink-secondary)] mt-1">
            Observe the autonomous 4-tier ripple triggered by 1 strip retail sale at the counter.
          </p>
        </div>

        {/* ⚡ Sell 1 Strip & Watch Live Button */}
        <button
          type="button"
          onClick={handleTriggerSellOneStrip}
          disabled={isTriggeringLive}
          className="inline-flex items-center gap-2 px-4 py-2 font-mono text-xs font-bold bg-[#00AEBB] text-black hover:bg-[#009da9] active:translate-y-px transition-all shadow-sm disabled:opacity-50 self-start md:self-auto shrink-0"
        >
          <Zap className="w-4 h-4 fill-black" />
          {isTriggeringLive ? "Cascading..." : "⚡ Sell 1 Strip & Watch Live"}
        </button>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* Control Bar: Cascade Selector, Playback Controls, Speed Selector      */}
      {/* --------------------------------------------------------------------- */}
      <div className="editorial-card p-3.5 border border-[var(--border)] bg-[var(--surface)] space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Historical Cascade Selector Dropdown */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="text-[var(--ink-muted)]">Cascade:</span>
            <select
              aria-label="Historical Cascade Selector"
              value={selectedCorrelationId}
              onChange={(e) => {
                setSelectedCorrelationId(e.target.value);
                setSearchParams({ correlation_id: e.target.value });
                setCurrentStepIndex(3);
                setSelectedStepIndex(0);
                setIsPlaying(false);
              }}
              className="px-2.5 py-1.5 border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs font-mono focus:outline-none focus:border-[#00AEBB] max-w-[280px]"
            >
              {recentCascades.map((c: CascadeSummary) => (
                <option key={c.correlation_id} value={c.correlation_id}>
                  {c.correlation_id} ({c.product_name || "Item"})
                </option>
              ))}
            </select>

            {/* Manual ID Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (manualInputId.trim()) {
                  setSelectedCorrelationId(manualInputId.trim());
                  setSearchParams({ correlation_id: manualInputId.trim() });
                  setManualInputId("");
                }
              }}
              className="flex items-center gap-1"
            >
              <input
                type="text"
                placeholder="Paste ID..."
                value={manualInputId}
                onChange={(e) => setManualInputId(e.target.value)}
                className="w-24 px-2 py-1 border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs font-mono focus:outline-none focus:border-[#00AEBB]"
              />
              <button
                type="submit"
                className="px-2 py-1 text-xs font-mono border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink)] hover:bg-[var(--canvas-elevated)]"
              >
                Go
              </button>
            </form>
          </div>

          {/* Mode Pill */}
          <div className="flex items-center gap-1.5 font-mono text-xs px-2.5 py-1 border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink)]">
            <Radio className="w-3.5 h-3.5 text-[#00AEBB]" />
            <span>Deterministic Historical Replay</span>
          </div>
        </div>

        {/* Playback Controls & Speed */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-2.5 border-t border-[var(--border-subtle)]">
          {/* Step Replay Buttons */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRestart}
              className="p-1.5 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--canvas-elevated)] text-[var(--ink)] transition-colors"
              title="Restart from Step 1"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={handleStepBack}
              disabled={currentStepIndex <= 0}
              className="p-1.5 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--canvas-elevated)] text-[var(--ink)] disabled:opacity-40 transition-colors"
              title="Step Back"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={togglePlay}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-semibold transition-colors ${
                isPlaying
                  ? "bg-amber-500 text-black hover:bg-amber-400"
                  : "bg-[#00AEBB] text-black hover:bg-[#009da9]"
              }`}
            >
              {isPlaying ? (
                <>
                  <Pause className="w-3.5 h-3.5 fill-black" /> Pause
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-black" /> Play Replay
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleStepForward}
              disabled={currentStepIndex >= orderedSteps.length - 1}
              className="p-1.5 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--canvas-elevated)] text-[var(--ink)] disabled:opacity-40 transition-colors"
              title="Step Forward"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>

            <span className="text-xs font-mono text-[var(--ink-secondary)] ml-2">
              Tier {4 - currentStepIndex} of 4 Active
            </span>
          </div>

          {/* Speed Controls */}
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <span className="text-[var(--ink-muted)]">Speed:</span>
            {[0.5, 1, 2, 4].map((speed) => (
              <button
                key={speed}
                type="button"
                onClick={() => setPlaybackSpeed(speed)}
                className={`px-2 py-1 text-xs font-mono border transition-colors ${
                  playbackSpeed === speed
                    ? "border-[#00AEBB] bg-[#00AEBB]/10 text-[#00AEBB] font-bold"
                    : "border-[var(--border)] bg-[var(--surface)] text-[var(--ink-secondary)] hover:text-[var(--ink)]"
                }`}
              >
                {speed}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* Main Workspace: React Flow Canvas (Left) + Inspector Panel (Right)    */}
      {/* --------------------------------------------------------------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: 4-Tier Interactive React Flow Canvas (8 cols) */}
        <div className="lg:col-span-8 editorial-card border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
          <div className="p-3 border-b border-[var(--border-subtle)] flex items-center justify-between text-xs font-mono text-[var(--ink-secondary)]">
            <div className="flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-[#00AEBB]" />
              <span>4-Tier Supply Chain Topology Flow</span>
            </div>
            <span className="text-[11px] text-[var(--ink-muted)]">
              Click node to inspect agent reasoning
            </span>
          </div>

          <div className="h-[460px] w-full bg-[var(--canvas)] relative">
            {traceLoading ? (
              <div className="h-full flex items-center justify-center text-xs font-mono text-[var(--ink-muted)]">
                Loading cascade graph state...
              </div>
            ) : (
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodeClick={onNodeClick}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                minZoom={0.4}
                maxZoom={1.5}
                attributionPosition="bottom-left"
              >
                <Background color="var(--border)" gap={16} />
                <Controls showInteractive={false} />
              </ReactFlow>
            )}
          </div>
        </div>

        {/* Right: Agent Reasoning & Telemetry Inspector (4 cols) */}
        <div className="lg:col-span-4 editorial-card border border-[var(--border)] bg-[var(--surface)] p-4 space-y-4 max-h-[520px] overflow-y-auto">
          {/* Header */}
          <div className="pb-3 border-b border-[var(--border-subtle)] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase font-bold text-[var(--ink-muted)]">
                Tier {activeStep?.tier ?? 4} Telemetry
              </span>
              <StatusBadge status={activeStep?.status || "succeeded"} size="sm" />
            </div>

            <h3 className="font-serif font-bold text-base text-[var(--ink)]">
              {activeStep?.tier_label || "Supply Chain Node"}
            </h3>
            <p className="font-mono text-[11px] text-[var(--ink-secondary)]">
              {activeStep?.agent_name || "agent"}
            </p>
          </div>

          {/* Execution Telemetry Strip */}
          <div className="p-2.5 border border-[var(--border-subtle)] bg-[var(--surface-muted)] space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[var(--ink-muted)]">Model:</span>
              <span className="font-semibold text-[var(--ink)] truncate max-w-[150px]">
                {activeStep?.model || "meta/llama-3.1-70b"}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[var(--ink-muted)]">Provider:</span>
              <span className="text-[var(--ink)] uppercase">
                {activeStep?.provider || "groq"}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[var(--ink-muted)]">Latency:</span>
              <span className="text-[var(--ink)]">
                {activeStep?.duration_ms ? `${activeStep.duration_ms.toFixed(1)} ms` : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--border-subtle)]">
              <span className="text-[var(--ink-muted)]">Tokens (P / C / Tot):</span>
              <span className="font-bold text-[var(--ink)]">
                {activeStep?.prompt_tokens ?? 0} / {activeStep?.completion_tokens ?? 0} /{" "}
                <span className="text-[#00AEBB]">{activeStep?.total_tokens ?? 0}</span>
              </span>
            </div>
          </div>

          {/* Plain-Language Agent Reasoning Card */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-mono font-semibold text-[var(--ink)]">
              <Sparkles className="w-3.5 h-3.5 text-[#00AEBB]" />
              <span>Agent Decision Rationale</span>
            </div>
            <div className="p-3 border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--ink-secondary)] leading-relaxed">
              {activeStep?.reasoning || "Reasoning trace pending execution."}
            </div>
          </div>

          {/* Domain Artifacts */}
          {activeStep?.entities_created && Object.keys(activeStep.entities_created).length > 0 && (
            <div className="space-y-1.5">
              <span className="text-xs font-mono font-semibold text-[var(--ink)]">
                Domain Artifacts Created
              </span>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(activeStep.entities_created).map(([key, val]) => (
                  <span
                    key={key}
                    className="font-mono text-[10px] px-2 py-0.5 border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink)]"
                  >
                    {key}: <span className="font-bold">{String(val)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Collapsible JSON Viewers for Input and Output */}
          <div className="space-y-2 pt-2 border-t border-[var(--border-subtle)]">
            <details className="text-xs group">
              <summary className="font-mono font-semibold text-[var(--ink)] cursor-pointer hover:text-[#00AEBB] select-none py-1">
                ▶ Input Payload JSON
              </summary>
              <div className="mt-1.5">
                <JsonViewer data={activeStep?.input || {}} maxHeight="140px" />
              </div>
            </details>

            <details className="text-xs group" open>
              <summary className="font-mono font-semibold text-[var(--ink)] cursor-pointer hover:text-[#00AEBB] select-none py-1">
                ▼ Output Response JSON
              </summary>
              <div className="mt-1.5">
                <JsonViewer data={activeStep?.output || {}} maxHeight="140px" />
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
};
