// Decides, on every route change, whether the public-site recorder may run —
// and on a page where it may, reports which sections were seen and which
// calls to action were pressed.
//
// **The rule is two conditions, and both must hold**: the path is a public
// marketing page (`TRACKED_PATHS`), and the visitor is signed out. The second
// is not decoration: a signed-in visitor on the home page has their name in the
// navbar, and that is personal data on a page we would otherwise record.
// While the session check is still in flight (`user === null`) nothing starts,
// because "not yet known" is not "signed out".
//
// Anything else stops the recorder for the rest of the tab — see `lib/track.js`
// for why a stop is final. Renders nothing.
//
// **Every field is masked before the recorder can read it.** Clarity masks
// inputs in its default mode, but that is a setting on a dashboard somebody can
// change; `data-clarity-mask` on the element is in the code. The observer
// stamps it on every input, textarea, select and editable region as it appears,
// and the contact form carries it statically as well, so the one form a
// visitor fills in on these pages is masked whichever runs first.
//
// **The events are read off the markup, not wired into each page**, so the
// site as it stands today is measured without editing a page:
//   - `section_view` — each outermost `<section>` on the page, once per
//     page view, the first time half of it is on screen (or, for a section
//     taller than two screens, half a screen of it). Its id is
//     `data-track-section`, else `id`, else `data-testid`.
//   - `cta_click` — a link or button marked `data-cta`, a `data-testid`
//     containing "cta", or any link into signup.
//   - `outbound_whatsapp` — any link to wa.me or api.whatsapp.com. The number
//     is never sent: the event carries the page and the element's id.
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import {
    EVENTS,
    isTrackedPath,
    startTracking,
    stopTracking,
    track,
    trackingActive,
} from "@/lib/track";

const MASK_SELECTOR = "input, textarea, select, [contenteditable=''], [contenteditable='true']";
const WHATSAPP_HREF = /^(https?:\/\/)?(wa\.me|api\.whatsapp\.com|chat\.whatsapp\.com)\b|^whatsapp:/i;

export function sectionId(el, index) {
    return (
        el.getAttribute("data-track-section") ||
        el.id ||
        el.getAttribute("data-testid") ||
        `section-${index + 1}`
    );
}

/** What a click on `el` reports, or null. Exported for the tests. */
export function classifyClick(el) {
    if (!el || !el.closest) return null;
    // A button nested in a link (`<Link><Button>`) is one control: the id is
    // usually on the link, so read both.
    const anchor = el.closest("a");
    const button = el.closest("button");
    if (!anchor && !button) return null;
    const href = (anchor && anchor.getAttribute("href")) || "";
    const testid =
        (button && button.getAttribute("data-testid")) || (anchor && anchor.getAttribute("data-testid")) || "";
    const target = button || anchor;
    if (WHATSAPP_HREF.test(href)) {
        return { event: EVENTS.outboundWhatsapp, props: { target: testid || "whatsapp" } };
    }
    const marked = target.closest("[data-cta]");
    if (marked) return { event: EVENTS.ctaClick, props: { cta: marked.getAttribute("data-cta") } };
    if (/cta/i.test(testid) || href.startsWith("/signup")) {
        return { event: EVENTS.ctaClick, props: { cta: testid || href } };
    }
    return null;
}

function maskFields(root) {
    if (!root || !root.querySelectorAll) return;
    const nodes = root.matches && root.matches(MASK_SELECTOR) ? [root] : [];
    root.querySelectorAll(MASK_SELECTOR).forEach((n) => nodes.push(n));
    nodes.forEach((n) => n.setAttribute("data-clarity-mask", "true"));
}

// Inside `<main>` where the page has one; the home page on this tree does not,
// so the fallback is every outermost section outside the header and footer.
function topLevelSections() {
    const root = document.querySelector("main") || document.body;
    return Array.from(root.querySelectorAll("section")).filter(
        (s) => !s.parentElement.closest("section") && !s.closest("header, footer, nav"),
    );
}

export default function AnalyticsGate() {
    const { pathname } = useLocation();
    const { user } = useAuth();
    const allowed = isTrackedPath(pathname) && user === false;

    // Start or stop. A signed-in visitor, or any untracked path, stops it.
    useEffect(() => {
        if (allowed) startTracking();
        else if (user !== null || !isTrackedPath(pathname)) stopTracking();
    }, [allowed, user, pathname]);

    // One page view's worth of observers.
    useEffect(() => {
        if (!allowed || !trackingActive() || typeof window === "undefined") return undefined;
        const page = pathname;
        const seen = new Set();
        const watched = new WeakSet();

        const io =
            typeof IntersectionObserver === "undefined"
                ? null
                : new IntersectionObserver(
                      (entries) => {
                          entries.forEach((entry) => {
                              if (!entry.isIntersecting) return;
                              const half =
                                  entry.intersectionRatio >= 0.5 ||
                                  entry.intersectionRect.height >= window.innerHeight * 0.5;
                              if (!half) return;
                              const id = entry.target.dataset.weareSectionId;
                              if (!id || seen.has(id)) return;
                              seen.add(id);
                              track(EVENTS.sectionView, { page, section: id });
                              io.unobserve(entry.target);
                          });
                      },
                      { threshold: [0, 0.25, 0.5, 0.75, 1] },
                  );

        const scan = () => {
            maskFields(document.body);
            if (!io) return;
            topLevelSections().forEach((s, i) => {
                if (watched.has(s)) return;
                watched.add(s);
                s.dataset.weareSectionId = sectionId(s, i);
                io.observe(s);
            });
        };
        scan();
        const mo = new MutationObserver(scan);
        mo.observe(document.body, { childList: true, subtree: true });

        const onClick = (e) => {
            const hit = classifyClick(e.target);
            if (hit) track(hit.event, { page, ...hit.props });
        };
        document.addEventListener("click", onClick, true);

        return () => {
            mo.disconnect();
            if (io) io.disconnect();
            document.removeEventListener("click", onClick, true);
        };
    }, [allowed, pathname]);

    return null;
}
