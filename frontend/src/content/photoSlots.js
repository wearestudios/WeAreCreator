// Every photograph the public site has room for, in one place.
//
// **The site ships without photography and takes it later with no code
// change.** No image path is written in JSX on the public pages: a page names
// a slot, `<PhotoSlot id="…" />`, and this file says what is in it. Adding a
// photograph is a file drop into `public/img/photos/` plus one `src` line, and
// nothing else moves, because the box is reserved by `width`/`height` whether
// or not the picture has arrived.
//
// Each entry:
//
//   src               the file, or null while the slot is empty
//   alt               what the picture shows. Written when the photograph is
//                     chosen, not before — alt text for a picture nobody has
//                     taken is a guess read aloud.
//   focal             CSS object-position, so a crop keeps the subject
//   width, height     the size to shoot or export at; also the reserved ratio
//   brief             one sentence for a photographer — **development and
//                     Vercel previews only** (see `SHOW_BRIEFS`)
//   fallbackHeadline  what a visitor sees while `src` is null, in production:
//                     a navy panel with this line in display type. It has to
//                     read as a finished section, not as something missing.
//   fallbackAccent    the one word of the headline set in Fraunces italic red
//   fallbackLine      an optional sentence under it
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
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 2400,
        height: 1200,
        brief: SHOW_BRIEFS
            ? "A creator mid-shoot at a venue — phone on a small rig, the room busy around them. Daylight or warm interior light; keep the left third quiet for a headline."
            : null,
        fallbackHeadline: "The shoot still has to be good.",
        fallbackAccent: "good",
        fallbackLine:
            "Verified creators who turn up, shoot well and post what they agreed. That part is on us.",
    },
    "brands-full-room": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 2400,
        height: 1200,
        brief: SHOW_BRIEFS
            ? "A venue full on an ordinary weeknight, creators among the guests, phones out at the table. Wide, warm, no faces to camera; keep the left third quiet for a headline."
            : null,
        fallbackHeadline: "A full room on a Tuesday is the only metric that matters",
        fallbackAccent: null,
        fallbackLine: null,
    },
    "creators-on-shoot": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 2400,
        height: 1200,
        brief: SHOW_BRIEFS
            ? "A creator framing a shot of a dish or a product, seen from just behind the shoulder. Natural light; keep the left third quiet for a headline."
            : null,
        fallbackHeadline: "Turn up, shoot it well, get paid",
        fallbackAccent: null,
        fallbackLine: null,
    },
};

/** The slot, or a thrown error: a misspelt id must fail loudly, not render an
 * empty box nobody notices is the wrong one. */
export function photoSlot(id) {
    const slot = PHOTO_SLOTS[id];
    if (!slot) throw new Error(`Unknown photo slot "${id}" — add it to content/photoSlots.js`);
    return slot;
}
