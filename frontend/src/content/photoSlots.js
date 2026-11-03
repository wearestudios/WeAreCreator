// Every photograph the public site has room for, in one place.
//
// **Photographs arrive with no code change.** No image path is written in JSX
// on the public pages: a page names a slot, `<PhotoSlot id="…" />`, and this
// file says what is in it. Adding a photograph is an original dropped into
// `public/img/photos/_incoming/`, one run of `npm run photos`
// (`scripts/prepare-photos.mjs`: crop to the slot's ratio, two WebP widths
// inside their byte budgets, metadata stripped), and this file's
// `src`/`srcSet`/`alt`/`focal` for the slot. Nothing else moves, because the
// box is reserved by the layout whether or not the picture has arrived.
//
// Each entry:
//
//   src               the large export, or null while the slot is empty
//   srcSet            both exports with their widths, so a phone is sent the
//                     1200px file and a laptop the 2400px one. Written by
//                     `scripts/prepare-photos.mjs`, which prints the line
//   alt               what the picture shows, in one plain sentence and with
//                     nobody named. Written when the photograph is chosen,
//                     not before — alt text for a picture nobody has taken is
//                     a guess read aloud
//   focal             CSS object-position, so a crop keeps the subject — and,
//                     on the two bands, keeps the subject out from under the
//                     headline card, which sits bottom left
//   width, height     the size the large file is exported at; also the
//                     reserved ratio
//   brief             one sentence for a photographer — **development and
//                     Vercel previews only** (see `SHOW_BRIEFS`)
//   fallbackHeadline  what a visitor sees while `src` is null, in production:
//                     a navy panel with this line in display type. It has to
//                     read as a finished section, not as something missing.
//   fallbackAccent    the one word of the headline set in Fraunces italic red
//   fallbackLine      an optional sentence under it
//   fallbackIllustration
//                     the drawing that fills the slot, full bleed, while `src`
//                     is null in production. The headline sits on a navy band
//                     over it so it keeps its contrast whatever the drawing
//                     is. When `src` is set the photograph replaces the
//                     drawing and nothing else changes.
//
// **No real person is named in a brief**, and nobody from WeAre Studios: a
// slot is described by what the frame needs, never by who is in it.

/**
 * True in development and on a Vercel preview, false on a production build.
 *
 * **Every brief below is written `SHOW_BRIEFS ? "…" : null`, inline, on
 * purpose.** On a production build both halves of this expression are
 * literals after the build's environment substitution, so the minifier folds
 * it to `false` and drops the string itself: the photographer's notes are not
 * hidden in production, they are not in the bundle at all. A helper function
 * around the string would keep it — the minifier does not reliably see
 * through a call. `test_site_foundations.py` builds nothing, but asserts the
 * shape; the PR's build grep is what checks the result.
 *
 * Vercel exposes `REACT_APP_VERCEL_ENV` to a CRA build automatically
 * (`production`, `preview` or `development`).
 */
export const SHOW_BRIEFS =
    process.env.NODE_ENV !== "production" || process.env.REACT_APP_VERCEL_ENV === "preview";

export const PHOTO_SLOTS = {
    "home-on-location": {
        // **Still the drawing**: the photograph for this slot did not arrive
        // with the other five. The size is the 3:2 frame slide C draws it in,
        // so the export and the frame agree when it does.
        src: null,
        srcSet: null,
        alt: "",
        focal: "65% 50%",
        width: 2400,
        height: 1600,
        brief: SHOW_BRIEFS
            ? "A creator mid-shoot at a venue — phone on a small rig, the room busy around them. Daylight or warm interior light; subject on the right, bottom-left and top-right calm for the booking card and the chip drawn over it. 3:2."
            : null,
        fallbackIllustration: "/img/marketing/home-on-location.svg",
        fallbackHeadline: "The shoot still has to be good.",
        fallbackAccent: "good",
        fallbackLine:
            "Verified creators who turn up, shoot well and post what they agreed. That part is on us.",
    },
    "brands-full-room": {
        src: "/img/photos/brands-full-room-2400.webp",
        srcSet: "/img/photos/brands-full-room-1200.webp 1200w, /img/photos/brands-full-room-2400.webp 2400w",
        alt: "A packed restaurant at dinner, long tables of people eating, two of them photographing their food.",
        focal: "60% 50%",
        width: 2400,
        height: 1200,
        brief: SHOW_BRIEFS
            ? "A venue full on an ordinary weeknight, creators among the guests, phones out at the table. Wide, warm, no faces to camera; keep the left third quiet for a headline."
            : null,
        fallbackIllustration: "/img/marketing/brands-full-house.svg",
        fallbackHeadline: "A full room on a Tuesday is the only metric that matters",
        fallbackAccent: null,
        fallbackLine: null,
    },
    "creators-on-shoot": {
        src: "/img/photos/creators-on-shoot-2400.webp",
        srcSet: "/img/photos/creators-on-shoot-1200.webp 1200w, /img/photos/creators-on-shoot-2400.webp 2400w",
        alt: "A man photographing a dessert on a café table with his phone, beside a window.",
        focal: "85% 50%",
        width: 2400,
        height: 1200,
        brief: SHOW_BRIEFS
            ? "A creator framing a shot of a dish or a product, seen from just behind the shoulder. Natural light; keep the left third quiet for a headline."
            : null,
        // `creators-cafe-shoot` is beside "Briefs that fit" on the same page,
        // so the band takes the wide venue rather than repeat it.
        fallbackIllustration: "/img/marketing/home-venue-wide.svg",
        fallbackHeadline: "Turn up, shoot it well, get paid",
        fallbackAccent: null,
        fallbackLine: null,
    },
};

/**
 * The tinted slots outside the marketing pages — the auth asides and the 404 —
 * which draw `PlaceholderImage` rather than a `PhotoSlot` and so have no
 * headline fallback. Their notes are photographer briefs like the ones above
 * and are held to the same rule: written `SHOW_BRIEFS ? "…" : null` in this
 * module, where the minifier can fold it, so a production bundle carries no
 * copy of them. They used to be literal `note` props at each call site and
 * shipped as a `data-placeholder` attribute on the sign-in screen.
 */
export const PLACEHOLDER_BRIEFS = {
    "auth-login": SHOW_BRIEFS
        ? "Creator and brand manager reviewing a shoot plan on a phone at a venue table, portrait crop for the auth aside"
        : null,
    "auth-signup": SHOW_BRIEFS ? "Creator setting up a shot on location, portrait crop for the auth aside" : null,
    "not-found": SHOW_BRIEFS ? "Empty venue between shoots, chairs stacked, light through a window, 4:3" : null,
};

/**
 * The photographs in the three tinted slots, in every environment: a real
 * picture wins over the drawing and over the brief, the way `src` does on a
 * `PhotoSlot`. Same shape as a `PHOTO_SLOTS` entry's picture half, exported
 * by the same script (900/1800 for the two portrait asides, 1200/2400 for the
 * 404). A slot missing here falls back to its drawing in production and its
 * brief in development, exactly as before.
 */
export const PLACEHOLDER_PHOTOS = {
    "auth-login": {
        src: "/img/photos/auth-login-1800.webp",
        srcSet: "/img/photos/auth-login-900.webp 900w, /img/photos/auth-login-1800.webp 1800w",
        alt: "Two people at a café table looking at a phone together, coffee cups and an open notebook between them.",
        focal: "50% 50%",
    },
    "auth-signup": {
        src: "/img/photos/auth-signup-1800.webp",
        srcSet: "/img/photos/auth-signup-900.webp 900w, /img/photos/auth-signup-1800.webp 1800w",
        alt: "A woman adjusting a ring light on a small camera rig set up on a bar counter.",
        focal: "50% 50%",
    },
    "not-found": {
        src: "/img/photos/not-found-2400.webp",
        srcSet: "/img/photos/not-found-1200.webp 1200w, /img/photos/not-found-2400.webp 2400w",
        alt: "An empty café in the afternoon, chairs stacked on the tables and sunlight across the wooden floor.",
        focal: "50% 50%",
    },
};

/**
 * What the three tinted slots show in production when there is no photograph,
 * where there is no brief to show: a drawing that fits the screen, instead of
 * an empty tint. In development and on a preview they keep the brief exactly
 * as before.
 */
export const PLACEHOLDER_ILLUSTRATIONS = {
    // A creator and a brand manager going over a shoot at a venue table.
    "auth-login": "/img/marketing/how-table-talk.svg",
    // A creator setting up a shot on location.
    "auth-signup": "/img/marketing/home-on-location.svg",
    // A venue between shoots.
    "not-found": "/img/marketing/home-venue-wide.svg",
};

/** The slot, or a thrown error: a misspelt id must fail loudly, not render an
 * empty box nobody notices is the wrong one. */
export function photoSlot(id) {
    const slot = PHOTO_SLOTS[id];
    if (!slot) throw new Error(`Unknown photo slot "${id}" — add it to content/photoSlots.js`);
    return slot;
}
