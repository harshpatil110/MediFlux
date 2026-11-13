/**
 * Sovereign Prescription Scanner & Schedule H Compliance Screen (/prescriptions)
 *
 * Implements Task 19 & Task 27:
 * - Sovereign local-only execution banner (sensitivity="sensitive").
 * - Multi-source ingestion: drag-and-drop file upload + 5 synthetic fixture presets.
 * - Image preview canvas.
 * - Structured parse console: final verdict badge, redacted patient initials,
 *   physician registry validation card, per-drug CDSCO schedule breakdown table.
 * - One-click Schedule H POS sale trigger linking to Demand Cascade.
 * - Statutory compliance audit history table.
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Eye,
  FileCheck,
  FileText,
  Lock,
  Pill,
  RefreshCw,
  ShieldCheck,
  Upload,
  UserCheck,
  UserX,
  XCircle,
  Zap,
} from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { PrescriptionFixture, PrescriptionRecord } from "../types/api";

export const PrescriptionsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // State
  const [selectedFixture, setSelectedFixture] = useState<PrescriptionFixture | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [activeResult, setActiveResult] = useState<PrescriptionRecord | null>(null);
  const [historyDetail, setHistoryDetail] = useState<PrescriptionRecord | null>(null);
  const [posSuccessMsg, setPosSuccessMsg] = useState<string | null>(null);

  // Queries
  const { data: fixtures = [], isLoading: fixturesLoading } = useQuery({
    queryKey: ["prescription-fixtures"],
    queryFn: () => api.prescriptions.getFixtures(),
  });

  const {
    data: historyData,
    isLoading: historyLoading,
    refetch: refetchHistory,
  } = useQuery({
    queryKey: ["prescriptions-history"],
    queryFn: () => api.prescriptions.list({ limit: 50 }),
  });

  const prescriptionsList: PrescriptionRecord[] = historyData?.prescriptions || [];

  // Mutations
  const scanMutation = useMutation({
    mutationFn: async () => {
      setPosSuccessMsg(null);
      if (selectedFile) {
        const formData = new FormData();
        formData.append("file", selectedFile);
        formData.append("node_id", "11111111-1111-1111-1111-111111111111");
        return await api.prescriptions.scan(formData);
      }
      if (selectedFixture) {
        return await api.prescriptions.scan({
          fixture_name: selectedFixture.filename,
          node_id: "11111111-1111-1111-1111-111111111111",
        });
      }
      throw new Error("Select a fixture preset or upload a prescription file first.");
    },
    onSuccess: (data) => {
      setActiveResult(data);
      queryClient.invalidateQueries({ queryKey: ["prescriptions-history"] });
    },
  });

  // Handle fixture selection
  const handleSelectFixture = (f: PrescriptionFixture) => {
    setSelectedFixture(f);
    setSelectedFile(null);
    setImagePreviewUrl(f.data_uri || null);
    setActiveResult(null);
    setPosSuccessMsg(null);
  };

  // Handle file drop/upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setSelectedFixture(null);
      setActiveResult(null);
      setPosSuccessMsg(null);
      const reader = new FileReader();
      reader.onload = (ev) => {
        setImagePreviewUrl(ev.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  // Trigger POS test sale with prescription
  const handleTestPosSale = async (rx: PrescriptionRecord) => {
    try {
      const scheduleHDrug = rx.drugs.find(
        (d) => d.schedule_class === "H" || d.schedule_class === "H1" || d.requires_prescription
      ) || rx.drugs[0];

      const sku = scheduleHDrug?.sku || "MED-AMX-500";
      const qty = scheduleHDrug?.quantity || 1;

      // Navigate to Cascade with prefilled parameters or submit sale
      navigate(`/cascade?rx_id=${encodeURIComponent(rx.id)}&sku=${encodeURIComponent(sku)}&qty=${qty}`);
    } catch (err: any) {
      setPosSuccessMsg(`Sale dispatch failed: ${err.message}`);
    }
  };

  // Table Columns for History
  const historyColumns: Column<PrescriptionRecord>[] = [
    {
      key: "rx_number",
      header: "Rx Identifier",
      sortable: true,
      render: (row) => (
        <div>
          <span className="font-mono text-xs font-semibold text-[var(--accent-teal)]">
            {row.rx_number || `RX-${row.id.slice(0, 8).toUpperCase()}`}
          </span>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">
            Sensitivity: {row.sensitivity}
          </div>
        </div>
      ),
    },
    {
      key: "patient_initials",
      header: "Patient (PII Masked)",
      sortable: true,
      render: (row) => (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
          <Lock className="w-3 h-3 text-[var(--accent-teal)]" />
          {row.patient_initials || "ANON"}
        </span>
      ),
    },
    {
      key: "doctor_name",
      header: "Prescribing Physician",
      sortable: true,
      render: (row) => (
        <div>
          <div className="text-xs font-medium text-[var(--text-primary)]">{row.doctor_name}</div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">
            Reg: {row.doctor_registration_no || "MISSING"}
          </div>
        </div>
      ),
    },
    {
      key: "doctor_verified",
      header: "Registry Status",
      sortable: true,
      render: (row) =>
        row.doctor_verified ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" /> Verified
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-amber-600 dark:text-amber-400">
            <AlertTriangle className="w-3.5 h-3.5" /> Unverified
          </span>
        ),
    },
    {
      key: "decision",
      header: "Compliance Verdict",
      sortable: true,
      render: (row) => {
        const isApproved = row.decision === "approve_dispense" || row.status === "approved";
        const isFlagged = row.decision === "flag" || row.status === "flagged";
        return (
          <StatusBadge
            status={isApproved ? "approved" : isFlagged ? "flagged" : "quarantined"}
            label={isApproved ? "Approved" : isFlagged ? "HITL Review" : "Rejected"}
            size="sm"
          />
        );
      },
    },
    {
      key: "created_at",
      header: "Scanned At",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)]">
          {row.created_at ? new Date(row.created_at).toLocaleTimeString() : "Recent"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Sovereign Local Execution Banner */}
      <div className="p-4 bg-[var(--bg-surface)] border-l-4 border-l-[var(--accent-teal)] border border-[var(--border-subtle)] flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-[var(--accent-teal)]/10 text-[var(--accent-teal)]">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-wider font-bold text-[var(--accent-teal)]">
                SOVEREIGN LOCAL EXECUTION • SENSITIVITY: SENSITIVE
              </span>
              <span className="px-1.5 py-0.5 text-[10px] font-mono bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/40">
                Zero Cloud Leakage
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              CDSCO compliance parser runs fully on-premises. Patient identities are irreversibly redacted to initials
              (<code className="font-mono text-[var(--text-primary)]">patient_initials</code>) prior to any persistence or statutory ledger propagation.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px] text-[var(--text-secondary)] bg-[var(--bg-canvas)] px-3 py-1.5 border border-[var(--border-subtle)]">
          <Lock className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
          <span>Statutory DPCO & Schedule H Registry</span>
        </div>
      </div>

      {/* 2. Top Ingestion Studio: 2 Columns (Left: Studio & Fixtures, Right: Structured Verdict Console) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Upload Studio & Fixture Pills (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5">
              <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                <Upload className="w-4 h-4 text-[var(--accent-teal)]" />
                Prescription Ingestion Studio
              </h3>
              <span className="text-[11px] font-mono text-[var(--text-secondary)]">PNG, JPG, PDF</span>
            </div>

            {/* 1-Click Synthetic Fixtures */}
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-[var(--text-secondary)] block">
                Synthetic Prescription Fixtures (1-Click Test Scenarios):
              </label>
              <div className="grid grid-cols-1 gap-1.5">
                {fixturesLoading ? (
                  <div className="text-xs font-mono text-[var(--text-secondary)] p-2">Loading presets...</div>
                ) : (
                  fixtures.map((f) => {
                    const isSelected = selectedFixture?.filename === f.filename;
                    const isExpectedApproved = f.expected_status === "approved";
                    return (
                      <button
                        key={f.id}
                        type="button"
                        onClick={() => handleSelectFixture(f)}
                        className={`text-left p-2.5 border text-xs transition-all flex items-start justify-between gap-2 ${
                          isSelected
                            ? "border-[var(--accent-teal)] bg-[var(--accent-teal)]/10 text-[var(--text-primary)]"
                            : "border-[var(--border-subtle)] bg-[var(--bg-canvas)] hover:border-[var(--text-secondary)] text-[var(--text-secondary)]"
                        }`}
                      >
                        <div className="space-y-0.5">
                          <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                            <FileText className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                            {f.label}
                          </div>
                          <div className="text-[11px] text-[var(--text-secondary)] leading-snug">
                            {f.description}
                          </div>
                          <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                            Physician: {f.doctor_name} • Reg: {f.reg_no}
                          </div>
                        </div>

                        <span
                          className={`px-1.5 py-0.5 text-[9px] font-mono shrink-0 uppercase tracking-wider border ${
                            isExpectedApproved
                              ? "bg-teal-50 text-teal-800 border-teal-300 dark:bg-teal-950/50 dark:text-teal-300"
                              : "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/50 dark:text-amber-300"
                          }`}
                        >
                          {f.expected_verdict}
                        </span>
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            {/* Custom File Drag & Drop Zone */}
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-[var(--text-secondary)] block">
                Or Upload Scanned Physical Prescription:
              </label>
              <label className="border-2 border-dashed border-[var(--border-subtle)] hover:border-[var(--accent-teal)] bg-[var(--bg-canvas)] p-4 flex flex-col items-center justify-center cursor-pointer transition-colors text-center">
                <Upload className="w-6 h-6 text-[var(--text-secondary)] mb-1" />
                <span className="text-xs font-medium text-[var(--text-primary)]">
                  {selectedFile ? selectedFile.name : "Choose file or drag & drop"}
                </span>
                <span className="text-[10px] font-mono text-[var(--text-secondary)] mt-0.5">
                  Processed locally under Sovereign LLM Guard
                </span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>

            {/* Image Preview Canvas */}
            {imagePreviewUrl && (
              <div className="space-y-1.5 border-t border-[var(--border-subtle)] pt-3">
                <div className="flex items-center justify-between text-xs font-mono text-[var(--text-secondary)]">
                  <span>Prescription Scan Preview</span>
                  <span className="text-[10px] text-[var(--accent-teal)]">Ready to Parse</span>
                </div>
                <div className="p-2 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] max-h-48 overflow-hidden flex items-center justify-center">
                  <img
                    src={imagePreviewUrl}
                    alt="Prescription preview"
                    className="max-h-44 object-contain shadow-xs"
                  />
                </div>
              </div>
            )}

            {/* Scan Action Button */}
            <button
              type="button"
              disabled={scanMutation.isPending || (!selectedFixture && !selectedFile)}
              onClick={() => scanMutation.mutate()}
              className="w-full py-2.5 px-4 bg-[var(--accent-teal)] hover:opacity-90 disabled:opacity-50 text-[var(--bg-surface)] font-mono text-xs uppercase tracking-wider font-semibold flex items-center justify-center gap-2 transition-all"
            >
              {scanMutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Sovereign Parsing & Registry Check...
                </>
              ) : (
                <>
                  <FileCheck className="w-4 h-4" /> Scan & Validate Prescription
                </>
              )}
            </button>

            {scanMutation.isError && (
              <div className="p-2.5 text-xs font-mono text-coral-700 bg-coral-50 border border-coral-200 dark:bg-coral-950/40 dark:text-coral-300">
                Parsing Error: {(scanMutation.error as any)?.message || "Failed to process scan."}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Structured Parse & Verdict Console (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {activeResult ? (
            <div className="p-5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-5">
              {/* Verdict Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-4">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
                    Autonomous Compliance Verdict
                  </span>
                  <h3 className="text-base font-serif font-bold text-[var(--text-primary)]">
                    {activeResult.rx_number || `RX-${activeResult.id.slice(0, 8).toUpperCase()}`}
                  </h3>
                </div>

                {/* Final Decision Badge */}
                {activeResult.decision === "approve_dispense" || activeResult.status === "approved" ? (
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-teal-50 dark:bg-teal-950/60 border border-[var(--accent-teal)] text-[var(--accent-teal)] font-mono text-xs font-bold uppercase tracking-wider">
                    <CheckCircle2 className="w-4 h-4" />
                    APPROVE DISPENSE
                  </div>
                ) : activeResult.decision === "flag" || activeResult.status === "flagged" ? (
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-amber-50 dark:bg-amber-950/60 border border-amber-500 text-amber-700 dark:text-amber-300 font-mono text-xs font-bold uppercase tracking-wider">
                    <AlertTriangle className="w-4 h-4" />
                    FLAGGED FOR HITL REVIEW
                  </div>
                ) : (
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-coral-50 dark:bg-coral-950/60 border border-coral-500 text-coral-700 dark:text-coral-300 font-mono text-xs font-bold uppercase tracking-wider">
                    <XCircle className="w-4 h-4" />
                    REJECTED
                  </div>
                )}
              </div>

              {/* Patient Redaction & Doctor Registry Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Patient Privacy Redaction */}
                <div className="p-3.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
                      Patient Identity
                    </span>
                    <span className="px-1.5 py-0.5 text-[9px] font-mono bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-300/40">
                      PII REDACTED
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-mono font-bold text-[var(--text-primary)]">
                      {activeResult.patient_initials || "ANON"}
                    </span>
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      (Initials Only • Zero PII Retained)
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                    Local sensitivity tag: <code className="text-[var(--accent-teal)]">sensitive</code>
                  </div>
                </div>

                {/* Physician Verification Card */}
                <div className="p-3.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[var(--text-secondary)]">
                      Physician Registry
                    </span>
                    {activeResult.doctor_verified ? (
                      <span className="px-1.5 py-0.5 text-[9px] font-mono bg-teal-100 text-teal-800 dark:bg-teal-950/50 dark:text-teal-300 border border-teal-300 flex items-center gap-1">
                        <UserCheck className="w-3 h-3" /> VERIFIED
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.5 text-[9px] font-mono bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-300 flex items-center gap-1">
                        <UserX className="w-3 h-3" /> UNVERIFIED
                      </span>
                    )}
                  </div>
                  <div className="font-medium text-xs text-[var(--text-primary)]">
                    {activeResult.doctor_name || "Unknown Doctor"}
                  </div>
                  <div className="text-[10px] font-mono text-[var(--text-secondary)]">
                    Reg No:{" "}
                    <span className="text-[var(--text-primary)] font-semibold">
                      {activeResult.doctor_registration_no || "MISSING / INVALID"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Per-Drug CDSCO Schedule Breakdown Table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold flex items-center gap-1.5">
                    <Pill className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                    CDSCO Drug Schedule Classification & Formulary Inspection
                  </h4>
                  <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                    {activeResult.drugs?.length || 0} formulation(s) identified
                  </span>
                </div>

                <div className="border border-[var(--border-subtle)] overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-[var(--bg-canvas)] border-b border-[var(--border-subtle)] text-[var(--text-secondary)]">
                      <tr>
                        <th className="p-2.5">Medication Name</th>
                        <th className="p-2.5">Dosage</th>
                        <th className="p-2.5">Qty</th>
                        <th className="p-2.5">CDSCO Schedule</th>
                        <th className="p-2.5">Rx Mandatory</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border-subtle)] bg-[var(--bg-surface)]">
                      {activeResult.drugs && activeResult.drugs.length > 0 ? (
                        activeResult.drugs.map((drug, idx) => {
                          const isSchH =
                            drug.schedule_class === "H" ||
                            drug.schedule_class === "H1" ||
                            drug.schedule_class === "X";
                          return (
                            <tr key={idx} className="hover:bg-[var(--bg-canvas)]/50">
                              <td className="p-2.5 font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                                <Pill className="w-3 h-3 text-[var(--accent-teal)]" />
                                {drug.name}
                              </td>
                              <td className="p-2.5 text-[var(--text-secondary)]">{drug.dose || "—"}</td>
                              <td className="p-2.5 text-[var(--text-primary)]">{drug.quantity || 1}</td>
                              <td className="p-2.5">
                                <span
                                  className={`px-1.5 py-0.5 text-[10px] font-bold border ${
                                    isSchH
                                      ? "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200"
                                      : "bg-teal-50 text-teal-800 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300"
                                  }`}
                                >
                                  Schedule {drug.schedule_class || "OTC"}
                                </span>
                              </td>
                              <td className="p-2.5">
                                {drug.requires_prescription || isSchH ? (
                                  <span className="text-amber-600 dark:text-amber-400 font-semibold text-[10px]">
                                    MANDATORY
                                  </span>
                                ) : (
                                  <span className="text-[var(--text-secondary)] text-[10px]">OPTIONAL (OTC)</span>
                                )}
                              </td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={5} className="p-4 text-center text-xs text-[var(--text-secondary)]">
                            No medication items parsed from scan.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Action Buttons depending on verdict */}
              <div className="pt-2 border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3">
                {activeResult.status === "approved" || activeResult.decision === "approve_dispense" ? (
                  <button
                    type="button"
                    onClick={() => handleTestPosSale(activeResult)}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-teal)] text-[var(--bg-surface)] font-mono text-xs font-semibold uppercase tracking-wider hover:opacity-90 transition-all shadow-xs"
                  >
                    <Zap className="w-4 h-4" />
                    💊 Test Schedule H POS Sale with Rx ID
                    <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </button>
                ) : activeResult.hitl_task_id ? (
                  <Link
                    to="/approvals"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white font-mono text-xs font-semibold uppercase tracking-wider hover:bg-amber-700 transition-all shadow-xs"
                  >
                    <Eye className="w-4 h-4" />
                    Inspect Pending HITL Task in Approvals Inbox
                    <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </Link>
                ) : (
                  <div className="text-xs font-mono text-[var(--text-secondary)]">
                    Prescription rejected due to invalid doctor license or unlisted entity.
                  </div>
                )}

                <span className="text-[11px] font-mono text-[var(--text-secondary)]">
                  Correlation ID: {activeResult.correlation_id || "corr-local"}
                </span>
              </div>

              {posSuccessMsg && (
                <div className="p-2.5 text-xs font-mono bg-teal-50 border border-teal-200 text-teal-800 dark:bg-teal-950/40 dark:text-teal-200">
                  {posSuccessMsg}
                </div>
              )}
            </div>
          ) : (
            <div className="p-12 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center space-y-3">
              <FileCheck className="w-12 h-12 text-[var(--text-secondary)] opacity-30 mx-auto" />
              <h4 className="text-sm font-serif font-bold text-[var(--text-primary)]">
                Awaiting Prescription Scan Input
              </h4>
              <p className="text-xs text-[var(--text-secondary)] max-w-md mx-auto">
                Select one of the 5 synthetic fixture presets on the left or upload an image to trigger sovereign OCR extraction, CDSCO schedule verification, and physician registry validation.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 3. Statutory Compliance History Ledger */}
      <div className="space-y-3">
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5">
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Clock className="w-4 h-4 text-[var(--accent-teal)]" />
              Statutory CDSCO Schedule H Compliance & Prescription History
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Immutable local log of verified prescriptions, doctor validation statuses, and dispensed medication schedules.
            </p>
          </div>
          <button
            type="button"
            onClick={() => refetchHistory()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh History
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-8">
            <DataTable
              data={prescriptionsList}
              columns={historyColumns}
              keyExtractor={(row) => row.id}
              isLoading={historyLoading}
              onRowClick={(row) => setHistoryDetail(row)}
              searchPlaceholder="Search physician, Rx number, patient initials, or decision..."
              searchFilter={(row, q) =>
                (row.rx_number || "").toLowerCase().includes(q) ||
                (row.doctor_name || "").toLowerCase().includes(q) ||
                (row.patient_initials || "").toLowerCase().includes(q) ||
                (row.decision || "").toLowerCase().includes(q)
              }
              emptyTitle="No prescriptions recorded"
              emptyDescription="Processed prescriptions will appear in this sovereign statutory registry."
              pageSize={8}
            />
          </div>

          <div className="lg:col-span-4 space-y-3">
            <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] font-semibold">
              Selected Record Inspector
            </h4>
            {historyDetail ? (
              <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
                <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
                  <span className="font-semibold text-xs text-[var(--text-primary)]">
                    {historyDetail.rx_number || historyDetail.id}
                  </span>
                  <StatusBadge
                    status={historyDetail.status === "approved" ? "approved" : "flagged"}
                    label={historyDetail.status}
                    size="sm"
                  />
                </div>

                <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Patient Initials:</span>
                    <span className="font-bold text-[var(--text-primary)]">{historyDetail.patient_initials}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Doctor:</span>
                    <span>{historyDetail.doctor_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Doctor Verified:</span>
                    <span>{historyDetail.doctor_verified ? "Yes ✓" : "No ✗"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Formulations:</span>
                    <span>{historyDetail.drugs?.length || 0}</span>
                  </div>
                </div>

                <JsonViewer data={historyDetail} title="Full Cryptographic Prescription Record" defaultExpanded={false} />
              </div>
            ) : (
              <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
                <FileText className="w-8 h-8 opacity-30 mx-auto mb-2" />
                <p>Click any prescription row in the history table to inspect cryptographic and compliance metadata.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
