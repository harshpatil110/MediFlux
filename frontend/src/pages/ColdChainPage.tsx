/**
 * Cold Chain Telemetry Page (/cold-chain)
 * Real-time IoT temperature monitoring, Arrhenius shelf-life decay, and autonomous batch quarantining.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Snowflake, Thermometer } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { ColdChainBatch } from "../types/api";

export const ColdChainPage: React.FC = () => {
  const [selectedBatch, setSelectedBatch] = useState<ColdChainBatch | null>(null);

  const {
    data: batches = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["coldchain-batches"],
    queryFn: () => api.coldchain.listBatches(),
  });

  const columns: Column<ColdChainBatch>[] = [
    {
      key: "product_name",
      header: "Biologic SKU & Batch",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
            <Snowflake className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
            {row.product_name}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">
            Batch ID: {row.batch_id}
          </div>
        </div>
      ),
    },
    {
      key: "last_temperature",
      header: "Last Sensor Temp",
      sortable: true,
      render: (row) => {
        const temp = row.last_temperature;
        const isExcursion = temp < 2 || temp > 8;
        return (
          <span
            className={`font-mono text-xs font-semibold flex items-center gap-1 ${
              isExcursion ? "text-rose-600 dark:text-rose-400" : "text-teal-700 dark:text-teal-300"
            }`}
          >
            <Thermometer className="w-3.5 h-3.5" />
            {temp !== undefined ? `${temp.toFixed(1)}°C` : "4.0°C"}
          </span>
        );
      },
    },
    {
      key: "storage_range",
      header: "Storage Bounds",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-secondary)]">
          {row.storage_range || "2°C to 8°C"}
        </span>
      ),
    },
    {
      key: "shelf_life_estimate",
      header: "Arrhenius Shelf Life",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)]">
          {row.shelf_life_estimate || "Nominal"}
        </span>
      ),
    },
    {
      key: "is_quarantined",
      header: "Safety Gate",
      sortable: true,
      render: (row) => (
        <StatusBadge
          status={row.is_quarantined ? "quarantined" : "approved"}
          label={row.is_quarantined ? "Quarantined" : "Cleared"}
          size="sm"
        />
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            Cold Chain Telemetry & Kinetic Stability
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            IoT sensor telemetry streams, temperature excursion alarms, and autonomous quarantine locks.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Sensors
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 space-y-2">
          <DataTable
            data={batches}
            columns={columns}
            keyExtractor={(row) => row.batch_id}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedBatch(row)}
            searchPlaceholder="Search product, batch ID, or quarantine status..."
            searchFilter={(row, q) =>
              row.product_name.toLowerCase().includes(q) ||
              row.batch_id.toLowerCase().includes(q) ||
              Boolean(row.node_name && row.node_name.toLowerCase().includes(q))
            }
            emptyTitle="No cold-chain batches registered"
            emptyDescription="Batches marked as cold-chain will appear here with live IoT temperature readings."
            pageSize={8}
          />
        </div>

        <div className="lg:col-span-4 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Sensor Telemetry & Arrhenius Diagnostics
          </h3>
          {selectedBatch ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-xs text-[var(--text-primary)]">
                    {selectedBatch.product_name}
                  </h4>
                  <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                    Batch: {selectedBatch.batch_id}
                  </span>
                </div>
                <StatusBadge
                  status={selectedBatch.is_quarantined ? "quarantined" : "approved"}
                  size="sm"
                />
              </div>

              <div className="p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Target Range:</span>
                  <span>{selectedBatch.storage_range || "2.0°C - 8.0°C"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Last Observed:</span>
                  <span className="font-semibold">{selectedBatch.last_temperature?.toFixed(1)}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Stability Estimate:</span>
                  <span>{selectedBatch.shelf_life_estimate}</span>
                </div>
              </div>

              <JsonViewer data={selectedBatch} title="Complete Batch Sensor Record" defaultExpanded={false} />
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <Thermometer className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Select any cold-chain batch to inspect thermal history and degradation curve.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
