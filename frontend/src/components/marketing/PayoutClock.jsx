// When a creator is actually paid.
//
// The survey that drove the payout window found the thing this draws: late
// payment is what creators name most often, and the striking half is that
// creators who *were* paid inside a week still named it — because nothing ever
// said when payment was coming, and an unstated wait is assumed to be a long
// one. A sentence saying "paid within seven days" answers that. A timeline
// showing seven against ninety answers it in the one glance somebody gives a
// page they have not decided to read yet.
//
// **Our number is real and is read from the one place that holds it.**
// `CREATOR_PAYOUT_DAYS` mirrors `server.py`'s platform default, under a drift
// test, so this page and the promise printed on every brief cannot disagree.
// It is deliberately not fetched: these pages render before there is anything
// to fetch, which is the same reason `platformTerms.js` and `execution.js`
// are mirrored rather than requested.
//
// **The track is SVG and everything else is HTML, for two reasons that point
// the same way.** `role="img"` makes a subtree presentational, so a chart
// drawn entirely in SVG reaches a screen reader as its label and nothing else
// — the numbers have to be real text to be heard, resized or reflowed. And a
// `preserveAspectRatio="none"` viewBox stretches whatever is inside it, which
// is harmless for the two rectangles of the track and would turn a round
// marker into an ellipse at desktop width. So the rectangles are SVG and the
// markers are HTML dots placed by percentage.
import React, { useRef } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";

import Reveal from "@/components/marketing/Reveal";
import { DUR, EASE, VIEWPORT } from "@/components/marketing/motion";
import { CREATOR_PAYOUT_DAYS } from "@/lib/payoutWindow";
import { MARKETING as IDS } from "@/constants/testIds";

// ---------------------------------------------------------------------------
// NEEDS A SOURCE
// ---------------------------------------------------------------------------
// `theirDays` is a claim about *other* operators' payment terms. Nothing in
// this codebase backs it — unlike `CREATOR_PAYOUT_DAYS`, which is a stored
// platform setting an admin can read and change, printed on every brief and
// frozen into the terms a creator accepts.
//
// It renders because the operation asserts it, and it is a prop so sourcing it
// is one edit at the call site. **Until it is sourced the marker carries
// `data-unsourced`**, so the claim is greppable in the built page rather than
// living only in somebody's memory. These pages are held to "every claim is
// checkable"; this one is not yet.
export const UNSOURCED = ["theirDays"];

/** The axis. Fixed rather than derived from the markers, so the gap is read
 *  against a scale that does not move when a figure is corrected. */
const SCALE_DAYS = 90;

// One block, because these are words on `/for-creators` and the page's budget
// counts words a reader meets wherever they are declared — the argument
// `test_marketing_pages.py` already makes for `CampaignFilm`'s captions. The
// `aria-label` is deliberately absent: it stands in for the picture rather
// than adding to the page, and charging the budget for it would make
// describing a chart properly cost copy.
export const COPY = {
    scaleStart: "Day 0",
    scaleEnd: "Day",
    ours: "After your delivery is approved",
    theirs: "Terms commonly quoted elsewhere",
    gap: "The wait you are not doing",
    unit: "days",
};

const pct = (days) => Math.min(100, (days / SCALE_DAYS) * 100);

export function PayoutClock({
    ourDays = CREATOR_PAYOUT_DAYS,
    theirDays = 90,
    className = "",
}) {
    const reduced = useReducedMotion();
    // One observer for the track, for the reason `FeeFlow` records: a child
    // `motion` element's own `whileInView` is unreliable inside a variant
    // tree, and an explicit ref is deterministic.
    const ref = useRef(null);
    const inView = useInView(ref, VIEWPORT);
    const gap = Math.max(0, theirDays - ourDays);
    const ourAt = pct(ourDays);
    const theirAt = pct(theirDays);

    // The track draws, then the span fills, then the markers land. One beat
    // apart, inside the site's 200–400ms band, and nothing repeats.
    const step = 0.12;
    const draw = (delay, to = 1) => ({
        initial: false,
        animate: { scaleX: reduced || inView ? to : 0 },
        transition: reduced
            ? { duration: 0 }
            : { duration: DUR.slow, ease: EASE, delay },
    });

    return (
        <div data-testid={IDS.payoutClock} className={className}>
            {/* The scale, above the track, so the numbers under each marker
                are the markers' own and cannot be misread as the axis. */}
            <div className="flex justify-between text-xs uppercase tracking-[0.18em] text-muted-foreground">
                <span>{COPY.scaleStart}</span>
                <span>{COPY.scaleEnd} {SCALE_DAYS}</span>
            </div>

            <div ref={ref} className="relative mt-3 h-2">
                <svg
                    viewBox="0 0 1000 8"
                    preserveAspectRatio="none"
                    role="img"
                    aria-label={`A creator is paid within ${ourDays} days of approved delivery here, against terms of around ${theirDays} days elsewhere — a gap of ${gap} days.`}
                    className="absolute inset-0 h-2 w-full overflow-hidden rounded-full"
                >
                    <motion.rect
                        width="1000"
                        height="8"
                        fill="hsl(var(--graphic-track))"
                        style={{ originX: 0, transformBox: "fill-box" }}
                        {...draw(0)}
                    />
                    {/* The wait a creator does not have. Drawn from our marker
                        to theirs, which is what makes the span mean something
                        rather than being decoration between two dots. */}
                    <motion.rect
                        x={ourAt * 10}
                        width={(theirAt - ourAt) * 10}
                        height="8"
                        fill="hsl(var(--graphic-quiet))"
                        style={{ originX: 0, transformBox: "fill-box" }}
                        {...draw(step)}
                    />
                </svg>

                {/* HTML, not SVG: a circle in a `preserveAspectRatio="none"`
                    viewBox is an ellipse at any width but one. */}
                <Reveal
                    i={2}
                    noTravel
                    data-testid={IDS.payoutClockOurs}
                    className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-primary"
                    style={{ left: `${ourAt}%` }}
                />
                <Reveal
                    i={3}
                    noTravel
                    data-testid={IDS.payoutClockTheirs}
                    data-unsourced="theirDays"
                    className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-muted-foreground"
                    style={{ left: `${theirAt}%` }}
                />
            </div>

            {/* **Every figure is real text and never only a position on a
                bar.** Read aloud, in greyscale, or with the SVG blocked, the
                three numbers and what they mean all survive. */}
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
                <Reveal i={4}>
                    <p className="font-serif text-fluid-2xl text-primary">
                        {ourDays} {COPY.unit}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                        {COPY.ours}
                    </p>
                </Reveal>
                <Reveal i={5} data-unsourced="theirDays">
                    <p className="font-serif text-fluid-2xl text-foreground">
                        {theirDays} {COPY.unit}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                        {COPY.theirs}
                    </p>
                </Reveal>
                <Reveal i={6} data-testid={IDS.payoutClockGap}>
                    <p className="font-serif text-fluid-2xl text-foreground">
                        {gap} {COPY.unit}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                        {COPY.gap}
                    </p>
                </Reveal>
            </div>
        </div>
    );
}

export default PayoutClock;
