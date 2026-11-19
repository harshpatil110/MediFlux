# Mobile Vercel backend migration

Date: 19 November 2026

The mobile app, Expo configuration, and EAS preview and production profiles
default to `https://mediflux-backend.vercel.app`. The ignored `mobile/.env.local`
was updated without changing any Supabase values. A saved local or private LAN
address migrates once to the cloud address; standalone builds always migrate
local addresses. Settings has a one tap cloud preset and reset action.

Mobile API calls allow 25 seconds and health checks allow 15 seconds for cold
starts. Vercel stream errors or close events move the client to 4 second polling
of `/api/v1/events/recent`, retaining event IDs for replay and deduplication.
The Home connection label reports cloud polling in teal. Stream recovery probes
can return the client to SSE.

Live checks returned HTTP 200 for health, OpenAPI, products, seeded admin login,
profile, mobile summary, recent events, cold chain batches, pending tasks, and
barcode lookup. CORS preflights from localhost:8081 and a Vercel web origin also
returned 200 with the requested origin and headers. Protected endpoints return
401 without authentication, as expected. Existing backend CORS already permits
the required origins, so no backend source change was needed.

Chromium opened the exported mobile web app with fresh storage and an old saved
LAN target. Both sessions signed in against Vercel. A separate browser check
aborted the stream, observed the teal cloud polling label, and received HTTP 200
from recent events repeatedly.

Verification: `npx tsc --noEmit`, `npm run check` (35 mobile tests),
`npx expo config --type public`, and `npx expo export --platform android --clear`
passed. The public config showed the cloud URL, Android package, icon and build
plugin. EAS reported `Not logged in`, and no `EXPO_TOKEN` was supplied, so the
standalone APK could not be built or downloaded in this run.

To build the APK after EAS login or an `EXPO_TOKEN` is available:

```powershell
cd mobile
npx eas-cli build --platform android --profile preview --non-interactive --wait
```

Download the artifact URL reported by EAS to `mobile/builds/mediflux-android-vercel.apk`.
