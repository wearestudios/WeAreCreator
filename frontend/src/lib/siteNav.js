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

/**
 * The two partners, as one list.
 *
 * **Written once because two surfaces render it** — the contact page and the
 * footer — and a number written twice is a number that moves once. The stored
 * form is bare E.164, which is what a `tel:` and a `wa.me` href both want;
 * `formatPhone` builds the spaced reading form from it rather than a second
 * spelling being kept beside the first.
 *
 * **Both get a WhatsApp link as well as a phone one.** This business runs on
 * WhatsApp — every OTP and every notification in this product is delivered
 * there — so a contact page offering only a voice call is offering the wrong
 * door.
 */
export const CONTACT_PEOPLE = [
    { name: "Renukesh", role: "Co-founder", phone: "+919916154048" },
    { name: "Vinay Nagaraju", role: "Co-founder", phone: "+919686500765" },
];

/** `+919916154048` → `+91 99161 54048`. Display only; hrefs take the raw value. */
export function formatPhone(e164) {
    const m = /^\+91(\d{5})(\d{5})$/.exec(e164);
    return m ? `+91 ${m[1]} ${m[2]}` : e164;
}

/** What a `wa.me` link wants: the digits, no `+`. */
export function whatsappHref(e164) {
    return `https://wa.me/${e164.replace(/\D/g, "")}`;
}

/**
 * The case-study shelf.
 *
 * **Server-rendered by the backend**, like `/c/{id}` and `/brands/{id}`, so
 * everything that points at it uses a plain `<a>` rather than a `<Link>` — a
 * router link is swallowed by the SPA and answered with the catch-all. Named
 * here because three places link to it (the footer and both proof strips) and
 * a path written out three times is a path that moves twice.
 *
 * Mirrors `CASE_STUDY_PATH` in `server.py`.
 */
export const WORK_PATH = "/work";

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
            // **`external`, and not because it leaves the site.** `/work` is
            // server-rendered by the backend like `/c/{id}` — see PREVIEW.md
            // — so a `<Link>` would be caught by the router and answered with
            // the SPA's catch-all, which is the exact failure the audience
            // pages had for months. `FooterLink` picks `<a>` off this flag.
            { label: "Our work", to: WORK_PATH, external: true },
            { label: "How it works", to: "/how-it-works" },
            { label: "Why WeAre Creators", to: "/why-weare" },
            // Was a bare `mailto:`. The page carries the address *and* both
            // partners on WhatsApp, so the link goes there and the mailto
            // survives on the page rather than as the only way through.
            { label: "Contact", to: "/contact" },
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

/**
 * The logged-out menu, in the order somebody reads it: which audience am I,
 * then how does it work, then why you.
 *
 * `components/marketing/MarketingNavbar.jsx` renders these. The shared
 * `components/Navbar.jsx` keeps its own copy of the same four, deliberately —
 * it is on nineteen authenticated surfaces and is out of scope for marketing
 * changes, so it is left alone rather than edited to import this. A unit test
 * compares the two lists, because two copies is exactly how one of them ends
 * up pointing at a page that moved.
 */
export const MARKETING_LINKS = [
    { to: "/for-brands", label: "For brands", testId: "nav-for-brands" },
    { to: "/for-creators", label: "For creators", testId: "nav-for-creators" },
    { to: "/how-it-works", label: "How it works", testId: "nav-how" },
    { to: "/why-weare", label: "Why WeAre Creators", testId: "nav-why" },
    { to: "/contact", label: "Contact", testId: "nav-contact" },
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

/**
 * The line above the headline, in one place.
 *
 * It read "Vol. 01 · Bengaluru · Influencer studio", inlined separately on the
 * home page and the brief feed — so it was two strings that had to be edited
 * together and were not. Three problems in eight words:
 *
 * - **"Vol. 01" is a magazine's furniture.** It implies a second volume that
 *   does not exist and tells a first-time visitor nothing about what the site
 *   is or whether it is for them.
 * - **The city contradicted the product.** Signup is open and creators join
 *   from anywhere; an eyebrow on every page naming one city tells everybody
 *   else they are in the wrong place before they have read a word.
 * - **"Influencer studio" describes us, not the offer.** The visitor's
 *   question is what they get, not what we are.
 *
 * **It does not say "nationwide" either**, and that is deliberate rather than
 * timid: "every city", "pan-India", "across India" and "nationwide" are in
 * `_FORBIDDEN_MARKETING_PHRASES` on the server, because the network really is
 * deepest in Bengaluru and a claim the operation cannot back is worse than the
 * city it replaces. Dropping the geography fixes the contradiction without
 * inventing a bigger one. Where depth is genuinely the point, the pages say it
 * in a sentence that can be defended — see the positioning note in CLAUDE.md.
 */
export const HERO_EYEBROW = "Paid briefs · Verified creators · India";
