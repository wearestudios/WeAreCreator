// Where the brand's money actually goes, drawn.
//
// The strongest commercial fact the product has was a sentence on a pricing
// card: our fee is charged on top of the creator's rate, never out of it.
// Written down it is a claim a reader skims; drawn as the money moving from
// the brand, through us, to the creator — and arriving whole — it is an
// argument they can follow. That is why this earns motion: the animation *is*
// the explanation, three steps filling in the order the money travels.
//
// **Restored from the pre-revamp /for-brands (8263b6f), and adapted on two
// counts the old version could not survive on today's pages:**
//
//   - **It compared us with "the category"**, a 35–60% share it said other
//     operators pay creators. Nothing in this codebase backs that figure — it
//     carried `data-unsourced` for exactly that reason — and these pages now
//     carry only claims the product keeps. The comparison column is gone; what
//     is drawn is our own flow, every step of which is true.
//   - **Every word and figure comes from `BRANDS.pricing.flow`** in the
//     content module. The one number is the creator's share, 100%, which is
//     true by construction: the fee sits on the brand's side of the invoice.
//     **Our fee is printed only when `FACTS.platformFeePercent` is set** —
//     while it is `null` the flow animates with no fee figure at all, never
//     an invented one. And there is no escrow step, because there is no
//     escrow: the middle of the flow is us invoicing the brand and paying the
//     creator after approval, which is what happens.
//
// **The drawing is SVG and the words are HTML, which is an accessibility
// decision rather than a layout one.** `role="img"` makes a subtree
// presentational, so a figure built entirely in SVG reaches a screen reader as
// its label and nothing else — and `<text>` inside an SVG does not reflow at
// 390px either. So each bar is an SVG carrying its step as an `aria-label`,
// and every label and figure beside them is real HTML text.
import React, { useRef } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";

import CountUp from "@/components/marketing/CountUp";
import Reveal from "@/components/marketing/Reveal";
import { DUR, EASE, VIEWPORT } from "@/components/marketing/motion";
import { MARKETING as IDS } from "@/constants/testIds";
import { platformFeeText } from "@/content/marketing";

/**
 * @param {{ flow: object, feePercent?: number|null, className?: string }} props
 *   `flow` is `BRANDS.pricing.flow`. `feePercent` defaults to
 *   `FACTS.platformFeePercent` through `platformFeeText`, and prints nothing
 *   while that is null.
 */
export function FeeFlow({ flow, feePercent, className = "" }) {
    const reduced = useReducedMotion();
    // **One observer for the whole flow, rather than `whileInView` on each
    // bar.** Each bar sits inside a `Reveal`, which is a variant tree, and a
    // child `motion` element with an object-valued `whileInView` inside a
    // parent running named variants does not reliably receive its own
    // animation — measured on the old version of this file. One ref decides
    // for all three, so they cannot disagree about whether they have arrived.
    const ref = useRef(null);
    const inView = useInView(ref, VIEWPORT);
    const fee = feePercent === undefined ? platformFeeText() : platformFeeText(feePercent);

    return (
        <div ref={ref} data-testid={IDS.feeFlow} className={className}>
            <Reveal as="p" className="text-body font-medium text-foreground">
                {flow.label}
            </Reveal>
            <ol className="mt-6 grid gap-6 md:grid-cols-3 md:gap-5">
                {flow.steps.map((step, i) => (
                    <li key={step.key} data-testid={IDS.feeFlowStep(step.key)}>
                        <Reveal i={i}>
                            {/* The money arriving at this step, drawn. Left to
                                right, a beat apart, which is the direction it
                                travels. Scale on the X axis from a left origin
                                — a width animation would lay out on every
                                frame, which the motion layer bans. */}
                            <svg
                                viewBox="0 0 100 8"
                                preserveAspectRatio="none"
                                role="img"
                                aria-label={`${i + 1} of ${flow.steps.length}: ${step.who}. ${step.line}`}
                                className="block h-2 w-full overflow-hidden rounded-full"
                            >
                                <rect width="100" height="8" fill="hsl(var(--muted))" />
                                <motion.rect
                                    width="100"
                                    height="8"
                                    // Navy for the two steps the money passes
                                    // through; the red, as a fill, on the step
                                    // where it lands.
                                    fill={i === flow.steps.length - 1 ? "hsl(var(--accent))" : "hsl(var(--primary))"}
                                    // **`originX`, not `transformOrigin`**, and
                                    // `transform-box: fill-box` beside it:
                                    // Framer writes its own origin, and an SVG
                                    // element resolves one against the viewBox
                                    // by default. Both were measured wrong on
                                    // the old version before they were set.
                                    style={{ originX: 0, transformBox: "fill-box" }}
                                    initial={false}
                                    animate={{ scaleX: reduced || inView ? 1 : 0 }}
                                    transition={
                                        reduced
                                            ? { duration: 0 }
                                            : { duration: DUR.slow, ease: EASE, delay: 0.15 + i * 0.35 }
                                    }
                                />
                            </svg>
                            <p className="mkt-h3 mt-5 text-heading">{step.who}</p>
                            <p className="mkt-body mt-2 text-muted-foreground">{step.line}</p>
                            {step.key === "weare" && fee ? (
                                <p data-testid={IDS.feeFlowFee} className="mt-3 text-body font-medium text-foreground">
                                    {fee}
                                </p>
                            ) : null}
                        </Reveal>
                    </li>
                ))}
            </ol>
            <Reveal i={3} className="mt-10 flex flex-wrap items-baseline gap-x-4 gap-y-1 border-t border-border pt-6">
                {/* Read once, whole; the counting figure is decoration. The
                    meaning is never in the colour alone — the words say it. */}
                <span className="sr-only">
                    {flow.share}% {flow.shareLabel}
                </span>
                <span aria-hidden data-testid={IDS.feeFlowShare("creator")} className="mkt-h2 text-heading">
                    <CountUp value={flow.share} />%
                </span>
                <span aria-hidden className="text-body text-muted-foreground">
                    {flow.shareLabel}
                </span>
            </Reveal>
        </div>
    );
}

export default FeeFlow;
