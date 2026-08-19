// One small piece the film's UI needs, kept out of `filmUI.jsx` so that file
// is nothing but drawings.
import React from "react";

/**
 * A creator's avatar, as an initial on a tinted disc.
 *
 * Deliberately a monogram rather than a face: a stock portrait would be a
 * third-party fetch on the front page, and a made-up one is a person who does
 * not exist being used as evidence. The hue is derived from the name so three
 * applicants in a row are visibly three people.
 */
export function CreatorMonogram({ name }) {
    let h = 0x811c9dc5;
    for (let i = 0; i < name.length; i += 1) {
        h ^= name.charCodeAt(i);
        h = Math.imul(h, 0x01000193) >>> 0;
    }
    const hue = 14 + (h % 27);
    return (
        <span
            aria-hidden
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full font-serif text-sm text-white/90"
            style={{ backgroundColor: `hsl(${hue} 55% 26%)` }}
        >
            {name.slice(0, 1)}
        </span>
    );
}

export default CreatorMonogram;
