/**
 * The WeAre Creators logo, in three lockups.
 *
 * One component for every surface, because the thing that used to stand here
 * was a `bg-red-500` square with a serif `W` in it, repeated inline at nine
 * call sites with two different spellings of the accent colour — so the mark
 * was whatever each file happened to say it was.
 *
 * **The SVG is inlined rather than loaded through `<img>`**, and that is what
 * makes the tone rule below work: an `<img>` is an opaque document that cannot
 * see `currentColor`, so colouring it per surface would mean two files and a
 * decision at every call site about which one to reach for.
 *
 * **Tone comes from the surface, through the mechanism that already decides
 * it.** Marketing is navy and is the *absence* of `data-theme`; the product
 * sets `data-theme="light"` before first paint (see `public/index.html` and
 * `lib/surfaceTheme.js`). So `tone="auto"` — the default — is two CSS rules in
 * `index.css` keyed on that attribute, and this component never asks what path
 * it is on. A `useLocation` here would be a third copy of the prefix list and
 * would be wrong for a frame on every first paint, which is the one thing the
 * pre-paint script exists to prevent.
 *
 * The shared `Navbar` and `Footer` are why it has to be automatic rather than
 * decided per call site: both render on marketing (`/campaigns`, `/legal`) and
 * inside the product, so a hardcoded tone would be wrong on one of them.
 *
 * `tone="white"` and `tone="brand"` force it, for a call site sitting on a
 * field its own surface does not describe — white type on the coral handshake
 * band, say.
 *
 * **The red is a literal and deliberately not `--primary`.** On marketing the
 * two happen to be the same value (#FF2731) and on the product they are not:
 * `--primary` flips to navy there, because navy is the primary *action* on a
 * light canvas. So a mark painted with the token would be red on the home page
 * and navy in the app — the exact failure `test_brand.py` has guarded against
 * since the palette landed, arriving by a different door.
 */
import React from "react";

import { BANDS, LAYOUTS, RATIOS } from "./paths";

/** The ink, where it is forced: the brand red (#FF2731), read from the one
 *  constant `--weare-logo-ink` also reads, so the two cannot disagree. */
export const LOGO_INK = "hsl(var(--brand-red))";

const TONE_CLASS = {
    // Both rules live in index.css, keyed on the surface attribute.
    auto: "weare-logo",
    white: "text-brand-white",
    brand: "",
};

/**
 * @param {"horizontal"|"stacked"|"mark"} variant
 * @param {"auto"|"brand"|"white"} tone
 * @param {number} height  rendered height in px; the width follows the ratio
 */
export default function Logo({
    variant = "horizontal",
    tone = "auto",
    height = 30,
    className = "",
    title = "WeAre Creators",
    ...rest
}) {
    const layout = LAYOUTS[variant] || LAYOUTS.horizontal;
    const ratio = RATIOS[variant] || RATIOS.horizontal;

    // **Both dimensions are set, never just the height.** An SVG with one
    // dimension is laid out at its default 300x150 until the browser has the
    // viewBox, which on the navbar is a header that reflows while the page
    // hydrates — the shift every reserved box in this product exists to stop.
    const width = Math.round(height * ratio * 100) / 100;

    return (
        <svg
            role="img"
            aria-label={title}
            viewBox={layout.view}
            width={width}
            height={height}
            fill="currentColor"
            focusable="false"
            className={[TONE_CLASS[tone] ?? TONE_CLASS.auto, className]
                .filter(Boolean)
                .join(" ")}
            style={tone === "brand" ? { color: LOGO_INK } : undefined}
            {...rest}
        >
            {layout.parts.map(([band, transform]) => (
                <path key={band} transform={transform} d={BANDS[band].d} />
            ))}
        </svg>
    );
}
