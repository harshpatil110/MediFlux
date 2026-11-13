/**
 * Cold-Chain Biologics Telemetry Monitor & Auto-Quarantine Screen (/cold-chain)
 *
 * Implements Task 20 & Task 27:
 * - Top KPI strip (active batches, quarantined count, thermal compliance).
 * - Admin Sensor Simulator controls (Normal, Thermal Excursion >8°C, Mechanical Shock >8g).
 * - Cold-chain batches grid with real-time stock balances (zeroes on quarantine) and Arrhenius decay.
 * - Live Recharts telemetry charts:
 *     1. Temperature (°C) vs 2°C–8°C safe envelope.
 *     2. Humidity (%) & Mechanical Shock (g-force) with 4g & 8g reference lines.
 * - Arrhenius Shelf-Life model breakdown card.
 * - Quarantine history feed with Excursion Analyst clinical narrative and restock cascade trace link.
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertOctagon,
  ArrowRight,
  CheckCircle2,
  Clock,
  Flame,
  Gauge,
  Package,
  RefreshCw,
  ShieldAlert,
  Snowflake,
  Sparkles,
  Thermometer,
  Zap,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import { api } from "../lib/api";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { ColdChainBatchDetail, ColdChainSimulationResult, QuarantineRecord } from "../types/api";

export const ColdChainPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [selectedBatchId, setSelectedBatchId] = useState<string>("BIO-INS-01");
  const [simulationResult, setSimulationResult] = useState<ColdChainSimulationResult | null>(null);

  // Queries
  const {
    data: batchesData,
    isLoading: batchesLoading,
    refetch: refetchBatches,
  } = useQuery({
    queryKey: ["coldchain-batches"],
    queryFn: () => api.coldchain.listBatches(),
  });

  const {
    data: quarantinesData,
    isLoading: quarantinesLoading,
    refetch: refetchQuarantines,
  } = useQuery({
    queryKey: ["coldchain-quarantines"],
    queryFn: () => api.coldchain.listQuarantines(),
  });

  const batches: ColdChainBatchDetail[] = batchesData?.batches || [];
  const quarantines: QuarantineRecord[] = quarantinesData?.quarantines || [];

  // Active selected batch
  const activeBatch: ColdChainBatchDetail | undefined =
    batches.find((b) => b.batch_id === selectedBatchId) || batches[0];

  // Simulation Mutation
  const simulateMutation = useMutation({
    mutationFn: async ({ mode }: { mode: "normal" | "excursion" | "shock" }) => {
      const targetId = activeBatch ? activeBatch.batch_id : "BIO-INS-01";
      return await api.coldchain.simulate({
        batch_id: targetId,
        mode,
        steps: 4,
      });
    },
    onSuccess: (data) => {
      setSimulationResult(data);
      queryClient.invalidateQueries({ queryKey: ["coldchain-batches"] });
      queryClient.invalidateQueries({ queryKey: ["coldchain-quarantines"] });
    },
  });

  // KPI Computations
  const totalBatches = batches.length;
  const quarantinedCount = batches.filter((b) => b.status === "quarantined").length;
  const activeCount = totalBatches - quarantinedCount;
  const avgShelfLifePct =
    batches.length > 0
      ? (batches.reduce((acc, b) => acc + (b.shelf_life_estimate?.shelf_life_pct || 100), 0) / batches.length).toFixed(1)
      : "100.0";

  // Recharts chart data preparation
  const chartData = (activeBatch?.readings || []).map((r, idx) => ({
    time: r.ts ? new Date(r.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : `T-${idx * 15}m`,
    temp: Number(r.temperature_c.toFixed(1)),
    shock: Number((r.shock_g || 0.2).toFixed(2)),
    humidity: Number((r.humidity || 50).toFixed(0)),
    mode: r.mode || "normal",
  }));

  const lastReading = activeBatch?.readings?.slice(-1)[0] || activeBatch?.last_reading;
  const isCurrentlyBreached =
    lastReading && (lastReading.temperature_c < 2.0 || lastReading.temperature_c > 8.0 || (lastReading.shock_g || 0) > 8.0);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Header & KPI Strip */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Snowflake className="w-5 h-5 text-[var(--accent-teal)]" />
            Cold-Chain Biologics Telemetry & Auto-Quarantine Monitor
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Real-time IoT thermal envelope tracking (2.0°C – 8.0°C), Arrhenius shelf-life decay modeling, and autonomous quarantine execution.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            refetchBatches();
            refetchQuarantines();
          }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)] self-start md:self-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Telemetry
        </button>
      </div>

      {/* Top 4 KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Total Monitored Batches
          </span>
          <div className="text-2xl font-mono font-bold text-[var(--text-primary)]">{totalBatches}</div>
          <div className="text-[10px] text-[var(--text-secondary)]">Biologics & Vaccines</div>
        </div>

        <div className="p-3.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Active / In-Envelope
          </span>
          <div className="text-2xl font-mono font-bold text-emerald-600 dark:text-emerald-400">{activeCount}</div>
          <div className="text-[10px] text-[var(--text-secondary)]">Within 2.0°C – 8.0°C bounds</div>
        </div>

        <div className="p-3.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Quarantined Batches
          </span>
          <div className="text-2xl font-mono font-bold text-coral-600 dark:text-coral-400">
            {quarantinedCount}
          </div>
          <div className="text-[10px] text-[var(--text-secondary)]">Available Qty Zeroed (0)</div>
        </div>

        <div className="p-3.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Mean Remaining Viability
          </span>
          <div className="text-2xl font-mono font-bold text-[var(--accent-teal)]">{avgShelfLifePct}%</div>
          <div className="text-[10px] text-[var(--text-secondary)]">Arrhenius Potency Model</div>
        </div>
      </div>

      {/* 2. Admin Sensor Simulator Controls Bar */}
      <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-2.5">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-[var(--accent-teal)]" />
            <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-[var(--text-primary)]">
              Admin IoT Sensor Telemetry Simulator
            </h3>
          </div>
          <span className="text-[10px] font-mono text-[var(--text-secondary)]">
            Autonomous multi-agent restock trigger testbed
          </span>
        </div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Target Batch Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-[var(--text-secondary)] shrink-0">Target Biologic Batch:</span>
            <select
              value={activeBatch?.batch_id || ""}
              onChange={(e) => {
                setSelectedBatchId(e.target.value);
                setSimulationResult(null);
              }}
              className="px-3 py-1.5 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
            >
              {batches.map((b) => (
                <option key={b.batch_id} value={b.batch_id}>
                  {b.batch_id} — {b.product_name} ({b.status.toUpperCase()})
                </option>
              ))}
            </select>
          </div>

          {/* 3 Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={simulateMutation.isPending}
              onClick={() => simulateMutation.mutate({ mode: "normal" })}
              className="px-3 py-1.5 text-xs font-mono font-semibold bg-[var(--bg-canvas)] border border-[var(--border-subtle)] hover:border-emerald-500 hover:text-emerald-600 text-[var(--text-primary)] flex items-center gap-1.5 transition-all disabled:opacity-50"
            >
              <Thermometer className="w-3.5 h-3.5 text-emerald-500" />
              🌡️ Run Normal Telemetry (4.8°C)
            </button>

            <button
              type="button"
              disabled={simulateMutation.isPending}
              onClick={() => simulateMutation.mutate({ mode: "excursion" })}
              className="px-3 py-1.5 text-xs font-mono font-semibold bg-amber-50 dark:bg-amber-950/40 border border-amber-400 text-amber-800 dark:text-amber-200 hover:bg-amber-100 flex items-center gap-1.5 transition-all disabled:opacity-50"
            >
              <Flame className="w-3.5 h-3.5 text-amber-600" />
              🔥 Trigger Thermal Excursion (&gt;8°C)
            </button>

            <button
              type="button"
              disabled={simulateMutation.isPending}
              onClick={() => simulateMutation.mutate({ mode: "shock" })}
              className="px-3 py-1.5 text-xs font-mono font-semibold bg-coral-50 dark:bg-coral-950/40 border border-coral-400 text-coral-800 dark:text-coral-200 hover:bg-coral-100 flex items-center gap-1.5 transition-all disabled:opacity-50"
            >
              <Zap className="w-3.5 h-3.5 text-coral-600" />
              💥 Trigger Transit Shock (&gt;8g)
            </button>
          </div>
        </div>

        {/* Simulation Feedback Alert */}
        {simulationResult && (
          <div
            className={`p-3 text-xs font-mono border flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
              simulationResult.quarantined
                ? "bg-coral-50 text-coral-900 border-coral-300 dark:bg-coral-950/50 dark:text-coral-200"
                : "bg-teal-50 text-teal-900 border-teal-300 dark:bg-teal-950/50 dark:text-teal-200"
            }`}
          >
            <div className="flex items-center gap-2">
              {simulationResult.quarantined ? (
                <ShieldAlert className="w-4 h-4 text-coral-600 shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0" />
              )}
              <span>
                <strong>Simulation [{simulationResult.mode.toUpperCase()}]:</strong> Batch {simulationResult.batch_id} evaluated with verdict{" "}
                <code className="font-bold underline">{simulationResult.final_decision.toUpperCase()}</code>. Available stock: {simulationResult.available_quantity}.
              </span>
            </div>

            {simulationResult.rebalance_correlation_id && (
              <Link
                to={`/cascade?corr_id=${simulationResult.rebalance_correlation_id}`}
                className="text-[11px] underline font-bold flex items-center gap-1 hover:opacity-80"
              >
                Inspect Restock Trace <ArrowRight className="w-3 h-3" />
              </Link>
            )}
          </div>
        )}
      </div>

      {/* 3. Batches Grid: 3 Biologics Cards */}
      <div className="space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
          <Package className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
          Monitored Cold-Chain Batches Fleet
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {batchesLoading ? (
            <div className="col-span-3 text-xs font-mono text-[var(--text-secondary)] p-6 bg-[var(--bg-surface)] text-center">
              Loading cold-chain batches...
            </div>
          ) : (
            batches.map((b) => {
              const isSelected = activeBatch?.batch_id === b.batch_id;
              const isQuarantined = b.status === "quarantined";
              const lastTemp = b.last_reading?.temperature_c ?? 5.0;
              const shelfPct = b.shelf_life_estimate?.shelf_life_pct ?? 100;

              return (
                <div
                  key={b.batch_id}
                  onClick={() => setSelectedBatchId(b.batch_id)}
                  className={`p-4 bg-[var(--bg-surface)] border cursor-pointer transition-all space-y-3 relative ${
                    isSelected
                      ? "border-[var(--accent-teal)] shadow-sm"
                      : "border-[var(--border-subtle)] hover:border-[var(--text-secondary)]"
                  }`}
                >
                  {/* Status & Temp header */}
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-[var(--accent-teal)]">
                      {b.batch_id}
                    </span>
                    <StatusBadge
                      status={isQuarantined ? "quarantined" : "approved"}
                      label={isQuarantined ? "QUARANTINED" : "ACTIVE"}
                      size="sm"
                    />
                  </div>

                  {/* Product Name */}
                  <div>
                    <h4 className="font-semibold text-xs text-[var(--text-primary)]">{b.product_name}</h4>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                      Safe Bounds: {b.storage_min_c.toFixed(1)}°C – {b.storage_max_c.toFixed(1)}°C
                    </span>
                  </div>

                  {/* Live Metrics Row */}
                  <div className="p-2.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-[var(--text-secondary)] block">Sensor Temp</span>
                      <span
                        className={`font-bold ${
                          lastTemp < 2.0 || lastTemp > 8.0
                            ? "text-coral-600 dark:text-coral-400"
                            : "text-emerald-600 dark:text-emerald-400"
                        }`}
                      >
                        {lastTemp.toFixed(1)}°C
                      </span>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] text-[var(--text-secondary)] block">Available Stock</span>
                      <span
                        className={`font-bold ${
                          isQuarantined ? "text-coral-600 line-through" : "text-[var(--text-primary)]"
                        }`}
                      >
                        {b.available_quantity} units
                      </span>
                    </div>
                  </div>

                  {/* Arrhenius Shelf Life Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-[10px] font-mono">
                      <span className="text-[var(--text-secondary)]">Remaining Potency:</span>
                      <span className="font-bold text-[var(--text-primary)]">{shelfPct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-[var(--border-subtle)] h-1.5 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${
                          shelfPct > 70
                            ? "bg-[var(--accent-teal)]"
                            : shelfPct > 40
                            ? "bg-amber-500"
                            : "bg-coral-500"
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, shelfPct))}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[9px] font-mono text-[var(--text-secondary)]">
                      <span>Est: {b.shelf_life_estimate?.estimated_remaining_days?.toFixed(0) || 180} days</span>
                      <span>Nominal: 180 days</span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 4. Live Recharts Telemetry Section & Arrhenius Diagnostics */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: 2 Recharts Telemetry Charts (8 cols) */}
        <div className="lg:col-span-8 space-y-5">
          {/* Chart 1: Temperature Envelope */}
          <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                  <Thermometer className="w-4 h-4 text-[var(--accent-teal)]" />
                  Thermal Telemetry vs Safe Storage Envelope (2.0°C – 8.0°C)
                </h4>
                <p className="text-[11px] text-[var(--text-secondary)]">
                  Monitoring {activeBatch?.product_name || "Biologic"} ({activeBatch?.batch_id})
                </p>
              </div>

              {isCurrentlyBreached ? (
                <span className="px-2 py-0.5 text-[10px] font-mono bg-coral-100 text-coral-800 dark:bg-coral-950/60 dark:text-coral-200 border border-coral-400 font-bold animate-pulse">
                  THERMAL EXCURSION ACTIVE
                </span>
              ) : (
                <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200 border border-emerald-400">
                  ENVELOPE NOMINAL
                </span>
              )}
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#D8D3C3" opacity={0.4} />
                  <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#5C584E" }} stroke="#D8D3C3" />
                  <YAxis
                    domain={[0, 25]}
                    tick={{ fontSize: 11, fill: "#5C584E" }}
                    stroke="#D8D3C3"
                    unit="°C"
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#DFDBCA",
                      borderColor: "#D8D3C3",
                      borderRadius: 0,
                      fontSize: 11,
                      fontFamily: "monospace",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace" }} />
                  {/* Safe Boundaries Reference Lines */}
                  <ReferenceLine
                    y={8.0}
                    label={{ value: "Max Safe Bound (8.0°C)", fill: "#E05252", fontSize: 10, position: "top" }}
                    stroke="#E05252"
                    strokeDasharray="4 4"
                  />
                  <ReferenceLine
                    y={2.0}
                    label={{ value: "Min Safe Bound (2.0°C)", fill: "#00AEBB", fontSize: 10, position: "bottom" }}
                    stroke="#00AEBB"
                    strokeDasharray="4 4"
                  />
                  <Line
                    type="monotone"
                    dataKey="temp"
                    name="Core Sensor (°C)"
                    stroke="#00AEBB"
                    strokeWidth={2.5}
                    dot={{ r: 4, fill: "#00AEBB" }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Mechanical Shock & Humidity */}
          <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-amber-500" />
                  Mechanical Transit Shock (g-force) & Container Humidity (%)
                </h4>
                <p className="text-[11px] text-[var(--text-secondary)]">
                  Shock threshold: Warning at 4.0g • Breach at 8.0g
                </p>
              </div>
            </div>

            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#D8D3C3" opacity={0.4} />
                  <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#5C584E" }} stroke="#D8D3C3" />
                  <YAxis
                    domain={[0, 12]}
                    tick={{ fontSize: 11, fill: "#5C584E" }}
                    stroke="#D8D3C3"
                    unit="g"
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#DFDBCA",
                      borderColor: "#D8D3C3",
                      borderRadius: 0,
                      fontSize: 11,
                      fontFamily: "monospace",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace" }} />
                  <ReferenceLine
                    y={8.0}
                    label={{ value: "Critical Shock Breach (8.0g)", fill: "#E05252", fontSize: 10 }}
                    stroke="#E05252"
                    strokeDasharray="4 4"
                  />
                  <ReferenceLine
                    y={4.0}
                    label={{ value: "Warning Threshold (4.0g)", fill: "#E5A93C", fontSize: 10 }}
                    stroke="#E5A93C"
                    strokeDasharray="4 4"
                  />
                  <Line
                    type="stepAfter"
                    dataKey="shock"
                    name="Mechanical Shock (g)"
                    stroke="#E5A93C"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#E5A93C" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right: Arrhenius Model Card & Batch Inspector (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Arrhenius Shelf-Life Math Card */}
          <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
            <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
              Arrhenius Degradation Model
            </h4>

            <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-2 text-xs font-mono">
              <div className="text-[10px] text-[var(--text-secondary)] leading-tight">
                Formula: <code className="text-[var(--accent-teal)]">k(T) = A • exp(-Ea / (R • T))</code>
              </div>

              <div className="flex justify-between border-b border-[var(--border-subtle)] pb-1.5">
                <span className="text-[var(--text-secondary)]">Nominal Shelf-Life:</span>
                <span className="font-semibold text-[var(--text-primary)]">
                  {activeBatch?.shelf_life_estimate?.nominal_remaining_days || 180} days
                </span>
              </div>

              <div className="flex justify-between border-b border-[var(--border-subtle)] pb-1.5">
                <span className="text-[var(--text-secondary)]">Degradation Incurred:</span>
                <span className="font-semibold text-coral-600">
                  -{(activeBatch?.shelf_life_estimate?.degradation_days || 0).toFixed(1)} days
                </span>
              </div>

              <div className="flex justify-between border-b border-[var(--border-subtle)] pb-1.5">
                <span className="text-[var(--text-secondary)]">Effective Remaining:</span>
                <span className="font-bold text-[var(--text-primary)]">
                  {(activeBatch?.shelf_life_estimate?.estimated_remaining_days || 180).toFixed(1)} days
                </span>
              </div>

              <div className="flex justify-between items-center pt-0.5">
                <span className="text-[var(--text-secondary)]">Potency Status:</span>
                <span
                  className={`font-bold px-1.5 py-0.5 text-[10px] uppercase border ${
                    (activeBatch?.shelf_life_estimate?.shelf_life_pct || 100) > 70
                      ? "bg-teal-50 text-teal-800 border-teal-300 dark:bg-teal-950/40 dark:text-teal-200"
                      : "bg-coral-50 text-coral-800 border-coral-300 dark:bg-coral-950/40 dark:text-coral-200"
                  }`}
                >
                  {activeBatch?.shelf_life_estimate?.decision || "ok"}
                </span>
              </div>
            </div>

            <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
              When ambient exposure exceeds 8.0°C or mechanical shock breaches 8.0g, kinetic acceleration drops
              therapeutic potency below 70%, triggering autonomous quarantine and zeroing retail availability.
            </p>
          </div>

          {/* Raw JSON Inspector */}
          {activeBatch && (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
              <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold">
                Batch IoT Record Inspector
              </h4>
              <JsonViewer data={activeBatch} title="Live Batch Sensor State" defaultExpanded={false} />
            </div>
          )}
        </div>
      </div>

      {/* 5. Quarantine History & Clinical Narrative Feed */}
      <div className="p-5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5">
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-coral-600" />
              Autonomous Quarantine Audit Trail & Excursion Analyst Narratives
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Clinical justification log generated by the Excursion Analyst Agent following thermal breaches.
            </p>
          </div>
          <span className="text-xs font-mono text-[var(--text-secondary)]">
            {quarantines.length} incident(s) recorded
          </span>
        </div>

        {quarantinesLoading ? (
          <div className="text-xs font-mono text-[var(--text-secondary)] p-4 text-center">
            Loading quarantine records...
          </div>
        ) : quarantines.length === 0 ? (
          <div className="p-8 text-center text-xs text-[var(--text-secondary)] bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 opacity-60 mx-auto mb-1.5" />
            <p className="font-semibold text-[var(--text-primary)]">Zero Quarantines Active</p>
            <p className="text-[11px]">All biologics are currently operating within statutory storage boundaries.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {quarantines.map((q) => (
              <div
                key={q.id}
                className="p-3.5 bg-[var(--bg-canvas)] border-l-4 border-l-coral-500 border border-[var(--border-subtle)] space-y-2"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-[var(--text-primary)]">{q.batch_id}</span>
                    <span className="px-1.5 py-0.2 text-[10px] bg-coral-100 text-coral-800 dark:bg-coral-950/60 dark:text-coral-300 font-bold uppercase">
                      QUARANTINED (0 UNITS AVAIL)
                    </span>
                  </div>
                  <span className="text-[11px] text-[var(--text-secondary)] flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(q.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="text-xs text-[var(--text-primary)] leading-relaxed bg-[var(--bg-surface)] p-2.5 border border-[var(--border-subtle)] font-mono">
                  {q.narrative || q.reason || "Autonomous quarantine triggered due to environmental excursion breach."}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-[var(--text-secondary)] pt-1">
                  <span>Action ID: {q.id}</span>
                  {q.rebalance_correlation_id && (
                    <Link
                      to={`/cascade?corr_id=${q.rebalance_correlation_id}`}
                      className="inline-flex items-center gap-1 font-semibold text-[var(--accent-teal)] hover:underline"
                    >
                      🔗 Restock Cascade Rebalancing Trace ({q.rebalance_correlation_id.slice(0, 8)}...)
                      <ArrowRight className="w-3 h-3" />
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
