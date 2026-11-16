# Task M7 Specification: Cold-Chain Monitor and Notifications (Local and Remote Push)

## 1. Overview
Task M7 provides comprehensive cold-chain monitoring, telemetry time-series visualization, Arrhenius shelf-life degradation models, and autonomous quarantine management for sensitive biologics, alongside a dual-stage notification architecture:
- **Stage A (Local Notifications & Tap Deep-Linking)**: Foreground and background local alerts triggered via Server-Sent Events (SSE) on topics `hitl` and `coldchain`, interactive visual push alert banners, and deep-link routing (`/approvals/${taskId}` and `/cold-chain/${batchId}`).
- **Stage B (Remote Push Notifications & Device Token Management)**: RLS-secured `public.device_tokens` table, `POST /api/v1/devices`, `DELETE /api/v1/devices/{token}`, `GET /api/v1/devices`, and a non-blocking backend Expo Push dispatch service that filters recipients by role/node permissions, purges stale tokens on `DeviceNotRegistered`, and records tamper-evident audit logs.

---

## 2. Technical Architecture & Endpoints

### 2.1 Database & Migrations (`backend/supabase/migrations/20261116_create_device_tokens.sql`)
- Table `public.device_tokens`:
  - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id UUID NOT NULL`
  - `role VARCHAR(50)`
  - `node_id UUID REFERENCES public.nodes(id) ON DELETE SET NULL`
  - `token VARCHAR(255) NOT NULL UNIQUE`
  - `platform VARCHAR(32) NOT NULL DEFAULT 'android'` (`'android' | 'ios' | 'web' | 'expo'`)
  - `preferences JSONB DEFAULT '{"hitl": true, "coldchain": true}'::jsonb`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- Row-Level Security (RLS) policies:
  - Users can `SELECT`, `INSERT`, `UPDATE`, and `DELETE` only their own tokens (`auth.uid() = user_id`).
  - Full access for backend service-role (`auth.role() = 'service_role'`).

### 2.2 Device Token Endpoints (`backend/app/api/v1/endpoints/devices.py`)
- `POST /api/v1/devices`:
  - Upserts device push tokens bound to authenticated caller (`actor.user_id`, `actor.role`, `actor.node_id`).
  - Logs `action="device.token.registered"` to `public.audit_ledger` with masked token.
  - Returns HTTP 201 Created.
- `DELETE /api/v1/devices/{token:path}`:
  - Caller must own token (or caller is `admin`); returns HTTP 403 Forbidden on cross-user deletion attempts.
  - Deletes from DB and in-memory store; logs `action="device.token.removed"`.
  - Returns HTTP 200 OK `{"removed": true, "token": token}`.
- `GET /api/v1/devices`:
  - Returns caller's registered device tokens (or all if admin).

### 2.3 Backend Expo Push Service (`backend/app/services/push_notifications.py`)
- Configured via `settings.PUSH_ENABLED` and `settings.EXPO_PUSH_URL`.
- Subscribed to `in_process_event_bus` on `hitl` (`hitl.created`) and `coldchain` (`batch.quarantined`, `coldchain.quarantined`).
- Role & Node Recipient Filtering:
  - `hitl.created`: Selects tokens matching task `allowed_roles` (`config/hitl_policies.yaml`), scoped to `node_id` (or all for `admin`/`regulator`), with `preferences.hitl != false`.
  - `batch.quarantined`: Selects tokens scoped to affected `node_id` (or all for `admin`/`regulator`), with `preferences.coldchain != false`.
- Privacy-Safe Push Payload:
  - Titles and bodies contain zero sensitive patient data or secrets.
  - Data payload includes `type`, `taskId` / `batchId`, and `deepLink`.
- Automatic Token Cleanup:
  - Processes Expo ticket receipts; when `details.error == "DeviceNotRegistered"` (or invalid token format), automatically removes the stale token from DB and memory.
  - Logs `action="push.notification.cleaned_invalid_token"`.
- Non-blocking: all operations wrapped in exception guards, logging `action="push.notification.sent"` to `audit_ledger`.

### 2.4 Cold-Chain Endpoints (`backend/app/api/v1/endpoints/coldchain.py`)
- `GET /api/v1/coldchain/batches`:
  - Enriches all batches with sensor readings array, `last_reading`, Arrhenius shelf-life estimates, `node_id`, `node_name`, normalized status (`'ok' | 'warn' | 'quarantined'`), and `quarantine` metadata.
- `GET /api/v1/coldchain/batches/{batch_id}`:
  - Returns detailed batch telemetry, readings array, Arrhenius degradation breakdown, and quarantine audit trace. Returns HTTP 404 if not found.
- `GET /api/v1/coldchain/quarantines`:
  - Returns all quarantine actions enriched with Excursion Analyst plain-language reasons and cascade correlation IDs.
- `POST /api/v1/coldchain/simulate`:
  - Injects synthetic sensor series (`normal` vs `excursion`). On excursion breach, automatically triggers auto-quarantine, stock zeroing, rebalancing cascade, and `batch.quarantined` event broadcast.

---

## 3. Mobile Components & Screens (`mobile/`)

### 3.1 SVG Telemetry Chart (`mobile/src/features/coldchain/TelemetryChart.tsx`)
- Native-compatible SVG chart built with `react-native-svg` (`Svg`, `Line`, `Polyline`, `Circle`, `Rect`, `Text`).
- Visualizes time-series temperatures with dashed threshold lines:
  - Upper threshold: `8.0°C` in Coral Red (`#EF4444`)
  - Lower threshold: `2.0°C` in Electric Teal (`#00AEBB`)
- Dynamic data point dots colored by reading decision (`ok` vs `excursion`).
- Secondary badges for humidity (%) and mechanical shock (`g`).

### 3.2 Notification Service & Preferences (`mobile/src/features/notifications/`)
- `notificationService.ts`:
  - Configures high-importance Android channels (`mediflux-coldchain`, `mediflux-approvals`).
  - Implements `getDevicePushToken` with deterministic fallback token for web and simulators.
  - Implements pure, unit-testable `handleNotificationTapPayload(data, router)` for deep-link routing.
- `preferences.ts`:
  - Manages persistent user preferences in `AsyncStorage` (`mediflux_notification_prefs_v1`) for `coldchainAlerts`, `approvalAlerts`, and `pushEnabled`.
- `NotificationBanner.tsx`:
  - In-app interactive banner displaying live alerts for 6 seconds with tap deep-link navigation.

### 3.3 Screens
- `mobile/app/(tabs)/cold-chain.tsx`:
  - Top view switcher: `Batches (N)` vs `Quarantine History (M)`.
  - Status filter chips: `All`, `OK`, `Warn`, `Quarantined`.
  - 1-tap simulation triggers: "Normal Reading" and "Simulate Excursion".
  - Batch cards with temperature, humidity, shock, Arrhenius shelf-life progress bars, and status badges.
- `mobile/app/cold-chain/[id].tsx`:
  - Detailed telemetry view with SVG Telemetry Chart.
  - Shelf-life breakdown card (nominal, thermal penalty, shock penalty, effective remaining).
  - Excursion Analyst Quarantine section (when quarantined) with explanation, zeroed stock, audit entry reference, and "View Dynamic Rebalancing Cascade Trace →" deep-link button.
- `mobile/app/(auth)/settings.tsx`:
  - Notification Preferences card with toggles, registered push token status, and "Send Test Notification" button.
- `mobile/src/features/auth/AuthContext.tsx`:
  - Registers push token on login (`POST /api/v1/devices`) and deletes token on logout (`DELETE /api/v1/devices/{token}`).
- `mobile/app/_layout.tsx`:
  - Integrates `NotificationBridge` subscribing to SSE events on `hitl` and `coldchain` to schedule local notifications and show in-app alert banners.

---

## 4. Verification & Definition of Done

- **Automated Pytest Suite**: `backend/tests/test_task_m7_coldchain_and_notifications.py` (7 tests covering all 4 acceptance criteria).
- **Linter**: `backend/venv/Scripts/ruff.exe check backend/app/ backend/tests/` passes with 0 warnings/errors.
- **Mobile TypeScript & Lint**: `npm run typecheck` (`tsc --noEmit`) and `npm run lint` in `mobile/` pass with 0 errors.
- **Web Export**: `npx expo export --platform web` bundles cleanly (2,376 modules).
