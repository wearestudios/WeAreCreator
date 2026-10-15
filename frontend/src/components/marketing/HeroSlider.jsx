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
import React, { useEffect, useRef } from "react";

import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import { EASE } from "@/components/marketing/motion";
import { PHRASES } from "@/components/marketing/KineticHeadline";
import {
    HOLD_MS,
    WIPE_MS,
    useSectorCycle,
} from "@/components/marketing/sectorCycle";
import { LANDING_HERO as IDS } from "@/constants/testIds";

// `HOLD_MS` and `WIPE_MS` are imported, not declared. They used to live here
// as 7000 alongside a 4000 in `KineticHeadline`, which is the whole defect
// `sectorCycle` exists to remove: one clock, read by both.

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

/** How many upcoming frames the rail shows. */
const RAIL_LENGTH = 3;

/** One thumbnail plus its gap, in rem — how far the track travels. */
const RAIL_STEP_REM = 5.25 + 0.75;

/** `01`, `08` — the index is read, so it is zero-padded. */
const pad = (n) => String(n).padStart(2, "0");

/**
 * One slide: the wipe's window, the wipe's held picture, the drift, the image.
 *
 * **Four nested elements, and each one owns exactly one transform.** The two
 * wipe halves cancel so the photograph holds still while the window opens
 * over it; the drift pans; the image is the picture. Collapsing any two onto
 * one node would make them share a timeline — the incoming slide would begin
 * its pan already half-revealed — and all four are transforms, so the
 * compositor owns the lot and nothing touches layout.
 */
function Slide({ slide, index, incoming, paused, reduced, eager }) {
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

    // Only the arriving slide animates. The one underneath is already in
    // place and is simply uncovered.
    const wipe = (name) =>
        reduced || !incoming
            ? undefined
            : {
                  animationName: name,
                  animationDuration: `${WIPE_MS}ms`,
                  animationTimingFunction: EASE_CSS,
                  animationFillMode: "both",
                  willChange: "transform",
              };

    return (
        <div
            data-testid={IDS.slide(index)}
            className="absolute inset-0 overflow-hidden"
            style={wipe("heroWipeWindow")}
        >
            <div className="absolute inset-0" style={wipe("heroWipeHold")}>
                <div ref={driftRef} className="absolute inset-0" style={drift}>
                    <PlaceholderImage
                        testid={IDS.slideImage(index)}
                        note={slide.note}
                        src={slide.image}
                        // **Decorative, so empty.** This is a background
                        // behind the `h1` and under a scrim, inside a subtree
                        // that is `aria-hidden` in its entirety — the headline
                        // already carries the meaning, and a screen reader
                        // announcing eight photographs of nothing in
                        // particular is noise. The page-section slots are the
                        // opposite case and describe themselves.
                        alt=""
                        // `fill`, not a ratio: the hero's height is set by its
                        // content, and an aspect class would fight `inset-0`.
                        fill
                        eager={eager}
                    />
                </div>
            </div>
        </div>
    );
}

/**
 * The rail: the next three frames, sliding left by one on each advance.
 *
 * **This replaced a row of dots, and it is the thing worth taking from the
 * reference.** Dots say how many there are and which one you are on; a rail
 * of upcoming frames says what is coming, which is the only reason to wait.
 * It moves by `transform` rather than by reordering, so an advance is one
 * composited slide rather than three elements changing their contents.
 *
 * Each frame is a real `<button>` and sits outside the `aria-hidden` subtree,
 * exactly as the dots did — these are controls, and a picture of where a
 * control goes is not a substitute for naming it.
 */
function FrameRail({ slides, index, goTo }) {
    const upcoming = Array.from(
        { length: RAIL_LENGTH },
        (_, n) => (index + n + 1) % slides.length,
    );

    return (
        <div
            data-testid={IDS.rail}
            className="pointer-events-auto hidden items-end overflow-hidden md:flex"
        >
            {/* **The track travels; the slots do not.** Keying three buttons
                by phrase made React move the DOM nodes on every advance,
                which the browser records as a layout shift — measured at
                0.0007 per advance, every six seconds, unbounded. The slots
                are keyed by position so their nodes are stable, and the
                movement is one `translateX` on the track, restarted by the
                index. */}
            <div
                key={index}
                data-testid={IDS.railTrack}
                className="flex items-end gap-3"
                style={{
                    "--rail-step": `${RAIL_STEP_REM}rem`,
                    animationName: "heroRailSlide",
                    animationDuration: `${WIPE_MS}ms`,
                    animationTimingFunction: EASE_CSS,
                    animationFillMode: "both",
                }}
            >
                {upcoming.map((i, n) => (
                    <button
                        key={n}
                        type="button"
                        data-testid={IDS.railFrame(i)}
                        aria-label={`Show ${slides[i].phrase}`}
                        aria-current={i === index ? "true" : undefined}
                        onClick={() => goTo(i)}
                        style={{ opacity: 1 - n * 0.22 }}
                        className="relative h-14 w-[5.25rem] shrink-0 overflow-hidden rounded border border-border/60 transition-colors duration-200 hover:border-primary/60"
                    >
                        <PlaceholderImage
                            note={slides[i].note}
                            src={slides[i].image}
                            alt=""
                            fill
                        />
                    </button>
                ))}
            </div>
        </div>
    );
}

/**
 * The slider.
 *
 * `aria-hidden` in its entirety: the `h1` above already carries the meaning,
 * and a screen reader announcing eight photographs of nothing in particular is
 * noise. The controls are the exception — they sit outside the hidden subtree
 * and name the slide they go to.
 */
export default function HeroSlider({ className = "" }) {
    // **One clock, and it is not this component's.** `HeroSlider` held a
    // 7000ms `setTimeout` while `KineticHeadline` held a 4000ms
    // `setInterval`; they drifted apart by the second slide and never
    // recovered, so the word named one sector while the picture showed
    // another. `sectorCycle` owns the index and both read it.
    const { index: active, leaving, paused, reduced, goTo } = useSectorCycle();

    // **The incoming slide paints last, which reverses the order this file
    // used to document — and the order follows from the transition.** With a
    // crossfade the outgoing slide has to be on top: it dissolves to reveal
    // the one underneath, and painting the incoming above would cover the old
    // one at full opacity on the frame it mounts, a hard cut with a fade
    // running invisibly beneath it. A wipe is the opposite. The incoming
    // slide is the thing that moves, so it opens *over* the outgoing one,
    // which stays still and is simply uncovered. Still two layers, never
    // more: an invisible compositing layer still composites, and that budget
    // is what got this component rebuilt rather than restored.
    const painted = reduced
        ? [0]
        : [leaving, active].filter((i) => i !== null && i !== undefined);

    return (
        <div
            className={`absolute inset-0 overflow-hidden ${className}`}
        >
            <div data-testid={IDS.slides} aria-hidden className="absolute inset-0">
                {painted.map((i) => (
                    <Slide
                        key={i}
                        slide={SLIDES[i]}
                        index={i}
                        incoming={i === active && leaving !== null}
                        paused={paused}
                        reduced={reduced}
                        // Only the first slide is worth the early fetch; the
                        // rest arrive six seconds apart.
                        eager={i === 0}
                    />
                ))}
            </div>

            {/* **The scrim has to actually cover the type column**, which is
                what makes a full-bleed hero safe. The old one ran
                `from-background via-background/85 to-background/40` across
                the whole width — it had released most of its cover by the
                middle of the type and still dimmed the far edge of a picture
                nothing was written over. This holds near-solid to 42%, which
                is past the type column's right edge, and then goes to
                transparent so the half the photograph was composed for is
                the photograph.

                Its own layer, not a property of the slide: the slide already
                sets `background-image` and one of the two would silently win
                — the rule `.grain-surface` exists for — and on the slide it
                would wipe in and out with the picture, so the headline's
                legibility would pulse every six seconds. */}
            {/* **Two scrims, because the layout is two layouts.** At `lg`
                and up the type is in six of twelve and the picture owns the
                right half, so the cover is horizontal: near-solid past the
                column's edge at 55%, then released so the half the
                photograph was composed for is the photograph.

                Below `lg` the grid collapses to one column and the type
                spans the full width, so a horizontal scrim covers the left
                of a headline and abandons its right — measured at 390 with
                the 42% version: headline 1.48:1, subheading 1.03:1. There
                the cover has to be the whole frame, and the picture is
                atmosphere rather than subject. That is the honest trade on a
                390px screen; the alternative is a headline nobody can read
                over a photograph nobody can see past it. */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background via-background/92 to-background/80 lg:hidden"
            />
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 hidden bg-gradient-to-r from-background from-35% via-background/90 via-[58%] to-transparent lg:block"
            />
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent"
            />

            {/* Controls, so outside the hidden subtree, and aligned to the
                content column so they sit under the type at every width. */}
            <div className="pointer-events-none absolute inset-x-0 bottom-6 z-10">
                <div className="mx-auto flex max-w-7xl items-end justify-between gap-6 px-6">
                    {/* The left end carries nothing at `md` and up: the
                        controls belong with the picture, and the picture is
                        the right-hand half. */}
                    {/* **Below `md` the rail and the index are gone and the
                        dots come back.** Three thumbnails and a counter on a
                        390px screen is clutter laid over the one place the
                        headline has to be read, and the rail's own argument —
                        showing what is coming — is worth less than the space
                        it costs there. */}
                    {!reduced && (
                        <div
                            data-testid={IDS.dots}
                            className="pointer-events-auto inline-flex items-center gap-2 md:hidden"
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
                    )}

                    {/* The index, its progress bar and the rail, together
                        and right-aligned — the controls sit with the picture
                        they control, not under the type column.

                        **The bar is the visible proof that the picture and
                        the word are on one clock**: it fills over exactly the
                        hold both of them wait out, and pauses with the
                        slider. Keyed on the active index so it restarts per
                        slide; `scaleX` on a 2px rule, so it composites. */}
                    <div className="ml-auto hidden items-end gap-5 md:flex">
                    <div className="flex flex-col items-start gap-2">
                        <p
                            data-testid={IDS.index}
                            className="text-xs uppercase tracking-[0.2em] text-muted-foreground"
                        >
                            {pad(active + 1)} / {pad(SLIDES.length)}
                        </p>
                        <div
                            aria-hidden
                            className="h-0.5 w-24 overflow-hidden rounded-full bg-foreground/15"
                        >
                            <div
                                key={active}
                                data-testid={IDS.progress}
                                className="h-full w-full origin-left bg-primary"
                                style={
                                    reduced
                                        ? { transform: "scaleX(1)" }
                                        : {
                                              animationName: "heroProgress",
                                              animationDuration: `${HOLD_MS}ms`,
                                              animationTimingFunction: "linear",
                                              animationFillMode: "both",
                                              animationPlayState: paused
                                                  ? "paused"
                                                  : "running",
                                          }
                                }
                            />
                        </div>
                    </div>

                    {!reduced && (
                        <FrameRail slides={SLIDES} index={active} goTo={goTo} />
                    )}
                    </div>
                </div>
            </div>
        </div>
    );
}
