// The drawn illustrations the public pages place beside their copy.
//
// **A page names an illustration and this file says where it lives**, the
// arrangement `photoSlots.js` uses for photographs: no image path is written
// in a page, so moving or replacing a drawing is one line here. The files are
// in `public/img/marketing/`, which the build copies to the site root
// untouched — no import, no bundling, no hash — and each is a few kilobytes
// of SVG, so a drawing never costs what a photograph would.
//
// `width` and `height` are each file's own viewBox. They set the reserved
// ratio wherever a caller does not ask for a crop, so an illustration that
// has not arrived still holds its box.
//
// **They are decoration.** Every one is placed beside text that already says
// what it shows, so each is rendered with an empty `alt` and a screen reader
// skips it rather than reading a description of a drawing.
//
// Placed by meaning, as the pre-revamp pages had them (8263b6f). The rest of
// the folder is accounted for elsewhere or left out on purpose: the three
// photo-slot stand-ins are named in `photoSlots.js`, the six `float-*`
// drawings belong to the unmounted floating cards. `why-planning` sat unused
// until the "What the AI does" cards gave it a meaning: the desk where a brief
// gets drafted.

const at = (name) => `/img/marketing/${name}.svg`;

export const ILLUSTRATIONS = {
    // Home: the four steps, and who built it.
    "how-briefing": { src: at("how-briefing"), width: 1600, height: 1200 },
    "how-table-talk": { src: at("how-table-talk"), width: 1600, height: 900 },
    "why-shoot-day": { src: at("why-shoot-day"), width: 2520, height: 1080 },
    "creators-payment": { src: at("creators-payment"), width: 1200, height: 800 },
    "why-production": { src: at("why-production"), width: 1600, height: 900 },
    // For brands.
    "brands-city-dusk": { src: at("brands-city-dusk"), width: 1200, height: 800 },
    "why-roster-tablet": { src: at("why-roster-tablet"), width: 1200, height: 800 },
    "brands-door-checkin": { src: at("brands-door-checkin"), width: 1600, height: 1200 },
    "how-report-desk": { src: at("how-report-desk"), width: 1000, height: 800 },
    // For creators.
    "creators-profile-phone": { src: at("creators-profile-phone"), width: 1600, height: 1200 },
    "creators-cafe-shoot": { src: at("creators-cafe-shoot"), width: 1600, height: 900 },
    "why-fees-closeup": { src: at("why-fees-closeup"), width: 1000, height: 800 },
    // Home: "What the AI does" — named by the cards in content/marketing.js.
    "why-planning": { src: at("why-planning"), width: 1600, height: 1200 },
};

/** The illustration, or a thrown error: a misspelt name must fail loudly
 * rather than draw an empty frame nobody notices is the wrong one. */
export function illustration(name) {
    const art = ILLUSTRATIONS[name];
    if (!art) throw new Error(`Unknown illustration "${name}" — add it to content/illustrations.js`);
    return art;
}
