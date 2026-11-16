# Task M8 Specification: Network Copilot and Cascade History (Lite)

## 1. Overview
Task M8 provides an RLS-scoped conversational Supply Chain Copilot and a multi-tier Cascade History & Animated Replay experience for MediFlux mobile:
1. **RLS-Scoped Natural-Language Copilot (`mobile/app/(tabs)/copilot.tsx`)**:
   - Strictly scopes all queries and citations to the caller's authorized supply-chain node (when caller is a retail `pharmacy`).
   - Grounded natural-language reasoning with multi-entity Reference Chips (`inventory`, `batch`, `approval`, `cascade`).
   - In-memory session-only conversation state (never persisted to `AsyncStorage`), auto-cleared on logout.
   - Role-aware suggested prompts (`getSuggestedQuestionsForRole`).
   - Progressive answer reveal, live animated activity steps, and friendly LLM error recovery (`formatCopilotError`) with 1-tap retry.
2. **Cascade History & Animated Replay (`mobile/app/cascade/index.tsx`, `mobile/app/cascade/[id].tsx`, `CascadeTimeline.tsx`)**:
   - Cascade Listing endpoint `GET /api/v1/cascade` with RLS node filtering, outcome filtering, and 3 baseline seeded cascades (`casc-seed-01`, `casc-seed-02`, `casc-seed-03`).
   - Full 5-stage trace retrieval (`GET /api/v1/cascade/{correlation_id}`) spanning `supervisor`, `pharmacy`, `stockist`, `distributor`, and `manufacturer`.
   - Reusable `CascadeTimeline` component with Interactive Replay Controller Bar, Play/Pause/Restart buttons, speed pills (`1x`, `2x`, `4x`), and step scrubber.

---

## 2. Technical Architecture & Endpoints

### 2.1 Cascade Listing & Observability (`backend/app/api/v1/endpoints/cascade.py`)
- `GET /api/v1/cascade`:
  - Query parameters: `limit: int = Query(default=25, ge=1, le=100)`, `outcome: Optional[str] = Query(default=None)`.
  - Row-Level Security (RLS): If `current_user.role == "pharmacy"`, strictly filters to cascades originating from or involving `current_user.node_id`. Admins and regulators see all network cascades.
  - Return schema (`CascadeSummaryItem`):
    - `correlation_id: str`
    - `product_id: str`
    - `product_name: str`
    - `sku: str`
    - `pharmacy_node_id: str`
    - `pharmacy_name: str`
    - `created_at: str`
    - `outcome: str` (`complete | partial | waiting_approval`)
    - `steps_completed: int`
    - `total_steps: int`
    - `total_duration_ms: float`
    - `total_tokens: int`
    - `summary: str`
- `GET /api/v1/cascade/{correlation_id}`:
  - Retrieves exact ordered 5-stage trace:
    - Tier 5: Supervisor Orchestrator (`supervisor`)
    - Tier 4: Pharmacy Edge Node (`pharmacy`)
    - Tier 3: Stockist Regional Hub (`stockist`)
    - Tier 2: Logistics Distributor (`distributor`)
    - Tier 1: Formulation Plant (`manufacturer`)
  - Guaranteed deterministic replay for past cascades.

### 2.2 Copilot RLS & Citations (`backend/app/graphs/copilot.py` & `backend/app/api/v1/endpoints/copilot.py`)
- `POST /api/v1/copilot/query`:
  - `CopilotScope`: Enforces caller identity; pharmacy users cannot override `node_id`.
  - `get_stockout_risk`: Strictly scopes candidate pharmacies to caller's node when `role == "pharmacy"`.
  - Multi-Entity Reference Chips Contract:
    - `id: str`
    - `type: str` (`inventory | batch | approval | cascade`)
    - `label: str`
    - `node_id: str | None`
    - `node_name: str | None`
    - `product_id: str | None`
    - `barcode: str | None`
    - `deep_link: str | None`
  - Structured Error Code Mapping:
    - `429` / Rate Limit: `LLM_PROVIDER_BUSY` (`retryable: true`)
    - `503` / Unreachable: `SOVEREIGN_LOCAL_MODEL_OFFLINE` (`retryable: true`)
    - `403` / Forbidden: `COPILOT_FORBIDDEN_SCOPE` (`retryable: false`)

---

## 3. Mobile Features (`mobile/`)

### 3.1 Network Copilot (`mobile/app/(tabs)/copilot.tsx`)
- In-memory conversation state: `messages: CopilotChatMessage[]` kept in memory only; cleared on logout or "Clear Chat".
- Header navigation button to switch to Cascade History.
- Live activity indicator cycling through execution steps while query is in flight.
- Bubble layout with Ink Black `#031211` user bubble and Warm Ivory Copilot card with 1px structural borders and Electric Teal accents.
- Friendly error card with 1-tap retry.

### 3.2 Reference Chips & Deep Linking (`mobile/src/features/copilot/ReferenceChipList.tsx`)
- Resolves reference chip types to mobile routes:
  - `inventory`: `/(tabs)/sell?product_id=${product_id}`
  - `batch`: `/cold-chain/${batch_id}`
  - `approval`: `/approvals/${task_id}`
  - `cascade`: `/cascade/${correlation_id}?mode=replay`

### 3.3 Cascade History & Replay (`mobile/app/cascade/index.tsx` & `CascadeTimeline.tsx`)
- Outcome filtering pills: `All`, `Complete`, `Partial`, `Waiting Approval`.
- Replay Controller Bar:
  - Play/Pause/Restart buttons.
  - Speed pills: `1x` (1200ms), `2x` (600ms), `4x` (300ms).
  - Step progress scrubber and animated step-by-step transition.
- Pure testable helpers: `computeReplayDisplaySteps` and `getReplayIntervalMs` in `mobile/src/features/cascade/replayHelpers.ts`.

---

## 4. Verification & Automated Test Coverage
- `backend/tests/test_task_m8_copilot_and_cascade_history.py` (9 tests, 100% pass):
  - Baseline seeded cascades schema & retrieval.
  - Strict pharmacy RLS isolation on `GET /api/v1/cascade` and `POST /api/v1/copilot/query`.
  - 5-stage trace retrieval for past correlation IDs.
  - Error mapping (429, 503, 403).
- Full mobile suite `test_task_m1_mobile_foundation.py` through `test_task_m8_copilot_and_cascade_history.py` (73 tests, 100% pass).
- TypeScript strict typecheck (`tsc --noEmit`) and ESLint: 0 errors.
- Expo web export (`npx expo export --platform web`): clean bundle export.
