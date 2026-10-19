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

// `react-app` resolved to an absolute path, because the bare name does not
// resolve here and fails the build outright ("Failed to load config react-app
// to extend from"). This install nests `eslint-config-react-app` inside
// `react-scripts/node_modules` rather than hoisting it, and ESLint resolves a
// `baseConfig` extends entry against the project root, where it is not. CRA's
// own config has the same problem and solves it the same way — it extends
// `require.resolve('eslint-config-react-app/base')`, not `'react-app/base'`.
//
// Resolved from react-scripts' own directory rather than by naming the nested
// path, so this keeps working if a future install hoists the package.
const REACT_APP_ESLINT_CONFIG = require.resolve("eslint-config-react-app", {
  paths: [path.dirname(require.resolve("react-scripts/package.json"))],
});

const webpackConfig = {
  eslint: {
    // **`react-app` comes first, and leaving it out is what let two crashes
    // ship.** `configure` REPLACES create-react-app's own `baseConfig` rather
    // than adding to it, so an extends array naming only the react-hooks
    // plugin took `eslint-config-react-app` out of the build entirely — and
    // with it `no-undef`. An undefined identifier was not a lint error
    // anywhere in this frontend, which is the mechanism behind both
    // ReferenceErrors this codebase has shipped to a real screen: `Navigate`
    // in `pages/CreatorHome.jsx`, and `istStartOfDay` in the manager's
    // `shared.jsx`. Neither was a typo a reviewer would catch by eye, and
    // both threw on render rather than at build.
    //
    // `react-app` also carries the parser (`@babel/eslint-parser`), the
    // browser/node/jest globals and `settings.react.version` through its own
    // `./base` — which is what CRA's `baseConfig` pointed at and what this
    // override had been dropping too. That matters more than it looks: with
    // `no-undef` on and no `env.browser`, every `window` and `sessionStorage`
    // in the app would itself be an undefined name.
    configure: {
      extends: [REACT_APP_ESLINT_CONFIG, "plugin:react-hooks/recommended"],
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
