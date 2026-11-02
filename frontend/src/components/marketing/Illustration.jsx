// One of the drawn illustrations, placed beside the copy it goes with.
//
// The page names it; `content/illustrations.js` says where the file is, so no
// image path is written in a page (the rule photographs already follow).
//
// - **Decorative**: an empty `alt`, because the text beside every one of
//   these already says what it shows.
// - **The box is reserved before the file arrives**: the ratio sits on the
//   frame, never on the `<img>`, so a drawing still on its way occupies the
//   space it will fill and nothing below it moves. `ratio` crops to a shared
//   shape where a row of them has to line up; otherwise it is the drawing's
//   own.
// - **Lazy unless the caller says it is above the fold**, and only then
//   without the entrance: a hero illustration that waits for an observer is
//   a hero illustration that paints late.
// - It rises in once with `Rise`, the old pages' `Reveal` entrance, so the
//   reduced-motion rule in the stylesheet covers it with everything else.
import React from "react";

import { Rise } from "@/components/marketing/primitives";
import { illustration } from "@/content/illustrations";

/**
 * @param {{ name: string, ratio?: string, eager?: boolean, i?: number,
 *           focal?: string, className?: string, testid?: string }} props
 */
export default function Illustration({ name, ratio, eager = false, i = 0, focal = "50% 50%", className = "", testid }) {
    const art = illustration(name);
    const frame = (
        <div
            data-testid={testid}
            data-illustration={name}
            className={`relative w-full overflow-hidden rounded-lg border border-border bg-muted ${eager ? className : ""}`}
            style={{ aspectRatio: ratio || `${art.width} / ${art.height}` }}
        >
            <img
                src={art.src}
                alt=""
                width={art.width}
                height={art.height}
                loading={eager ? "eager" : "lazy"}
                decoding="async"
                className="absolute inset-0 h-full w-full object-cover"
                style={{ objectPosition: focal }}
            />
        </div>
    );
    if (eager) return frame;
    return (
        <Rise i={i} className={className}>
            {frame}
        </Rise>
    );
}
