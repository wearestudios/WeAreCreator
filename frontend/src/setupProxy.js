// The dev server's half of the deploy rewrites.
//
// Five paths are rendered by the *backend*, not by this app: a brief at
// /c/{id}, a brand at /brands/{id}, the two audience pages, and the sitemap.
// In production they reach the API host through the rewrites in `vercel.json`
// (see PREVIEW.md). There was no equivalent locally, so webpack-dev-server's
// history fallback answered all five with `index.html`, the SPA loaded, and
// the router's catch-all sent the visitor to `/`.
//
// That is not a cosmetic gap. The navbar and the footer link to /for-creators
// and /for-brands as **real anchors**, deliberately, so the browser asks the
// server rather than letting the router swallow the navigation — which means
// those two links silently bounced off home for anyone running the stack the
// way PREVIEW.md says to run it. The Share button had the same problem: it
// copies `http://localhost:3000/c/<id>`, which opened the app instead of the
// page it names.
//
// CRA loads this file automatically in development. It does not exist in a
// production build, so it cannot mask a missing rewrite on the deployed site.
const { createProxyMiddleware } = require("http-proxy-middleware");

// Same default the app's own API base falls back to, and the port
// docker-compose publishes the API on.
const BACKEND = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";

// Kept in step with the rewrites in `vercel.json` — those entries and these
// patterns are one decision, and PREVIEW.md is where it is written down. A
// unit test fails if the two lists drift.
//
// Regexes rather than the ":id" path syntax vercel.json uses: this is matched
// by a filter function, not by a router, and http-proxy-middleware's string
// contexts are prefixes rather than patterns — "/c/:id" as a context would
// match the literal characters and nothing else.
const SERVER_RENDERED = [
    /^\/c\/[^/]+\/?$/,
    /^\/brands\/[^/]+\/?$/,
    /^\/for-brands\/?$/,
    /^\/for-creators\/?$/,
    /^\/sitemap\.xml$/,
];

module.exports = function (app) {
    app.use(
        createProxyMiddleware(
            // Match on the path alone. A query string is not part of the
            // decision, and dev-server sockets must never be swept up in it.
            (pathname) => SERVER_RENDERED.some((re) => re.test(pathname)),
            {
                target: BACKEND,
                changeOrigin: true,
                // The backend builds absolute URLs — canonicals, Open Graph
                // images — from the request's own host, so it has to see the
                // origin the browser actually typed. Otherwise the local page
                // describes a different site from the one being read.
                xfwd: true,
                logLevel: "warn",
            },
        ),
    );
};
