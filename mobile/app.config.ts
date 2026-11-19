import { ExpoConfig, ConfigContext } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'NexusChain India (MediFlux)',
  slug: 'mediflux-mobile',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  scheme: 'mediflux',
  userInterfaceStyle: 'automatic',
  splash: {
    image: './assets/splash.png',
    resizeMode: 'contain',
    backgroundColor: '#031211',
  },
  assetBundlePatterns: ['**/*'],
  ios: {
    supportsTablet: true,
    bundleIdentifier: 'in.mediflux.mobile',
  },
  android: {
    versionCode: 2,
    permissions: ['CAMERA', 'INTERNET', 'ACCESS_NETWORK_STATE', 'POST_NOTIFICATIONS'],
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#031211',
    },
    package: 'in.mediflux.mobile',
  },
  web: {
    bundler: 'metro',
    output: 'single',
    favicon: './assets/favicon.png',
  },
  plugins: [
    'expo-router',
    'expo-font',
    [
      'expo-build-properties',
      {
        android: {
          usesCleartextTraffic: true,
        },
      },
    ],
  ],
  experiments: {
    typedRoutes: true,
  },
  extra: {
    eas: {
      projectId: '07a2c88f-2613-4b36-a417-e2b814fe2a16',
    },
    apiUrl: process.env.EXPO_PUBLIC_API_URL || 'https://mediflux-backend.vercel.app',
    lanApiUrl: process.env.EXPO_PUBLIC_LAN_API_URL || '',
    environment: process.env.NODE_ENV || 'development',
  },
});

