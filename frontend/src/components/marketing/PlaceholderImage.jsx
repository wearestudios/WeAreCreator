// A designed hole where a photograph goes.
//
// Every marketing page has deliberate image slots, and there is no owned
// photography yet. The three bad answers are: leave the slot out (and rebuild
// the layout when the photos arrive), hotlink stock (which is what the hero,
// the login screen and the signup screen used to do — somebody else's pictures
// of nowhere in particular, fetched from a CDN we do not control, on the pages
// arguing that the work is real and local), or draw a grey box with a camera
// icon, which reads as a broken image rather than a considered one.
//
// So: a tint from the warm palette with the site's own grain over it, inside a
// container that already occupies the exact space the photograph will. Nothing
// is fetched. Dropping a real image in is one prop — `src` — and the layout
// does not move, because the ratio is on the container and never on the <img>.
//
// **Every slot carries a `note`**, rendered as a comment in the source and
// visible on the element as `data-placeholder`, saying what belongs there.
// A slot nobody can brief is a slot that stays empty.
import React from "react";

/**
 * The tint, derived from the slot's own name.
 *
 * A single gradient repeated down a page reads as a template; four unrelated
 * ones read as a mess. So the hue is nudged within a narrow warm band around
 * ember — the same trick `lib/cover.js` uses for campaign covers, and the same
 * reason: neighbouring slots should be visibly different without any of them
 * leaving the palette.
 */
function tintFor(seed) {
    let h = 0x811c9dc5;
    for (let i = 0; i < seed.length; i += 1) {
        h ^= seed.charCodeAt(i);
        h = Math.imul(h, 0x01000193) >>> 0;
    }
    // 14°–40° spans burnt orange through to a deep amber. Outside that it
    // stops looking like this brand.
    return 14 + (h % 27);
}

const RATIO = {
    "16/9": "aspect-[16/9]",
    "4/3": "aspect-[4/3]",
    "3/2": "aspect-[3/2]",
    "1/1": "aspect-square",
    "5/4": "aspect-[5/4]",
    "21/9": "aspect-[21/9]",
};

/**
 * @param {string}  note   what should go here, in a sentence somebody could
 *                         hand to a photographer
 * @param {string}  ratio  one of RATIO's keys; the container reserves it
 * @param {string=} src    a real image, once there is one — the tint stays
 *                         behind it as the loading ground
 * @param {boolean=} fill  fill a positioned parent instead of reserving a
 *                         ratio. For a slot whose height something else has
 *                         already decided — a section background. An aspect
 *                         class and `h-full` would fight, and the ratio would
 *                         win at some widths and not others.
 */
export function PlaceholderImage({
    note,
    ratio = "16/9",
    src,
    alt = "",
    fill = false,
    className = "",
    testid,
    children,
}) {
    const hue = tintFor(note);

    return (
        <div
            data-testid={testid}
            data-placeholder={src ? undefined : note}
            className={`relative overflow-hidden ${
                fill
                    ? "absolute inset-0"
                    : `rounded-lg border border-white/10 ${RATIO[ratio] || RATIO["16/9"]}`
            } ${className}`}
            style={{
                // Two stops and a dark floor, so the tint reads as lit rather
                // than as a flat swatch. Kept off `bg-*` utilities because the
                // hue is computed.
                backgroundImage: `linear-gradient(135deg, hsl(${hue} 78% 22%) 0%, hsl(${
                    hue + 6
                } 60% 12%) 45%, hsl(24 18% 7%) 100%)`,
            }}
        >
            {src ? (
                <img
                    src={src}
                    alt={alt}
                    loading="lazy"
                    decoding="async"
                    className="absolute inset-0 h-full w-full object-cover"
                />
            ) : null}

            {/* The overlay variant, never `.grain-surface`: this element sets
                `background-image` for the gradient, and the surface variant
                would set it too — one of the two silently wins. Same rule the
                design foundations state, and the reason `.grain` exists. */}
            <div aria-hidden className="grain pointer-events-none absolute inset-0" />

            {/* A hairline of ember along the top edge. Enough to say the slot
                is designed rather than missing, without drawing a label a
                visitor would have to ignore. */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-ember-500/40 to-transparent"
            />

            {children}
        </div>
    );
}

export default PlaceholderImage;
