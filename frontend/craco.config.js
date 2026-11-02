// craco.config.js
const path = require("path");
require("dotenv").config();

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

function makeDevServerV5Compatible(devServerConfig) {
  const {
    https,
    onAfterSetupMiddleware,
    onBeforeSetupMiddleware,
    onListening,
    setupMiddlewares,
    ...compatibleConfig
  } = devServerConfig;

  compatibleConfig.server =
    typeof https === "object"
      ? { type: "https", options: https }
      : https
        ? "https"
        : "http";
  compatibleConfig.headers = {
    ...compatibleConfig.headers,
    "Cross-Origin-Resource-Policy": "same-origin",
  };

  if (onBeforeSetupMiddleware || setupMiddlewares) {
    compatibleConfig.setupMiddlewares = (middlewares, devServer) => {
      if (onBeforeSetupMiddleware) {
        onBeforeSetupMiddleware(devServer);
      }

      return setupMiddlewares
        ? setupMiddlewares(middlewares, devServer)
        : middlewares;
    };
  }

  compatibleConfig.onListening = (devServer) => {
    devServer.close ??= (callback) => devServer.stopCallback(callback);

    if (onListening) {
      onListening(devServer);
    }
    if (onAfterSetupMiddleware) {
      onAfterSetupMiddleware(devServer);
    }
  };

  return compatibleConfig;
}

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

// **Extend CRA's lint config, never replace it.** react-scripts hands the
// ESLint plugin `eslint-config-react-app/base` only — a parser and two JSX
// rules — and relies on `"eslintConfig": {"extends": "react-app"}` in
// package.json for everything else. This project has no such key, so for as
// long as this block extended only the react-hooks recommended preset the
// build linted with no `no-undef`, no `no-unused-vars` and no jsx-a11y: an
// undefined identifier compiled cleanly and threw at runtime, which is how a
// whole page once shipped as a ReferenceError. The full config is resolved
// from react-scripts' own copy, because that is the ESLint (8.x) the plugin
// actually runs; the top-level eslint 9 in devDependencies is a different
// tool. `deepMergeWithArray` appends this to CRA's base, so both apply.
// `test_lint_config.py` holds this line.
const reactAppEslintConfig = require.resolve("eslint-config-react-app", {
  paths: [path.dirname(require.resolve("react-scripts/package.json"))],
});

const webpackConfig = {
  eslint: {
    configure: {
      extends: [reactAppEslintConfig],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // **Leave root-absolute `url()`s alone.** The self-hosted fonts are
      // served from `public/fonts/` at a stable address so `index.html` can
      // preload the hero face by name; css-loader would otherwise try to
      // bundle `/fonts/…` as a module, fail to resolve it, and hash it if it
      // could — which is exactly the address a preload cannot know.
      // Relative `url()`s (images under src/) still go through the bundler.
      const leaveRootUrls = (rules) =>
        rules.forEach((rule) => {
          if (rule.oneOf) leaveRootUrls(rule.oneOf);
          (Array.isArray(rule.use) ? rule.use : []).forEach((use) => {
            if (use && typeof use === "object" && /[\\/]css-loader[\\/]/.test(use.loader || "")) {
              use.options = { ...use.options, url: { filter: (url) => !url.startsWith("/") } };
            }
          });
        });
      leaveRootUrls(webpackConfig.module.rules);

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

const configureDevServer = webpackConfig.devServer;
webpackConfig.devServer = (devServerConfig) =>
  makeDevServerV5Compatible(configureDevServer(devServerConfig));

module.exports = webpackConfig;
