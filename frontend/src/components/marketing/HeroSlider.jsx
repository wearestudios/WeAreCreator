// The hero's picture — a framed panel in the hero's right column.
//
// **It is not a background any more.** A slider was here before and was
// removed on a measurement: a full-viewport compositing layer cross-fading
// every seven seconds, on the page most likely to be opened on mobile data.
// `FloatingCards` replaced it, the slider came back underneath the cards, and
// the result was three layers arguing over one area — type over cards over
// picture, with a scrim heavy enough to keep the headline readable muting the
// picture it was laid over. The hero is two columns now: the type has a
// column and this has a panel, so nothing readable sits over it and the
// scrims are gone.
//
// Four things are different from the version that was removed. The first was
// a budget set against a full-viewport layer; **this is a panel, so it is no
// longer required — it is kept**, because it is the right shape for the
// problem whatever the element's size, and the cost of losing it is paid on
// exactly the devices least able to afford it:
//
//   - **At most two layers are painted, ever.** The deck is eight slides and
//     the DOM holds the outgoing one and the incoming one. Rendering all
//     eight with seven at `opacity: 0` would pay for them in full — an
//     invisible compositing layer still composites.
//   - **The slides come from the headline.** One per `PHRASES` entry, in
//     order, so the picture changes as the words morph. The old deck carried
//     its own headline per slide, which made the page appear to sell four
//     products; this carries no copy at all.
//   - **Ken Burns rides the image layer, never the container.** The container
//     is the clipping box; scaling it would grow the hole it reserves.
//   - **Reduced motion gets slide one and no timer** — the end state on first
//     paint, not a shortened animation.
//
// The root stays `absolute inset-0`, so it fills whatever box it is given.
// The panel that gives it one owns the aspect ratio, which is why filling a
// slot here moves nothing.
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

// The photographs, one per note and **indexed the same way `NOTES` is**.
//
// Deliberately a parallel array rather than an eight-item list of objects:
// `PHRASES` is derived from `CATEGORY_OPTIONS`, so a ninth sector added to the
// enum has to degrade rather than break the deck. Written out as objects, the
// ninth slide would be `undefined` and the map would throw; written this way
// it wraps to the first image exactly as the note and the drift already wrap —
// a picture that is one sector out of step is worse than the right one and
// very much better than a blank hero.
//
// Served from `public/img/marketing/`, which CRA copies to the site root
// untouched — no import, no bundling, no hashed filename, so a reshoot is a
// file swap rather than a build change. Nothing is fetched from a third party;
// the sweep that enforces that is a blunt substring check over whole files.
const IMAGES = [
    "/img/marketing/hero-fnb.svg",
    "/img/marketing/hero-hospitality.svg",
    "/img/marketing/hero-retail.svg",
    "/img/marketing/hero-real-estate.svg",
    "/img/marketing/hero-fashion.svg",
    "/img/marketing/hero-travel.svg",
    "/img/marketing/hero-wellness.svg",
    "/img/marketing/hero-lifestyle.svg",
];

export const SLIDES = PHRASES.map((phrase, i) => ({
    phrase,
    note: NOTES[i % NOTES.length],
    image: IMAGES[i % IMAGES.length],
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
    // app's motion layer already holds. Left on, this keeps a compositor
    // layer alive for the life of the page — which on a full-viewport
    // version of this element is precisely the cost the original slider was
    // removed for, and is not worth paying at panel size either.
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
                    src={slide.image}
                    // **Decorative, so empty.** The panel sits beside the
                    // headline inside a subtree that is `aria-hidden` in
                    // its entirety — the headline already carries the
                    // meaning, and a screen reader announcing eight
                    // photographs of nothing in particular is noise. The
                    // page-section slots are the opposite case and describe
                    // themselves.
                    alt=""
                    // `fill`, not a ratio: the panel owns the aspect ratio,
                    // and a second one here would fight `inset-0`.
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
 * `aria-hidden` in its entirety: the `h1` beside it already carries the
 * meaning, and a screen reader announcing eight photographs of nothing in
 * particular is noise. The dots are the exception — they are controls, so
 * they sit outside the hidden subtree and name the slide they go to.
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
        // it parked at `opacity: 0` — a transparent layer still composites,
        // which is the cost this whole component is budgeted against.
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

    // **The listeners bind to the parent, which is now the panel.** They used
    // to reach the whole hero section, and had to: the slider was the
    // full-bleed ground behind the content column, so a pointer over the
    // headline was never over this element and handlers on it would have
    // paused only for the few pixels of background either side of the type.
    //
    // The parent is the framed panel now, so the same line of code means
    // something better — hovering the picture pauses it, and hovering the
    // words does not stop a picture the reader is not looking at.
    //
    // `focusin`/`focusout` rather than `focus`/`blur`: the latter do not
    // bubble, so tabbing to the dots inside the panel would not reach this.
    const rootRef = useRef(null);
    useEffect(() => {
        const panel = rootRef.current?.parentElement;
        if (!panel) return undefined;
        const hold = () => setPaused(true);
        const release = () => setPaused(false);
        panel.addEventListener("pointerenter", hold);
        panel.addEventListener("pointerleave", release);
        panel.addEventListener("focusin", hold);
        panel.addEventListener("focusout", release);
        return () => {
            panel.removeEventListener("pointerenter", hold);
            panel.removeEventListener("pointerleave", release);
            panel.removeEventListener("focusin", hold);
            panel.removeEventListener("focusout", release);
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

            {/* **The two scrims are gone, and their absence is the point.**
                They were a heavy left-to-right wash plus a bottom gradient,
                and they existed for one job: keeping poster type legible over
                the picture. The type has its own column now and nothing
                readable sits over this at all, so a scrim would only mute an
                illustration for no one's benefit.

                What is left is a soft bottom vignette, purely so the dots
                have something to sit on. It is its own layer rather than a
                property of the slide, the rule that has not changed: the
                slide already sets `background-image`, and one of the two
                would silently win. */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-t from-background/55 via-transparent to-transparent"
            />

            {/* Controls, so outside the hidden subtree. **Inside the panel**,
                which is the whole change: they used to be aligned to the page
                column with `mx-auto max-w-7xl px-6`, back when the slider was
                the full-bleed ground and the type sat on it. The picture is a
                panel now and the page column has nothing to do with where it
                is. */}
            {!reduced && (
                <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 px-4 pb-4">
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
            )}
        </div>
    );
}
