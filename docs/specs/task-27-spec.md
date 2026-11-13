# Task 27 Specification: Compliance, Copilot, and Developer Portal Screens

## Overview
Task 27 completes the full suite of specialized compliance, operational intelligence, and third-party developer screens for **MediFlux**:

1. **Sovereign Prescription Scanner & Schedule H Compliance (`frontend/src/pages/PrescriptionsPage.tsx`)**:
   - **Sovereign Local Execution Banner**: Emphasizes strict on-premises sovereign execution (`sensitivity="sensitive"`), ensuring zero cloud data leakage and statutory privacy protection.
   - **Privacy Redaction**: Irreversibly extracts and displays patient initials only (`patient_initials`, e.g., `R.K.`) with zero full patient names retained or persisted.
   - **Ingestion Studio & 5 Synthetic Presets**:
     1. Valid Standard Rx (`valid_prescription.png`): Approved dispense, Dr. A. K. Sharma (MCI-2019-88412).
     2. Schedule H Antibiotic Rx (`schedule_h_prescription.png`): Approved dispense, Dr. Priya Nair (DMC-55102), statutory Schedule H Rx log.
     3. Unknown Physician Rx (`unknown_doctor.png`): Doctor unverified in CDSCO / State Registry, routes to HITL approval.
     4. Missing Reg Number Rx (`missing_reg_no.png`): Missing physician license number, flagged for pharmacist inbox.
     5. Unlisted Formulation Rx (`unlisted_drug.png`): Unlisted active chemical entity, routes to pharmacist dual authorization.
   - **Preview & Structured Parse Console**: Live image preview, final verdict badge (`APPROVE DISPENSE` in Teal, `FLAGGED FOR HITL REVIEW` in Amber with link to `/approvals`, `REJECTED` in Coral), Doctor Registry verification card (`VERIFIED IN REGISTRY ✓` vs `UNVERIFIED ✗`), and Per-Drug CDSCO Schedule breakdown table (OTC, Schedule H, Schedule H1, Schedule X).
   - **Schedule H POS Sale Dispatch**: "💊 Test Schedule H POS Sale with prescription_id" button linking directly to the Demand Cascade.
   - **Statutory Audit History**: Searchable compliance and prescription scan registry ledger.

2. **Cold-Chain Biologics Telemetry Monitor & Auto-Quarantine (`frontend/src/pages/ColdChainPage.tsx`)**:
   - **Top KPI Strip**: Real-time count of monitored cold-chain batches, active within envelope (2.0°C–8.0°C), quarantined batches (available quantity zeroed), and mean remaining viability %.
   - **Admin IoT Sensor Simulator**: Batch selector with 3 interactive simulation modes:
     - 🌡️ *Run Normal Telemetry* (nominal 4.8°C).
     - 🔥 *Trigger Thermal Excursion* (escalates > 8.0°C, triggers auto-quarantine, zeroes available inventory, and initiates Dynamic Balancing Agent rebalance cascade).
     - 💥 *Trigger Transit Shock* (mechanical shock spike > 8.0g threshold).
   - **Cold-Chain Batches Fleet Grid**: Batch status badges, available inventory (strikes through and zeroes on quarantine), and Arrhenius potency progress bar.
   - **Live Recharts Telemetry Visualizers**:
     - *Chart 1*: Temperature (°C) vs safe envelope with 2.0°C and 8.0°C reference lines.
     - *Chart 2*: Mechanical shock (g-force) and container humidity (%) with 4.0g warning and 8.0g critical breach reference lines.
   - **Arrhenius Shelf-Life Diagnostics**: Breakdown card detailing the Arrhenius kinetic model formula, nominal shelf-life days, degradation days incurred, and effective remaining days.
   - **Quarantine History & Clinical Narrative Feed**: Detailed clinical justification log by the Excursion Analyst Agent with clickable correlation ID link to restock trace.

3. **Network Copilot & Semantic Vector Search (`frontend/src/pages/CopilotPage.tsx`)**:
   - **Caller RLS Scope Header**: Live indicator displaying authenticated user operational scope (`Scope: PHARMACY NODE (RLS BOUND)` vs `Scope: NETWORK ADMIN (FULL TOPOLOGY)`).
   - **Suggested Operational Quick-Chips**: One-click prompt pills for real-time stock balances, cold-chain excursion checks, DPCO price ceiling gazettes, and open HITL approvals.
   - **Conversational Intelligence**: Progressive tool execution pills (`tools_used: ["lookup_inventory", "check_coldchain", "search_gazettes"]`) and grounded reasoning.
   - **Multi-Entity Navigation Chips**: Clickable entity badges below answers linking directly to `/overview`, `/regulatory-lab`, `/cold-chain`, `/approvals`, and `/cascade`.
   - **pgvector Semantic Search Tab**: Direct cosine-similarity vector search across vectorized product catalogs, regulatory gazettes, and cold-chain incident embeddings.

4. **Developer Platform & MCP Server Hub (`frontend/src/pages/DeveloperPage.tsx`)**:
   - **Tab 1: Scoped API Key Management**:
     - Provisioning form with human-readable name, rate limits (1–10,000 req/min), optional node UUID binding, and granular scope checkboxes (`read:inventory`, `write:events`, `read:stream`, `read:audit`, `use:copilot`, `manage:adapters`, `manage:hitl`, `*`).
     - Show-once modal displaying plaintext 256-bit secret key with 1-click copy ("Will never be displayed again").
     - Provisioned keys table with key prefix, scopes, rate limits, created dates, and instant revocation.
   - **Tab 2: Webhooks & Delivery Logs**:
     - Subscription studio for target HTTPS/HTTP endpoints with HMAC-SHA256 signature verification.
     - "🚀 Deliver Test Webhook" trigger button for immediate signed test events.
     - Delivery log table displaying HTTP response codes, latency in ms, HMAC headers, and payload/response inspector.
   - **Tab 3: Interactive Code Snippets & OpenAPI Hub**:
     - Direct access links to Swagger UI (`/docs`), ReDoc (`/redoc`), and OpenAPI JSON.
     - Copyable integration snippets in `cURL`, `Python (httpx)`, and `JavaScript (fetch)` with active developer key automatically interpolated.
   - **Tab 4: MCP Server Hub (Task 23 Model Context Protocol)**:
     - Registry table listing all 7 official MCP domain tools (`get_inventory`, `get_stockout_risk`, `list_open_approvals`, `get_cascade_trace`, `ask_copilot`, `submit_sale_event`, `decide_approval`).
     - Ready-to-paste JSON client configs for Claude Desktop, Cursor, and Antigravity.
     - Interactive MCP Tool Tester calling `POST /api/v1/mcp/call` over HTTP.

## Backend Endpoints Added & Enriched
- `GET /api/v1/prescriptions`: Lists prescriptions with strict patient initials redaction and `sensitivity="sensitive"`.
- `GET /api/v1/prescriptions/fixtures`: Returns 5 synthetic prescription fixtures with embedded base64 data URIs.
- `POST /api/v1/prescriptions`: Supports multipart and JSON `fixture_name` / `image_base64`, executes Sovereign LangGraph pipeline, logs compliance and audit trails, emits `prescription.scanned`.
- `GET /api/v1/coldchain/batches`: Enriched with 6+ chronological telemetry readings (`ts`, `temperature_c`, `humidity`, `shock_g`) and Arrhenius shelf-life estimates.
- `POST /api/v1/coldchain/simulate`: Injects synthetic normal, excursion, or shock telemetry; executes cold-chain auto-quarantine, zeroes stock, records clinical narrative, and triggers restock trace.
- `POST /api/v1/copilot/query`: Accepts both `question` and `query` parameters, returns grounded tools and references.
- `GET /api/v1/developer/keys`, `POST /api/v1/developer/keys`, `DELETE /api/v1/developer/keys/{id}`: Scoped API key lifecycle.
- `GET /api/v1/developer/webhooks`, `POST /api/v1/developer/webhooks/{id}/test`: Webhook subscription and signed delivery engine.
- `GET /api/v1/mcp/tools`, `POST /api/v1/mcp/call`: Model Context Protocol tool discovery and execution.

## Verification
- Automated test suite `backend/tests/test_task27_portal_compliance_copilot_ui.py` passes 8/8 tests.
- Full backend test suite passes with 0 regressions.
- Backend linter `ruff check .` passes with 0 warnings/errors.
- Frontend build `npm --prefix frontend run build` passes with 0 errors.
- Design strictly complies with Warm Editorial Minimalism (`#E8E4D3` ivory canvas, `#00AEBB` teal accent, `#D8D3C3` borders).
