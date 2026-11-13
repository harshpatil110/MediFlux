/**
 * Cryptographic Audit Ledger Page (/audit)
 * Immutable SHA-256 hash-chained verification trail and cryptographic integrity checks.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Hash, Link2, RefreshCw, ScrollText, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { AuditLedgerEntry } from "../types/api";

export const AuditPage: React.FC = () => {
  const [selectedEntry, setSelectedEntry] = useState<AuditLedgerEntry | null>(null);
  const [verificationResult, setVerificationResult] = useState<{
    valid: boolean;
    verified_count: number;
    message: string;
  } | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  const {
    data: entries = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["audit-ledger"],
    queryFn: () => api.audit.listLedger({ limit: 50 }),
  });

  const handleVerifyChain = async () => {
    setIsVerifying(true);
    try {
      const res = await api.audit.verifyChain();
      setVerificationResult(res);
    } catch (err: any) {
      setVerificationResult({
        valid: false,
        verified_count: 0,
        message: err.message || "Failed verifying cryptographic audit chain.",
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const columns: Column<AuditLedgerEntry>[] = [
    {
      key: "sequence_number",
      header: "Seq #",
      sortable: true,
      render: (row) => (
        <span className="font-mono font-semibold text-xs text-[var(--accent-teal)]">
          #{row.sequence_number}
        </span>
      ),
    },
    {
      key: "action",
      header: "Operation Action",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)]">{row.action}</div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">Role: {row.actor_role}</div>
        </div>
      ),
    },
    {
      key: "entry_hash",
      header: "Current SHA-256 Hash",
      render: (row) => (
        <span className="font-mono text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
          <Hash className="w-3 h-3 text-[var(--accent-teal)]" />
          {row.entry_hash ? `${row.entry_hash.slice(0, 16)}...` : "—"}
        </span>
      ),
    },
    {
      key: "prev_hash",
      header: "Chained Prev Hash",
      render: (row) => (
        <span className="font-mono text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
          <Link2 className="w-3 h-3 opacity-50" />
          {row.prev_hash ? `${row.prev_hash.slice(0, 12)}...` : "000000000000..."}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Recorded At",
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            Cryptographic Audit Ledger
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Tamper-evident, hash-chained statutory ledger of all state mutations, orders, and approvals.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleVerifyChain}
            disabled={isVerifying}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium bg-[var(--accent-teal)] text-white hover:bg-[var(--accent-teal)]/90 transition-colors disabled:opacity-50"
          >
            {isVerifying ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ShieldCheck className="w-3.5 h-3.5" />
            )}
            Verify Hash Chain
          </button>
          <button
            type="button"
            onClick={() => refetch()}
            className="p-1.5 border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
            title="Refresh ledger"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {verificationResult && (
        <div
          className={`p-4 border flex items-center justify-between text-xs ${
            verificationResult.valid
              ? "bg-teal-500/10 border-teal-500/30 text-teal-800 dark:text-teal-200"
              : "bg-rose-500/10 border-rose-500/30 text-rose-800 dark:text-rose-200"
          }`}
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[var(--accent-teal)]" />
            <div>
              <span className="font-semibold">
                {verificationResult.valid ? "Cryptographic Chain Verified" : "Chain Integrity Error"}
              </span>
              <p className="text-[11px] opacity-80">{verificationResult.message}</p>
            </div>
          </div>
          <span className="font-mono text-xs">
            {verificationResult.verified_count} blocks checked
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 space-y-2">
          <DataTable
            data={entries}
            columns={columns}
            keyExtractor={(row) => row.id}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedEntry(row)}
            searchPlaceholder="Search action, actor role, or hash..."
            searchFilter={(row, q) =>
              row.action.toLowerCase().includes(q) ||
              row.actor_role.toLowerCase().includes(q) ||
              row.entry_hash.toLowerCase().includes(q)
            }
            emptyTitle="No audit records"
            emptyDescription="Statutory actions will append to the cryptographic ledger."
            pageSize={8}
          />
        </div>

        <div className="lg:col-span-4 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Block Integrity Inspector
          </h3>
          {selectedEntry ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs text-[var(--text-primary)]">
                  Block #{selectedEntry.sequence_number}
                </span>
                <StatusBadge status="approved" label="Sealed" size="sm" />
              </div>

              <div className="space-y-1.5 text-xs font-mono">
                <div>
                  <span className="text-[var(--text-secondary)] block text-[10px] uppercase">Action:</span>
                  <span className="text-[var(--text-primary)] font-semibold">{selectedEntry.action}</span>
                </div>
                <div>
                  <span className="text-[var(--text-secondary)] block text-[10px] uppercase">Actor Role:</span>
                  <span className="text-[var(--text-primary)]">{selectedEntry.actor_role}</span>
                </div>
                <div>
                  <span className="text-[var(--text-secondary)] block text-[10px] uppercase">Node ID:</span>
                  <span className="text-[var(--text-secondary)] truncate block">{selectedEntry.node_id}</span>
                </div>
              </div>

              <JsonViewer data={selectedEntry.details} title="Block Payload" defaultExpanded={false} />
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <ScrollText className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Select any audit block to inspect cryptographic hash chaining and details.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
