// The hero's moving background — a reversal, and what it had to pay.
//
// A slider was here before and was removed on a measurement: a full-viewport
// compositing layer cross-fading every seven seconds, on the page most likely
// to be opened on mobile data. `FloatingCards` replaced it and said the same
// thing better — four categories visible *at once* rather than one at a time
// behind a scrim heavy enough to keep the headline readable.
//
// This brings the movement back under that budget rather than in spite of it.
// Four things are different from the version that went:
//
//   - **At most two layers are painted, ever.** The deck is four slides and
//     the DOM holds the outgoing one and the incoming one. Four simultaneous
//     full-viewport layers is the cost that got the original removed, and
//     rendering all four with three at `opacity: 0` would pay it in full —
//     an invisible compositing layer still composites.
//   - **The slides come from the headline.** One per `PHRASES` entry, in
//     order, so the picture changes as the words morph. The old deck carried
//     its own headline per slide, which made the page appear to sell four
//     products; this carries no copy at all.
//   - **Ken Burns rides the image layer, never the container.** The container
//     is the clipping box; scaling it would grow the hole it reserves.
//   - **Reduced motion gets slide one and no timer** — the end state on first
//     paint, not a shortened animation.
//
// Nothing is fetched from a third party. Every slide is a `PlaceholderImage`,
// which is a computed tint and a brief for a photographer. A test sweeps every
// source file for hotlinked stock photography, and it is a blunt substring
// check over whole files — so this comment deliberately does not name the CDN
// it looks for. Teaching the sweep to skip comments would mean stripping from
// `//` onward, which also strips the `//` in `https://` and would hide a real
// hotlink: the bluntness is the value.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import { EASE } from "@/components/marketing/motion";
import { PHRASES } from "@/components/marketing/KineticHeadline";
import { LANDING_HERO as IDS } from "@/constants/testIds";

/** How long each slide holds, including its crossfade. */
export const HOLD_MS = 7000;
/** The crossfade. Long enough to read as a dissolve rather than a cut. */
export const FADE_MS = 600;

/**
 * **One curve, derived rather than retyped.** `EASE` is the marketing layer's
 * only easing and `--weare-ease` is the same four numbers in CSS; writing
 * `cubic-bezier(0.22, 1, 0.36, 1)` here would be a third copy that a future
 * edit could desynchronise. Building the string from `EASE` makes a second
 * curve impossible without changing the first.
 */
const EASE_CSS = `cubic-bezier(${EASE.join(", ")})`;

/**
 * The deck: one slide per headline phrase, in the headline's own order.
 *
 * **The notes are the deliverable here.** A slot nobody can brief is a slot
 * that stays empty, so each is a sentence somebody could hand to a
 * photographer — and `drift` alternates so consecutive slides do not pan the
 * same way. Four identical drifts read as one looping clip rather than as a
 * sequence.
 */
// One per sector, in `PHRASES` order, so the picture changes as the word does.
//
// **Eight rather than four, and it costs nothing at runtime.** The budget this
// slider came back under is *painted layers* — the DOM holds the outgoing
// slide and the incoming one and never more, whatever the deck length — so
// matching the headline's eight is four more placeholder notes and zero extra
// compositing. Letting the deck fall out of step with the words was the other
// option, and a picture of a restaurant under the word "Retail" is worse than
// no picture.
//
// `drift` alternates so consecutive slides do not pan the same way: identical
// drifts read as one looping clip rather than as a sequence.
const DRIFTS = ["leftUp", "rightDown", "leftDown", "rightUp"];

const NOTES = [
    // PLACEHOLDER IMAGE: Restaurant on opening night, full tables, warm
    // service light, shot wide from the pass
    "Restaurant on opening night, full tables, warm service light, shot wide from the pass",
    // PLACEHOLDER IMAGE: Boutique hotel room at golden hour, balcony doors
    // open to the city
    "Boutique hotel room at golden hour, balcony doors open to the city",
    // PLACEHOLDER IMAGE: Shop floor mid-afternoon, a creator filming a product
    // wall, staff serving behind
    "Shop floor mid-afternoon, a creator filming a product wall, staff serving behind",
    // PLACEHOLDER IMAGE: Show flat with the balcony doors open, a creator
    // filming the room from the hallway
    "Show flat with the balcony doors open, a creator filming the room from the hallway",
    // PLACEHOLDER IMAGE: Fashion creator mid-shoot against a plain wall,
    // outfit caught in motion
    "Fashion creator mid-shoot against a plain wall, outfit caught in motion",
    // PLACEHOLDER IMAGE: Train window at first light, a phone filming the
    // landscape, bags on the seat
    "Train window at first light, a phone filming the landscape, bags on the seat",
    // PLACEHOLDER IMAGE: Studio class mid-session, one participant filming
    // from the back of the room
    "Studio class mid-session, one participant filming from the back of the room",
    // PLACEHOLDER IMAGE: Flat-lay of a morning routine on a linen bed, hands
    // arranging the last object
    "Flat-lay of a morning routine on a linen bed, hands arranging the last object",
];

export const SLIDES = PHRASES.map((phrase, i) => ({
    phrase,
    note: NOTES[i % NOTES.length],
    drift: DRIFTS[i % DRIFTS.length],
}));

/** The four Ken Burns keyframe names, defined in `index.css`. */
const DRIFT_ANIMATION = {
    leftUp: "heroDriftLeftUp",
    rightDown: "heroDriftRightDown",
    leftDown: "heroDriftLeftDown",
    rightUp: "heroDriftRightUp",
};

/**
 * One slide layer: a crossfade wrapper, a drifting layer, and the picture.
 *
 * Three nested elements rather than one, because the two animations have to
 * be separable. Opacity and transform on the same node means the crossfade
 * and the pan share a timeline, and the incoming slide would start its pan
 * already faded in. They are also the two properties a compositor can animate
 * without touching layout, which is the whole reason this is affordable.
 */
function Slide({ slide, index, visible, paused, reduced, eager }) {
    const driftRef = useRef(null);

    // **`will-change` is released when the animation ends**, the rule the
    // app's motion layer already holds. Left on, a full-viewport layer keeps a
    // compositor layer alive for the life of the page — which on this element
    // is precisely the cost the original slider was removed for.
    useEffect(() => {
        const node = driftRef.current;
        if (!node) return undefined;
        const release = () => {
            node.style.willChange = "auto";
        };
        node.addEventListener("animationend", release);
        return () => node.removeEventListener("animationend", release);
    }, []);

    const drift = reduced
        ? undefined
        : {
              animationName: DRIFT_ANIMATION[slide.drift],
              // The pan runs the slide's whole hold, so it is still moving
              // when the next one begins to arrive.
              animationDuration: `${HOLD_MS}ms`,
              animationTimingFunction: "linear",
              animationFillMode: "both",
              animationPlayState: paused ? "paused" : "running",
              willChange: "transform",
          };

    return (
        <div
            data-testid={IDS.slide(index)}
            // Opacity only. The layer is painted whether or not it is visible,
            // which is why only two are ever mounted.
            className="absolute inset-0"
            style={
                reduced
                    ? undefined
                    : {
                          opacity: visible ? 1 : 0,
                          transition: `opacity ${FADE_MS}ms ${EASE_CSS}`,
                      }
            }
        >
            <div ref={driftRef} className="absolute inset-0" style={drift}>
                <PlaceholderImage
                    testid={IDS.slideImage(index)}
                    note={slide.note}
                    // `fill`, not a ratio: the hero's height is set by its
                    // content, and an aspect class would fight `inset-0`.
                    fill
                    eager={eager}
                />
            </div>
        </div>
    );
}

/**
 * The slider.
 *
 * `aria-hidden` in its entirety: the `h1` above already carries the meaning,
 * and a screen reader announcing four photographs of nothing in particular is
 * noise. The dots are the exception — they are controls, so they sit outside
 * the hidden subtree and name the slide they go to.
 */
export default function HeroSlider({ className = "" }) {
    const reduced = useReducedMotion();
    const [active, setActive] = useState(0);
    // The slide fading out. `null` once the fade has finished, which is what
    // takes the third and fourth layers out of the DOM.
    const [leaving, setLeaving] = useState(null);
    const [paused, setPaused] = useState(false);
    const timer = useRef(null);
    const fadeTimer = useRef(null);

    // The active index as a ref as well as state, so `goTo` can read the
    // current slide without depending on it — a callback that changes every
    // slide would restart the timer effect on every tick.
    const activeRef = useRef(0);

    const goTo = useCallback((next) => {
        const current = activeRef.current;
        if (next === current) return;
        activeRef.current = next;
        setLeaving(current);
        setActive(next);
        clearTimeout(fadeTimer.current);
        // Drop the outgoing layer once it is invisible, rather than leaving
        // it parked at `opacity: 0` — a transparent full-viewport layer still
        // composites, which is the cost this whole component is budgeted
        // against.
        fadeTimer.current = setTimeout(() => setLeaving(null), FADE_MS);
    }, []);

    // **One timer, cleared on pause.** Under reduced motion it never starts —
    // slide one is the end state, not a frame of an animation.
    useEffect(() => {
        if (reduced || paused) return undefined;
        timer.current = setTimeout(
            () => goTo((active + 1) % SLIDES.length),
            HOLD_MS,
        );
        return () => clearTimeout(timer.current);
    }, [active, paused, reduced, goTo]);

    useEffect(() => () => {
        clearTimeout(timer.current);
        clearTimeout(fadeTimer.current);
    }, []);

    // **The listeners go on the hero, not on the slider.** The slider is
    // `absolute inset-0` *behind* the content, so a pointer over the headline
    // is over the content column and never over this element — handlers here
    // would pause only when somebody hovered the few pixels of background
    // either side of the type, which is the opposite of the case this is for.
    // Binding to the parent keeps the paused state owned by the component
    // that uses it while detecting the thing that actually matters: a reader
    // stopped on the hero.
    const rootRef = useRef(null);
    useEffect(() => {
        const hero = rootRef.current?.parentElement;
        if (!hero) return undefined;
        const hold = () => setPaused(true);
        const release = () => setPaused(false);
        hero.addEventListener("pointerenter", hold);
        hero.addEventListener("pointerleave", release);
        // `focusin`/`focusout` rather than `focus`/`blur`: the latter do not
        // bubble, so tabbing to a CTA inside the hero would not reach this.
        hero.addEventListener("focusin", hold);
        hero.addEventListener("focusout", release);
        return () => {
            hero.removeEventListener("pointerenter", hold);
            hero.removeEventListener("pointerleave", release);
            hero.removeEventListener("focusin", hold);
            hero.removeEventListener("focusout", release);
        };
    }, []);

    // **Order matters, and it is the opposite of the obvious one.** The
    // outgoing slide renders *last* so it sits on top, and fades out to
    // reveal the incoming one underneath. Painting the incoming above would
    // have it cover the old slide at full opacity the frame it mounts — a
    // hard cut, with a 600ms fade running invisibly beneath it. Dissolving
    // one layer is also half the work of fading two.
    const painted = reduced
        ? [0]
        : [active, leaving].filter((i) => i !== null && i !== undefined);

    return (
        <div
            ref={rootRef}
            className={`absolute inset-0 overflow-hidden ${className}`}
        >
            <div data-testid={IDS.slides} aria-hidden className="absolute inset-0">
                {painted.map((i) => (
                    <Slide
                        key={i}
                        slide={SLIDES[i]}
                        index={i}
                        visible={i === active}
                        paused={paused}
                        reduced={reduced}
                        // Only the first slide is worth the early fetch; the
                        // rest arrive seven seconds apart.
                        eager={i === 0}
                    />
                ))}
            </div>

            {/* **The scrim is its own layer**, not a property of the slide.
                Putting it on the slide would mean setting `background-image`
                on an element that already has one — the rule `.grain-surface`
                exists to avoid — and it would fade in and out with the
                picture, so the headline's legibility would pulse every seven
                seconds.

                Heaviest on the left, where the type sits, and lighter on the
                right so the picture is still a picture. */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-r from-background via-background/85 to-background/40"
            />
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-t from-background via-transparent to-background/60"
            />

            {/* Controls, so outside the hidden subtree. Aligned to the content
                column rather than to the viewport, so they sit under the type
                at every width. */}
            {!reduced && (
                <div className="pointer-events-none absolute inset-x-0 bottom-6 z-10">
                    <div className="mx-auto max-w-7xl px-6">
                        <div
                            data-testid={IDS.dots}
                            className="pointer-events-auto inline-flex items-center gap-2"
                        >
                            {SLIDES.map((slide, i) => (
                                <button
                                    key={slide.phrase}
                                    type="button"
                                    data-testid={IDS.dot(i)}
                                    aria-label={`Show ${slide.phrase}`}
                                    aria-current={i === active ? "true" : undefined}
                                    onClick={() => goTo(i)}
                                    className={`h-2 rounded-full transition-all duration-200 ${
                                        i === active
                                            ? "w-6 bg-primary"
                                            : "w-2 bg-foreground/35 hover:bg-foreground/60"
                                    }`}
                                />
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
