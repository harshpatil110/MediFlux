// Learn more https://docs.expo.io/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const projectRoot = __dirname;
const monorepoRoot = path.resolve(projectRoot, '..');

const config = getDefaultConfig(projectRoot);

// 1. Watch monorepo packages/shared
config.watchFolders = [
  path.resolve(monorepoRoot, 'packages', 'shared'),
];

// 2. Extra node modules mapping for monorepo package imports
config.resolver.extraNodeModules = {
  '@mediflux/shared': path.resolve(monorepoRoot, 'packages', 'shared', 'src'),
};

// 3. Ensure local node_modules take precedence
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
];

module.exports = config;
