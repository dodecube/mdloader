// Shared web-ext options. API credentials come from the environment:
//   WEB_EXT_API_KEY    = AMO JWT issuer  (user:12345:67)
//   WEB_EXT_API_SECRET = AMO JWT secret
module.exports = {
  sourceDir: "extension",
  artifactsDir: "artifacts",
  build: { overwriteDest: true },
  lint: { selfHosted: true },
  sign: { channel: "unlisted" },
  run: { startUrl: ["https://www.last.fm/"] },
};
