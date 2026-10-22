// Every photograph the public site has room for, in one place.
//
// **The site ships without photography and has to take it later with no code
// change.** So no image path is written in JSX anywhere on the public pages:
// a page names a slot, `<PhotoSlot id="…" />`, and this file says what is in
// it. Adding a photograph is a file drop into `public/img/photos/` plus one
// line here — `src` — and nothing else moves, because the box is reserved by
// `width`/`height` whether or not the picture has arrived.
//
// Each entry:
//
//   src     the file, or null while the slot is empty
//   alt     what the picture shows, for somebody who cannot see it. Written
//           when the photograph is chosen, not before — alt text describing a
//           picture nobody has taken is a guess read aloud.
//   focal   CSS object-position, so a crop keeps the subject at every width
//   width, height   the size to shoot or export at; also the reserved ratio
//   brief   one sentence somebody could hand a photographer. It is visible on
//           the empty slot, because a slot nobody can brief stays empty.
//
// **No real person is named in a brief**, and nobody from WeAre Studios: a
// slot is described by what the frame needs, never by who is in it.

export const PHOTO_SLOTS = {
    "home-band": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 2400,
        height: 1200,
        brief:
            "A creator mid-shoot at a venue, phone on a small rig, the room busy around them. Daylight or warm interior light; leave the left third quiet for a headline.",
    },
    "brands-band": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 2400,
        height: 1200,
        brief:
            "A brand team reviewing a draft together on a laptop at a café table. Hands and screens, no logos; leave the left third quiet for a headline.",
    },
    "creators-band": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 2400,
        height: 1200,
        brief:
            "A creator framing a shot of a dish or a product, seen from just behind the shoulder. Natural light; leave the left third quiet for a headline.",
    },
    "client-1": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 1200,
        height: 900,
        brief: "The first client's space, as a guest sees it on a good evening. No people facing camera.",
    },
    "client-2": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 1200,
        height: 900,
        brief: "The second client's product or space, shot from content we made for them, with their permission.",
    },
    "client-3": {
        src: null,
        alt: "",
        focal: "50% 50%",
        width: 1200,
        height: 900,
        brief: "The third client's product or space, shot from content we made for them, with their permission.",
    },
};

/** The slot, or a thrown error: a misspelt id must fail loudly, not render an
 * empty box nobody notices is the wrong one. */
export function photoSlot(id) {
    const slot = PHOTO_SLOTS[id];
    if (!slot) throw new Error(`Unknown photo slot "${id}" — add it to content/photoSlots.js`);
    return slot;
}
