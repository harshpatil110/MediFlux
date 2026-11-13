# Task 26 Specification: Workflow Screens

## Overview
Task 26 delivers the mission-critical operational workflow screens for **MediFlux**:
1. **Approvals Inbox (`frontend/src/pages/ApprovalsPage.tsx`)**:
   - Operator decision queue for Human-in-the-Loop (HITL) checkpoints.
   - Desktop Notification Hook (`useDesktopNotifications.ts`) integrating with SSE `hitl.created` events.
   - Split-pane layout with task queue, risk level badges (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), and SLA expiration countdown.
   - Deep inspection console with agent reasoning, context-aware payload diff, operator justification notes, and immediate graph resumption ("Approve & Resume Graph" / "Reject & Abort").
   - Post-decision feedback banner confirming resumed workflow details and cryptographic audit logging.

2. **Audit Ledger Viewer (`frontend/src/pages/AuditPage.tsx`)**:
   - Cryptographic verification banner with "🔒 Verify Hash Chain Integrity" executing `POST /api/v1/audit/verify`.
   - Live status card reporting verification status (`CHAIN VERIFIED (INTACT)` vs `TAMPER DETECTED`), total blocks verified, genesis hash, and head hash.
   - Filterable audit table supporting search and action filters.
   - Block detail drawer with plain-language explanations, recursive SHA-256 link visual (`prev_hash` $\rightarrow$ digest $\rightarrow$ `entry_hash`), and structured payload JSON viewer.

3. **Adapter Forge (`frontend/src/pages/AdapterForgePage.tsx`)**:
   - Studio generator featuring 1-click fixture selector pills (CSV, XML, JSON from `GET /api/v1/adapters/fixtures`).
   - "⚡ Forge & Register Adapter" button (`POST /api/v1/adapters/generate`) synthesizing self-evolving Python translators.
   - 4-Stage visual step tracker (Schema Inspector $\rightarrow$ Adapter Coder $\rightarrow$ Restricted Guard Tester $\rightarrow$ Registry Sealing).
   - Adapter Marketplace registry with version history and "⏪ Rollback Version" button (`POST /api/v1/adapters/{id}/rollback`).
   - "Try It Live" real-time ingestion sandbox (`POST /api/v1/ingest/{adapter_id}`) returning canonical events and `correlation_id`.

4. **Regulatory Hot-Swap Lab (`frontend/src/pages/RegulatoryLabPage.tsx`)**:
   - Notice Ingestion Studio with 1-click synthetic presets (NPPA DPCO Price Ceiling, CDSCO Track-and-Trace from `GET /api/v1/regulatory/fixtures`).
   - "🧬 Run Regulatory Pipeline" button (`POST /api/v1/regulatory/notifications`).
   - 5-Stage visual pipeline tracker (Analyst $\rightarrow$ DevOps Coder $\rightarrow$ Staging Guard $\rightarrow$ Human Approval Gate with "✓ Approve Gate & Hot-Swap Now" $\rightarrow$ Zero-Downtime Hot-Swap Active with "⏪ Rollback to v1").
   - Side-by-side code diff viewer for active module (`pricing_engine`) v1 vs staged v2.
   - Interactive Before / After Rule Test Sandbox (`POST /api/v1/regulatory/price-check`) demonstrating real-time DPCO ceiling enforcement (₹12.50 cap on `PARA-500`) without backend restart.

## Compliance
- Adheres strictly to `AGENTS.md` (no Redis, Docker, WASM, or Kafka).
- Adheres strictly to `design.md` Warm Editorial Minimalism design system (Warm Ivory canvas, Electric Teal `#00AEBB` accent, Ink Black typography, crisp 1px borders `#D8D3C3`).
