// Analytics for the public site, behind one function.
//
// `track(event, props)` is the only thing a page calls. Which provider answers
// it is decided here and nowhere else, so swapping Microsoft Clarity for
// PostHog later is a new entry in `PROVIDERS` and no page changes.
//
// **Public marketing pages only, and only for somebody who is not signed in.**
// A session recording of a signed-in screen is a recording of a phone number,
// a payout account and a PAN, and the masking a recorder offers is a setting
// on somebody else's server. So the recorder is never loaded on a signed-in
// route and never runs for a signed-in visitor even on a public one (the
// navbar carries their name). `AnalyticsGate` is what applies the rule; this
// module only refuses to do anything while it says no. `test_public_analytics.py`
// holds both halves.
//
// **With `REACT_APP_CLARITY_ID` unset, every call is a no-op** — no script, no
// request, no global. That is the state of every laptop, every test run and
// every deployment until somebody sets the variable in Vercel.
//
// Leaving the public pages calls `clarity("stop")` (a real method on the
// clarity-js API — its queue dispatches `clarity[method]`), and the stop is
// final for the tab: restarting needs the tag's own configuration, and a
// recording that resumes silently after a sign-in screen is the one shape of
// failure this file exists to rule out.

/** The paths a recorder may run on. Exact matches; a trailing slash is folded. */
export const TRACKED_PATHS = [
    "/",
    "/for-brands",
    "/for-creators",
    "/how-it-works",
    "/why-weare",
    "/contact",
    "/terms",
    "/privacy",
];

/** The three events, spelled once. */
export const EVENTS = {
    sectionView: "section_view",
    ctaClick: "cta_click",
    outboundWhatsapp: "outbound_whatsapp",
};

export function isTrackedPath(pathname) {
    const path = (pathname || "/").replace(/\/+$/, "") || "/";
    return TRACKED_PATHS.includes(path);
}

/** Microsoft Clarity, loaded from its own tag only when asked to start. */
function clarity(id) {
    let injected = false;
    const call = (...args) => {
        if (typeof window === "undefined" || typeof window.clarity !== "function") return;
        window.clarity(...args);
    };
    return {
        name: "clarity",
        load() {
            if (injected || typeof document === "undefined") return;
            injected = true;
            // Clarity's own snippet: a queue first, so calls made before the
            // tag arrives are replayed by it rather than lost.
            window.clarity =
                window.clarity ||
                function queue() {
                    (window.clarity.q = window.clarity.q || []).push(arguments);
                };
            const script = document.createElement("script");
            script.async = true;
            script.src = `https://www.clarity.ms/tag/${encodeURIComponent(id)}`;
            script.dataset.weareAnalytics = "clarity";
            // A visitor can leave the public pages before the tag lands. The
            // queued "stop" covers that, and this covers a tag that started
            // itself without replaying the queue.
            script.onload = () => {
                if (state.stopped) call("stop");
            };
            document.head.appendChild(script);
        },
        event(name, props) {
            // Clarity's custom events are bare strings, so the one detail
            // worth filtering on rides in the name.
            call("event", name);
            const detail = props && (props.section || props.cta || props.target);
            if (detail) call("event", `${name}:${props.page || ""}#${detail}`);
        },
        stop() {
            call("stop");
        },
    };
}

const PROVIDERS = {
    clarity: () => (process.env.REACT_APP_CLARITY_ID ? clarity(process.env.REACT_APP_CLARITY_ID) : null),
};

const state = { provider: undefined, started: false, stopped: false };

function provider() {
    if (state.provider === undefined) state.provider = PROVIDERS.clarity();
    return state.provider;
}

/** True once a provider is configured and running for this tab. */
export function trackingActive() {
    return Boolean(provider()) && state.started && !state.stopped;
}

/**
 * Load the recorder. Called by `AnalyticsGate` on a tracked path for a
 * signed-out visitor, and by nothing else.
 */
export function startTracking() {
    const p = provider();
    if (!p || state.stopped || state.started) return;
    state.started = true;
    p.load();
}

/**
 * Stop for the rest of this tab. A no-op when nothing has started: somebody
 * who lands on the sign-in screen and then goes to the home page was never
 * recorded, so there is nothing to have left.
 */
export function stopTracking() {
    if (!state.started || state.stopped) return;
    state.stopped = true;
    if (provider()) provider().stop();
}

/** Send one event. A no-op unless tracking is running. */
export function track(event, props = {}) {
    if (!trackingActive()) return;
    provider().event(event, props);
}

/** For tests: forget the tab's state. */
export function _resetTracking() {
    state.provider = undefined;
    state.started = false;
    state.stopped = false;
}
