# NexusChain India Mobile App: mobile-tasks.md

---

# PHASE 1: MOBILE FOUNDATION

## Task M1: Expo project setup, shared API package and backend connectivity

**Objective:** Create the React Native (Expo + TypeScript) project, a shared API client package, and a reliable way to reach the local FastAPI backend from a phone.

**Context:** The mobile app is a thin client over the existing public API (`/api/v1`, Supabase Auth, SSE stream, standard error format `{error: {code, message, details}}`). No new business logic is built on the phone. The backend is already complete (Tasks 1 to 30 of tasks.md). Package names and APIs change often, so check each library's current Expo documentation before installing.

### M1.1 Project scaffold

- Create `mobile/` in the monorepo with Expo + TypeScript (use the current recommended Expo template with Expo Router).
- Folder layout:

```
mobile/
  app/                 (Expo Router routes: (auth)/, (tabs)/)
  src/
    api/               (client wrapper, hooks)
    components/        (shared UI: Card, Badge, Timeline, EmptyState, ErrorState)
    features/          (pos, approvals, prescriptions, coldchain, copilot, cascade)
    hooks/             (useEventStream, useNetworkStatus)
    lib/               (config, storage, format helpers)
    theme/
  app.config.ts
  package.json
```

- Add ESLint, TypeScript strict mode, and a `README` section with run commands.
- Pick one UI approach (React Native Paper or NativeWind) and use it consistently.

### M1.2 Shared API package

- Create `packages/shared/` containing TypeScript types, enums (roles, tiers, HITL status, event types) and the SSE event type definitions.
- Generate the API client/types from the exported OpenAPI JSON (`docs/openapi.json` from Task 30) with a script `scripts/gen-api`; if monorepo module resolution (Metro) causes trouble, fall back to a script that copies the generated files into both `frontend/` and `mobile/`.
- API client wrapper in `mobile/src/api/client.ts`: base URL from config, attaches the Supabase JWT, parses the standard error format into a typed `ApiError`, request timeout, JSON and multipart helpers.

### M1.3 Backend URL configuration

- `lib/config.ts`: default backend URL from Expo config/env, overridable at runtime and persisted locally (the Settings screen in M2 edits it).
- A "Connection status" helper that calls `/health` and reports reachable/unreachable.

### M1.4 Phone-to-backend connectivity (documented and scripted)

- A phone cannot use `localhost`: use the laptop's LAN IP on the same Wi-Fi; Android emulator uses `10.0.2.2`.
- Update `scripts/start-all` with a `--lan` option that starts FastAPI on `0.0.0.0` and prints the LAN URL to enter in the app.
- Confirm backend CORS is not blocking (native clients do not enforce CORS, but test requests anyway).

### M1.5 Navigation skeleton

- Route groups: `(auth)` for login/settings, `(tabs)` for the main app with placeholder screens: Home, Sell, Approvals, Scan Rx, Cold Chain, Copilot.

**Deliverables:** running Expo app, shared package, generated API client, `scripts/gen-api`, updated `start-all`, connectivity notes in `docs/MOBILE.md`.

**Acceptance criteria:**

- [ ] `npx expo start` launches and the app opens on a real phone via Expo Go.
- [ ] The app shows "Backend reachable" when pointed at the laptop's LAN URL.
- [ ] Regenerating the API client from OpenAPI works with one command.
- [ ] TypeScript strict mode and lint pass.

**Depends on:** Tasks 4, 22, 30 (from tasks.md).

---

## Task M2: Authentication, secure session and role-aware navigation

**Objective:** Let users log in with their existing Supabase accounts and see only the tabs their role allows.

**Context:** Roles: pharmacy, stockist, distributor, manufacturer, admin. RLS on the backend already restricts data per node; the app must also hide irrelevant screens. The backend exposes `GET /api/v1/me` returning role and node.

### M2.1 Supabase client for React Native

- Install `@supabase/supabase-js` and the React Native URL polyfill if required by the current Supabase docs.
- Session persistence: Supabase sessions can exceed the size limits of secure key-value stores, so follow Supabase's current React Native guidance (for example, AsyncStorage for the session or an encrypted-storage pattern with the key held in secure storage). Verify against current docs before choosing.
- Auto-refresh tokens while the app is in the foreground; stop refreshing in the background (use `AppState`).

### M2.2 Auth flows

- Login screen (email + password), loading and error states, logout.
- Global auth provider: on start restore the session, call `/me`, store `{role, node_id, node_name}`; redirect to `(auth)` if unauthenticated.
- Global 401 handling: refresh once, then force logout.
- Development-only quick-login chips for the seeded demo users (hidden in release builds).

### M2.3 Role-aware navigation

- Tab visibility map, for example:
  - pharmacy: Home, Sell, Scan Rx, Approvals (view only if policy allows), Copilot
  - stockist/distributor/manufacturer: Home, Approvals, Cold Chain, Copilot
  - admin: all tabs
- Header badge showing role and node name.

### M2.4 Settings screen

- Backend URL field with "Test connection", current user, logout, app version.

**Deliverables:** auth provider, login and settings screens, role-aware tabs, tests for the role map.

**Acceptance criteria:**

- [ ] Each seeded role logs in and sees only its allowed tabs.
- [ ] The session survives an app restart; logout clears it.
- [ ] An expired token triggers refresh, then logout if refresh fails.
- [ ] Changing the backend URL in Settings takes effect without rebuilding.

**Depends on:** Task M1, Task 3 (tasks.md).

---

## Task M3: Live event stream, home dashboard and mobile summary endpoint

**Objective:** Receive real-time updates from the backend reliably on a phone and show a live home screen.

**Context:** The backend streams events via SSE at `GET /api/v1/stream?topics=...` with `Last-Event-ID` replay. React Native has no built-in `EventSource`, and the native browser version cannot send an Authorization header, so use an SSE client library for React Native that supports custom headers (for example `react-native-sse`; verify it is maintained and compatible with your Expo SDK). Mobile networks drop connections often, so reconnection and a polling fallback are required.

### M3.1 `useEventStream(topics, options)` hook

- Opens the SSE connection with the JWT in the Authorization header.
- Reconnects with exponential backoff; sends `Last-Event-ID` to receive missed events.
- Pauses when the app goes to the background and reconnects on foreground (`AppState`).
- Exposes: `status` (connecting/open/retrying/failed), `events`, `lastEvent`.
- Deduplicates events by id; keeps a bounded in-memory buffer.

### M3.2 Polling fallback

- If the stream fails repeatedly, fall back to polling a lightweight endpoint every few seconds.
- Backend addition: `GET /api/v1/events/recent?since=<id or timestamp>&topics=...` (RLS-scoped, bounded) if no equivalent exists yet.

### M3.3 Mobile summary endpoint

- Backend addition: `GET /api/v1/mobile/summary` returning in one call: events today, low-stock count (visible scope), open approvals, quarantined batches, last cascade correlation_id.
- Add a test and OpenAPI description; regenerate the client.

### M3.4 Home screen

- KPI cards from the summary; live activity feed from the stream (agent name, tier, one-line summary, time); connection indicator; pull-to-refresh.
- Tapping a feed item that has a `correlation_id` opens the cascade timeline screen (built in M4 and reused in M8).

**Deliverables:** `useEventStream`, polling fallback, backend endpoints and tests, Home screen.

**Acceptance criteria:**

- [ ] Posting a sale from the POS simulator makes the activity feed update on the phone within seconds.
- [ ] Turning airplane mode on and off reconnects and fills missed events.
- [ ] Killing the stream endpoint triggers polling fallback; restoring it returns to streaming.
- [ ] Backgrounding the app stops the connection; foregrounding restores it.

**Depends on:** Tasks M1, M2, Task 6 (tasks.md).

---

# PHASE 2: CORE MOBILE SCREENS

## Task M4: Pharmacy POS Lite (barcode scan, sale, live cascade timeline)

**Objective:** Scan a medicine strip, record one sale, and watch the cascade run through all four tiers on the phone. This is the main mobile demo, so finish it first.

**Context:** The headline RFP requirement is single-unit demand propagation. The sale endpoint is `POST /api/v1/events/sale` (idempotent on `event_id`); the trace is available via SSE (`agent.activity`, `cascade.updates`) and `GET /api/v1/cascade/{correlation_id}`. Products are synthetic, so barcodes must be seeded.

### M4.1 Backend additions

- Migration: add `barcode` (unique, nullable) to `products`; update the seed script to assign barcodes to synthetic products.
- Endpoint `GET /api/v1/products/by-barcode/{code}` returning product details, schedule class and flags.
- Script `scripts/make-barcodes` generating a printable sheet (PNG/PDF) of barcodes or QR codes for the seeded products, saved in `fixtures/barcodes/`, for use in demos.

### M4.2 Scanner

- Use `expo-camera` barcode scanning; handle camera permission request and denial with a settings prompt.
- On scan: look up the product; show name, schedule class, lifesaving/cold-chain badges; debounce repeated scans.
- Manual fallback: search products by name and pick one.

### M4.3 Sale flow

- Batch selection: list the pharmacy's batches with stock for that product; preselect the earliest-expiry batch with stock; allow override; warn for near-expiry or quarantined batches (quarantined are not selectable).
- Schedule H products: require attaching an approved prescription (from M6); otherwise show a clear warning that the pharmacy agent will flag a compliance hold.
- Quantity defaults to 1 strip; "Sell" button generates a client-side UUID `event_id` and posts the sale; retrying uses the same `event_id` (safe).

### M4.4 Live cascade timeline

- After posting, subscribe by `correlation_id` and show a vertical timeline: Supervisor → Pharmacy → Stockist → Distributor → Manufacturer, with per-agent state (waiting, running, done, skipped, failed), one-line reasoning, duration and tokens.
- Expandable step detail showing the agent's structured output (formatted, not raw JSON by default).
- Skipped tiers show the Supervisor's reason; HITL pauses show "Waiting for approval" with a link to M5.
- Reusable `CascadeTimeline` component (also used in M8).

### M4.5 Edge cases

- Network failure after posting: show "sent, waiting for confirmation" and recover via `GET /cascade/{id}` or retry with the same `event_id`.
- Haptic feedback on success (optional).

**Deliverables:** scanner, sale flow, `CascadeTimeline`, backend endpoint and migration, barcode sheet, tests.

**Acceptance criteria:**

- [ ] Scanning a printed barcode selects the right product and completes a sale.
- [ ] All four tiers (or logged skips) appear in order on the phone for a single strip.
- [ ] Double-tapping "Sell" or retrying does not create two inventory changes.
- [ ] A Schedule H product without a prescription shows the warning.

**Depends on:** Tasks M3, Tasks 6, 10 to 14, 19 (tasks.md).

---

## Task M5: Approvals (Human-in-the-Loop) on mobile

**Objective:** Approve or reject risky agent actions from the phone.

**Context:** HITL tasks come from `GET /api/v1/hitl/tasks` and are decided via `POST /api/v1/hitl/tasks/{id}/decision {decision, note}`. Task types: cross-border shipment, in-progress batch modification, regulatory module activation, doctor verification failure, Schedule H override. Only roles allowed by `config/hitl_policies.yaml` may decide; the backend enforces this and the UI must reflect it.

### M5.1 List screen

- Tabs or filter: Pending / Decided; cards showing type, risk level, requesting agent, age and expiry countdown; pull-to-refresh; tab badge with pending count updated from the `hitl` SSE topic.

### M5.2 Detail screen

- Type-specific renderers:
  - cross-border shipment: route, products, flags, priority
  - batch modification: batch, change, API stock impact
  - regulatory activation: summary of change, test results, simplified diff (collapsible; full diff stays on desktop)
  - doctor verification / Schedule H: parsed prescription fields (minimal necessary data)
- Agent reasoning section and links to the related cascade or audit entry.
- Generic JSON fallback renderer for unknown types.

### M5.3 Decision flow

- Approve/Reject buttons with a note field and a confirmation dialog; optional biometric confirmation using `expo-local-authentication` (check availability; skip if unsupported).
- Buttons hidden or disabled with an explanation if the user's role cannot decide (also handle the backend's 403 gracefully).
- Optimistic UI is not used for decisions; wait for the server result, then show the outcome (resumed graph, rejected, expired).

### M5.4 Edge cases

- Task already decided or expired by someone else: show the current status instead of an error.

**Deliverables:** Approvals list and detail screens, renderers, tests.

**Acceptance criteria:**

- [ ] A cross-border shipment triggered from the web/simulator appears on the phone live.
- [ ] Approving from the phone resumes the graph (visible in the cascade trace).
- [ ] A user without approver rights cannot decide.
- [ ] An expired task shows as expired, not as an error.

**Depends on:** Tasks M3, M4, Task 15 (tasks.md).

---

## Task M6: Prescription scan and Schedule H compliance

**Objective:** Photograph a prescription and see the parsed result, schedule classes, doctor verification and final decision.

**Context:** `POST /api/v1/prescriptions` (multipart) runs the prescription graph using local-only models for sensitive data. All demo prescriptions are synthetic. Processing with a local vision model can take a while, so the UI must show progress. Prescription images are sensitive: do not keep them on the device longer than needed.

### M6.1 Capture

- Use `expo-camera` or `expo-image-picker` (camera and gallery); handle permissions.
- Compress/resize with `expo-image-manipulator` to a sensible size before upload; show a preview with retake.

### M6.2 Upload and progress

- Multipart upload with progress; then track processing by SSE or polling `GET /api/v1/prescriptions/{id}`.
- Step indicator matching the graph: parsing → schedule check → doctor verification → decision.
- Privacy notice in the UI: processed by local models only.

### M6.3 Result screen

- Parsed fields (doctor name, registration number, patient initials, drugs and doses), a per-drug schedule class badge (unknown drugs shown as "unknown", never guessed), doctor verification result, final decision (approve dispense / flagged / rejected) and the compliance log reference.
- Flagged items show "sent for approval" and link to M5.

### M6.4 Link to sales

- An approved prescription can be attached to a sale in M4 (pass the prescription id to the sale flow).
- History list of recent prescriptions for the pharmacy (RLS-scoped).

### M6.5 Cleanup

- Delete cached image files after upload completes or on screen exit.

**Deliverables:** capture, upload, result and history screens, tests with mocked API.

**Acceptance criteria:**

- [ ] The valid synthetic fixture photographed from the phone is approved.
- [ ] The unknown-doctor fixture shows flagged and appears in Approvals.
- [ ] An approved prescription attached to a Schedule H sale passes the pharmacy check in the cascade.
- [ ] No image files remain in the app cache after the flow ends.

**Depends on:** Tasks M4, M5, Task 19 (tasks.md).

---

# PHASE 3: ALERTS AND AI ON MOBILE

## Task M7: Cold-chain monitor and notifications (local and remote push)

**Objective:** Show cold-chain status on the phone and alert users to quarantines and new approvals, even when the app is closed (remote push).

**Context:** Cold-chain data comes from `GET /api/v1/coldchain/batches` and `/coldchain/quarantines`; events arrive on the `coldchain` and `hitl` topics. Expo push has platform and SDK restrictions (Expo Go versus development builds), so check Expo's current push notification documentation first. Deliver in two stages: local notifications first (safe), remote push second.

### M7.1 Cold-chain screens

- Batch list: product, node, status badge (ok/warn/quarantined), last reading, shelf-life estimate; filter by status.
- Batch detail: recent readings chart (use a React Native-compatible chart library; verify compatibility with the current Expo SDK), quarantine reason from the Excursion Analyst, related cascade or audit link.
- Quarantines history list.

### M7.2 Stage A: local notifications

- Configure `expo-notifications` (permissions, Android channels).
- While the app is open or recently backgrounded and the SSE stream is alive, fire local notifications for `hitl.created` (to eligible approver roles) and batch quarantined events.
- Notification tap deep-links to the relevant screen (approval detail or batch detail).

### M7.3 Stage B: remote push

- Migration: `device_tokens` table (user_id, token, platform, created_at) with RLS (users manage only their own).
- Endpoints: `POST /api/v1/devices` (register/refresh token), `DELETE /api/v1/devices/{token}`; register on login, remove on logout.
- Backend push sender: subscribes to `hitl` and `coldchain` bus events, selects recipients by role and node scope, sends via Expo's push service using `httpx`, processes receipts, and deletes invalid tokens; errors never block the event pipeline.
- Config flag `PUSH_ENABLED` and logging of sends in the audit ledger or a log table (no sensitive payloads in the push body).

### M7.4 Preferences

- Settings toggles for notification types.

**Deliverables:** cold-chain screens, local notifications, device-token endpoints and migration, push sender, tests.

**Acceptance criteria:**

- [ ] Triggering a cold-chain excursion makes the batch show as quarantined on the phone and produces a notification.
- [ ] A new approval triggers a notification that opens the correct approval on tap.
- [ ] (If remote push is working in your build) a notification arrives with the app fully closed.
- [ ] Logging out removes the device token; invalid tokens are cleaned up by the backend.

**Depends on:** Tasks M3, M5, Tasks 20, 22 (tasks.md).

---

## Task M8: Network Copilot and Cascade History (lite)

**Objective:** Give mobile users a natural-language assistant and a history of past cascades.

**Context:** `POST /api/v1/copilot/query {question}` returns an answer, references and a trace id; it is read-only and honors the caller's RLS scope. `GET /api/v1/cascade/{correlation_id}` returns stored traces. The cascade timeline component from M4 is reused.

### M8.1 Copilot chat

- Chat UI with message bubbles, input with keyboard-safe layout, loading state showing activity ("searching inventory…"), retry on failure.
- If streaming exists (SSE from Task 21), show the answer progressively; otherwise show a single response with a loading indicator.
- Reference chips under answers (inventory item, batch, approval, cascade trace) that deep-link to the matching screens.
- Suggested questions by role (for example, "Which pharmacies are at risk of running out of X?" or "What is waiting for my approval?").
- Conversation kept in memory for the session only (not persisted).

### M8.2 Cascade History

- List of recent cascades (use `GET /api/v1/events/recent` or an agent-runs listing endpoint; add a small `GET /api/v1/cascade?limit=` list endpoint on the backend if one does not exist): product, pharmacy, time, outcome (complete/partial/waiting approval).
- Tapping opens the replay view: the same `CascadeTimeline`, with a "replay" mode that animates stored steps in order at selectable speed.

### M8.3 Error handling

- Copilot or LLM failures show a friendly message (provider busy, try again) based on the standard error codes.

**Deliverables:** Copilot screen, Cascade History screen, optional list endpoint, tests.

**Acceptance criteria:**

- [ ] A copilot question about stockout risk returns correct seeded data with tappable references.
- [ ] A pharmacy user cannot retrieve other pharmacies' data through the copilot.
- [ ] Any past correlation_id can be replayed from the history list.

**Depends on:** Tasks M4, M7, Task 21 (tasks.md).

---

# PHASE 4: HARDENING AND DISTRIBUTION

## Task M9: Polish, resilience and testing

**Objective:** Make the app robust and presentable for the interview demo.

**Context:** The app is evaluated live; most failures will come from network drops, slow free-tier LLM responses, permissions and device differences, not from logic bugs.

### M9.1 UX states

- Every screen has loading, empty, error and offline states; a global offline banner using a network-status library (for example `@react-native-community/netinfo`; verify Expo compatibility).
- Pull-to-refresh where lists exist; use `FlatList` for long lists; avoid unnecessary re-renders in the live feed (memoization, bounded buffers).
- Dark mode support and consistent theming; accessible labels and adequate touch sizes.
- App icon, splash screen and app name.

### M9.2 Automated tests

- Jest plus React Native Testing Library: API client (error parsing, auth header), `useEventStream` (reconnect, dedupe, fallback with a fake SSE source), role-aware tab map, `CascadeTimeline` rendering for done/skipped/failed/waiting states, sale idempotency logic.
- Mock the API with a lightweight mock server or MSW-style mocks.
- Type check and lint in CI-style script `npm run check`.

### M9.3 Manual test matrix on real devices

- Android and iOS devices you have access to (or at minimum one real device plus an emulator).
- Checklist: login, role tabs, scan permission denied/granted, sale flow, retry after network loss, approval decision, prescription flow, quarantine notification, copilot, backend URL change, backgrounding and foregrounding.
- Failure injection: backend down, expired token, SSE dropped, slow LLM response, invalid camera permission.

### M9.4 Demo data and reset

- Ensure the backend demo reset script (Task 29) also resets mobile-related data (device tokens, barcode seed).
- Capture screenshots for the README.

**Deliverables:** polished app, test suite, manual test checklist in `docs/MOBILE.md`, screenshots.

**Acceptance criteria:**

- [ ] `npm run check` (types, lint, tests) passes.
- [ ] The full mobile demo path works twice in a row from the reset state.
- [ ] Turning the network off mid-flow produces clear messages and recovery, not crashes.

**Depends on:** Tasks M1 to M8, Task 29 (tasks.md).

---

## Task M10: Distribution, documentation and demo integration

**Objective:** Make the mobile app easy for reviewers to run, and integrate it into the final submission.

**Context:** The simplest reliable demo is Expo Go on a real phone connected to your laptop's backend. An installable Android APK is a bonus. iOS distribution outside Expo Go and TestFlight requires an Apple developer account, so do not promise an iOS installer. EAS Build free-tier limits and Expo SDK requirements change, so check current Expo documentation.

### M10.1 Run paths

- **Path A (primary):** Expo Go on a phone, same Wi-Fi as the laptop, backend started with `scripts/start-all --lan`; write step-by-step instructions including how to find the LAN IP and set it in Settings.
- **Path B (bonus):** Android APK through EAS Build: create `eas.json` with a preview profile that produces an APK; configure app identifiers; handle cleartext HTTP for a local backend in non-release builds (current Android and iOS rules require HTTPS for release builds, so document using a tunnel or a hosted backend for a standalone demo; for Android dev/preview builds use the Expo build-properties configuration for cleartext traffic if needed).
- Remote push may require a development/preview build rather than Expo Go (see M7); document what works in each path.

### M10.2 Documentation

- `docs/MOBILE.md`: architecture (thin client over the public API), screens and which endpoints they use, setup and run paths, troubleshooting (LAN IP, firewall rules on Windows, emulator addresses, SSE issues), known limitations.
- Update the main `README` with a Mobile section and screenshots; update `docs/ARCHITECTURE.md` with the mobile client; update `docs/API_GUIDE.md` noting the new endpoints (`/devices`, `/mobile/summary`, `/products/by-barcode/{code}`, `/events/recent`, optional `/cascade` list).
- Append mobile entries to `docs/HOW_AI_BUILT_THIS.md`.

### M10.3 Demo script update

- Add a mobile segment to the timed demo script (Task 30): (1) scan a strip on the phone and watch the cascade, (2) approve a cross-border shipment from the phone, (3) photograph a prescription, (4) receive a cold-chain alert, (5) ask the copilot a question.
- Record a short backup video of the mobile flow.
- Prepare the talking point: the mobile app is a thin client over the public API, which demonstrates that "others can build over it".

### M10.4 Final checklist

- Fresh clone test of the mobile app from the README, no secrets committed, `.env.example` updated with mobile variables, tag a release including `mobile/`.

**Deliverables:** run instructions, optional APK, docs, updated demo script and video.

**Acceptance criteria:**

- [ ] A reviewer can run the mobile app on their phone using only the README (Path A).
- [ ] (Bonus) The APK installs on an Android device and reaches the backend.
- [ ] The full mobile demo segment runs cleanly twice from the reset state.
- [ ] All new endpoints appear in the OpenAPI docs.

**Depends on:** Tasks M1 to M9, Task 30 (tasks.md).
