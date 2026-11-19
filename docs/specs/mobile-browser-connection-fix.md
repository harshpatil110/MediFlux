# Mobile browser backend connectivity

Date: 19 November 2026

## Problem

The mobile export embedded `EXPO_PUBLIC_API_URL` and `EXPO_PUBLIC_LAN_API_URL`
from a previous LAN launch. Opening that build on localhost sent health checks
and authentication to the phone-facing LAN address while FastAPI listened only
on `127.0.0.1:8000`, causing `ERR_CONNECTION_REFUSED`.

## Behavior

- Web previews use the browser host on port 8000 when the configured API matches
  the generated LAN hint. Separate explicit API targets remain supported.
- Native Android/iOS retain their configured LAN target and emulator defaults.
- A saved URL matching the generated LAN hint is migrated to the localhost API
  only in a local browser and after that API responds successfully. Other saved
  server choices remain intact.
- Root initialization loads the saved backend URL before mounting authentication
  and API consumers.
- Saving a server URL immediately refreshes connection health and reconnects SSE.
- Home summary fetching uses a stable callback; receiving a new summary no longer
  triggers another fetch. Summary, approval-count, and stream requests wait for a user.

## Verification

- Ten URL regression cases cover browser host selection, explicit remote APIs,
  native LAN selection, Android emulator fallback, saved LAN recovery, unavailable
  local servers, and saved custom targets. The complete mobile suite has 33 tests.
- Actual Chromium checks pass with no injected backend override: fresh storage,
  the old LAN preset saved in storage, default pharmacy login, session restoration,
  immediate server-setting updates, stable idle requests, live events, barcode sale,
  five cascade stages, approvals, prescription scan, cold chain, and copilot.
- Mobile TypeScript checks and Android/iOS/web exports pass. Frontend build and
  backend Ruff checks pass. The Python suite passes all 406 tests with UTF-8 output.

On Windows, use `$env:PYTHONUTF8='1'` for the Python checks: existing generator and
launcher subprocesses print Unicode checkmarks. Build frontend assets before running
pytest because its existing UI smoke check reads `frontend/dist/index.html`.

The browser still receives a non-blocking animation fallback warning from the
installed navigation library's native-driver badge animation after login. This
does not affect API connectivity. Physical-device verification is outside this fix.

For browser regressions without a forced mobile URL:

```powershell
$env:PYTHONUTF8='1'
.\backend\venv\Scripts\python.exe -m scripts.verify_clients --api-url http://localhost:8000 --mobile-url http://localhost:8081 --mobile-default-backend
```

The rebuilt mobile export remains served at `http://localhost:8081`. Refresh the
open browser tab with Ctrl+F5 to load the new bundle.
