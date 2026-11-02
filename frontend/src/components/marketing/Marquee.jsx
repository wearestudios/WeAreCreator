// A row of names scrolling sideways, continuously.
//
// **It pauses on hover and on focus within it**, so anybody trying to read one
// name can, and it is static under `prefers-reduced-motion` — the duplicate
// track is hidden and the names wrap as an ordinary list. Both are CSS, in the
// motion block of `index.css`, so this component has no motion branch.
//
// **The one exception to the single curve.** Everything else on the public
// site eases on `--weare-ease`; a loop must run at constant speed, or it
// visibly stalls at the seam every cycle, so the marquee is `linear`. The
// test names this as the only `linear` animation allowed on a public page.
//
// The list is announced once. The second copy, which exists only so the loop
// has no gap, is `aria-hidden` — a screen reader hearing every name twice is
// hearing the implementation.
import React from "react";

/**
 * @param {{ items: string[], label: string, repeat?: number, className?: string,
 *           itemClassName?: string, testid?: string }} props
 */
export function Marquee({ items, label, repeat = 4, className = "", itemClassName = "", testid }) {
    // Each track repeats the list so one track is wider than a 1920px screen
    // with three short names in it; the seam is between two identical tracks.
    const run = Array.from({ length: repeat }, () => items).flat();
    const track = (hidden) => (
        <ul
            className={`mkt-marquee-track ${hidden ? "mkt-marquee-dup" : ""}`}
            aria-hidden={hidden ? true : undefined}
        >
            {run.map((item, i) => (
                <li
                    key={`${item}-${i}`}
                    // Only the first copy of each name is read; the rest of
                    // the run is the same names again.
                    aria-hidden={!hidden && i >= items.length ? true : undefined}
                    className={itemClassName}
                >
                    {item}
                </li>
            ))}
        </ul>
    );
    return (
        <div role="region" aria-label={label} data-testid={testid} className={`mkt-marquee ${className}`}>
            {track(false)}
            {track(true)}
        </div>
    );
}

export default Marquee;
