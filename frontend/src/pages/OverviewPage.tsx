/**
 * Overview Page (/overview)
 * Flagship Network Operations Control Tower:
 * 1. 4 Live KPI Cards (Events Today with SSE pulse, Stockout Risks, Open Approvals, Quarantined Batches)
 * 2. Interactive POS Simulator Control Bar (Sell 1 Strip CTA, Steady, Burst, Stockout)
 * 3. Inventory Table with Search, Tier Filter, Low-Stock Highlighting
 * 4. Real-time Live Event Feed (Merged SSE + Historical with correlation_id deep-links)
 */

import React, { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  Zap,
} from "lucide-react";
import { api } from "../lib/api";
import { useEventStream } from "../hooks/useEventStream";
import type { InventoryItem, NetworkNode, Product, SystemEvent } from "../types/api";

export const OverviewPage: React.FC = () => {
  const inventorySectionRef = useRef<HTMLDivElement>(null);

  // ---------------------------------------------------------------------------
  // State for POS Simulator & Filters
  // ---------------------------------------------------------------------------
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [selectedPharmacyId, setSelectedPharmacyId] = useState<string>("");
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationToast, setSimulationToast] = useState<{
    correlation_id: string;
    mode: string;
    message: string;
  } | null>(null);

  const [inventorySearch, setInventorySearch] = useState<string>("");
  const [showLowStockOnly, setShowLowStockOnly] = useState<boolean>(false);

  // ---------------------------------------------------------------------------
  // Data Queries
  // ---------------------------------------------------------------------------
  const {
    data: kpis,
    isLoading: kpisLoading,
    refetch: refetchKpis,
  } = useQuery({
    queryKey: ["overview-kpis"],
    queryFn: () => api.overview.getKpis(),
    refetchInterval: 10000,
  });

  const {
    data: products = [],
    isLoading: productsLoading,
  } = useQuery({
    queryKey: ["products-list"],
    queryFn: () => api.products.list({ limit: 50 }),
  });

  const {
    data: pharmacyNodes = [],
    isLoading: pharmaciesLoading,
  } = useQuery({
    queryKey: ["pharmacy-nodes"],
    queryFn: () => api.nodes.list({ tier: "pharmacy", limit: 50 }),
  });

  const {
    data: inventoryItems = [],
    isLoading: inventoryLoading,
    refetch: refetchInventory,
  } = useQuery({
    queryKey: ["inventory-list"],
    queryFn: () => api.inventory.list({ limit: 100 }),
    refetchInterval: 15000,
  });

  const {
    data: historicalEvents = [],
    isLoading: eventsLoading,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: ["recent-events"],
    queryFn: () => api.events.list({ limit: 40 }),
  });

  // ---------------------------------------------------------------------------
  // Real-Time SSE Stream Hook
  // ---------------------------------------------------------------------------
  const {
    events: liveStreamEvents,
    connectionState: sseState,
  } = useEventStream({
    topics: ["*"],
    maxEvents: 50,
  });

  // Merge live stream events with historical events (de-duplicated by event_id)
  const mergedEvents = useMemo(() => {
    const seen = new Set<string>();
    const combined: SystemEvent[] = [];

    for (const evt of liveStreamEvents) {
      if (evt.event_id && !seen.has(evt.event_id)) {
        seen.add(evt.event_id);
        combined.push(evt);
      }
    }
    for (const evt of historicalEvents) {
      if (evt.event_id && !seen.has(evt.event_id)) {
        seen.add(evt.event_id);
        combined.push(evt);
      }
    }
    return combined.slice(0, 50);
  }, [liveStreamEvents, historicalEvents]);

  // Set default product and pharmacy once loaded
  React.useEffect(() => {
    if (products.length > 0 && !selectedProductId) {
      setSelectedProductId(products[0].id);
    }
  }, [products, selectedProductId]);

  React.useEffect(() => {
    if (pharmacyNodes.length > 0 && !selectedPharmacyId) {
      setSelectedPharmacyId(pharmacyNodes[0].id);
    }
  }, [pharmacyNodes, selectedPharmacyId]);

  // ---------------------------------------------------------------------------
  // Simulator Trigger Handler
  // ---------------------------------------------------------------------------
  const handleTriggerSimulation = async (
    mode: "single" | "steady" | "burst" | "stockout"
  ) => {
    setIsSimulating(true);
    setSimulationToast(null);

    try {
      const res = await api.simulator.triggerPos({
        mode,
        product_id: selectedProductId || undefined,
        pharmacy_id: selectedPharmacyId || undefined,
        quantity: mode === "single" ? 1 : mode === "stockout" ? 25 : undefined,
      });

      const modeLabels: Record<string, string> = {
        single: "Single strip POS sale registered. 4-tier demand cascade propagating...",
        steady: "Steady POS stream active. Sequential cascades propagating...",
        burst: "Demand spike burst initiated. Multiple concurrent cascades propagating...",
        stockout: "Stockout threshold breached. Emergency replenishment cascade propagating...",
      };

      setSimulationToast({
        correlation_id: res.correlation_id,
        mode,
        message: modeLabels[mode] || "Demand cascade initiated.",
      });

      // Refresh KPIs and events after trigger
      setTimeout(() => {
        refetchKpis();
        refetchInventory();
        refetchEvents();
      }, 1200);
    } catch (err: any) {
      setSimulationToast({
        correlation_id: "",
        mode,
        message: `Simulation error: ${err.message || "Failed to trigger cascade"}`,
      });
    } finally {
      setIsSimulating(false);
    }
  };

  // Scroll to inventory and filter low stock
  const handleStockoutCardClick = () => {
    setShowLowStockOnly(true);
    if (inventorySectionRef.current) {
      inventorySectionRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  // ---------------------------------------------------------------------------
  // Filtered Inventory
  // ---------------------------------------------------------------------------
  const filteredInventory = useMemo(() => {
    return inventoryItems.filter((item: InventoryItem) => {
      const available = item.quantity_on_hand ?? 0;
      const safety = item.safety_stock ?? 0;
      const isLowStock = available <= safety;

      if (showLowStockOnly && !isLowStock) {
        return false;
      }

      const q = inventorySearch.toLowerCase();
      const productName = (item.products?.name || "").toLowerCase();
      const productSku = (item.products?.sku || "").toLowerCase();
      const batchNo = (item.batches?.batch_number || item.batch_id || "").toLowerCase();
      const nodeId = (item.node_id || "").toLowerCase();

      const matchesSearch =
        !q ||
        productName.includes(q) ||
        productSku.includes(q) ||
        batchNo.includes(q) ||
        nodeId.includes(q);

      return matchesSearch;
    });
  }, [inventoryItems, showLowStockOnly, inventorySearch]);

  const handleRefreshAll = () => {
    refetchKpis();
    refetchInventory();
    refetchEvents();
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-serif font-bold text-[var(--ink)] tracking-tight">
              Network Operations Control Tower
            </h1>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-medium border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink-secondary)]">
              4-TIER CASCS
            </span>
          </div>
          <p className="text-xs text-[var(--ink-secondary)] mt-1">
            Real-time single-unit demand propagation, inventory balance, and autonomous agent coordination.
          </p>
        </div>

        <div className="flex items-center gap-3 self-start sm:self-auto">
          {/* Live SSE Status Pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] text-[var(--ink-secondary)]">
            <span
              className={`w-2 h-2 rounded-full ${
                sseState === "connected"
                  ? "bg-emerald-500 animate-pulse"
                  : "bg-amber-500"
              }`}
            />
            <span className="capitalize">{sseState}</span>
          </div>

          <button
            type="button"
            onClick={handleRefreshAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--canvas-elevated)] text-[var(--ink)] transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Sync
          </button>
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* Section 1: POS Demand Simulator Control Bar                            */}
      {/* --------------------------------------------------------------------- */}
      <div className="editorial-card p-4 sm:p-5 border border-[var(--border)] bg-[var(--surface)] space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#00AEBB]" />
              <span className="text-xs font-mono uppercase tracking-wider text-[var(--ink-secondary)] font-semibold">
                Autonomous Demand Propagation Simulator
              </span>
            </div>
            <p className="text-xs text-[var(--ink-secondary)]">
              Simulate retail counter transactions to trigger deterministic multi-tier LangGraph cascades.
            </p>
          </div>

          {/* Target Selectors */}
          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="text-[var(--ink-muted)]">Pharmacy:</span>
              <select
                aria-label="Pharmacy Node Selector"
                value={selectedPharmacyId}
                onChange={(e) => setSelectedPharmacyId(e.target.value)}
                disabled={isSimulating || pharmaciesLoading}
                className="px-2.5 py-1.5 border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs focus:outline-none focus:border-[#00AEBB]"
              >
                {pharmacyNodes.map((n: NetworkNode) => (
                  <option key={n.id} value={n.id}>
                    {n.name} ({n.city})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[var(--ink-muted)]">Product:</span>
              <select
                aria-label="Product Selector"
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(e.target.value)}
                disabled={isSimulating || productsLoading}
                className="px-2.5 py-1.5 border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] text-xs focus:outline-none focus:border-[#00AEBB]"
              >
                {products.map((p: Product) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Simulator Action Buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[var(--border-subtle)]">
          {/* Primary CTA: Sell 1 Strip */}
          <button
            type="button"
            onClick={() => handleTriggerSimulation("single")}
            disabled={isSimulating}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-mono font-semibold bg-[#00AEBB] text-black hover:bg-[#009da9] active:translate-y-px transition-all shadow-sm disabled:opacity-50"
          >
            <Zap className="w-3.5 h-3.5 fill-black" />
            Sell 1 Strip
          </button>

          {/* Secondary CTA: Steady Traffic */}
          <button
            type="button"
            onClick={() => handleTriggerSimulation("steady")}
            disabled={isSimulating}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--canvas-elevated)] text-[var(--ink)] transition-colors disabled:opacity-50"
          >
            Steady Traffic
          </button>

          {/* Secondary CTA: Burst Spike */}
          <button
            type="button"
            onClick={() => handleTriggerSimulation("burst")}
            disabled={isSimulating}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--canvas-elevated)] text-[var(--ink)] transition-colors disabled:opacity-50"
          >
            Burst Spike
          </button>

          {/* Secondary CTA: Trigger Stockout */}
          <button
            type="button"
            onClick={() => handleTriggerSimulation("stockout")}
            disabled={isSimulating}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-mono border border-amber-500/40 bg-amber-500/5 hover:bg-amber-500/10 text-amber-700 dark:text-amber-400 transition-colors disabled:opacity-50"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            Trigger Stockout
          </button>

          {isSimulating && (
            <span className="text-xs font-mono text-[var(--ink-secondary)] animate-pulse flex items-center gap-1.5 ml-2">
              <RefreshCw className="w-3 h-3 animate-spin text-[#00AEBB]" />
              Executing 4-tier cascade...
            </span>
          )}
        </div>

        {/* Simulation Feedback Banner */}
        {simulationToast && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 border border-[#00AEBB]/40 bg-[#00AEBB]/5 text-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#00AEBB] shrink-0" />
              <div>
                <span className="font-semibold text-[var(--ink)]">{simulationToast.message}</span>
                {simulationToast.correlation_id && (
                  <span className="ml-2 font-mono text-[11px] text-[var(--ink-secondary)]">
                    Correlation ID: {simulationToast.correlation_id}
                  </span>
                )}
              </div>
            </div>

            {simulationToast.correlation_id && (
              <Link
                to={`/cascade?correlation_id=${simulationToast.correlation_id}`}
                className="inline-flex items-center gap-1 font-mono font-medium text-black bg-[#00AEBB] hover:bg-[#009da9] px-2.5 py-1 text-xs transition-colors shrink-0"
              >
                Watch Cascade Replay <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>
        )}
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* Section 2: 4 Live KPI Cards                                           */}
      {/* --------------------------------------------------------------------- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Events Today */}
        <div className="editorial-card p-4 border border-[var(--border)] bg-[var(--surface)] space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-[var(--ink-secondary)]">
            <span className="uppercase tracking-wider">Events Today</span>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#00AEBB] animate-ping" />
              <Radio className="w-3.5 h-3.5 text-[#00AEBB]" />
            </div>
          </div>
          <div className="text-3xl font-serif font-bold text-[var(--ink)]">
            {kpisLoading ? "—" : kpis?.events_today?.toLocaleString() ?? 0}
          </div>
          <div className="text-[11px] font-mono text-[var(--ink-muted)] flex items-center gap-1">
            <span>{kpis?.total_events?.toLocaleString() ?? 0} total events logged</span>
          </div>
        </div>

        {/* KPI 2: Stockout Risks (Clickable) */}
        <button
          type="button"
          onClick={handleStockoutCardClick}
          className="editorial-card p-4 border border-[var(--border)] bg-[var(--surface)] text-left hover:border-amber-500/60 transition-all space-y-2 group"
        >
          <div className="flex items-center justify-between text-xs font-mono text-[var(--ink-secondary)]">
            <span className="uppercase tracking-wider">Stockout Risks</span>
            <AlertCircle className="w-3.5 h-3.5 text-amber-500 group-hover:scale-110 transition-transform" />
          </div>
          <div className="text-3xl font-serif font-bold text-amber-600 dark:text-amber-400">
            {kpisLoading ? "—" : kpis?.stockout_risks ?? 0}
          </div>
          <div className="text-[11px] font-mono text-[var(--ink-muted)] flex items-center justify-between">
            <span>≤ Safety stock limit</span>
            <span className="text-[#00AEBB] group-hover:underline">Filter table ↓</span>
          </div>
        </button>

        {/* KPI 3: Open Approvals (Clickable) */}
        <Link
          to="/approvals"
          className="editorial-card p-4 border border-[var(--border)] bg-[var(--surface)] text-left hover:border-[#00AEBB]/60 transition-all space-y-2 group block"
        >
          <div className="flex items-center justify-between text-xs font-mono text-[var(--ink-secondary)]">
            <span className="uppercase tracking-wider">Open Approvals</span>
            <Clock className="w-3.5 h-3.5 text-[#00AEBB] group-hover:scale-110 transition-transform" />
          </div>
          <div className="text-3xl font-serif font-bold text-[var(--ink)]">
            {kpisLoading ? "—" : kpis?.open_approvals ?? 0}
          </div>
          <div className="text-[11px] font-mono text-[var(--ink-muted)] flex items-center justify-between">
            <span>Pending HITL decisions</span>
            <span className="text-[#00AEBB] group-hover:underline">View queue →</span>
          </div>
        </Link>

        {/* KPI 4: Quarantined Batches (Clickable) */}
        <Link
          to="/cold-chain"
          className="editorial-card p-4 border border-[var(--border)] bg-[var(--surface)] text-left hover:border-rose-500/60 transition-all space-y-2 group block"
        >
          <div className="flex items-center justify-between text-xs font-mono text-[var(--ink-secondary)]">
            <span className="uppercase tracking-wider">Quarantined Batches</span>
            <ShieldAlert className="w-3.5 h-3.5 text-rose-500 group-hover:scale-110 transition-transform" />
          </div>
          <div className="text-3xl font-serif font-bold text-rose-600 dark:text-rose-400">
            {kpisLoading ? "—" : kpis?.quarantined_batches ?? 0}
          </div>
          <div className="text-[11px] font-mono text-[var(--ink-muted)] flex items-center justify-between">
            <span>Excursions & compliance holds</span>
            <span className="text-[#00AEBB] group-hover:underline">Cold-chain →</span>
          </div>
        </Link>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* Section 3: Split Grid (Inventory Table & Live Event Feed)             */}
      {/* --------------------------------------------------------------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Inventory Table (7 cols) */}
        <div
          ref={inventorySectionRef}
          className="lg:col-span-7 editorial-card border border-[var(--border)] bg-[var(--surface)] overflow-hidden"
        >
          {/* Header & Controls */}
          <div className="p-4 border-b border-[var(--border-subtle)] space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-serif font-bold text-[var(--ink)]">
                  Network Inventory Positions
                </h2>
                <p className="text-xs text-[var(--ink-secondary)]">
                  Live stock records across retail pharmacy, stockist, and distributor facilities.
                </p>
              </div>

              <span className="text-xs font-mono text-[var(--ink-muted)]">
                {filteredInventory.length} items
              </span>
            </div>

            {/* Filter Bar */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[180px]">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-muted)]" />
                <input
                  type="text"
                  placeholder="Search product, SKU, batch..."
                  value={inventorySearch}
                  onChange={(e) => setInventorySearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs font-mono border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:border-[#00AEBB]"
                />
              </div>

              {/* Show Low Stock Only Toggle */}
              <button
                type="button"
                onClick={() => setShowLowStockOnly(!showLowStockOnly)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border transition-colors ${
                  showLowStockOnly
                    ? "border-amber-500 bg-amber-500/10 text-amber-700 dark:text-amber-400 font-semibold"
                    : "border-[var(--border)] bg-[var(--surface)] text-[var(--ink-secondary)] hover:text-[var(--ink)]"
                }`}
              >
                <AlertTriangle className="w-3 h-3 text-amber-500" />
                Low Stock Only {kpis?.stockout_risks ? `(${kpis.stockout_risks})` : ""}
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto max-h-[520px]">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 bg-[var(--surface-muted)] border-b border-[var(--border)] text-[var(--ink-secondary)] font-mono text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3">Product / SKU</th>
                  <th className="py-2.5 px-3">Facility</th>
                  <th className="py-2.5 px-3">Batch</th>
                  <th className="py-2.5 px-3 text-right">Available</th>
                  <th className="py-2.5 px-3 text-right">Safety</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)] font-mono">
                {inventoryLoading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[var(--ink-muted)]">
                      Loading inventory telemetry...
                    </td>
                  </tr>
                ) : filteredInventory.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[var(--ink-muted)]">
                      No inventory records match filters.
                    </td>
                  </tr>
                ) : (
                  filteredInventory.map((item: InventoryItem) => {
                    const available = item.quantity_on_hand ?? 0;
                    const safety = item.safety_stock ?? 0;
                    const isLowStock = available <= safety;
                    const productName = item.products?.name || "Pharmaceutical Item";
                    const productSku = item.products?.sku || "MED-SKU";
                    const batchNumber = item.batches?.batch_number || item.batch_id || "B-INIT";

                    return (
                      <tr
                        key={item.id}
                        className={`transition-colors hover:bg-[var(--canvas-elevated)] ${
                          isLowStock
                            ? "bg-amber-500/5 border-l-4 border-l-amber-500 dark:bg-amber-950/15"
                            : ""
                        }`}
                      >
                        <td className="py-2.5 px-3">
                          <div className="font-sans font-semibold text-[var(--ink)]">
                            {productName}
                          </div>
                          <div className="text-[10px] text-[var(--ink-muted)]">{productSku}</div>
                        </td>
                        <td className="py-2.5 px-3 text-[var(--ink-secondary)]">
                          <div className="truncate max-w-[130px] font-sans">
                            {item.node_id.slice(0, 8)}...
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-[var(--ink-secondary)]">
                          {batchNumber}
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-[var(--ink)]">
                          {available.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-right text-[var(--ink-muted)]">
                          {safety.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3">
                          {isLowStock ? (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono font-semibold bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-500/40">
                              <AlertCircle className="w-2.5 h-2.5" />
                              LOW STOCK
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                              OPTIMAL
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Live Event Feed (5 cols) */}
        <div className="lg:col-span-5 editorial-card border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-[#00AEBB]" />
              <h2 className="text-base font-serif font-bold text-[var(--ink)]">
                Live Event Feed
              </h2>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-[var(--ink-muted)]">
              <span>{mergedEvents.length} events</span>
            </div>
          </div>

          {/* Events List */}
          <div className="divide-y divide-[var(--border-subtle)] max-h-[520px] overflow-y-auto">
            {eventsLoading && mergedEvents.length === 0 ? (
              <div className="py-8 text-center text-xs font-mono text-[var(--ink-muted)]">
                Listening for events...
              </div>
            ) : mergedEvents.length === 0 ? (
              <div className="py-8 text-center text-xs font-mono text-[var(--ink-muted)]">
                No events streamed yet. Click "Sell 1 Strip" above to generate a cascade!
              </div>
            ) : (
              mergedEvents.map((evt: SystemEvent, idx: number) => {
                const corrId = evt.correlation_id;
                const formattedTime = evt.timestamp
                  ? new Date(evt.timestamp).toLocaleTimeString()
                  : "Now";
                const payloadSummary =
                  evt.payload?.medicine_name ||
                  evt.payload?.summary ||
                  evt.payload?.details ||
                  JSON.stringify(evt.payload || {}).slice(0, 70);

                return (
                  <div
                    key={evt.event_id || `${evt.correlation_id}-${idx}`}
                    className="p-3 hover:bg-[var(--canvas-elevated)] transition-colors space-y-1.5 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[10px] px-1.5 py-0.5 border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink)] font-semibold uppercase">
                          {evt.type}
                        </span>
                        {corrId && (
                          <Link
                            to={`/cascade?correlation_id=${corrId}`}
                            className="font-mono text-[10px] text-[#00AEBB] hover:underline flex items-center gap-0.5"
                            title="Replay in Cascade"
                          >
                            <span>{corrId.slice(0, 10)}...</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </Link>
                        )}
                      </div>

                      <span className="font-mono text-[10px] text-[var(--ink-muted)]">
                        {formattedTime}
                      </span>
                    </div>

                    <p className="text-[var(--ink-secondary)] text-xs line-clamp-2">
                      {payloadSummary}
                    </p>
                  </div>
                );
              })
            )}
          </div>

          <div className="p-2.5 border-t border-[var(--border-subtle)] bg-[var(--surface-muted)] text-center">
            <Link
              to="/cascade"
              className="text-xs font-mono text-[#00AEBB] hover:underline inline-flex items-center gap-1"
            >
              Open Full Cascade Studio <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
