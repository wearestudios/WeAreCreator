/**
 * Light and dark, for the admin console and nowhere else.
 *
 * An admin sits in front of this for hours, which is a different relationship
 * from the one a creator has with their dashboard — and a different one from
 * what the rest of the product is designed for. So the console gets a choice
 * and the marketing site, the creator app, the brand app and the manager
 * screens stay dark.
 *
 * **The attribute goes on `<html>`, and the scoping is that it is only there
 * while a console route is mounted.** A wrapper `<div data-theme>` is the
 * obvious version and does not work: Radix portals every dialog, sheet,
 * popover, the command palette and every toast into `document.body`, so a
 * wrapper-scoped theme would leave all of them dark on a light console —
 * which is most of the surface the theme has to cover. Putting it on the root
 * and taking it off on the way out gives the same scoping with none of that.
 *
 * Three places have to agree about this and do:
 *   - `public/index.html` applies it before first paint;
 *   - this module applies it on mount and clears it on unmount;
 *   - `index.css` defines what `[data-theme="light"]` means.
 */

export const THEMES = ["dark", "light"];

/** The one key, spelled once. */
export const THEME_STORAGE_KEY = "weare:console-theme";

/** Where the theme applies. Kept here so the guard and the pre-paint script
 *  cannot come to disagree about which routes are "the console". */
export const CONSOLE_PATH_PREFIX = "/admin";

export const isConsolePath = (pathname) =>
    String(pathname || "").startsWith(CONSOLE_PATH_PREFIX);

/**
 * What this machine's operating system asks for.
 *
 * The default on a first visit, because an admin who has set their laptop to
 * light has already answered this question once and should not be asked
 * again. `matchMedia` is absent in jsdom and in some embedded webviews, so a
 * missing one reads as dark — which is what the console has always been.
 */
export function systemTheme() {
    try {
        return window.matchMedia?.("(prefers-color-scheme: light)")?.matches
            ? "light"
            : "dark";
    } catch {
        return "dark";
    }
}

/**
 * The theme this reader has chosen, or `null` if they never have.
 *
 * **`null` is a real answer.** It is the difference between "follow this
 * machine" and "they picked dark", and only the first should change when
 * somebody switches their OS at dusk. Collapsing them would silently freeze
 * every admin who has never opened the menu onto whatever their OS said the
 * first time they loaded the page.
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
 * made. Without it, every hard load would paint dark and then flip, which is
 * the flash this whole arrangement exists to avoid.
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
    // Dark is the absence of the attribute rather than `data-theme="dark"`,
    // so the default state of the document is the default state of the
    // product — and a bug that fails to set anything fails to dark, which is
    // what every other surface here is.
    else root.removeAttribute("data-theme");
    // Native controls — scrollbars, form widgets, the spinner inside a
    // `datetime-local` — take their cue from this and nothing else. Without
    // it a light console keeps dark scrollbars, which is the tell that a
    // theme was painted on rather than applied.
    root.style.colorScheme = theme === "light" ? "light" : "dark";
}

/** Take it off, on the way out of the console. */
export function clearTheme() {
    const root = document?.documentElement;
    if (!root) return;
    root.removeAttribute("data-theme");
    root.style.colorScheme = "dark";
}

/**
 * What to show, given what the account says.
 *
 * One reader, so the pre-paint script, the shell and the menu cannot disagree
 * about precedence: an explicit choice wins, then this browser's cache of one,
 * then the operating system.
 */
export function resolveTheme(accountTheme) {
    if (THEMES.includes(accountTheme)) return accountTheme;
    return storedTheme() || systemTheme();
}
