/**
 * Sovereign Prescriptions & Compliance Page (/prescriptions)
 * CDSCO Schedule H/H1/X compliance audit trail and physician verification.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pill, RefreshCw, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { ComplianceLog } from "../types/api";

export const PrescriptionsPage: React.FC = () => {
  const [selectedLog, setSelectedLog] = useState<ComplianceLog | null>(null);

  const {
    data: logs = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["compliance-logs"],
    queryFn: () => api.compliance.listLogs({ limit: 50 }),
  });

  const columns: Column<ComplianceLog>[] = [
    {
      key: "drug_name",
      header: "Pharmaceutical SKU",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
            <Pill className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
            {row.drug_name}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">
            Schedule {row.schedule} • Qty: {row.dispensed_qty}
          </div>
        </div>
      ),
    },
    {
      key: "doctor_reg_number",
      header: "Prescribing Physician",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)]">
          {row.doctor_reg_number}
        </span>
      ),
    },
    {
      key: "patient_identifier",
      header: "Patient Token",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-secondary)]">
          {row.patient_identifier}
        </span>
      ),
    },
    {
      key: "is_verified",
      header: "CDSCO Registry",
      sortable: true,
      render: (row) => (
        <StatusBadge
          status={row.is_verified ? "approved" : "flagged"}
          label={row.is_verified ? "Verified" : "Unverified"}
          size="sm"
        />
      ),
    },
    {
      key: "created_at",
      header: "Dispensed At",
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
            Schedule H Prescriptions & Registry Ledger
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Cryptographically audited retail dispensing log with statutory physician credential validation.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Logs
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 space-y-2">
          <DataTable
            data={logs}
            columns={columns}
            keyExtractor={(row) => row.id}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedLog(row)}
            searchPlaceholder="Search drug name, doctor registration, or schedule..."
            searchFilter={(row, q) =>
              row.drug_name.toLowerCase().includes(q) ||
              row.doctor_reg_number.toLowerCase().includes(q) ||
              row.schedule.toLowerCase().includes(q)
            }
            emptyTitle="No compliance logs recorded"
            emptyDescription="Dispensed Schedule H prescriptions will appear in this registry ledger."
            pageSize={10}
          />
        </div>

        <div className="lg:col-span-4 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Prescription Audit Detail
          </h3>
          {selectedLog ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs text-[var(--text-primary)]">{selectedLog.drug_name}</span>
                <StatusBadge status={selectedLog.is_verified ? "approved" : "flagged"} size="sm" />
              </div>

              <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono space-y-1">
                <div>
                  <span className="text-[var(--text-secondary)]">Doctor Reg:</span> {selectedLog.doctor_reg_number}
                </div>
                <div>
                  <span className="text-[var(--text-secondary)]">Patient Hash:</span> {selectedLog.patient_identifier}
                </div>
                <div>
                  <span className="text-[var(--text-secondary)]">Node:</span> {selectedLog.node_id}
                </div>
              </div>

              <JsonViewer data={selectedLog} title="Raw Compliance Ledger Entry" defaultExpanded={false} />
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Select any prescription entry to view CDSCO statutory audit metadata.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
