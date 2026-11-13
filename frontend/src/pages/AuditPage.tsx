/**
 * Cryptographic Audit Ledger Page (/audit)
 * Immutable SHA-256 hash-chained verification trail, live integrity verifier,
 * and block link visualizer.
 */

import React, { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Hash,
  Link2,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  ShieldAlert,
  ArrowDown,
  Search,
  Filter,
  Layers,
  Copy,
} from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { AuditLedgerEntry, AuditVerificationResult } from "../types/api";

export const AuditPage: React.FC = () => {
  const [selectedEntry, setSelectedEntry] = useState<AuditLedgerEntry | null>(null);
  const [verificationResult, setVerificationResult] = useState<AuditVerificationResult | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const {
    data: entries = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["audit-ledger", actionFilter],
    queryFn: async () => {
      const params: any = { limit: 100 };
      if (actionFilter !== "all") params.action = actionFilter;
      return api.audit.listLedger(params);
    },
    refetchInterval: 15000,
  });

  const handleVerifyChain = async () => {
    setIsVerifying(true);
    try {
      const res = await api.audit.verifyChain();
      setVerificationResult(res);
    } catch (err: any) {
      setVerificationResult({
        valid: false,
        status: "tampered",
        total_entries: 0,
        verified_entries: 0,
        genesis_hash: "",
        head_hash: "",
        verified_at: new Date().toISOString(),
        message: err.message || "Failed verifying cryptographic audit chain.",
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Distinct action types for filter
  const actionTypes = useMemo(() => {
    const set = new Set<string>();
    entries.forEach((e) => {
      if (e.action) set.add(e.action);
    });
    return Array.from(set);
  }, [entries]);

  // Filtered entries
  const filteredEntries = useMemo(() => {
    if (!searchQuery.trim()) return entries;
    const q = searchQuery.toLowerCase();
    return entries.filter((row) => {
      const action = (row.action || "").toLowerCase();
      const actor = (row.actor || row.actor_role || "").toLowerCase();
      const node = (row.node_id || "").toLowerCase();
      const hash = (row.entry_hash || row.hash || "").toLowerCase();
      const prevHash = (row.prev_hash || "").toLowerCase();
      const explanation = (row.explanation || "").toLowerCase();
      return (
        action.includes(q) ||
        actor.includes(q) ||
        node.includes(q) ||
        hash.includes(q) ||
        prevHash.includes(q) ||
        explanation.includes(q)
      );
    });
  }, [entries, searchQuery]);

  // Columns for DataTable
  const columns: Column<AuditLedgerEntry>[] = [
    {
      key: "seq",
      header: "Seq #",
      sortable: true,
      render: (row) => (
        <span className="font-mono font-bold text-xs text-[var(--accent-teal)]">
          #{row.seq ?? row.sequence_number ?? 0}
        </span>
      ),
    },
    {
      key: "action",
      header: "Action / Event",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-xs text-[var(--text-primary)]">{row.action}</div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">
            actor: {row.actor || row.actor_role || "system"}
          </div>
        </div>
      ),
    },
    {
      key: "entry_hash",
      header: "Entry Digest (SHA-256)",
      render: (row) => {
        const hash = row.entry_hash || row.hash || "";
        return (
          <span className="font-mono text-[11px] text-[var(--text-secondary)] flex items-center gap-1">
            <Hash className="w-3 h-3 text-[var(--accent-teal)]" />
            {hash ? `${hash.slice(0, 14)}...` : "—"}
          </span>
        );
      },
    },
    {
      key: "prev_hash",
      header: "Parent Hash",
      render: (row) => (
        <span className="font-mono text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
          <Link2 className="w-3 h-3 opacity-50" />
          {row.prev_hash ? `${row.prev_hash.slice(0, 10)}...` : "0000000000..."}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Timestamp",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)]">
          {row.created_at || row.ts ? new Date(row.created_at || row.ts || "").toLocaleTimeString() : "Recent"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header & Hash Verification Control */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
              Cryptographic Audit Ledger
            </h2>
            <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-[var(--accent-teal)]/10 text-[var(--accent-teal)] border border-[var(--accent-teal)]/30 font-semibold">
              Immutable Chain
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Tamper-evident, hash-chained statutory record of all state transitions, approvals, pricing modifications, and stock movements.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleVerifyChain}
            disabled={isVerifying}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium bg-[var(--accent-teal)] text-white hover:opacity-90 transition-colors disabled:opacity-50"
          >
            {isVerifying ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ShieldCheck className="w-3.5 h-3.5" />
            )}
            <span>🔒 Verify Hash Chain Integrity</span>
          </button>

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isLoading}
            className="p-1.5 border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
            title="Refresh ledger"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Verification Status Card Banner */}
      {verificationResult && (
        <div
          className={`p-4 border transition-all ${
            verificationResult.valid
              ? "bg-teal-500/10 border-teal-500/40 text-teal-950 dark:text-teal-50"
              : "bg-rose-500/10 border-rose-500/40 text-rose-950 dark:text-rose-50"
          }`}
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              {verificationResult.valid ? (
                <ShieldCheck className="w-5 h-5 text-[var(--accent-teal)] shrink-0 mt-0.5" />
              ) : (
                <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              )}
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm">
                    {verificationResult.valid ? "CHAIN VERIFIED (INTACT)" : "TAMPER DETECTED"}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)]">
                    {verificationResult.verified_entries} of {verificationResult.total_entries} Blocks Verified
                  </span>
                </div>
                <p className="text-xs opacity-90 mt-0.5">
                  {verificationResult.message ||
                    (verificationResult.valid
                      ? "Cryptographic SHA-256 recursive digest verification passed from Genesis (0*64) through ledger head."
                      : "Cryptographic hash chain validation failed: entry hash did not match calculated parent digest.")}
                </p>
              </div>
            </div>

            <div className="text-[11px] font-mono opacity-80 text-right shrink-0">
              Verified {new Date(verificationResult.verified_at).toLocaleTimeString()}
            </div>
          </div>

          {/* Cryptographic Hashes Overview */}
          <div className="mt-3 pt-3 border-t border-[var(--border-subtle)]/50 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-2 bg-[var(--bg-surface)] border border-[var(--border-subtle)]">
              <div className="text-[10px] uppercase text-[var(--text-secondary)] font-semibold flex justify-between">
                <span>Genesis Hash (Block #0)</span>
                {copiedHash === "genesis" ? (
                  <span className="text-[var(--accent-teal)]">Copied!</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => copyToClipboard(verificationResult.genesis_hash, "genesis")}
                    className="hover:text-[var(--accent-teal)]"
                  >
                    <Copy className="w-3 h-3" />
                  </button>
                )}
              </div>
              <div className="truncate text-[11px] text-[var(--text-primary)] mt-0.5">
                {verificationResult.genesis_hash || "0000000000000000000000000000000000000000000000000000000000000000"}
              </div>
            </div>

            <div className="p-2 bg-[var(--bg-surface)] border border-[var(--border-subtle)]">
              <div className="text-[10px] uppercase text-[var(--text-secondary)] font-semibold flex justify-between">
                <span>Head Hash (Latest Sealed Block)</span>
                {copiedHash === "head" ? (
                  <span className="text-[var(--accent-teal)]">Copied!</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => copyToClipboard(verificationResult.head_hash, "head")}
                    className="hover:text-[var(--accent-teal)]"
                  >
                    <Copy className="w-3 h-3" />
                  </button>
                )}
              </div>
              <div className="truncate text-[11px] text-[var(--text-primary)] mt-0.5">
                {verificationResult.head_hash || "—"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Filter Action:</span>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="px-2.5 py-1 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
          >
            <option value="all">All Actions</option>
            {actionTypes.map((action) => (
              <option key={action} value={action}>
                {action}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-[var(--text-secondary)]" />
            <input
              type="text"
              placeholder="Search hash, action, actor, node..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-2.5 py-1 text-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent-teal)] w-64"
            />
          </div>
        </div>
      </div>

      {/* Main Grid: Audit Table + Block Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Table View */}
        <div className="lg:col-span-7 space-y-2">
          <DataTable
            data={filteredEntries}
            columns={columns}
            keyExtractor={(row) => row.id || `audit-${row.seq || Math.random()}`}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedEntry(row)}
            emptyTitle="No audit records"
            emptyDescription="All state changes and human sign-offs will appear here with cryptographic seals."
            pageSize={10}
          />
        </div>

        {/* Block Detail & Cryptographic Hash Link Visualizer */}
        <div className="lg:col-span-5 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
            <span>Block Integrity & Hash Chain Inspector</span>
          </h3>

          {selectedEntry ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-sm text-[var(--accent-teal)]">
                      Block #{selectedEntry.seq ?? selectedEntry.sequence_number ?? 0}
                    </span>
                    <span className="px-1.5 py-0.5 text-[10px] font-mono bg-teal-500/10 text-[var(--accent-teal)] border border-teal-500/30">
                      SEALED
                    </span>
                  </div>
                  <div className="text-xs font-semibold text-[var(--text-primary)] mt-1">
                    {selectedEntry.action}
                  </div>
                </div>
                <div className="text-right text-[10px] font-mono text-[var(--text-secondary)]">
                  {selectedEntry.created_at || selectedEntry.ts
                    ? new Date(selectedEntry.created_at || selectedEntry.ts || "").toLocaleString()
                    : "N/A"}
                </div>
              </div>

              {/* Plain-Language Explanation */}
              {selectedEntry.explanation && (
                <div className="p-2.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)]">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)] block mb-1">
                    Plain-Language Audit Explanation:
                  </span>
                  <p className="leading-relaxed">{selectedEntry.explanation}</p>
                </div>
              )}

              {/* Cryptographic Link Visualizer */}
              <div className="space-y-2 p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)] block">
                  Cryptographic Chain Link: H[i] = SHA-256(H[i-1] + seq + action + payload)
                </span>

                {/* Parent Hash */}
                <div className="p-2 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-0.5">
                  <div className="flex items-center justify-between text-[10px] font-mono text-[var(--text-secondary)]">
                    <span>Parent Hash (prev_hash)</span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(selectedEntry.prev_hash, "prev")}
                      className="hover:text-[var(--accent-teal)]"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="font-mono text-[10px] text-[var(--text-secondary)] break-all select-all">
                    {selectedEntry.prev_hash || "0000000000000000000000000000000000000000000000000000000000000000"}
                  </div>
                </div>

                {/* Chaining Arrow */}
                <div className="flex justify-center text-[var(--accent-teal)] py-0.5">
                  <ArrowDown className="w-4 h-4 animate-pulse" />
                </div>

                {/* Current Entry Hash */}
                <div className="p-2 bg-[var(--bg-surface)] border border-[var(--accent-teal)]/40 space-y-0.5">
                  <div className="flex items-center justify-between text-[10px] font-mono text-[var(--accent-teal)] font-semibold">
                    <span>Current Entry Digest (entry_hash)</span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(selectedEntry.entry_hash || selectedEntry.hash || "", "curr")}
                      className="hover:text-[var(--accent-teal)]"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="font-mono text-[10px] text-[var(--text-primary)] font-bold break-all select-all">
                    {selectedEntry.entry_hash || selectedEntry.hash || "—"}
                  </div>
                </div>
              </div>

              {/* Actor & Metadata */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[10px] text-[var(--text-secondary)] uppercase block">Actor:</span>
                  <span className="text-[var(--text-primary)] font-semibold">
                    {selectedEntry.actor || selectedEntry.actor_role || "system"}
                  </span>
                </div>
                <div className="p-2 bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[10px] text-[var(--text-secondary)] uppercase block">Node ID:</span>
                  <span className="text-[var(--text-primary)] truncate block">
                    {selectedEntry.node_id || "Network Wide"}
                  </span>
                </div>
              </div>

              {/* Payload JSON */}
              <div className="space-y-1">
                <JsonViewer
                  data={selectedEntry.payload || selectedEntry.details || {}}
                  title="Block State Payload"
                  defaultExpanded={false}
                />
              </div>
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)] space-y-2">
              <ScrollText className="w-8 h-8 opacity-30 mx-auto text-[var(--accent-teal)]" />
              <p className="font-medium text-[var(--text-primary)]">Select an entry from the ledger</p>
              <p className="text-[11px]">
                Inspect recursive SHA-256 digests, payload snapshots, and statutory audit seals.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
