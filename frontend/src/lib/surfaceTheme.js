/**
 * Which surface a route is on.
 *
 *   MARKETING   navy canvas, red CTAs — everything a signed-out stranger
 *               can land on
 *   PRODUCT     light canvas, navy CTAs — everything behind a sign-in
 *
 * **The line is authentication, and it is drawn on the path rather than on
 * the session.** The session is not known at first paint, and the one thing
 * this has to get right is the first paint — a dashboard that flashes navy
 * before turning light is the exact failure the pre-paint script exists to
 * prevent. Every product route requires auth anyway, so the path is a
 * faithful proxy and is available synchronously.
 *
 * **The attribute goes on `<html>`.** A wrapper `<div data-theme>` is the
 * obvious version and does not work: Radix portals every dialog, sheet,
 * popover, the command palette and every toast into `document.body`, so a
 * wrapper-scoped surface would leave all of them on the wrong one.
 *
 * Three places have to agree and do:
 *   - `public/index.html` applies it before first paint;
 *   - `SurfaceGuard` in `App.js` re-applies it on every navigation;
 *   - `index.css` defines what the attribute means.
 *
 * This replaced `consoleTheme.js`, which did the same job pointing the other
 * way — light was an admin's opt-in and everything else was dark. The machine
 * is the same; what changed is which surface is the default and how much of
 * the product is on the other one.
 */

export const THEMES = ["dark", "light"];

/** The one key, spelled once. */
export const THEME_STORAGE_KEY = "weare:console-theme";

/** Where an admin's own choice still applies. */
export const CONSOLE_PATH_PREFIX = "/admin";

export const isConsolePath = (pathname) =>
    String(pathname || "").startsWith(CONSOLE_PATH_PREFIX);

/**
 * The authenticated product, by path prefix.
 *
 * `/admin/login` is in here on purpose: it is a staff doorway, not an
 * acquisition surface, and nobody lands on it from a search. `/login` and
 * `/signup` are deliberately *not* — those are the end of the marketing
 * journey, and a stranger arriving there has been reading navy for three
 * pages.
 */
export const PRODUCT_PREFIXES = [
    "/dashboard",
    "/onboarding",
    "/profile",
    "/admin",
    "/manager",
    "/calendar",
    "/check-in",
    // The trailing slash matters, the way it does in robots.txt: this is the
    // brand's own console, and `/brands/{id}` — the public brand page — must
    // stay on marketing.
    "/brand/",
];

/**
 * Whether a path is a product screen.
 *
 * **`/campaigns` is the awkward one and is split rather than lumped.** The
 * feed and a brief's detail page are public — a creator browses them signed
 * out, and they are linked from the marketing site — so they are marketing.
 * Posting or editing a brief is a brand authoring something inside the
 * product. Lumping the whole prefix either way would put an authoring form on
 * a navy canvas or a public feed on a light one.
 */
export function isProductPath(pathname) {
    const path = String(pathname || "/");
    if (path === "/campaigns/new") return true;
    if (/^\/campaigns\/[^/]+\/edit\/?$/.test(path)) return true;
    return PRODUCT_PREFIXES.some(
        (p) => path === p.replace(/\/$/, "") || path.startsWith(p),
    );
}

/**
 * What this machine's operating system asks for.
 *
 * Only ever consulted for the console override, and only when an admin has
 * never chosen. `matchMedia` is absent in jsdom and in some embedded
 * webviews, so a missing one reads as light — which is what the product is.
 */
export function systemTheme() {
    try {
        return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches
            ? "dark"
            : "light";
    } catch {
        return "light";
    }
}

/**
 * The console theme this admin has chosen, or `null` if they never have.
 *
 * **`null` is a real answer** — the difference between "follow this machine"
 * and "they picked light", and only the first should change when somebody
 * switches their OS at dusk.
 */
export function storedTheme() {
    try {
        const value = window.localStorage?.getItem(THEME_STORAGE_KEY);
        return THEMES.includes(value) ? value : null;
    } catch {
        // Private windows and blocked site data throw on access rather than
        // returning null. The console still has to render.
        return null;
    }
}

/**
 * The local cache of the account's choice.
 *
 * The account is the record — see `PUT /auth/me/console-theme` — and this is
 * what lets the pre-paint script know the answer before any request has been
 * made.
 */
export function rememberTheme(theme) {
    try {
        if (theme === null) window.localStorage?.removeItem(THEME_STORAGE_KEY);
        else if (THEMES.includes(theme))
            window.localStorage?.setItem(THEME_STORAGE_KEY, theme);
    } catch {
        // Not being able to remember it is a worse experience, not a broken
        // one: the server still has the choice and the next `/auth/me`
        // brings it back.
    }
}

/** Write it onto the document. The only place the attribute is set. */
export function applyTheme(theme) {
    const root = document?.documentElement;
    if (!root) return;
    if (theme === "light") root.setAttribute("data-theme", "light");
    // Marketing navy is the absence of the attribute rather than
    // `data-theme="dark"`, so the default state of the document is the brand's
    // default surface — and a bug that fails to set anything fails to navy,
    // which is what an unauthenticated first paint should be.
    else root.removeAttribute("data-theme");
    // Native controls — scrollbars, form widgets, the spinner inside a
    // `datetime-local` — take their cue from this and nothing else. Without
    // it a light product keeps dark scrollbars, which is the tell that a
    // surface was painted on rather than applied.
    root.style.colorScheme = theme === "light" ? "light" : "dark";
}

/**
 * The surface for a path, given what the account says about the console.
 *
 * One reader, so the pre-paint script, the guard and the account menu cannot
 * disagree. Marketing is never overridable — an admin's console preference is
 * a preference about *their console*, not a licence to repaint the home page.
 */
export function surfaceFor(pathname, accountTheme) {
    if (!isProductPath(pathname)) return "dark";
    if (!isConsolePath(pathname)) return "light";
    // Inside the console only: an explicit choice wins, then this browser's
    // cache of one, then the operating system.
    if (THEMES.includes(accountTheme)) return accountTheme;
    return storedTheme() || systemTheme();
}

/** Back-compat for the account menu, which only ever asks about the console. */
export function resolveTheme(accountTheme) {
    if (THEMES.includes(accountTheme)) return accountTheme;
    return storedTheme() || systemTheme();
}
