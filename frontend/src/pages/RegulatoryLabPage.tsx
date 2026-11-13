/**
 * Regulatory Hot-Swap Lab Page (/regulatory-lab)
 * Autonomous CDSCO & NPPA notification ingestion, 5-stage hot-swap pipeline tracker,
 * side-by-side AST code diff viewer, and live before/after DPCO price-check sandbox.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  RefreshCw,
  Scale,
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  FileCode,
  ShieldCheck,
  Play,
  TrendingDown,
} from "lucide-react";
import { api } from "../lib/api";
import { StatusBadge } from "../components/shared/StatusBadge";
import type { RegulatoryFixture, RegulatoryRun, PriceCheckResult } from "../types/api";

export const RegulatoryLabPage: React.FC = () => {
  // Studio Inputs
  const [noticeTitle, setNoticeTitle] = useState<string>(
    "NPPA Notification SO 1421(E) - Ceiling Price Revision for Paracetamol 500mg"
  );
  const [noticeSource, setNoticeSource] = useState<string>("NPPA / Ministry of Chemicals & Fertilizers");
  const [noticeText, setNoticeText] = useState<string>(
    "MINISTRY OF CHEMICALS AND FERTILIZERS\n(National Pharmaceutical Pricing Authority)\nORDER\nNew Delhi, 13th November, 2026\n\nS.O. 1421(E). In exercise of powers conferred by paragraphs 4, 11 and 14 of the Drugs (Prices Control) Order, 2013 (DPCO 2013), the National Pharmaceutical Pricing Authority hereby fixes the ceiling price for Paracetamol 500mg Formulation (SKU: PARA-500) at INR 12.50 per unit.\n\nAll manufacturers and distributors are instructed to apply this revised ceiling price with immediate effect. Non-compliance will invite penalty under the Essential Commodities Act, 1955."
  );

  // Active Pipeline State
  const [isProcessingPipeline, setIsProcessingPipeline] = useState<boolean>(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<RegulatoryRun | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // Gate Approval & Rollback State
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [isRollingBack, setIsRollingBack] = useState<boolean>(false);

  // Price Sandbox State
  const [testSku, setTestSku] = useState<string>("PARA-500");
  const [testUnitPrice, setTestUnitPrice] = useState<number>(25.0);
  const [testQuantity, setTestQuantity] = useState<number>(10);
  const [isTestingPrice, setIsTestingPrice] = useState<boolean>(false);
  const [priceCheckResult, setPriceCheckResult] = useState<PriceCheckResult | null>(null);

  // Queries
  const { data: fixtures = [] } = useQuery<RegulatoryFixture[]>({
    queryKey: ["regulatory-fixtures"],
    queryFn: () => api.regulatory.getFixtures(),
  });

  const { data: pastRuns = [], refetch: refetchRuns } = useQuery<RegulatoryRun[]>({
    queryKey: ["regulatory-runs"],
    queryFn: async () => {
      const list = await api.regulatory.listRuns();
      if (list.length > 0 && !activeRunId) {
        setActiveRunId(list[0].id);
        setActiveRun(list[0]);
      }
      return list;
    },
  });

  // Handle Preset Fixture Selection
  const handleSelectFixture = (f: RegulatoryFixture) => {
    setNoticeTitle(f.title);
    setNoticeSource(f.source);
    setNoticeText(f.raw_text);
    if (f.test_payload) {
      setTestSku(f.test_payload.sku);
      setTestUnitPrice(f.test_payload.unit_price);
      setTestQuantity(f.test_payload.quantity);
    }
  };

  // Run Pipeline
  const handleRunPipeline = async () => {
    setIsProcessingPipeline(true);
    setPipelineError(null);
    try {
      const res = await api.regulatory.ingestNotice({
        title: noticeTitle,
        source: noticeSource,
        text: noticeText,
      });

      setActiveRunId(res.run_id);
      const run = await api.regulatory.getRun(res.run_id);
      setActiveRun(run);
      refetchRuns();
    } catch (err: any) {
      setPipelineError(err.message || "Failed running regulatory pipeline");
    } finally {
      setIsProcessingPipeline(false);
    }
  };

  // Approve Gate
  const handleApproveGate = async () => {
    if (!activeRunId) return;
    setIsApproving(true);
    try {
      await api.regulatory.approveRun(activeRunId);
      const updated = await api.regulatory.getRun(activeRunId);
      setActiveRun(updated);
      refetchRuns();
      // Automatically run price check to demonstrate hot-swap!
      handleRunPriceCheck();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setIsApproving(false);
    }
  };

  // Rollback Module
  const handleRollback = async () => {
    if (!activeRunId) return;
    setIsRollingBack(true);
    try {
      await api.regulatory.rollbackRun(activeRunId);
      const updated = await api.regulatory.getRun(activeRunId);
      setActiveRun(updated);
      refetchRuns();
      // Run price check to show rollback!
      handleRunPriceCheck();
    } catch (err: any) {
      alert(`Rollback failed: ${err.message}`);
    } finally {
      setIsRollingBack(false);
    }
  };

  // Run Live Price Sandbox Check
  const handleRunPriceCheck = async () => {
    setIsTestingPrice(true);
    try {
      const res = await api.regulatory.priceCheck({
        sku: testSku,
        unit_price: testUnitPrice,
        quantity: testQuantity,
        drug_name: "Paracetamol 500mg",
      });
      setPriceCheckResult(res);
    } catch (err: any) {
      console.error("Price check failed:", err);
    } finally {
      setIsTestingPrice(false);
    }
  };

  // Select historical run
  const handleSelectRun = async (runId: string) => {
    setActiveRunId(runId);
    try {
      const run = await api.regulatory.getRun(runId);
      setActiveRun(run);
    } catch (err: any) {
      console.error("Error fetching run:", err);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
              Regulatory Hot-Swap Lab & Policy Engine
            </h2>
            <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-[var(--accent-teal)]/10 text-[var(--accent-teal)] border border-[var(--accent-teal)]/30 font-semibold">
              Zero Downtime
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Autonomous CDSCO & NPPA gazette parsing, multi-agent code compilation, staging verification, and instant dynamic rule hot-swapping.
          </p>
        </div>

        <button
          type="button"
          onClick={() => refetchRuns()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Runs
        </button>
      </div>

      {/* SECTION 1: Notice Ingestion Studio */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-3 border-b border-[var(--border-subtle)]">
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Scale className="w-4 h-4 text-[var(--accent-teal)]" />
              <span>Gazette Directive Ingestion Studio</span>
            </h3>
            <p className="text-xs text-[var(--text-secondary)]">
              Paste or load statutory regulatory notifications to trigger autonomous analysis and hot-swap pipeline.
            </p>
          </div>

          {/* Synthetic presets pills */}
          {fixtures.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] font-mono text-[var(--text-secondary)] uppercase">Presets:</span>
              {fixtures.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => handleSelectFixture(f)}
                  className="px-2.5 py-1 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-canvas)] hover:border-[var(--accent-teal)] text-[var(--text-primary)] transition-all"
                >
                  {f.title.includes("Ceiling") ? "NPPA DPCO Price Cap" : "CDSCO Track & Trace"}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
                Directive Gazette Title
              </label>
              <input
                type="text"
                value={noticeTitle}
                onChange={(e) => setNoticeTitle(e.target.value)}
                className="w-full p-2 text-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
                Issuing Regulatory Authority
              </label>
              <input
                type="text"
                value={noticeSource}
                onChange={(e) => setNoticeSource(e.target.value)}
                className="w-full p-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
              Statutory Gazette Notification Text
            </label>
            <textarea
              value={noticeText}
              onChange={(e) => setNoticeText(e.target.value)}
              rows={5}
              className="w-full p-2 font-mono text-[11px] bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] resize-none"
            />
          </div>
        </div>

        <div className="pt-2 flex items-center justify-between border-t border-[var(--border-subtle)]">
          <div className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-[var(--accent-teal)]" />
            <span>Zero downtime in-process reload: existing threads remain uninterrupted</span>
          </div>

          <button
            type="button"
            disabled={isProcessingPipeline}
            onClick={handleRunPipeline}
            className="px-4 py-2 text-xs font-semibold bg-[var(--accent-teal)] text-white hover:opacity-90 transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {isProcessingPipeline ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Zap className="w-3.5 h-3.5" />
            )}
            <span>🧬 Run Regulatory Pipeline</span>
          </button>
        </div>

        {pipelineError && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-800 dark:text-rose-200 text-xs flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-500" />
            <span>{pipelineError}</span>
          </div>
        )}
      </div>

      {/* SECTION 2: 5-Stage Visual Pipeline Tracker */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs text-[var(--accent-teal)] uppercase font-semibold">
              Pipeline Run: {activeRun ? activeRun.id : "No Active Run"}
            </span>
            {activeRun && <StatusBadge status={activeRun.status} size="sm" />}
            {pastRuns.length > 1 && (
              <select
                value={activeRunId || ""}
                onChange={(e) => handleSelectRun(e.target.value)}
                className="px-2 py-0.5 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
              >
                {pastRuns.map((r) => (
                  <option key={r.id} value={r.id}>
                    Run {r.id.slice(0, 10)}... ({r.status})
                  </option>
                ))}
              </select>
            )}
          </div>

          {activeRun && (
            <div className="flex items-center gap-2">
              {/* Approval Button in gate stage */}
              {(activeRun.status === "awaiting_approval" || activeRun.status === "staged") && (
                <button
                  type="button"
                  disabled={isApproving}
                  onClick={handleApproveGate}
                  className="px-3 py-1.5 text-xs font-semibold bg-[var(--accent-teal)] text-white hover:opacity-90 flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{isApproving ? "Hot-Swapping..." : "✓ Approve Gate & Hot-Swap Now"}</span>
                </button>
              )}

              {/* Rollback button if deployed */}
              {activeRun.status === "deployed" && (
                <button
                  type="button"
                  disabled={isRollingBack}
                  onClick={handleRollback}
                  className="px-3 py-1.5 text-xs font-mono border border-amber-500/40 text-amber-700 dark:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>{isRollingBack ? "Rolling Back..." : "⏪ Rollback to v1"}</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* 5 Stages Tracker Grid */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {[
            {
              id: "analyst",
              stepNum: 1,
              title: "Regulatory Analyst",
              desc: "Extracts rules, SKU, and ceiling limits",
              isDone: !!activeRun,
            },
            {
              id: "coder",
              stepNum: 2,
              title: "DevOps Coder",
              desc: "Synthesizes Python module pricing_engine v2",
              isDone: !!activeRun,
            },
            {
              id: "guard",
              stepNum: 3,
              title: "Staging Guard",
              desc: "AST security analysis & compliance tests",
              isDone: !!activeRun,
            },
            {
              id: "gate",
              stepNum: 4,
              title: "Human Approval Gate",
              desc: "Statutory sign-off requirement",
              isDone: activeRun?.status === "deployed",
              isPending: activeRun?.status === "awaiting_approval" || activeRun?.status === "staged",
            },
            {
              id: "deploy",
              stepNum: 5,
              title: "Hot-Swap Active",
              desc: "Zero-downtime in-process registry update",
              isDone: activeRun?.status === "deployed",
            },
          ].map((stage) => {
            const isCompleted = stage.isDone;
            const isAwaiting = stage.isPending;

            return (
              <div
                key={stage.id}
                className={`p-3 border space-y-1 transition-all ${
                  isCompleted
                    ? "bg-teal-500/5 border-teal-500/30"
                    : isAwaiting
                    ? "bg-amber-500/5 border-amber-500/40 animate-pulse"
                    : "bg-[var(--bg-canvas)] border-[var(--border-subtle)] opacity-70"
                }`}
              >
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-[var(--text-primary)]">
                    {stage.stepNum}. {stage.title}
                  </span>
                  {isCompleted ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                  ) : isAwaiting ? (
                    <Clock className="w-3.5 h-3.5 text-amber-500" />
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-[var(--border-subtle)]" />
                  )}
                </div>
                <div className="text-[10px] text-[var(--text-secondary)]">{stage.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* SECTION 3: Side-by-Side Diff Viewer */}
      {activeRun && (
        <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
            <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
              <FileCode className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
              <span>Side-by-Side Code Diff: Module '{activeRun.target_module_name || "pricing_engine"}'</span>
            </h3>
            <span className="text-[10px] font-mono text-[var(--text-secondary)]">
              AST Compiled Python
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
            {/* Old Code (v1) */}
            <div className="space-y-1">
              <div className="flex items-center justify-between p-2 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[11px]">
                <span className="font-semibold text-[var(--text-secondary)]">
                  Active v1 (Uncapped Baseline)
                </span>
                <span className="text-[10px] text-rose-500">No DPCO Ceiling</span>
              </div>
              <pre className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[10px] text-[var(--text-primary)] max-h-60 overflow-auto leading-relaxed">
                {activeRun.old_source_code ||
                  `# pricing_engine v1 (Baseline)
def calculate_price(sku: str, unit_price: float, quantity: int) -> dict:
    # Baseline: no regulatory price caps applied
    return {
        "sku": sku,
        "unit_price": unit_price,
        "effective_price": unit_price,
        "total_amount": round(unit_price * quantity, 2),
        "price_capped": False,
        "ceiling_applied": None,
    }`}
              </pre>
            </div>

            {/* New Code (v2) */}
            <div className="space-y-1">
              <div className="flex items-center justify-between p-2 bg-teal-500/10 border border-teal-500/30 text-[11px]">
                <span className="font-semibold text-teal-800 dark:text-teal-200">
                  Staged v2 (NPPA SO 1421(E) Compliant)
                </span>
                <span className="text-[10px] text-[var(--accent-teal)] font-bold">
                  DPCO Cap ₹12.50 Enforced
                </span>
              </div>
              <pre className="p-3 bg-teal-500/5 border border-teal-500/20 text-[10px] text-[var(--text-primary)] max-h-60 overflow-auto leading-relaxed">
                {activeRun.new_source_code ||
                  `# pricing_engine v2 (NPPA SO 1421(E))
def calculate_price(sku: str, unit_price: float, quantity: int) -> dict:
    CEILING_PRICES = {"PARA-500": 12.50}
    ceiling = CEILING_PRICES.get(sku)
    effective_price = unit_price
    price_capped = False
    if ceiling is not None and unit_price > ceiling:
        effective_price = ceiling
        price_capped = True
    return {
        "sku": sku,
        "unit_price": unit_price,
        "effective_price": effective_price,
        "total_amount": round(effective_price * quantity, 2),
        "price_capped": price_capped,
        "ceiling_applied": ceiling if price_capped else None,
    }`}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 4: Interactive Before / After Rule Test Sandbox */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[var(--border-subtle)]">
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Zap className="w-4 h-4 text-[var(--accent-teal)]" />
              <span>Live Hot-Swap Verification Sandbox (Before vs After Test)</span>
            </h3>
            <p className="text-xs text-[var(--text-secondary)]">
              Send an order payload directly to the live <code className="font-mono text-[var(--accent-teal)]">POST /api/v1/regulatory/price-check</code> engine to verify if the NPPA ₹12.50 ceiling is enforced.
            </p>
          </div>

          <button
            type="button"
            disabled={isTestingPrice}
            onClick={handleRunPriceCheck}
            className="px-4 py-2 text-xs font-semibold bg-[var(--accent-teal)] text-white hover:opacity-90 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            {isTestingPrice ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            <span>⚡ Test Live Rule Engine</span>
          </button>
        </div>

        {/* Input Parameters */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
              Medicine SKU:
            </label>
            <input
              type="text"
              value={testSku}
              onChange={(e) => setTestSku(e.target.value)}
              className="w-full p-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
              Offered Retail Price (₹):
            </label>
            <input
              type="number"
              step="0.5"
              value={testUnitPrice}
              onChange={(e) => setTestUnitPrice(parseFloat(e.target.value) || 0)}
              className="w-full p-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
              Quantity (Strips):
            </label>
            <input
              type="number"
              value={testQuantity}
              onChange={(e) => setTestQuantity(parseInt(e.target.value, 10) || 1)}
              className="w-full p-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
            />
          </div>
        </div>

        {/* Results Card */}
        {priceCheckResult ? (
          <div className="p-4 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                  Live Rule Engine Evaluation:
                </span>
                <span className="px-2 py-0.5 text-[10px] font-mono bg-[var(--bg-surface)] border border-[var(--border-subtle)]">
                  Active Module Version: v{priceCheckResult.active_version}
                </span>
              </div>
              <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                Evaluated: {new Date(priceCheckResult.evaluated_at).toLocaleTimeString()}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Unit Price */}
              <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
                <div className="text-[10px] font-mono uppercase text-[var(--text-secondary)]">
                  Input Price vs Effective Price
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-base font-bold text-[var(--text-primary)]">
                    ₹{priceCheckResult.output.effective_price.toFixed(2)}
                  </span>
                  {priceCheckResult.output.price_capped && (
                    <span className="text-xs line-through text-[var(--text-secondary)]">
                      ₹{priceCheckResult.output.unit_price.toFixed(2)}
                    </span>
                  )}
                </div>
                {priceCheckResult.output.price_capped && (
                  <div className="text-[10px] font-mono text-[var(--accent-teal)] font-semibold flex items-center gap-1">
                    <TrendingDown className="w-3 h-3" />
                    <span>NPPA Ceiling ₹{priceCheckResult.output.ceiling_applied} Enforced</span>
                  </div>
                )}
              </div>

              {/* Total Calculation */}
              <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
                <div className="text-[10px] font-mono uppercase text-[var(--text-secondary)]">
                  Total Billable ({priceCheckResult.input.quantity} strips)
                </div>
                <div className="text-base font-bold text-[var(--text-primary)]">
                  ₹{priceCheckResult.output.total_amount.toFixed(2)}
                </div>
                <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                  {priceCheckResult.output.price_capped
                    ? `Saved ₹${((priceCheckResult.input.unit_price - priceCheckResult.output.effective_price) * priceCheckResult.input.quantity).toFixed(2)} for patient`
                    : "Standard uncapped rate"}
                </div>
              </div>

              {/* Compliance Status */}
              <div
                className={`p-3 border space-y-1 ${
                  priceCheckResult.output.price_capped
                    ? "bg-teal-500/10 border-teal-500/40 text-teal-900 dark:text-teal-100"
                    : "bg-stone-500/5 border-stone-500/20 text-stone-800 dark:text-stone-200"
                }`}
              >
                <div className="text-[10px] font-mono uppercase text-[var(--text-secondary)]">
                  Compliance Status
                </div>
                <div className="text-sm font-bold flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-[var(--accent-teal)]" />
                  <span>
                    {priceCheckResult.active_version >= 2
                      ? "HOT-SWAP ACTIVE: DPCO CAPPED"
                      : "BASELINE ACTIVE: UNCAPPED"}
                  </span>
                </div>
                <div className="text-[10px] font-mono opacity-80">
                  {priceCheckResult.active_version >= 2
                    ? "Module v2 applied without backend reload"
                    : "Click 'Approve Gate & Hot-Swap Now' above to hot-swap to v2"}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
            Click "⚡ Test Live Rule Engine" to verify live pricing enforcement before and after regulatory approval.
          </div>
        )}
      </div>
    </div>
  );
};
