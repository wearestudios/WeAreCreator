// The centrepiece: a campaign playing itself out as you scroll.
//
// Seven beats — a brief is posted, three creators apply, one is accepted, the
// confirmation reaches them on WhatsApp, a slot is booked, the draft is
// approved, the payout lands. It is the product demonstrating itself instead
// of a page describing it, which is the one thing a paragraph cannot do.
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
// On a phone, and under `prefers-reduced-motion`, the same seven beats render
// as a numbered stepped sequence — every UI piece drawn, every caption
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
import { Eyebrow } from "@/components/marketing/Sections";
import {
    ApplicantRow,
    ApprovalCard,
    BriefCard,
    MessageBubble,
    PayoutCard,
    SlotStrip,
} from "@/components/marketing/filmUI";
import { MARKETING as IDS } from "@/constants/testIds";

// The applicants. Three, because three is a shortlist and four is a list.
const APPLICANTS = [
    { name: "Ananya", followers: "24K", rate: "₹12,000" },
    { name: "Rohit", followers: "11K", rate: "₹9,500" },
    { name: "Meera", followers: "38K", rate: "₹14,000" },
];

const PAYOUT = 12000;

/**
 * The seven beats.
 *
 * `caption` is the only body copy the film adds to the page — a label each,
 * no supporting line. The UI piece beside it is the explanation, which is the
 * entire argument for building this rather than writing seven more sentences.
 */
export const BEATS = [
    { key: "brief", caption: "A brief goes up" },
    { key: "applied", caption: "Creators apply" },
    { key: "accepted", caption: "One is accepted" },
    { key: "message", caption: "They hear on WhatsApp" },
    { key: "slot", caption: "A slot is booked" },
    { key: "approved", caption: "The draft is approved" },
    { key: "paid", caption: "The creator is paid" },
];

/** Where each beat sits in the scroll, as a fraction of the section. */
function rangeFor(i) {
    const span = 1 / BEATS.length;
    const start = i * span;
    // Enter over the first 40% of the beat's range, then hold. The hold is
    // what makes it readable — a beat that is still arriving when the next one
    // starts is a blur.
    return [start, start + span * 0.4];
}

/** True once the viewport is wide enough for the film to be worth playing. */
function useWideEnough() {
    const [wide, setWide] = useState(false);
    useEffect(() => {
        const q = window.matchMedia("(min-width: 768px)");
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
    const opacity = useTransform(progress, [from, to], [0, 1]);
    const y = useTransform(progress, [from, to], [18, 0]);
    return (
        <motion.div style={{ opacity, y }} className={`absolute ${className}`}>
            {children}
        </motion.div>
    );
}

/** The caption for the beat currently playing. All seven are rendered and
 *  cross-faded, so this reverses as cleanly as everything else. */
function Caption({ index, progress }) {
    const [from, to] = rangeFor(index);
    const nextStart = (index + 1) / BEATS.length;
    const opacity = useTransform(
        progress,
        // Fade in with the beat, out as the next one starts. The last beat
        // holds to the end rather than fading into nothing.
        index === BEATS.length - 1
            ? [from, to, 1]
            : [from, to, nextStart, nextStart + 0.02],
        index === BEATS.length - 1 ? [0, 1, 1] : [0, 1, 1, 0],
    );
    return (
        <motion.p
            style={{ opacity }}
            className="absolute inset-x-0 font-serif text-fluid-3xl leading-tight tracking-tight"
        >
            {/* A real space, not just a margin. Without it the text layer —
                which is what a screen reader announces and what a copy-paste
                picks up — reads "01A brief goes up". */}
            <span className="mr-3 align-middle text-sm text-ember-500">
                {String(index + 1).padStart(2, "0")}
            </span>{" "}
            {BEATS[index].caption}
        </motion.p>
    );
}

/**
 * The pinned film. Only mounted when the viewport is wide and motion is
 * welcome — `CampaignFilm` decides, so this component never has to.
 */
function PinnedFilm() {
    const ref = useRef(null);
    const amountRef = useRef(null);
    const { scrollYProgress } = useScroll({
        target: ref,
        offset: ["start start", "end end"],
    });

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
        <div ref={ref} data-testid={IDS.filmTrack} className="relative h-[520vh]">
            {/* The pin. `sticky` and nothing else — the page scrolls normally
                and the reader can leave at any point. */}
            <div className="sticky top-16 flex h-[calc(100vh-4rem)] items-center overflow-hidden">
                <div className="mx-auto grid w-full max-w-7xl gap-10 px-6 lg:grid-cols-12 lg:items-center">
                    {/* The captions, stacked and cross-faded in place. A fixed
                        box, so nothing below the film moves while it plays. */}
                    <div className="relative h-28 lg:col-span-5">
                        {BEATS.map((b, i) => (
                            <Caption key={b.key} index={i} progress={scrollYProgress} />
                        ))}
                    </div>

                    {/* The stage. Everything inside is absolutely positioned so
                        beats compose rather than reflow. */}
                    <div
                        data-testid={IDS.filmStage}
                        aria-hidden
                        className="relative mx-auto h-[26rem] w-full max-w-md lg:col-span-7"
                    >
                        <Beat index={0} progress={scrollYProgress} className="inset-x-0 top-0">
                            <BriefCard />
                        </Beat>

                        {APPLICANTS.map((a, i) => (
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
                                <ApplicantRow {...APPLICANTS[0]} accepted />
                            </div>
                        </Beat>

                        <Beat index={3} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(330px)" }}>
                                <MessageBubble />
                            </div>
                        </Beat>

                        <Beat index={4} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(330px)" }}>
                                <SlotStrip booked={3} />
                            </div>
                        </Beat>

                        <Beat index={5} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(330px)" }}>
                                <ApprovalCard />
                            </div>
                        </Beat>

                        <Beat index={6} progress={scrollYProgress} className="inset-x-0">
                            <div style={{ transform: "translateY(320px)" }}>
                                <PayoutCard amountRef={amountRef} />
                            </div>
                        </Beat>
                    </div>
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
function SteppedFilm() {
    const amountRef = useRef(null);
    // The figure is simply its final value here — there is nothing to count
    // against, and a number that animates on a timer is the scroll-driven
    // version wearing a disguise.
    const pieces = useMemo(
        () => [
            <BriefCard key="brief" />,
            <div key="applied" className="space-y-2">
                {APPLICANTS.map((a) => (
                    <ApplicantRow key={a.name} {...a} />
                ))}
            </div>,
            <ApplicantRow key="accepted" {...APPLICANTS[0]} accepted />,
            <MessageBubble key="message" />,
            <SlotStrip key="slot" booked={3} />,
            <ApprovalCard key="approved" />,
            <PayoutCard key="paid" amountRef={amountRef} />,
        ],
        [],
    );

    return (
        <ol data-testid={IDS.filmSteps} className="mt-10 space-y-8">
            {BEATS.map((b, i) => (
                <Reveal key={b.key} as="li" i={i % 3} className="flex gap-4">
                    <span className="mt-1 shrink-0 font-serif text-sm text-ember-500">
                        {String(i + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0 flex-1">
                        <p className="font-serif text-fluid-xl leading-tight tracking-tight">
                            {b.caption}
                        </p>
                        <div className="mt-3 max-w-sm" aria-hidden>
                            {pieces[i]}
                        </div>
                    </div>
                </Reveal>
            ))}
        </ol>
    );
}

export function CampaignFilm({ eyebrow = "One campaign", title }) {
    const reduced = useReducedMotion();
    const wide = useWideEnough();
    // `wide` starts false, so the first paint on every device is the stepped
    // version. That is the right way round: the fallback appearing briefly on
    // a desktop costs nothing, while a pinned section flashing on a phone
    // before it is torn down is five screens of scroll appearing and vanishing.
    const play = wide && !reduced;

    return (
        <section
            data-testid={IDS.film}
            data-mode={play ? "pinned" : "stepped"}
            className="border-b border-white/10"
        >
            <div className="mx-auto max-w-7xl px-6 pt-16 md:pt-20">
                <Reveal>
                    <Eyebrow>{eyebrow}</Eyebrow>
                </Reveal>
                <Reveal i={1}>
                    <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        {title}
                    </h2>
                </Reveal>
            </div>

            {play ? <PinnedFilm /> : (
                <div className="mx-auto max-w-7xl px-6 pb-16 md:pb-20">
                    <SteppedFilm />
                </div>
            )}
        </section>
    );
}

export default CampaignFilm;
