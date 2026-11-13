/**
 * Adapter Forge Page (/adapter-forge)
 * Self-evolving Python AST-guarded translators adapting Marg, Tally, SAP, and legacy formats.
 * Includes Generator Studio, Step Progress Tracker, Adapter Registry with Rollback,
 * and "Try It Live" Live Ingestion Sandbox.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Code2,
  RefreshCw,
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  ShieldCheck,
  Terminal,
  Send,
  Layers,
} from "lucide-react";
import { api } from "../lib/api";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { Adapter, AdapterFixture, AdapterGenerationJob } from "../types/api";

export const AdapterForgePage: React.FC = () => {
  // Studio inputs
  const [adapterName, setAdapterName] = useState<string>("Marg POS Retail Ingestion");
  const [targetSchema, setTargetSchema] = useState<string>("SaleEvent");
  const [samplePayload, setSamplePayload] = useState<string>(
    'timestamp,store_code,sku,qty,price\n2026-11-13T10:00:00Z,PHARM-001,PARA-500,2,15.50'
  );
  const [expectedOutput, setExpectedOutput] = useState<string>(
    '{\n  "event_type": "pos_sale",\n  "product_id": "PARA-500",\n  "quantity": 2,\n  "unit_price": 15.50\n}'
  );

  // Generation state
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [activeJob, setActiveJob] = useState<AdapterGenerationJob | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  // Selection & Details
  const [selectedAdapterId, setSelectedAdapterId] = useState<string | null>(null);
  const [adapterDetails, setAdapterDetails] = useState<{ adapter: Adapter; versions: Adapter[] } | null>(null);
  const [isRollingBack, setIsRollingBack] = useState<boolean>(false);

  // Try It Live Sandbox state
  const [sandboxAdapterId, setSandboxAdapterId] = useState<string>("");
  const [sandboxPayload, setSandboxPayload] = useState<string>(
    'timestamp,store_code,sku,qty,price\n2026-11-13T10:00:00Z,PHARM-001,PARA-500,5,15.50'
  );
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  const [ingestResult, setIngestResult] = useState<any | null>(null);

  // Queries
  const { data: fixtures = [] } = useQuery<AdapterFixture[]>({
    queryKey: ["adapter-fixtures"],
    queryFn: () => api.adapters.getFixtures(),
  });

  const {
    data: adapters = [],
    refetch: refetchAdapters,
  } = useQuery<Adapter[]>({
    queryKey: ["adapters"],
    queryFn: async () => {
      const list = await api.adapters.list();
      if (list.length > 0 && !sandboxAdapterId) {
        setSandboxAdapterId(list[0].id);
      }
      return list;
    },
  });

  // Handle Fixture Selection
  const handleSelectFixture = (f: AdapterFixture) => {
    setAdapterName(f.name);
    setTargetSchema(f.target_schema || "SaleEvent");
    const raw = typeof f.sample_payload === "string" ? f.sample_payload : JSON.stringify(f.sample_payload, null, 2);
    setSamplePayload(raw);
    if (f.expected_output) {
      setExpectedOutput(JSON.stringify(f.expected_output, null, 2));
    }
  };

  // Generate Adapter
  const handleGenerate = async () => {
    setIsGenerating(true);
    setGenerationError(null);
    setActiveJob({
      job_id: `job-${Date.now()}`,
      adapter_name: adapterName,
      status: "running",
      events: [
        { step: "schema_inspector", status: "in_progress", message: "Analyzing input structure & data types..." },
      ],
    });

    try {
      let parsedSample: any = samplePayload;
      try {
        parsedSample = JSON.parse(samplePayload);
      } catch {
        // Keep string if CSV or XML
      }

      let parsedExpected: any = undefined;
      if (expectedOutput.trim()) {
        try {
          parsedExpected = JSON.parse(expectedOutput);
        } catch {
          // ignore
        }
      }

      const res = await api.adapters.generate({
        name: adapterName,
        target_schema: targetSchema,
        sample_payload: parsedSample,
        expected_output: parsedExpected,
      });

      // Poll or fetch job info
      const job = await api.adapters.getJob(res.job_id);
      setActiveJob(job);
      refetchAdapters();
      if (job.adapter_id) {
        setSandboxAdapterId(job.adapter_id);
      }
    } catch (err: any) {
      setGenerationError(err.message || "Failed to generate adapter");
      setActiveJob((prev) => (prev ? { ...prev, status: "failed" } : null));
    } finally {
      setIsGenerating(false);
    }
  };

  // Inspect Adapter Details
  const handleSelectAdapter = async (id: string) => {
    setSelectedAdapterId(id);
    try {
      const details = await api.adapters.getDetails(id);
      setAdapterDetails(details);
    } catch (err: any) {
      console.error("Failed fetching adapter details:", err);
    }
  };

  // Rollback Adapter
  const handleRollback = async (targetVersion: number) => {
    if (!selectedAdapterId) return;
    setIsRollingBack(true);
    try {
      await api.adapters.rollback(selectedAdapterId, targetVersion);
      refetchAdapters();
      const updated = await api.adapters.getDetails(selectedAdapterId);
      setAdapterDetails(updated);
    } catch (err: any) {
      alert(`Rollback failed: ${err.message}`);
    } finally {
      setIsRollingBack(false);
    }
  };

  // Try It Live Ingest
  const handleIngest = async () => {
    if (!sandboxAdapterId) return;
    setIsIngesting(true);
    setIngestResult(null);
    try {
      let payloadToSend: any = sandboxPayload;
      try {
        payloadToSend = JSON.parse(sandboxPayload);
      } catch {
        // keep as text
      }
      const res = await api.adapters.ingest(sandboxAdapterId, payloadToSend);
      setIngestResult(res);
    } catch (err: any) {
      setIngestResult({ error: err.message || "Ingestion failed" });
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
              Adapter Forge & Legacy Ingestion
            </h2>
            <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-[var(--accent-teal)]/10 text-[var(--accent-teal)] border border-[var(--accent-teal)]/30 font-semibold">
              AST Guarded
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Synthesize self-evolving Python translators for heterogeneous pharmacy, stockist, and manufacturer ERP formats (Marg, Tally, SAP, CSV, XML).
          </p>
        </div>

        <button
          type="button"
          onClick={() => refetchAdapters()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Registry
        </button>
      </div>

      {/* SECTION 1: Generator Studio */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-3 border-b border-[var(--border-subtle)]">
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Zap className="w-4 h-4 text-[var(--accent-teal)]" />
              <span>Studio: Adapter Generator</span>
            </h3>
            <p className="text-xs text-[var(--text-secondary)]">
              Select a sample fixture or paste legacy payloads to synthesize a secure Python AST transformation script.
            </p>
          </div>

          {/* Fixture Selector Pills */}
          {fixtures.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] font-mono text-[var(--text-secondary)] uppercase">Presets:</span>
              {fixtures.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => handleSelectFixture(f)}
                  className="px-2 py-1 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-canvas)] hover:border-[var(--accent-teal)] text-[var(--text-primary)] uppercase transition-all"
                >
                  {f.format}: {f.name.split(" ")[0]}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
                Adapter Name
              </label>
              <input
                type="text"
                value={adapterName}
                onChange={(e) => setAdapterName(e.target.value)}
                className="w-full p-2 text-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
                Target Canonical Schema
              </label>
              <select
                value={targetSchema}
                onChange={(e) => setTargetSchema(e.target.value)}
                className="w-full p-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
              >
                <option value="SaleEvent">SaleEvent (POS retail single-unit demand)</option>
                <option value="BatchUpdate">BatchUpdate (Batch manufacturing & cold-chain)</option>
                <option value="InventorySnapshot">InventorySnapshot (Daily stock reconciliation)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
                Expected Canonical Output (JSON)
              </label>
              <textarea
                value={expectedOutput}
                onChange={(e) => setExpectedOutput(e.target.value)}
                rows={4}
                className="w-full p-2 font-mono text-[11px] bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] resize-none"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)] mb-1">
              Sample Legacy Payload (CSV / XML / JSON)
            </label>
            <textarea
              value={samplePayload}
              onChange={(e) => setSamplePayload(e.target.value)}
              rows={9}
              className="w-full p-2 font-mono text-[11px] bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] resize-none"
            />
          </div>
        </div>

        <div className="pt-2 flex items-center justify-between border-t border-[var(--border-subtle)]">
          <div className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-[var(--accent-teal)]" />
            <span>Guarded with static AST validation (forbids imports, OS calls, & unmetered loops)</span>
          </div>

          <button
            type="button"
            disabled={isGenerating}
            onClick={handleGenerate}
            className="px-4 py-2 text-xs font-semibold bg-[var(--accent-teal)] text-white hover:opacity-90 transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {isGenerating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
            <span>⚡ Forge & Register Adapter</span>
          </button>
        </div>

        {generationError && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-800 dark:text-rose-200 text-xs flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-500" />
            <span>{generationError}</span>
          </div>
        )}
      </div>

      {/* SECTION 2: Step Progress Tracker (when job active or generated) */}
      {activeJob && (
        <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-[var(--accent-teal)] uppercase font-semibold">
                Job: {activeJob.job_id}
              </span>
              <StatusBadge status={activeJob.status} size="sm" />
            </div>
            <span className="text-[11px] font-mono text-[var(--text-secondary)]">
              Multi-Agent Code Synthesis & Verification
            </span>
          </div>

          {/* 4 Stages Tracker */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {[
              { id: "schema", label: "1. Schema Inspector", desc: "Type inferencing & schema map" },
              { id: "coder", label: "2. Adapter Coder", desc: "Python transformer synthesis" },
              { id: "guard", label: "3. Restricted Guard", desc: "AST security & test suite" },
              { id: "registry", label: "4. Registry Sealing", desc: "Version tag & zero-downtime" },
            ].map((step, idx) => (
              <div
                key={step.id}
                className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-1"
              >
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-[var(--text-primary)]">{step.label}</span>
                  {activeJob.status === "completed" || activeJob.status === "registered" ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                  ) : activeJob.status === "failed" && idx >= 2 ? (
                    <XCircle className="w-3.5 h-3.5 text-rose-500" />
                  ) : (
                    <Clock className="w-3.5 h-3.5 text-amber-500 animate-pulse" />
                  )}
                </div>
                <div className="text-[10px] text-[var(--text-secondary)]">{step.desc}</div>
              </div>
            ))}
          </div>

          {/* Generated code and test preview */}
          {activeJob.generated_code && (
            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-[var(--text-secondary)]">
                Synthesized Python Code Preview:
              </span>
              <pre className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[11px] font-mono text-[var(--text-primary)] max-h-48 overflow-auto leading-relaxed">
                {activeJob.generated_code}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* SECTION 3: Marketplace Registry & Version History */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
              <span>Adapter Marketplace Registry ({adapters.length})</span>
            </h3>
            <span className="text-[10px] font-mono text-[var(--text-secondary)]">Live In-Process</span>
          </div>

          <div className="space-y-2">
            {adapters.map((ad) => {
              const isSelected = selectedAdapterId === ad.id;
              return (
                <div
                  key={ad.id}
                  onClick={() => handleSelectAdapter(ad.id)}
                  className={`p-3.5 border cursor-pointer transition-all ${
                    isSelected
                      ? "bg-[var(--bg-surface)] border-[var(--accent-teal)] shadow-sm"
                      : "bg-[var(--bg-surface)]/70 border-[var(--border-subtle)] hover:border-[var(--border-strong)]"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-[var(--text-primary)]">{ad.name}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                          v{ad.version}
                        </span>
                      </div>
                      <div className="text-[10px] font-mono text-[var(--text-secondary)] mt-0.5">
                        ERP: {ad.erp_system} • ID: {ad.id}
                      </div>
                    </div>
                    <StatusBadge status={ad.status} size="sm" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Adapter Deep View & Rollback */}
        <div className="lg:col-span-5 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Adapter Code & Version Control
          </h3>

          {adapterDetails ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
                <div>
                  <div className="font-semibold text-xs text-[var(--text-primary)]">
                    {adapterDetails.adapter.name}
                  </div>
                  <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                    Active Version: v{adapterDetails.adapter.version}
                  </div>
                </div>
                <StatusBadge status={adapterDetails.adapter.status} size="sm" />
              </div>

              {/* Version History pills */}
              {adapterDetails.versions && adapterDetails.versions.length > 1 && (
                <div className="space-y-1.5">
                  <span className="text-[10px] font-mono text-[var(--text-secondary)] uppercase block">
                    Version History & Rollback:
                  </span>
                  <div className="flex items-center gap-2 flex-wrap">
                    {adapterDetails.versions.map((v) => (
                      <button
                        key={v.version}
                        type="button"
                        disabled={isRollingBack || v.version === adapterDetails.adapter.version}
                        onClick={() => handleRollback(Number(v.version))}
                        className={`px-2 py-1 text-[11px] font-mono border flex items-center gap-1 ${
                          v.version === adapterDetails.adapter.version
                            ? "bg-[var(--accent-teal)] text-white border-[var(--accent-teal)]"
                            : "bg-[var(--bg-canvas)] text-[var(--text-primary)] border-[var(--border-subtle)] hover:border-[var(--accent-teal)]"
                        }`}
                      >
                        <RotateCcw className="w-2.5 h-2.5" />
                        <span>v{v.version}</span>
                        {v.version !== adapterDetails.adapter.version && (
                          <span className="text-[9px] opacity-75">(Rollback)</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Code viewer */}
              {adapterDetails.adapter.source_code && (
                <div className="space-y-1">
                  <span className="text-[10px] font-mono text-[var(--text-secondary)] uppercase">
                    Compiled Python AST:
                  </span>
                  <pre className="p-2.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[10px] font-mono text-[var(--text-primary)] max-h-52 overflow-auto">
                    {adapterDetails.adapter.source_code}
                  </pre>
                </div>
              )}

              {/* Transformation Rules JSON */}
              <JsonViewer
                data={adapterDetails.adapter.transformation_rules}
                title="Transformation Schema"
                defaultExpanded={false}
              />
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <Code2 className="w-8 h-8 opacity-30 mx-auto mb-2 text-[var(--accent-teal)]" />
              <p>Select any adapter from the marketplace registry to inspect AST source code and trigger version rollbacks.</p>
            </div>
          )}
        </div>
      </div>

      {/* SECTION 4: "Try It Live" Sandbox */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Terminal className="w-4 h-4 text-[var(--accent-teal)]" />
              <span>Try It Live: Real-Time Ingestion Sandbox</span>
            </h3>
            <p className="text-xs text-[var(--text-secondary)]">
              Execute live HTTP ingestion against <code className="font-mono text-[var(--accent-teal)]">POST /api/v1/ingest/:adapter_id</code> and inspect the normalized canonical event.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-[var(--text-secondary)]">Target Adapter:</span>
            <select
              value={sandboxAdapterId}
              onChange={(e) => setSandboxAdapterId(e.target.value)}
              className="px-2.5 py-1 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]"
            >
              {adapters.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} (v{a.version})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)]">
              Raw Ingestion Payload (Plain Text / JSON / CSV):
            </label>
            <textarea
              value={sandboxPayload}
              onChange={(e) => setSandboxPayload(e.target.value)}
              rows={8}
              className="w-full p-2.5 font-mono text-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] resize-none"
            />
            <button
              type="button"
              disabled={isIngesting || !sandboxAdapterId}
              onClick={handleIngest}
              className="w-full py-2 text-xs font-semibold bg-[var(--accent-teal)] text-white hover:opacity-90 flex items-center justify-center gap-2 disabled:opacity-50 transition-all"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{isIngesting ? "Transforming & Ingesting..." : "🚀 Ingest Raw Payload"}</span>
            </button>
          </div>

          <div className="space-y-2">
            <label className="block text-[11px] font-mono uppercase text-[var(--text-secondary)]">
              Canonical Ingestion Result:
            </label>
            {ingestResult ? (
              <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-3 max-h-64 overflow-auto font-mono text-xs">
                {ingestResult.correlation_id && (
                  <div className="flex items-center justify-between text-[11px] pb-1 border-b border-[var(--border-subtle)]">
                    <span className="text-[var(--text-secondary)]">Correlation ID:</span>
                    <span className="text-[var(--accent-teal)] font-bold">{ingestResult.correlation_id}</span>
                  </div>
                )}
                <JsonViewer
                  data={ingestResult.canonical_event || ingestResult}
                  title="Normalized Event Payload"
                  defaultExpanded={true}
                />
              </div>
            ) : (
              <div className="p-8 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
                Click "🚀 Ingest Raw Payload" to trigger runtime AST transformation and see the emitted canonical event.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
