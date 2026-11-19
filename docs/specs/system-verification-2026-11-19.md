# Whole-project verification and reliability fixes

Date: 19 November 2026

## Scope

Run the repository and backend Python suites, backend lint, frontend lint/build/tests,
shared TypeScript checks, mobile checks and exports, packaged Electron checks,
Supabase schema reads, and the existing replay demonstrations. Exercise the actual
web and mobile clients in Chromium, checking browser exceptions and API responses.

## Corrections

- Distinguish `backend.tests` from the root `tests` package so root pytest can collect both.
- Share isolated test settings across both entry points; disable cloud database writes,
  remote push, and live embeddings during tests. Restore mutable settings after each test.
- Supply explicit dummy credentials to mocked provider failover tests. Update legacy
  assertions to the current mobile sale, cold-chain status, citation, and cascade contracts.
  Keep idempotency and stock decrement assertions in place.
- Unwrap the audit endpoint's `items` envelope before rendering the web ledger.
- Keep web stream dependencies stable, start subscriptions after authentication, and
  reconnect after a stream ends normally.
- Stop mobile notification and polling requests before authentication; avoid invoking
  native notification history APIs on web.
- Support `GET /api/v1/stream?named_events=false` for generic SSE message consumers.
  Preserve event type in the JSON payload and retain named events as the default.
  Let the mobile EventSource library detect the server's CRLF line endings.
- Fix mobile device registration and cold-chain URLs to include `/api/v1`.
- Stabilize the mobile refresh callback so restoring a session does not repeatedly
  fetch the profile and register the same push token.
- Align NetInfo, image picker, secure store, and Jest with Expo SDK 51's compatibility checks.
- Package the frontend as an explicit Electron resource and load it from
  `process.resourcesPath` in the packaged app.
- Install and configure frontend ESLint. Replace the nonexistent Vite favicon.
- Hide duplicate catalog formulations introduced by seeded UUID aliases.
- Correct the database verifier to inspect `doctor_registry` and use Windows-safe text.
- Refresh OpenAPI and the three generated TypeScript contracts.

## Reproducible checks

From the repository root:

```powershell
.\backend\venv\Scripts\python.exe -m pytest -q
.\backend\venv\Scripts\python.exe -m scripts.verify_supabase
.\backend\venv\Scripts\python.exe -m scripts.check_secrets
```

From `backend`: `venv\Scripts\python.exe -m pytest -q` and
`venv\Scripts\python.exe -m ruff check .`.

From `frontend`: `npm run lint`, `npm test`, and `npm run build`.

From `mobile`: `npm run check`, `npx expo install --check`, and
`npx expo export --platform all`.

From `desktop`: `npm run desktop:pack`. The artifact is
`desktop/out/win-unpacked/MediFlux Control Tower.exe`.
`npm run desktop:build` also succeeds and produces the unsigned portable Windows
binary `desktop/out/MediFlux Control Tower 1.0.0.exe`.

`scripts/verify_clients.py` uses Playwright Chromium against a running local replay
API, Vite frontend, and exported mobile web client. It verifies all 11 web screens,
web POS and audit verification, idle stream stability, mobile login, idle session
stability, live event arrival without reloading, barcode dispensing, five cascade
stages, approvals, prescriptions, cold chain, and copilot. Use the app's client
navigation when serving the mobile export with a plain static HTTP server.

```powershell
.\backend\venv\Scripts\python.exe -m playwright install chromium
.\backend\venv\Scripts\python.exe -m scripts.verify_clients
```

The optional `--desktop-cdp http://127.0.0.1:9224` checks a packaged Electron app
started with `--remote-debugging-port=9224`, including its native preload bridge.
Clear an inherited `ELECTRON_RUN_AS_NODE` before launching the desktop binary.

## Verification results and limits

Final automated results: 406 root Python tests pass (including the 363-test backend
suite), backend lint passes, frontend lint/build and eight test scenarios pass,
shared TypeScript checks pass, and mobile type checks and 23 Jest tests pass.
Expo exports web, Android, and iOS bundles with compatible native dependency versions.
All 31 Supabase tables pass read verification. The scripted replay demo, eight-step
mobile demo, and seven-step cascade/SSE/audit verification pass. Playwright checks pass
for the web and mobile workflows listed above and the packaged desktop app.
The database verifier reads tables; it does not apply migrations or reset cloud data.
Workflow demonstrations use deterministic replay/local state. Native mobile JavaScript
bundles are exported for Android and iOS; physical devices, native signing/builds, and
the deferred Tauri scaffold are outside this machine's runtime checks.

Live Ollama is reachable with `llama3.2:3b` and `qwen3:4b` installed. The repository's
default `llama3.2:latest` and `qwen2.5-coder:7b` tags are not installed on this machine;
live default-model inference is therefore not certified by the replay suite. A separate
live call through `OllamaProvider` using the installed `llama3.2:3b` returned valid JSON.
The web production build still reports its existing large-bundle warning.
Dependency installation reports advisories in the existing frontend/mobile dependency
trees; major framework upgrades and a complete dependency security remediation are not
part of these runtime fixes.
