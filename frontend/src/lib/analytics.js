/**
 * The funnel, pushed to the GTM dataLayer.
 *
 * **Five events, and they are the five steps that matter**: somebody lands, a
 * brand starts signing up, a campaign gets posted, a creator starts signing
 * up, a profile is submitted for review. Anything else is a number nobody
 * acts on, and a tag manager filled with events nobody reads is how the ones
 * that matter get lost.
 *
 * **The dataLayer is pushed to whether or not GTM is installed.** `dataLayer`
 * is an ordinary array that GTM adopts when it loads, so a build with no
 * container id still accumulates the events in memory and simply never sends
 * them — which means the call sites never have to ask whether analytics is
 * configured. Absent is a supported state, the rule Instagram and Maps
 * already hold here.
 *
 * **No personal data, ever.** A phone number, an email or a name must not
 * reach a third-party tag — the same line `errorLog.js` draws for crash
 * reports, and for the stronger reason that this one leaves the building. The
 * payloads carry a role, a count or an id at most; `track()` drops anything
 * whose key looks like contact detail rather than trusting every call site to
 * remember. A test plants those keys and asserts they do not survive.
 */

export const FUNNEL = {
    landing: "landing_view",
    brandSignupStarted: "brand_signup_started",
    campaignPosted: "campaign_posted",
    creatorSignupStarted: "creator_signup_started",
    profileSubmitted: "creator_profile_submitted",
};

// Keys that must never leave the browser. Blunt on purpose: personal data
// reaches a tag by somebody spreading a record into a payload, and that record
// can be any shape.
const FORBIDDEN = /phone|whatsapp|email|address|upi|ifsc|account|pan|password|otp|token|lat|lng|name/i;

function clean(payload) {
    const out = {};
    Object.entries(payload || {}).forEach(([key, value]) => {
        if (FORBIDDEN.test(key)) return;
        if (value === null || value === undefined) return;
        // Only scalars. An object could carry anything at any depth, and the
        // key check above only sees the top level.
        if (typeof value === "object") return;
        out[key] = value;
    });
    return out;
}

export function track(event, payload) {
    if (!event) return;
    try {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ event, ...clean(payload) });
    } catch {
        // A blocked or sandboxed dataLayer must never break a signup. This is
        // measurement; the product is the thing underneath it.
    }
}

/**
 * Inject the GTM container, once.
 *
 * Called from `App.js` at module load. **The id comes from the environment**
 * and is never hardcoded — the rule the Maps key already holds — and with no
 * id nothing is injected at all, so a developer build makes no third-party
 * request. `REACT_APP_GTM_ID` is baked in at build time like every other
 * `REACT_APP_*`.
 */
export function installAnalytics() {
    const id = (process.env.REACT_APP_GTM_ID || "").trim();
    window.dataLayer = window.dataLayer || [];
    if (!id || typeof document === "undefined") return false;
    if (document.getElementById("gtm-loader")) return true;

    window.dataLayer.push({
        "gtm.start": Date.now(),
        event: "gtm.js",
    });
    const script = document.createElement("script");
    script.id = "gtm-loader";
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(id)}`;
    document.head.appendChild(script);
    return true;
}
