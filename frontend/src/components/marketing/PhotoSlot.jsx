// A photograph, or what stands in for one until it exists.
//
// The page names a slot and `content/photoSlots.js` says what fills it, so a
// photograph arrives as a file drop and one manifest line, with no change to
// any component. This file never sees a path of its own.
//
// Three states:
//
//   - **a `src`**: the image, positioned on the slot's focal point, lazy
//     unless the caller says it is above the fold;
//   - **no `src`, in production**: the slot's drawing
//     (`fallbackIllustration`), full bleed, with the `fallbackHeadline` in
//     display type on a navy band across its foot. A visitor must read it as
//     a finished section — a dashed box on the live site is a site that is
//     not done. It used to be the navy panel alone, which read as finished
//     and also as empty; the drawing is what the pre-revamp site had there.
//     The band is navy at 92% over the drawing, so the headline's contrast
//     is the inverse ink on navy whatever the drawing underneath is doing;
//   - **no `src`, in development or on a Vercel preview**: the dashed
//     placeholder with the slot id, the size to shoot at and the brief, so
//     the people building the site can see what belongs there.
//
// **The brief never reaches production**, and that is structural rather than
// a branch here: on a production build the manifest's briefs are compiled out
// (see `SHOW_BRIEFS`), so there is no string for this file to render even if
// it tried.
//
// **The box is reserved in every state.** The ratio sits on the container,
// never on the `<img>`, so an image that has not loaded still occupies the
// space it will. `fill` hands the height to the parent instead, for a band
// whose height the layout decides.
import React from "react";

import { SHOW_BRIEFS, photoSlot } from "@/content/photoSlots";

function Headline({ text, accent }) {
    if (!accent || !text.includes(accent)) return text;
    const at = text.lastIndexOf(accent);
    return (
        <>
            {text.slice(0, at)}
            {/* Red as display type, which the colour rule allows at 40px and
                up — this is set at mkt-h1, 44px at its smallest, and says so
                on the element so the size rule can read it. */}
            <em className="mkt-h1 font-normal italic text-accent">{accent}</em>
            {text.slice(at + accent.length)}
        </>
    );
}

/**
 * @param {{ id: string, eager?: boolean, fill?: boolean, className?: string,
 *           headingLevel?: "h2" | "h3", bare?: boolean }} props
 *
 * `bare` draws the picture alone, without the headline band: for a frame
 * whose headline is already on the page beside it — the homepage slider's
 * "On location" slide, where the slot's headline is the slide's own `h2`.
 */
export default function PhotoSlot({ id, eager = false, fill = false, className = "", headingLevel = "h2", bare = false }) {
    const slot = photoSlot(id);
    const box = fill ? {} : { aspectRatio: `${slot.width} / ${slot.height}` };
    const frame = `relative w-full overflow-hidden ${fill ? "h-full" : ""} ${className}`;

    if (slot.src) {
        return (
            <div data-testid={`photo-slot-${id}`} data-slot={id} className={`${frame} bg-muted`} style={box}>
                <img
                    src={slot.src}
                    alt={slot.alt}
                    width={slot.width}
                    height={slot.height}
                    loading={eager ? "eager" : "lazy"}
                    decoding="async"
                    className="absolute inset-0 h-full w-full object-cover"
                    style={{ objectPosition: slot.focal }}
                />
            </div>
        );
    }

    if (SHOW_BRIEFS && slot.brief) {
        return (
            <div
                data-testid={`photo-slot-${id}`}
                data-slot={id}
                data-empty="placeholder"
                className={`${frame} flex flex-col justify-end gap-2 border-2 border-dashed border-tint/25 bg-muted p-5 text-left md:p-8`}
                style={box}
            >
                <span className="text-meta font-medium text-foreground">
                    {id} · {slot.width}×{slot.height}
                </span>
                <span className="max-w-xl text-meta text-muted-foreground">{slot.brief}</span>
            </div>
        );
    }

    // Production with no photograph: the drawing, and the headline on a navy
    // band over it. The section is navy underneath too, so the frame reads as
    // one piece while the drawing is still arriving.
    const Heading = headingLevel;
    return (
        <div
            data-testid={`photo-slot-${id}`}
            data-slot={id}
            data-empty="fallback"
            data-surface="inverse"
            className={`${frame} flex items-end bg-background text-foreground`}
            style={box}
        >
            {slot.fallbackIllustration ? (
                <img
                    src={slot.fallbackIllustration}
                    alt=""
                    width={slot.width}
                    height={slot.height}
                    loading={eager ? "eager" : "lazy"}
                    decoding="async"
                    className="absolute inset-0 h-full w-full object-cover"
                    style={{ objectPosition: slot.focal }}
                />
            ) : null}
            {bare ? null : (
                <div className="relative w-full bg-background/[0.92]">
                    <div className="max-w-4xl p-6 sm:p-10 md:px-16 md:py-12">
                        <Heading className="mkt-h1 text-foreground">
                            <Headline text={slot.fallbackHeadline} accent={slot.fallbackAccent} />
                        </Heading>
                        {slot.fallbackLine ? (
                            <p className="mkt-lead mt-5 max-w-2xl text-muted-foreground">{slot.fallbackLine}</p>
                        ) : null}
                    </div>
                </div>
            )}
        </div>
    );
}
