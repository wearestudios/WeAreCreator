// Per-page title, description, canonical and Open Graph tags.
//
// The marketing pages moved from being server-rendered by the backend into the
// SPA, which is what makes them reachable with a <Link> and what makes /404,
// /how-it-works and /why-weare possible at all. The cost is that the tags below
// are written by JavaScript, and that has a real limit worth stating rather
// than papering over:
//
//   Google and Bing render JavaScript and will read these. **WhatsApp does
//   not, and neither do most chat crawlers** — they fetch the HTML, read the
//   static tags in `public/index.html`, and never run a line of script. So a
//   link to /for-brands pasted into a chat previews with the site-wide card,
//   not this page's.
//
// That is the trade this restructure makes. It is recoverable without moving
// the pages back: point the Vercel rewrites at a prerender service, or add a
// `has` condition matching crawler user-agents. `/c/{id}` and `/brands/{id}`
// stay server-rendered by the backend precisely because a shared brief *is*
// the preview, and there the trade would not be worth making.
import { useEffect } from "react";

const SITE = "WeAre Creators";

/** Set (or create) one <meta>, keyed on the attribute that identifies it. */
function meta(attr, key, content) {
    let el = document.head.querySelector(`meta[${attr}="${key}"]`);
    if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, key);
        document.head.appendChild(el);
    }
    el.setAttribute("content", content);
}

function link(rel, href) {
    let el = document.head.querySelector(`link[rel="${rel}"]`);
    if (!el) {
        el = document.createElement("link");
        el.setAttribute("rel", rel);
        document.head.appendChild(el);
    }
    el.setAttribute("href", href);
}

/**
 * @param {string} title       the page's own title, without the site name
 * @param {string} description one sentence; used for both the meta and the OG
 * @param {string} path        this page's path, for the canonical and og:url
 */
export function PageMeta({ title, description, path }) {
    useEffect(() => {
        const full = `${title} · ${SITE}`;
        const url = `${window.location.origin}${path}`;

        document.title = full;
        meta("name", "description", description);
        link("canonical", url);

        meta("property", "og:title", title);
        meta("property", "og:description", description);
        meta("property", "og:url", url);
        meta("property", "og:type", "website");
        meta("property", "og:site_name", SITE);
        meta("name", "twitter:card", "summary_large_image");
        meta("name", "twitter:title", title);
        meta("name", "twitter:description", description);

        // Deliberately not restored on unmount. The next marketing page sets
        // its own, and an app page has no use for a stale marketing title —
        // resetting to a default here would make every navigation flash the
        // site name before the real one lands.
    }, [title, description, path]);

    return null;
}

export default PageMeta;
