// A brief with no picture, and a brand with no mark.
//
// Most briefs will not have a cover on the day they are posted, and a list
// where every row is the same grey rectangle is the problem this was meant to
// solve rather than a smaller version of it. So the fallback is *generated*:
// the brand's initial on a tint derived from the campaign's own id, stable
// across renders and different between neighbours in a list.
//
// `_cover_hue` in backend/server.py computes the same number the same way, so
// the card in the app and the server-rendered share page of the same brief are
// the same colour. Change one and change the other.

/**
 * 0–359, derived from an id. Deterministic, and cheap enough to call in a map.
 *
 * FNV-1a rather than a sum of character codes, which was the first version and
 * was measured to be useless: ids differing only in their last byte — which is
 * what consecutive ObjectIds are — came out two degrees apart, so a row of
 * coverless briefs was a row of the same rectangle. `Math.imul` because a plain
 * `*` on these operands leaves float range and stops being a 32-bit multiply,
 * which would make this disagree with the Python.
 */
export function coverHue(seed) {
    const text = String(seed || "?");
    let h = 2166136261;
    for (let i = 0; i < text.length; i += 1) {
        h ^= text.charCodeAt(i);
        h = Math.imul(h, 16777619) >>> 0;
    }
    return h % 360;
}

/**
 * The generated cover's background.
 *
 * Two layers: a soft light from the top-left and a body gradient into the page
 * ground, both at low saturation. Ember is the product's accent and is reserved
 * for things you can act on, so a decorative surface must not borrow it.
 */
export function coverGradient(seed) {
    const h = coverHue(seed);
    return {
        // Light enough that the tint is actually visible: at 14% the hue is
        // there in the values and gone on the screen, so two neighbouring
        // fallbacks read as the same black rectangle — the thing this exists to
        // avoid. Still well below the ember accent, which stays reserved for
        // things you can act on.
        backgroundImage: [
            `radial-gradient(120% 120% at 20% 0%, hsl(${h} 42% 32%) 0%, transparent 62%)`,
            `linear-gradient(140deg, hsl(${h} 30% 20%), hsl(${h} 22% 11%))`,
        ].join(", "),
    };
}

/** The letter drawn on a fallback cover or a monogram avatar. */
export function initialOf(...candidates) {
    for (const value of candidates) {
        const first = String(value || "").trim().charAt(0);
        if (first) return first.toUpperCase();
    }
    return "?";
}
