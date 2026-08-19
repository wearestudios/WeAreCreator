// The marketing site's own map, in one place.
//
// The footer is on every page a signed-out person can land on, and the site is
// now six pages rather than one — so the list below is the only definition of
// where anything is. `FOOTER_COLUMNS` is mirrored by `FOOTER_COLUMNS` in
// `backend/server.py`, which builds the sitemap from it, and a unit test fails
// if the two drift: the same arrangement `followerTiers.js` and
// `shootWindows.js` use, for the same reason.
//
// Paths only — no origin.
//
// The columns changed shape when the marketing site did. "Why WeAre" and "How
// it works" used to be the audience pages under borrowed names, because those
// were the only two pages that existed; each is now its own page, and the
// audience columns point at the audience pages.

export const CONTACT_EMAIL = "creators@wearemonk.in";

// `external` marks a destination the router must not handle — today only the
// mailto. The audience pages used to be marked too, back when the backend
// rendered them and a <Link> would have been swallowed by the SPA's
// catch-all. They are ordinary routes now.
export const FOOTER_COLUMNS = [
    {
        heading: "Creators",
        links: [
            { label: "For creators", to: "/for-creators" },
            { label: "Browse briefs", to: "/campaigns" },
            { label: "Join as a creator", to: "/signup?role=creator" },
        ],
    },
    {
        heading: "Brands",
        links: [
            { label: "For brands", to: "/for-brands" },
            { label: "Post a campaign", to: "/signup?role=brand" },
            { label: "Log in", to: "/login" },
        ],
    },
    {
        heading: "The site",
        links: [
            { label: "How it works", to: "/how-it-works" },
            { label: "Why WeAre", to: "/why-weare" },
            { label: "Contact", to: `mailto:${CONTACT_EMAIL}`, external: true },
        ],
    },
    {
        heading: "Company",
        links: [
            { label: "Terms", to: "/terms" },
            { label: "Privacy", to: "/privacy" },
        ],
    },
];

/** The marketing pages, for the sitemap and for tests that walk them all. */
export const MARKETING_PATHS = [
    "/",
    "/for-brands",
    "/for-creators",
    "/how-it-works",
    "/why-weare",
];

/** The year the copyright line prints. Read at render, not hardcoded — a
 *  stale year is the cheapest possible signal that a site is unmaintained. */
export const copyrightYear = () => new Date().getFullYear();
