/**
 * Demand Cascade Page (/cascade)
 * Live event cascade feed, multi-tier single-unit retail demand propagation,
 * and live trigger event simulation.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Play, RefreshCw, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import { JsonViewer } from "../components/shared/JsonViewer";
import type { SystemEvent } from "../types/api";

export const CascadePage: React.FC = () => {
  const [selectedEvent, setSelectedEvent] = useState<SystemEvent | null>(null);
  const [triggerStatus, setTriggerStatus] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState<boolean>(false);

  const {
    data: events = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["cascade-events"],
    queryFn: () => api.events.list({ limit: 50 }),
    refetchInterval: 10000,
  });

  const handleTriggerSale = async () => {
    setIsTriggering(true);
    setTriggerStatus(null);
    try {
      const salePayload = {
        pharmacy_id: "11111111-1111-1111-1111-111111111111",
        product_id: "00000000-0000-0000-0000-000000000001",
        batch_id: "BATCH-PAR-01",
        quantity: 1,
        source: "pos_retail_counter",
        payload: {
          medicine_name: "Paracetamol 650mg",
          dispensed_units: 1,
          customer_receipt: `RCP-${Date.now()}`,
        },
      };
      await api.events.postEvent(salePayload);
      setTriggerStatus("Single-unit POS sale emitted successfully! Cascade triggered.");
      refetch();
    } catch (err: any) {
      setTriggerStatus(`Error: ${err.message || "Failed to trigger sale"}`);
    } finally {
      setIsTriggering(false);
    }
  };

  const columns: Column<SystemEvent>[] = [
    {
      key: "type",
      header: "Event Topic",
      sortable: true,
      render: (row) => <StatusBadge status="active" label={row.type} size="sm" />,
    },
    {
      key: "event_id",
      header: "Event ID",
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)]">
          {row.event_id.slice(0, 16)}...
        </span>
      ),
    },
    {
      key: "correlation_id",
      header: "Correlation ID",
      render: (row) => (
        <span className="font-mono text-[10px] text-[var(--text-secondary)]">
          {row.correlation_id ? `${row.correlation_id.slice(0, 14)}...` : "—"}
        </span>
      ),
    },
    {
      key: "timestamp",
      header: "Timestamp",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-[11px] text-[var(--text-secondary)]">
          {row.timestamp ? new Date(row.timestamp).toLocaleTimeString() : "—"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Title & Simulator Trigger */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            Demand Cascade Observability
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Single-unit POS dispense propagation across Pharmacy → Stockist → Distributor → Manufacturer.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleTriggerSale}
            disabled={isTriggering}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium bg-[var(--accent-teal)] text-white hover:bg-[var(--accent-teal)]/90 transition-colors disabled:opacity-50"
          >
            {isTriggering ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            Trigger 1-Unit Retail Dispense
          </button>
          <button
            type="button"
            onClick={() => refetch()}
            className="p-1.5 border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)]"
            title="Refresh events"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {triggerStatus && (
        <div className="p-3 bg-teal-500/10 border border-teal-500/30 text-teal-800 dark:text-teal-200 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[var(--accent-teal)]" />
          <span>{triggerStatus}</span>
        </div>
      )}

      {/* Grid: Events List + Detailed Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 space-y-2">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Live Stream Event Ledger ({events.length} records)
          </h3>
          <DataTable
            data={events}
            columns={columns}
            keyExtractor={(row) => row.event_id}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedEvent(row)}
            searchPlaceholder="Search event topic, event_id, or correlation_id..."
            searchFilter={(row, q) =>
              row.type.toLowerCase().includes(q) ||
              row.event_id.toLowerCase().includes(q) ||
              row.correlation_id?.toLowerCase().includes(q)
            }
            pageSize={8}
          />
        </div>

        <div className="lg:col-span-4 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
            Event Payload Inspector
          </h3>
          {selectedEvent ? (
            <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <StatusBadge status="active" label={selectedEvent.type} size="sm" />
                <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                  {new Date(selectedEvent.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="text-[11px] font-mono text-[var(--text-secondary)] space-y-1">
                <div>
                  <span className="text-[var(--text-primary)] font-medium">Node:</span> {selectedEvent.node_id}
                </div>
                {selectedEvent.correlation_id && (
                  <div>
                    <span className="text-[var(--text-primary)] font-medium">Correlation:</span>{" "}
                    {selectedEvent.correlation_id}
                  </div>
                )}
              </div>
              <JsonViewer data={selectedEvent.payload} title="Payload Details" defaultExpanded={true} />
            </div>
          ) : (
            <div className="p-8 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-center text-xs text-[var(--text-secondary)]">
              <Activity className="w-8 h-8 opacity-30 mx-auto mb-2" />
              <p>Click on any event in the table to inspect its full payload envelope.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
