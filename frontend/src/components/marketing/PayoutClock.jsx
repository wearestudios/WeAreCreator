// When a creator is actually paid.
//
// The survey that drove the payout window found the thing this draws: late
// payment is what creators name most often, and the striking half is that
// creators who *were* paid inside a week still named it — because nothing ever
// said when payment was coming, and an unstated wait is assumed to be a long
// one. A sentence saying "paid within 7 days of approval" answers that. A
// track that runs from approval to paid, a day per tick, answers it in the
// one glance somebody gives a page they have not decided to read yet.
//
// **Our number is real and is read from the one place that holds it.**
// `CREATOR_PAYOUT_DAYS` mirrors `server.py`'s platform default, under a drift
// test, so this page and the promise printed on every brief cannot disagree.
// It is deliberately not fetched: these pages render before there is anything
// to fetch. Every word around it is `CREATORS.money.clock` in the content
// module.
//
// **Restored from the pre-revamp /for-creators (8263b6f) and narrowed to the
// half that is true.** It drew our 7 days against "around 90 days elsewhere",
// a figure nothing in this codebase backs — it carried `data-unsourced` for
// exactly that reason — and these pages now carry only claims the product
// keeps. So the scale is our own window: day 0 is the approval, the last day
// is the latest the money arrives, and there is no other operator on it.
//
// **The track is SVG and everything else is HTML.** `role="img"` makes a
// subtree presentational, so a chart drawn entirely in SVG reaches a screen
// reader as its label and nothing else; and a `preserveAspectRatio="none"`
// viewBox would turn a round marker into an ellipse. So the bar is SVG and the
// markers and figures are HTML.
import React, { useRef } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";

import Reveal from "@/components/marketing/Reveal";
import { DUR, EASE, VIEWPORT } from "@/components/marketing/motion";
import { CREATOR_PAYOUT_DAYS } from "@/lib/payoutWindow";
import { MARKETING as IDS } from "@/constants/testIds";

/**
 * @param {{ clock: object, ourDays?: number, className?: string }} props
 *   `clock` is `CREATORS.money.clock`.
 */
export function PayoutClock({ clock, ourDays = CREATOR_PAYOUT_DAYS, className = "" }) {
    const reduced = useReducedMotion();
    // One observer for the track, for the reason `FeeFlow` records: a child
    // `motion` element's own `whileInView` is unreliable inside a variant
    // tree, and an explicit ref is deterministic.
    const ref = useRef(null);
    const inView = useInView(ref, VIEWPORT);
    const days = Array.from({ length: ourDays + 1 }, (_, d) => d);

    return (
        <div data-testid={IDS.payoutClock} className={className}>
            <div ref={ref} className="relative h-2">
                <svg
                    viewBox="0 0 1000 8"
                    preserveAspectRatio="none"
                    role="img"
                    aria-label={`From the day your work is approved to the day you are paid: ${ourDays} ${clock.unit} at most.`}
                    className="absolute inset-0 h-2 w-full overflow-hidden rounded-full"
                >
                    <rect width="1000" height="8" fill="hsl(var(--muted))" />
                    {/* The wait, drawn from approval to paid — once, as the
                        track comes into view, and never again. */}
                    <motion.rect
                        width="1000"
                        height="8"
                        fill="hsl(var(--accent))"
                        style={{ originX: 0, transformBox: "fill-box" }}
                        initial={false}
                        animate={{ scaleX: reduced || inView ? 1 : 0 }}
                        transition={reduced ? { duration: 0 } : { duration: DUR.slow * 2, ease: EASE, delay: 0.1 }}
                    />
                </svg>

                {/* A tick per day, so "7" reads as a week of days rather than
                    as a number. HTML, not SVG: a circle in a
                    `preserveAspectRatio="none"` viewBox is an ellipse. */}
                {days.map((d) => {
                    const end = d === 0 || d === ourDays;
                    return (
                        <Reveal
                            key={d}
                            i={end ? (d === 0 ? 0 : 2) : 1}
                            noTravel
                            data-testid={d === 0 ? IDS.payoutClockStart : d === ourDays ? IDS.payoutClockOurs : undefined}
                            className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background ${
                                end ? "h-4 w-4 bg-foreground" : "h-2 w-2 bg-muted-foreground"
                            }`}
                            style={{ left: `${(d / ourDays) * 100}%` }}
                        />
                    );
                })}
            </div>

            {/* The two ends, named under their own markers, so a position on
                a bar is never the only way to read it. */}
            <div className="mt-4 flex justify-between gap-4 text-body text-muted-foreground">
                <span>{clock.start}</span>
                <span className="text-right">
                    {clock.end} day {ourDays}
                </span>
            </div>

            <Reveal i={3} className="mt-8">
                <p className="mkt-h2 text-heading">
                    {ourDays} {clock.unit}
                </p>
                <p className="mt-1 text-body text-muted-foreground">{clock.ours}</p>
            </Reveal>
        </div>
    );
}

export default PayoutClock;
