/**
 * Overview Page (/overview)
 * Network KPI summary cards and topological network nodes table.
 */

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Boxes,
  Building2,
  Layers,
  Package,
  Radio,
  RefreshCw,
} from "lucide-react";
import { api } from "../lib/api";
import { DataTable, type Column } from "../components/shared/DataTable";
import { StatusBadge } from "../components/shared/StatusBadge";
import type { NetworkNode } from "../types/api";

export const OverviewPage: React.FC = () => {
  const {
    data: kpis,
    isLoading: kpisLoading,
    refetch: refetchKpis,
  } = useQuery({
    queryKey: ["overview-kpis"],
    queryFn: () => api.overview.getKpis(),
  });

  const {
    data: nodes = [],
    isLoading: nodesLoading,
    refetch: refetchNodes,
  } = useQuery({
    queryKey: ["network-nodes"],
    queryFn: () => api.nodes.list({ limit: 50 }),
  });

  const columns: Column<NetworkNode>[] = [
    {
      key: "name",
      header: "Node Facility",
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-semibold text-[var(--text-primary)]">{row.name}</div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">{row.license_number}</div>
        </div>
      ),
    },
    {
      key: "tier",
      header: "Supply Tier",
      sortable: true,
      render: (row) => <StatusBadge status="active" label={row.tier} size="sm" />,
    },
    {
      key: "region",
      header: "Zone & Region",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-xs text-[var(--text-primary)]">
          {row.region} • {row.city}
        </span>
      ),
    },
    {
      key: "id",
      header: "Node UUID",
      render: (row) => (
        <span className="font-mono text-[10px] text-[var(--text-secondary)]">
          {row.id.slice(0, 8)}...
        </span>
      ),
    },
  ];

  const handleRefreshAll = () => {
    refetchKpis();
    refetchNodes();
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)]">
            Network Operations & Topography
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            4-Tier autonomous pharmaceutical supply chain control plane.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefreshAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)] transition-colors self-start sm:self-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Telemetry
        </button>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-[10px] font-mono uppercase">Network Nodes</span>
            <Building2 className="w-4 h-4 text-[var(--accent-teal)]" />
          </div>
          <div className="text-2xl font-serif font-bold text-[var(--text-primary)]">
            {kpisLoading ? "..." : kpis?.total_nodes ?? 25}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">4 tiers active</div>
        </div>

        <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-[10px] font-mono uppercase">Products</span>
            <Package className="w-4 h-4 text-[var(--accent-teal)]" />
          </div>
          <div className="text-2xl font-serif font-bold text-[var(--text-primary)]">
            {kpisLoading ? "..." : kpis?.total_products ?? 20}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">CDSCO Schedules</div>
        </div>

        <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-[10px] font-mono uppercase">Active Batches</span>
            <Boxes className="w-4 h-4 text-[var(--accent-teal)]" />
          </div>
          <div className="text-2xl font-serif font-bold text-[var(--text-primary)]">
            {kpisLoading ? "..." : kpis?.active_batches ?? 40}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">Barcoded items</div>
        </div>

        <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-[10px] font-mono uppercase">Inventory Rows</span>
            <Layers className="w-4 h-4 text-[var(--accent-teal)]" />
          </div>
          <div className="text-2xl font-serif font-bold text-[var(--text-primary)]">
            {kpisLoading ? "..." : kpis?.inventory_records ?? 425}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">Scoped balances</div>
        </div>

        <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1 col-span-2 md:col-span-1">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-[10px] font-mono uppercase">Events Streamed</span>
            <Radio className="w-4 h-4 text-[var(--accent-teal)]" />
          </div>
          <div className="text-2xl font-serif font-bold text-[var(--text-primary)]">
            {kpisLoading ? "..." : kpis?.total_events ?? 10}
          </div>
          <div className="text-[10px] font-mono text-[var(--text-secondary)]">Real-time bus</div>
        </div>
      </div>

      {/* Network Nodes Table */}
      <div className="space-y-2">
        <h3 className="text-sm font-serif font-bold text-[var(--text-primary)]">
          Seeded Network Nodes Topology
        </h3>
        <DataTable
          data={nodes}
          columns={columns}
          keyExtractor={(row) => row.id}
          isLoading={nodesLoading}
          searchPlaceholder="Search facility name, tier, city, or license..."
          searchFilter={(row, q) =>
            row.name.toLowerCase().includes(q) ||
            row.tier.toLowerCase().includes(q) ||
            row.city.toLowerCase().includes(q) ||
            row.license_number.toLowerCase().includes(q)
          }
          pageSize={10}
        />
      </div>
    </div>
  );
};
