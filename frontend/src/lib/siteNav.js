// The marketing site's own map, in one place.
//
// The footer exists twice — as a React component for the SPA's pages, and as
// plain HTML inside the server-rendered `/for-creators` and `/for-brands`.
// That is two renderers, and two renderers with two copies of the link list is
// how a footer ends up advertising a page that moved.
//
// So the links live here, once. `FOOTER_COLUMNS` is mirrored by
// `FOOTER_COLUMNS` in `backend/server.py` and a unit test fails if they drift,
// the same arrangement `followerTiers.js` and `shootWindows.js` already use.
//
// Paths only — no origin. The React footer hands them to `<Link>` or `<a>`
// depending on whether the destination is server-rendered; the HTML footer
// prefixes the app's origin, because it is being read on a page the backend
// served.

export const CONTACT_EMAIL = "creators@wearemonk.in";

// `external` marks a destination the backend renders rather than the SPA. The
// React footer has to use a real <a> for those or the router swallows the
// navigation and lands on the catch-all — the same trap the navbar's
// "For brands" entry documents.
export const FOOTER_COLUMNS = [
    {
        heading: "Creators",
        links: [
            { label: "Why WeAre", to: "/for-creators", external: true },
            { label: "Browse briefs", to: "/campaigns" },
            { label: "Join as a creator", to: "/signup?role=creator" },
        ],
    },
    {
        heading: "Brands",
        links: [
            { label: "How it works", to: "/for-brands", external: true },
            { label: "Post a campaign", to: "/signup?role=brand" },
            { label: "Log in", to: "/login" },
        ],
    },
    {
        heading: "Company",
        links: [
            { label: "Terms", to: "/terms" },
            { label: "Privacy", to: "/privacy" },
            { label: "Contact", to: `mailto:${CONTACT_EMAIL}`, external: true },
        ],
    },
];

/** The year the copyright line prints. Read at render, not hardcoded — a
 *  stale year is the cheapest possible signal that a site is unmaintained. */
export const copyrightYear = () => new Date().getFullYear();
