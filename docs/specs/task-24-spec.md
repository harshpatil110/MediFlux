# Task 24 Specification: Frontend Shell, Auth and Shared Infrastructure

## 1. Overview & Objective
Task 24 establishes the production React + TypeScript + Vite + Tailwind CSS application skeleton (`frontend/`) serving as the operational foundation for all 11 supply chain screens. It is wired directly to the real FastAPI backend API and Supabase Auth with zero mock-only stubs, role-aware navigation, shared UI primitives, a resilient `useEventStream` SSE hook with `Last-Event-ID` auto-reconnect, a live SSE debug panel, and all 11 operational screen routes scaffolded.

---

## 2. Architectural Components

### 2.1 Design System & Typography (`design.md`)
- **Visual Style**: Warm Editorial Minimalism.
- **Canvas & Surface**:
  - Canvas: `#E8E4D3` Warm Ivory (Light), `#141412` (Dark).
  - Surface: `#FFFFFF` (Light), `#1F1E1B` (Dark).
  - Accents: Electric Teal (`#00AEBB`), Emerald (`#10B981`), Amber (`#F59E0B`), Rose (`#F43F5E`).
  - Text: Ink Black (`#031211`), Charcoal (`#5C584E`).
  - Borders: Structural 1px crisp borders (`#D8D3C3` Light, `#2D2C27` Dark).
- **Typography Stack**:
  - Headings / Editorial Serif: `Playfair Display`, `Georgia`, serif.
  - Body / UI: `Inter`, -apple-system, sans-serif.
  - Technical / Code / Telemetry: `JetBrains Mono`, monospace.
- **Theme**: Light / Dark toggle persisted in `localStorage` (`mediflux_theme`) with automatic `.dark` root switching.

---

### 2.2 Backend Auth, CORS & Event Ingestion Enhancements
1. **Authentication Endpoints (`backend/app/api/v1/endpoints/auth.py`)**:
   - `GET /api/v1/auth/demo-users`: Returns all 7 seeded demo users with role credentials, node mappings, and route access matrices.
   - `POST /api/v1/auth/login`: Supports role-based quick login, demo password authentication, and Supabase JWT fallback.
   - `GET /api/v1/auth/me`: Returns enriched profile with assigned node topology and allowed navigation routes.
2. **CORS Middleware (`backend/app/main.py` & `backend/app/core/config.py`)**:
   - Allows `http://localhost:5173`, `http://127.0.0.1:5173`, `tauri://localhost`, `https://tauri.localhost`, `http://tauri.localhost`.
   - Exposes `Last-Event-ID`, `Retry-After`, `X-RateLimit-*`.
3. **Canonical Event Ingestion (`backend/app/api/v1/endpoints/events.py`)**:
   - `POST /api/v1/events`: Ingests either atomic retail POS sales (`SaleEvent`) or generic domain event envelopes, broadcasting to `pos.sales` or target topics.
   - `GET /api/v1/events`: Retrieves recent domain events from the event bus history and Supabase `events` table.
4. **AI Agent Observability (`backend/app/api/v1/endpoints/agents.py`)**:
   - `GET /api/v1/agents/runs`: Retrieves recent AI agent execution traces, model selections, and latencies.

---

### 2.3 Strict Role-Aware Navigation Matrix (`frontend/src/config/navigation.ts`)
| Screen Route | Allowed Roles | Description |
| :--- | :--- | :--- |
| `/overview` | All 7 Roles | Network telemetry, KPIs, topological nodes, and system health. |
| `/cascade` | `admin`, `regulator`, `manufacturer`, `distributor`, `stockist`, `pharmacy` | Single-unit POS demand propagation and multi-tier cascade traces. |
| `/agents` | `admin`, `manufacturer`, `distributor`, `stockist`, `developer` | Autonomous supply chain agent graph executions and LLM telemetry. |
| `/approvals` | `admin`, `regulator`, `manufacturer`, `distributor`, `stockist`, `pharmacy` | Human-in-the-Loop decision queues, timeout guards, and approvals. |
| `/adapter-forge` | `admin`, `manufacturer`, `pharmacy`, `developer` | Self-evolving legacy ERP translators and code generation sandbox. |
| `/regulatory-lab` | `admin`, `regulator` | CDSCO notification parsing, compliance mutations, and staging hot-swaps. |
| `/prescriptions` | `admin`, `regulator`, `pharmacy` | Sovereign multimodal prescription scanning and Schedule H ledger. |
| `/cold-chain` | `admin`, `regulator`, `manufacturer`, `distributor`, `stockist`, `pharmacy` | IoT environmental sensors, Arrhenius degradation, and batch quarantines. |
| `/audit` | `admin`, `regulator`, `developer` | Tamper-evident, hash-chained immutable cryptographic audit trail. |
| `/copilot` | All 7 Roles | RLS-scoped conversational AI agent with grounded supply chain citations. |
| `/developer` | `admin`, `developer` | API keys, HMAC webhooks, rate limiting, and system endpoints. |

Route enforcement is applied both at navigation render time (filtered sidebar) and route entry time via `<ProtectedRoute allowedRoles={...}>`.

---

### 2.4 Resilient SSE Streaming Hook & Live Debug Panel
- `useEventStream(topics)` (`frontend/src/hooks/useEventStream.ts`):
  - Subscribes to `/api/v1/events/stream` with topic filtering.
  - Sends `Last-Event-ID` header and query param for seamless replay across network reconnections.
  - Implements exponential backoff auto-reconnect.
  - Maintains an in-memory ring buffer of the latest 100 received events.
- `SseDebugPanel` (`frontend/src/components/layout/SseDebugPanel.tsx`):
  - Accessible via the top header status pill on every screen.
  - Real-time connection status indicator with live count.
  - Topic filter chips.
  - "Emit Live Test Event" trigger calling `POST /api/v1/events`.
  - Monospace JSON viewer with one-click copy.

---

### 2.5 Shared UI Primitives (`frontend/src/components/shared/`)
- `DataTable.tsx`: Generic typed data table with sorting, search filtering, pagination, and empty/loading states.
- `StatusBadge.tsx`: Semantic status badge mapping domain statuses to Warm Editorial styling.
- `JsonViewer.tsx`: Monospace collapsible JSON inspector with copy button.
- `LoadingState.tsx`: Warm Editorial spinner and progress indicator.
- `ErrorState.tsx`: Structured error card with optional retry action.
- `EmptyState.tsx`: Fallback state for empty collections.

---

## 3. Verification & Compliance
- **Frontend Build**: `tsc -b && vite build` passed cleanly with 0 errors (`dist/assets/index-*.js`, 94.87 kB gzip).
- **Backend Tests**: `backend/tests/test_task24_frontend_infra.py` (8/8 passed).
- **Full Backend Suite**: Verified with `pytest` and `ruff check .` with 0 warnings/errors.
