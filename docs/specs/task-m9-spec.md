# Task M9 Specification: Polish, Resilience and Testing

## 1. Overview
Task M9 hardens, polishes, and thoroughly validates the entire MediFlux mobile client (`mobile/`) and its corresponding backend test harness:
1. **Network Resilience & Global Offline Banner**:
   - Integrated `@react-native-community/netinfo` with fallback to browser `window.addEventListener('online' | 'offline')` on web.
   - Built programmatic network simulation toggles (`setSimulatedOffline(boolean)`, `resetSimulatedNetwork()`) for zero-hardware demo resilience testing.
   - Mounted `<GlobalOfflineBanner />` at application root with high-contrast Ink Black styling, 2px warning border, and accessible >=44pt retry button.
2. **State & Screen Polish**:
   - Reusable `LoadingState.tsx`, `EmptyState.tsx`, `ErrorState.tsx`, and `OfflineState.tsx` components enforcing minimum 44pt touch targets, accessibility roles, and friendly retry buttons.
   - List performance hardening via `React.memo` and `useCallback` on high-frequency feed/task list components.
3. **Warm Editorial Minimalism Theme Context & Assets**:
   - Implemented `ThemeContext.tsx` supporting `'light' | 'dark' | 'system'` modes with `AsyncStorage` persistence and dynamic token switching.
   - Generated high-resolution branding assets using Pillow: `icon.png` (1024x1024), `adaptive-icon.png` (1024x1024), `splash.png` (1284x2778), and `favicon.png` (48x48) adhering strictly to Warm Ivory `#E8E4D3`, Ink Black `#031211`, and Electric Teal `#00AEBB`.
   - Updated `mobile/app.config.ts` display name to `'NexusChain India (MediFlux)'`.
4. **Dev / Demo Resilience Controls**:
   - Added collapsible `🧪 Resilience & Failure Injection (Dev / Demo)` harness in `mobile/app/(auth)/settings.tsx` with 5 interactive triggers:
     - 401 Unauthorized Session Expiry
     - 429 Rate Limit Backoff
     - 503 LLM Copilot Offline Fallback
     - Network Offline Simulation
     - Reset Demo State (`POST /api/v1/demo/reset`)
5. **Automated Jest Test Suite & CI Validation**:
   - Created mobile Jest suite in `mobile/src/__tests__/`:
     - `saleIdempotency.test.ts`: Offline queue recovery and client-generated UUID deduplication.
     - `apiClient.test.ts`: Base URL discovery, auth header injection, 401 interceptor.
     - `useEventStream.test.ts`: SSE reconnection backoff and topic dispatching.
     - `roleMap.test.ts`: Role-based route guard and capability mapping.
     - `cascadeTimeline.test.ts`: Replay speed math and state transitions.
   - Configured `"check": "npm run typecheck && npm run lint && npm run test"` in `mobile/package.json`.
6. **Demo Reset, CLI Runner, and Visual Artifacts**:
   - Enhanced `scripts/reset_demo.py` to reset mobile state (device tokens, cold-chain temperatures 2-8°C, 20 catalog barcodes, baseline HITL tasks, and cascade history traces).
   - Created `scripts/run_mobile_demo.py` exercising 8 sequential end-to-end mobile user journeys.
   - Created `scripts/capture_mobile_screenshots.py` generating 6 high-DPI screenshots (780x1688) in `docs/screenshots/mobile/`.
   - Built comprehensive backend test suite in `backend/tests/test_task_m9_mobile_polish_and_resilience.py`.

---

## 2. Technical Architecture & Components

### 2.1 Network Resilience (`mobile/src/hooks/useNetworkStatus.ts` & `GlobalOfflineBanner.tsx`)
- `useNetworkStatus()` hook:
  - Tracks `isConnected: boolean`, `isInternetReachable: boolean | null`, `isSimulatedOffline: boolean`, and network type details.
  - Subscribes to `NetInfo.addEventListener` on native platforms.
  - Subscribes to `window.addEventListener('online' | 'offline')` on web.
  - Exposes `setSimulatedOffline(value: boolean)` and `resetSimulatedNetwork()` allowing programmatic toggling.
- `GlobalOfflineBanner`:
  - Positioned at the top of the viewport in `mobile/app/_layout.tsx`.
  - Animates in when offline or simulated offline.
  - Displays message: `"Offline Mode — Using cached data. Actions will queue until reconnected."`
  - Includes a >=44pt touch target button: `"Retry / Reconnect Now"`.

### 2.2 Reusable State Components (`mobile/src/components/`)
- `LoadingState.tsx`: Accessible loading indicator with `accessibilityRole="progressbar"`, custom title, and subtitle.
- `EmptyState.tsx`: High-contrast icon, empty message, and optional action button with minimum 44pt touch target (`accessibilityRole="button"`).
- `ErrorState.tsx`: Structural 1px border card with Crimson accent, clear error message, and 44pt Retry button.
- `OfflineState.tsx`: Standalone screen placeholder for views requiring network connectivity when offline.

### 2.3 Theme Context & Tokens (`mobile/src/theme/`)
- `tokens.ts`: Exported `lightColors`, `darkColors`, `colors`, typography tokens, and spacing tokens.
- `ThemeContext.tsx`:
  - Preferences: `'light' | 'dark' | 'system'`.
  - Persisted in `AsyncStorage.getItem('theme_preference')`.
  - Listens to device system changes via `useColorScheme()`.
  - Injected globally via `ThemeProvider` in `_layout.tsx`.

### 2.4 Dev Failure-Injection Controls (`mobile/app/(auth)/settings.tsx`)
- Collapsible section under Settings available in `__DEV__` or demo mode:
  1. **Simulate 401 Session Expiry**: Injects expired token into storage and calls protected endpoint to trigger automatic redirect to login.
  2. **Simulate 429 Rate Limit**: Simulates rapid bursts triggering exponential backoff notice.
  3. **Simulate 503 Sovereign Copilot Fallback**: Tests offline AI fallback message.
  4. **Toggle Network Offline Simulation**: Flips `setSimulatedOffline(!isSimulatedOffline)`.
  5. **Reset Demo State**: Issues `POST /api/v1/demo/reset` to restore pristine inventory and telemetry.

### 2.5 Automated Testing Suite (`mobile/src/__tests__/`)
- Configured Jest with `ts-jest` for TypeScript compilation:
  - `saleIdempotency.test.ts`: Validates client-side UUID persistence across network retries, preventing double-dispensing.
  - `apiClient.test.ts`: Validates Bearer token headers, custom base URL resolution, and error envelope parsing.
  - `useEventStream.test.ts`: Validates SSE exponential backoff reconnection logic.
  - `roleMap.test.ts`: Validates role-to-tab permissions and default screens.
  - `cascadeTimeline.test.ts`: Validates replay speed intervals (1200ms, 600ms, 300ms) and step computation.

---

## 3. Verification & Acceptance Criteria

| Criteria | Verification Method | Status |
| :--- | :--- | :--- |
| **AC1: Offline Resilience & NetInfo** | `useNetworkStatus` tests, simulated offline banner display, retry button >=44pt | PASS |
| **AC2: Branding Assets & App Config** | `icon.png`, `adaptive-icon.png`, `splash.png`, `favicon.png` per Design.md | PASS |
| **AC3: Jest Test Suite & CI Check** | `npm run check` (typecheck + lint + test) passes 23/23 tests | PASS |
| **AC4: Demo Reset & Runner** | `scripts/reset_demo.py` and `scripts/run_mobile_demo.py` repeatable consecutively | PASS |
| **AC5: Screenshots Gallery** | 6 high-DPI screenshots in `docs/screenshots/mobile/` documented in `docs/MOBILE.md` | PASS |
| **AC6: Backend Hardening Tests** | `test_task_m9_mobile_polish_and_resilience.py` 7/7 tests passing | PASS |
