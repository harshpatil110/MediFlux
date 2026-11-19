# Android preview APK build

Date: 20 November 2026

The Android preview profile produces an installable APK with
`EXPO_PUBLIC_API_URL=https://mediflux-backend.vercel.app`. The Expo app is linked
to EAS project `07a2c88f-2613-4b36-a417-e2b814fe2a16`. Android package
`in.mediflux.mobile` uses version code 1 and declares camera, internet, network
state, and notification permissions. All four referenced image assets opened as
valid PNG files.

Expo Doctor initially identified the redundant `@types/react-native` package and
missing direct `expo-font` dependency. Removing the type package, installing
`expo-font`, and registering its config plugin resolved both findings. Expo
Doctor then passed 17/17 checks. TypeScript, mobile checks (35 Jest tests), public
Expo config, and Android Metro export passed. The full Python suite passed 406
tests and backend Ruff passed.

The Expo CLI requires `.easignore` at the Git repository root for this monorepo.
It now includes the root Git ignore rules plus desktop release output and demo
videos. The EAS upload shrank from 219 MB to 16.3 MB. Temporary archive work used
a drive with sufficient free space because the system drive had less than 1 GB
available. The ignored local `.env.local` retains the Vercel URL; the preview
profile sets the same URL on the EAS build server.

Build record: https://expo.dev/accounts/harsh_110/projects/mediflux-mobile/builds/07034e16-116e-4cae-b2ba-8ff64bf1e78b
