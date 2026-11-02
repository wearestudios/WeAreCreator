// A campaign playing itself out as you scroll, beside the homepage's four
// steps.
//
// Seven beats under the four steps' own names — a brief goes up and verified
// creators apply (Offer), one is taken on and the fee is agreed in writing
// (Agree), a slot is booked and the brand approves the work (Deliver), and
// the creator is paid all of it within 7 days (Get paid). It is the product
// demonstrating itself instead of a page describing it, which is the one
// thing a paragraph cannot do.
//
// **Restored from the pre-revamp homepage (8263b6f), where it was a section of
// its own with a 520vh track.** It now sits in "How it works", in the column
// beside the illustrated steps, and the steps *are* its track: the stage is
// sticky in its column and plays against the steps' own scroll, so reading
// down the four steps plays the campaign beside them. Every word and figure
// comes from `HOME.film` in `content/marketing.js`, so the film and the steps
// tell one campaign rather than two.
//
// ---------------------------------------------------------------------------
// HOW THE SCROLL WORKS
//
// A tall outer section with a `sticky` inner stage. That is the whole
// mechanism: **the pin is `position: sticky` and nothing else.** No wheel
// listener, no `scrollTo`, no preventDefault — the page scrolls at exactly the
// rate the user's finger or wheel says it should, and they can keep going past
// the section at any point. Scroll hijack is the thing this pattern is usually
// guilty of and it is the thing most likely to make somebody close the tab.
//
// **Every beat is derived from `scrollYProgress`, never from state.** That is
// what makes it reverse cleanly: scrolling up is the same function evaluated
// at smaller numbers, so the film unwinds exactly rather than replaying
// forwards or sticking at the last beat somebody triggered. A `useState`
// beat-tracker with an effect would look identical going down and be wrong
// going up, and that failure is invisible until somebody scrolls back.
//
// ---------------------------------------------------------------------------
// THE FALLBACK IS NOT A DEGRADED MODE
//
// Below the two-column width, and under `prefers-reduced-motion`, the same
// seven beats render as a numbered stepped sequence — every UI piece drawn, every caption
// present, nothing pinned and nothing scroll-driven. It tells the identical
// story; it just tells it as a list rather than as a film.
//
// This is deliberate rather than a fallback bolted on. A pinned section eats
// five screens of scroll and, on a mid-range Android, a scroll-driven
// composite per frame is exactly the work that makes a phone feel cheap. The
// story survives the format change. The animation would not survive the phone.
//
// ---------------------------------------------------------------------------
// PERFORMANCE
//
//   - **Transforms and opacity only.** Every beat is `opacity` plus `y`,
//     driven by `useTransform` off one scroll progress value. Nothing animates
//     a layout property, so there is no reflow at any point in the film.
//   - **The counting figure never re-renders React.** It subscribes to a
//     motion value and writes `textContent` on a ref. A `setState` per frame
//     would re-render the whole stage sixty times a second to change four
//     characters.
//   - **The stage is a fixed box.** Beats fade in on top of each other inside
//     it rather than being appended, so the section's height never changes
//     while it plays — which is what stops the pin from juddering.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, useMotionValueEvent, useReducedMotion, useScroll, useTransform } from "framer-motion";

import Reveal from "@/components/marketing/Reveal";
import {
    ApplicantRow,
    ApprovalCard,
    BriefCard,
    MessageBubble,
    PayoutCard,
    SlotStrip,
} from "@/components/marketing/filmUI";
import { MARKETING as IDS } from "@/constants/testIds";

/**
 * The seven beats are `film.beats` in the content module. `caption` is the
 * only body copy the film adds to the page — a label each, no supporting
 * line. The UI piece beside it is the explanation, which is the entire
 * argument for building this rather than writing seven more sentences.
 */
const BEAT_COUNT = 7;

/** Where each beat sits in the scroll, as a fraction of the track. */
function rangeFor(i) {
    const span = 1 / BEAT_COUNT;
    const start = i * span;
    // Enter over the first 40% of the beat's range, then hold. The hold is
    // what makes it readable — a beat that is still arriving when the next one
    // starts is a blur.
    return [start, start + span * 0.4];
}

/** True once the viewport is wide enough for the film to be worth playing —
 *  `lg`, where the steps and the stage sit side by side. Below that the stage
 *  would be under the steps rather than beside them, with nothing to pin
 *  against. */
function useWideEnough() {
    const [wide, setWide] = useState(false);
    useEffect(() => {
        const q = window.matchMedia("(min-width: 1024px)");
        const sync = () => setWide(q.matches);
        sync();
        q.addEventListener("change", sync);
        return () => q.removeEventListener("change", sync);
    }, []);
    return wide;
}

/**
 * One beat's element on the pinned stage.
 *
 * Elements persist once they have arrived: the campaign accumulates rather
 * than each beat replacing the last, which is what makes it read as one story
 * instead of seven slides.
 */
function Beat({ index, progress, className = "", children }) {
    const [from, to] = rangeFor(index);
    // The first beat is on the stage before the track starts, so the column
    // is never an empty box beside the first step.
    const opacity = useTransform(progress, index === 0 ? [0, 0.001] : [from, to], index === 0 ? [1, 1] : [0, 1]);
    const y = useTransform(progress, index === 0 ? [0, 0.001] : [from, to], index === 0 ? [0, 0] : [18, 0]);
    return (
        <motion.div style={{ opacity, y }} className={`absolute ${className}`}>
            {children}
        </motion.div>
    );
}

/** The caption for the beat currently playing. All seven are rendered and
 *  cross-faded, so this reverses as cleanly as everything else. */
function Caption({ index, beat, stepTitle, progress }) {
    const [from] = rangeFor(index);
    const nextStart = (index + 1) / BEAT_COUNT;
    const last = index === BEAT_COUNT - 1;
    // The caption swaps over the same short stretch its predecessor leaves
    // in, rather than over the beat's whole entrance: fading in across the
    // entrance left a moment between one caption leaving and the next
    // arriving where the stage had none — measured at 1920 with the first
    // step centred on screen.
    const swap = 0.02;
    const opacity = useTransform(
        progress,
        // The first beat is there from the start and the last holds to the
        // end, so the stage is never captionless at either edge of the track.
        last ? [from, from + swap, 1] : index === 0 ? [0, nextStart, nextStart + swap] : [from, from + swap, nextStart, nextStart + swap],
        last ? [0, 1, 1] : index === 0 ? [1, 1, 0] : [0, 1, 1, 0],
    );
    return (
        <motion.p style={{ opacity }} className="mkt-h3 absolute inset-x-0 text-heading">
            {/* The step it belongs to, then the beat. A real space between
                them, not just a margin — without it the text layer, which a
                screen reader announces, reads "AgreeOne is taken on". */}
            <span className="mr-2 align-middle text-meta text-muted-foreground">{stepTitle}</span>{" "}
            {beat.caption}
        </motion.p>
    );
}

/**
 * The pinned film. Only mounted when the viewport is wide and motion is
 * welcome — `CampaignFilm` decides, so this component never has to.
 *
 * `trackRef` is the list of steps beside it: the film starts as the first
 * step reaches the middle of the screen and finishes as the last one leaves
 * it, so each beat plays while its own step is the one being read.
 */
function PinnedFilm({ film, steps, trackRef }) {
    const amountRef = useRef(null);
    const { scrollYProgress } = useScroll({
        target: trackRef,
        offset: ["start 0.55", "end 0.6"],
    });
    const { screen, beats } = film;
    const applicants = screen.applicants;
    const PAYOUT = screen.payout.amount;

    // The payout counts with scroll rather than on a timer, so it runs
    // backwards when you scroll back up. Written straight to the DOM node:
    // sixty React renders a second to change four characters is the kind of
    // thing that makes a phone warm.
    const [payFrom, payTo] = rangeFor(6);
    const amount = useTransform(scrollYProgress, [payFrom, payTo], [0, PAYOUT]);
    useMotionValueEvent(amount, "change", (v) => {
        if (amountRef.current) {
            amountRef.current.textContent = Math.round(v).toLocaleString("en-IN");
        }
    });

    return (
        // The pin. `sticky` and nothing else — the page scrolls normally and
        // the reader can leave at any point. It sticks inside the column the
        // steps sit beside, which is as tall as the steps, so it lets go
        // when the last step does.
        <div data-testid={IDS.filmTrack} className="sticky top-24">
            <div className="rounded-lg border border-border bg-muted p-6">
                {/* The captions, stacked and cross-faded in place. A fixed box,
                    so nothing below the film moves while it plays. */}
                <div className="relative h-16">
                    {beats.map((b, i) => (
                        <Caption
                            key={b.key}
                            index={i}
                            beat={b}
                            stepTitle={steps[b.step]}
                            progress={scrollYProgress}
                        />
                    ))}
                </div>

                {/* The stage. Everything inside is absolutely positioned so
                    beats compose rather than reflow. */}
                <div
                    data-testid={IDS.filmStage}
                    aria-hidden
                    className="relative mx-auto mt-4 h-[26rem] w-full max-w-md"
                >
                        <Beat index={0} progress={scrollYProgress} className="inset-x-0 top-0">
                            <BriefCard brief={screen.brief} />
                        </Beat>

                        {applicants.map((a, i) => (
                            <Beat
                                key={a.name}
                                index={1}
                                progress={scrollYProgress}
                                className="inset-x-0"
                                // Stacked beneath the brief. Static offsets, so
                                // the rows never move once placed.
                            >
                                <div style={{ transform: `translateY(${150 + i * 60}px)` }}>
                                    <ApplicantRow {...a} />
                                </div>
                            </Beat>
                        ))}

                        {/* Acceptance is the same row gaining a ring, drawn on
                            top of the plain one — the product's own behaviour,
                            not a new screen. */}
                        <Beat index={2} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(150px)" }}>
                                <ApplicantRow {...applicants[0]} accepted acceptedLabel={screen.accepted} />
                            </div>
                        </Beat>

                        <Beat index={3} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(330px)" }}>
                                <MessageBubble message={screen.message} />
                            </div>
                        </Beat>

                        <Beat index={4} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(330px)" }}>
                                <SlotStrip slot={screen.slot} />
                            </div>
                        </Beat>

                        <Beat index={5} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(330px)" }}>
                                <ApprovalCard approval={screen.approval} />
                            </div>
                        </Beat>

                        <Beat index={6} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(320px)" }}>
                                <PayoutCard payout={screen.payout} amountRef={amountRef} />
                            </div>
                        </Beat>
                </div>
            </div>
        </div>
    );
}

/**
 * The stepped sequence: the same seven beats, as a list.
 *
 * Every UI piece is drawn and every caption is present. The only thing missing
 * is the scroll choreography, which is the thing that does not survive a
 * mid-range phone.
 */
function SteppedFilm({ film, steps }) {
    const amountRef = useRef(null);
    const { screen, beats } = film;
    // The figure is simply its final value here — there is nothing to count
    // against, and a number that animates on a timer is the scroll-driven
    // version wearing a disguise.
    const pieces = useMemo(
        () => [
            <BriefCard key="brief" brief={screen.brief} />,
            <div key="applied" className="space-y-2">
                {screen.applicants.map((a) => (
                    <ApplicantRow key={a.name} {...a} />
                ))}
            </div>,
            <ApplicantRow key="accepted" {...screen.applicants[0]} accepted acceptedLabel={screen.accepted} />,
            <MessageBubble key="message" message={screen.message} />,
            <SlotStrip key="slot" slot={screen.slot} />,
            <ApprovalCard key="approved" approval={screen.approval} />,
            <PayoutCard key="paid" payout={screen.payout} amountRef={amountRef} />,
        ],
        [screen],
    );

    return (
        <ol data-testid={IDS.filmSteps} className="space-y-8">
            {beats.map((b, i) => (
                <Reveal key={b.key} as="li" i={i % 3} className="flex gap-4">
                    <span className="mt-1 w-16 shrink-0 text-meta text-muted-foreground">{steps[b.step]}</span>
                    <div className="min-w-0 flex-1">
                        <p className="mkt-h3 text-heading">{b.caption}</p>
                        <div className="mt-3 max-w-sm" aria-hidden>
                            {pieces[i]}
                        </div>
                    </div>
                </Reveal>
            ))}
        </ol>
    );
}

/**
 * @param {{ film: object, steps: Record<string, string>,
 *           trackRef: React.RefObject<HTMLElement> }} props
 *   `film` is `HOME.film`; `steps` maps a step key to its title, so a beat is
 *   labelled with the step it belongs to; `trackRef` is the list of steps the
 *   stage plays beside.
 */
export function CampaignFilm({ film, steps, trackRef }) {
    const reduced = useReducedMotion();
    const wide = useWideEnough();
    // `wide` starts false, so the first paint on every device is the stepped
    // version. That is the right way round: the fallback appearing briefly on
    // a desktop costs nothing, while a pinned stage flashing on a phone
    // before it is torn down is a column appearing and vanishing.
    const play = wide && !reduced;

    // A `div`, not a `section`: it is part of "How it works", and the
    // analytics read each outermost section as one, which it is not.
    return (
        <div data-testid={IDS.film} data-mode={play ? "pinned" : "stepped"} className="h-full">
            {play ? (
                <PinnedFilm film={film} steps={steps} trackRef={trackRef} />
            ) : (
                <SteppedFilm film={film} steps={steps} />
            )}
        </div>
    );
}

export default CampaignFilm;
