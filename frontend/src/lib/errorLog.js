// What we record when something breaks, and what we refuse to record.
//
// A crash report is only worth having if it says where and to whom, and it is
// only safe to have if that "to whom" is a role rather than a person. This
// product handles creators' phone numbers, addresses and payout details; a log
// line is a place those leak to that nobody audits, because logs feel like
// plumbing rather than a data store.
//
// So the contract is narrow and enforced here rather than at each call site:
//
//   Recorded — the component that threw, the route pattern it was on, the
//              actor's *role*, the error's name/message/stack, the React
//              component stack, and a timestamp.
//   Never    — names, phone numbers, WhatsApp numbers, emails, addresses,
//              UPI ids, PANs, or anything typed into a search box.
//
// The last of those is why the query string is dropped whole rather than
// filtered: ⌘K in the admin console searches on phone numbers, so
// `?q=%2B919876543210` is a real URL this app produces, and a redactor that has
// to recognise every shape of free text is a redactor that will one day miss one.

/** Most recent first, bounded. Support can ask somebody to paste this. */
const RING_LIMIT = 25;
const ring = [];

// Set by AuthProvider as the session changes. A module-level value rather than
// context because the two window-level handlers below run outside React
// entirely and still need to know who was signed in.
let ambient = { role: "anonymous", impersonating: false };

export function setLogContext(next) {
    ambient = { ...ambient, ...next };
}

export function getLogContext() {
    return { ...ambient };
}

// Deliberately blunt. Each of these can appear inside a thrown message when
// somebody interpolates a record into an error, which is the whole way personal
// data reaches a log in the first place.
const REDACTIONS = [
    // Anything shaped like an email.
    [/[^\s@<>"'`]+@[^\s@<>"'`]+\.[A-Za-z]{2,}/g, "[email]"],
    // E.164, with or without spaces and dashes: +91 98765 43210.
    [/\+\d[\d\s-]{7,17}\d/g, "[phone]"],
    // A bare Indian mobile, which is what people paste. Bounded by non-digits
    // so a 24-character ObjectId is not mistaken for one.
    [/(?<!\d)[6-9]\d{9}(?!\d)/g, "[phone]"],
    // PAN: five letters, four digits, a letter.
    [/(?<![A-Z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Z0-9])/g, "[pan]"],
    // A UPI handle — name@bank, which the email rule misses (no dot after @).
    [/(?<![\w.@])[\w.-]{2,}@[a-z]{3,}(?![\w.@])/g, "[upi]"],
];

/** Strip anything that looks like it identifies a person. */
export function redact(value) {
    if (typeof value !== "string") return value;
    let out = value;
    for (const [pattern, replacement] of REDACTIONS) out = out.replace(pattern, replacement);
    return out;
}

/**
 * The current route, with the query string removed.
 *
 * Path segments are kept — `/admin/creators/68f3…` is an opaque id, and "which
 * creator's page crashed" is most of the debugging value. What a person *typed*
 * is dropped entirely; see the note at the top.
 */
export function currentRoute() {
    try {
        const { pathname, search, hash } = window.location;
        return pathname + (search ? "?[redacted]" : "") + (hash ? "#…" : "");
    } catch {
        return "unknown";
    }
}

/** Stacks get long and the useful part is the top. */
const trim = (text, lines) =>
    typeof text === "string" ? text.split("\n").slice(0, lines).join("\n") : undefined;

/**
 * Record one failure.
 *
 * `source` says which mechanism caught it — a boundary, an unhandled rejection,
 * a window error — because "React caught this" and "nothing caught this" are
 * different bugs with different fixes, and a log that flattens them makes you
 * work that out again every time.
 */
export function logError(error, context = {}) {
    const entry = {
        at: new Date().toISOString(),
        source: context.source || "unknown",
        boundary: context.boundary,
        component: context.component,
        route: currentRoute(),
        role: ambient.role,
        // Worth knowing: a crash only reproducible under view-as is a crash in
        // the impersonated role's screens, not the admin's.
        impersonating: ambient.impersonating || undefined,
        name: error?.name,
        message: redact(error?.message || String(error ?? "")),
        stack: redact(trim(error?.stack, 12)),
        componentStack: redact(trim(context.componentStack, 12)),
        status: context.status,
        // The endpoint that failed, path only — an id is fine, a query is not.
        endpoint: context.endpoint ? redact(context.endpoint.split("?")[0]) : undefined,
    };

    ring.unshift(entry);
    if (ring.length > RING_LIMIT) ring.length = RING_LIMIT;

    // The sink. Console today; pointing this at a real collector is one call,
    // and everything above it is already redacted, so that change cannot
    // become a privacy change by accident.
    // eslint-disable-next-line no-console
    console.error(
        `[weare] ${entry.source}${entry.component ? " in " + entry.component : ""} — ${entry.message}`,
        entry,
    );
    return entry;
}

/** What support asks somebody to paste. Already redacted, by construction. */
export function recentErrors() {
    return ring.slice();
}

if (typeof window !== "undefined") {
    // Not a debug back door: everything in the ring has been through `redact`
    // on the way in, so there is nothing here that was not already safe to log.
    window.__weareErrors = recentErrors;
}
