// A photograph, or the labelled space where one will go.
//
// The page names a slot and `content/photoSlots.js` says what fills it, so a
// photograph arrives as a file drop and one manifest line, with no change to
// any component. This file never sees a path of its own.
//
// **The box is reserved either way.** The ratio comes from the slot's
// `width`/`height` and sits on the container, never on the `<img>`, so an
// image that has not loaded — or has not been taken yet — still occupies the
// space it will. `fill` hands the height to the parent instead, for a
// full-bleed band whose height the layout decides.
//
// **The empty state is a brief, not a grey box.** A dashed border, the slot
// id, the size to shoot at and the sentence a photographer would need. It is
// meant to be seen: an empty slot on a staging page should say what belongs
// there, and the same sentence is in the manifest beside the `src` that will
// replace it.
import React from "react";

import { photoSlot } from "@/content/photoSlots";

/**
 * @param {{ id: string, eager?: boolean, fill?: boolean, className?: string }} props
 *   eager — the first slot on a page, which loads at once; every other one
 *           is `loading="lazy"`.
 */
export default function PhotoSlot({ id, eager = false, fill = false, className = "" }) {
    const slot = photoSlot(id);
    const box = fill ? {} : { aspectRatio: `${slot.width} / ${slot.height}` };

    if (slot.src) {
        return (
            <div
                data-testid={`photo-slot-${id}`}
                data-slot={id}
                className={`relative overflow-hidden bg-muted ${fill ? "h-full w-full" : "w-full"} ${className}`}
                style={box}
            >
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

    return (
        <div
            data-testid={`photo-slot-${id}`}
            data-slot={id}
            data-empty="true"
            role="img"
            aria-label={`Photograph to come: ${slot.brief}`}
            className={`relative flex w-full flex-col justify-end gap-2 overflow-hidden border-2 border-dashed border-tint/25 bg-muted p-5 text-left md:p-8 ${fill ? "h-full" : ""} ${className}`}
            style={box}
        >
            <span className="font-mono text-meta text-foreground">
                {id} · {slot.width}×{slot.height}
            </span>
            <span className="max-w-xl text-meta text-muted-foreground">{slot.brief}</span>
        </div>
    );
}
