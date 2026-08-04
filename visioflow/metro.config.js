const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Ignore local build-verification artifacts. Metro otherwise indexes every
// previous export and can appear to start while never answering HTTP requests.
config.resolver.blockList = [
  /[\\/]\.codex-[^\\/]+[\\/].*/,
  /[\\/]\.tmp-route-check[\\/].*/,
];

module.exports = config;
