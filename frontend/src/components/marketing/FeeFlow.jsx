// Where the brand's money actually goes.
//
// This is the strongest differentiator the product has and it was a sentence:
// "our fee is charged on top of the creator rate". Written down it is a claim
// a reader skims; drawn as two flows ending in two different figures it is an
// argument they can check. That is the whole reason this earns motion when
// nothing else on the site does — the animation *is* the comparison, two
// columns filling to two different answers.
//
// **It never names a kind of company, and that is deliberate rather than
// coy.** `_FORBIDDEN_MARKETING_PHRASES` bans "middleman", "agency fees" and
// "without an agency" because WeAre Studios is an agency and the managed
// service is a real offering somebody chooses — a graphic arguing against
// intermediaries would be arguing against our own product. What the left
// column names is the *shape* of the deal, not who offers it: one bundled
// number with an unstated split. The enemy this site names is opacity, and
// opacity is what the left column draws.
//
// **The drawing is SVG and the numbers are HTML, which is an accessibility
// decision rather than a layout one.** `role="img"` makes a subtree
// presentational, so a figure built entirely in SVG reaches a screen reader as
// its label and nothing else — and `<text>` inside an SVG does not reflow at
// 390px either. So the proportion bars are an SVG that carries the finding as
// its `aria-label`, and every label and figure beside them is real HTML text
// that a reader hears and a browser can reflow and resize.
import React, { useRef } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";

import CountUp from "@/components/marketing/CountUp";
import Reveal from "@/components/marketing/Reveal";
import { DUR, EASE, VIEWPORT } from "@/components/marketing/motion";
import { MARKETING as IDS } from "@/constants/testIds";

// ---------------------------------------------------------------------------
// NEEDS A SOURCE
// ---------------------------------------------------------------------------
// `UNSOURCED` names every figure here that nothing in this codebase can back,
// in the shape the `NEEDS A LAWYER` blocks already use: flagged where it is,
// never quietly resolved.
//
// `theirShare` is a claim about what *other* operators pay creators. It is the
// one number on this graphic that is neither computed, stored, nor agreed
// anywhere in the product — unlike `OUR_SHARE`, which is `COMMISSION_TERMS`
// restated and is true by construction, because the fee is charged to the
// brand on a separate line and never deducted from the creator's.
//
// It renders because the operation asserts it, and it is a prop so that
// sourcing it later is one edit at the call site rather than a hunt through
// a component. **Until it is sourced it carries `data-unsourced`**, so the
// claim is greppable in the built page rather than only in somebody's memory.
// A marketing page here is held to "every claim is checkable"; this one is not
// yet, and saying so in the file is cheaper than discovering it in a
// complaint.
export const UNSOURCED = ["theirShare"];

/** True by construction — the fee sits on the brand's side of the invoice. */
const OUR_SHARE = 100;

// **The words live in one block because they count against the page's budget.**
// `test_marketing_pages.py` already reads `CampaignFilm`'s captions for the
// page that mounts it, on the stated grounds that reading only a page's own
// `COPY` "would let a section smuggle in copy by being a component". These are
// words on `/for-brands` and `/why-weare` by exactly that argument, so they
// are kept where the counter can read them rather than scattered through JSX.
//
// The `aria-label`s are deliberately **not** here. They are an alternative to
// the picture for somebody who cannot see it, not additional copy a sighted
// reader meets — counting them would charge the page twice for one claim and
// make describing a graphic properly cost words.
export const COPY = {
    theirsHeading: "How the category does it",
    theirsStepOne: "Brand pays one bundled number",
    theirsStepTwo: "An unstated cut comes out",
    theirsFoot: "of what the brand paid",

    oursHeading: "How we do it",
    oursStepOne: "Brand pays the creator's rate",
    oursStepTwo: "Our fee sits on top, published",
    oursFoot: "of their quoted rate",

    receives: "Creator receives",
};

export function FeeFlow({ theirShareLow = 35, theirShareHigh = 60, className = "" }) {
    const reduced = useReducedMotion();
    // **The bars are driven by an explicit observer rather than by
    // `whileInView`.** Each sits inside a `Reveal`, which is a variant tree —
    // and a child `motion` element with an object-valued `whileInView` inside
    // a parent running named variants does not reliably receive its own
    // animation. Measured: the bar stayed at `scaleX(0)` while its sibling,
    // whose target happens to be the identity scale, looked correct. One ref
    // on the container decides for both columns, so they cannot disagree
    // about whether they have arrived.
    const ref = useRef(null);
    const inView = useInView(ref, VIEWPORT);

    const theirs = {
        key: "theirs",
        heading: COPY.theirsHeading,
        steps: [COPY.theirsStepOne, COPY.theirsStepTwo],
        foot: COPY.theirsFoot,
        testid: IDS.feeFlowTheirs,
    };
    const ours = {
        key: "ours",
        heading: COPY.oursHeading,
        steps: [COPY.oursStepOne, COPY.oursStepTwo],
        foot: COPY.oursFoot,
        testid: IDS.feeFlowOurs,
    };

    return (
        <div
            ref={ref}
            data-testid={IDS.feeFlow}
            className={`grid gap-6 md:grid-cols-2 ${className}`}
        >
            {[theirs, ours].map((col, side) => {
                const accent = col.key === "ours";
                return (
                    <div
                        key={col.key}
                        data-testid={col.testid}
                        className="rounded-lg border border-border bg-card/60 p-6"
                    >
                        <Reveal i={side} as="p" className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            {col.heading}
                        </Reveal>

                        {/* Top to bottom on a stagger, which is the direction
                            the money travels — the index continues across the
                            column so the two sides fill a beat apart rather
                            than in lockstep. */}
                        {col.steps.map((step, i) => (
                            <Reveal
                                key={step}
                                i={side + i + 1}
                                as="p"
                                className="mt-4 text-sm leading-relaxed text-muted-foreground"
                            >
                                {step}
                            </Reveal>
                        ))}

                        <Reveal i={side + 3} className="mt-5">
                            {/* The proportion, drawn. The bar is the picture
                                and carries the finding; the figure under it is
                                real text. Scale on the X axis only, from a
                                left origin — a width animation would lay out
                                on every frame, which the motion layer bans. */}
                            <svg
                                viewBox="0 0 100 8"
                                preserveAspectRatio="none"
                                role="img"
                                aria-label={
                                    accent
                                        ? "A creator keeps the whole of their quoted rate, because our fee is charged to the brand on top of it."
                                        : `Of one bundled fee, a creator receives roughly ${theirShareLow} to ${theirShareHigh} per cent.`
                                }
                                className="block h-2 w-full overflow-hidden rounded-full"
                            >
                                <rect width="100" height="8" fill="hsl(var(--graphic-track))" />
                                <motion.rect
                                    width="100"
                                    height="8"
                                    fill={accent ? "hsl(var(--brand-red))" : "hsl(var(--graphic-quiet))"}
                                    // **`originX`, not `transformOrigin`.**
                                    // Framer manages the origin itself and
                                    // writes its own `transform-origin`, so a
                                    // CSS `transformOrigin` here is silently
                                    // overridden — measured as computing to
                                    // `50px 4px`, the rect's centre, which is
                                    // how this bar came to render at 20–80%.
                                    //
                                    // `transform-box: fill-box` is the other
                                    // half and is also load-bearing. An SVG
                                    // element resolves `transform-origin`
                                    // against the *viewBox* by default, so
                                    // "left center" anchors to the viewBox's
                                    // left edge rather than the rect's. Both
                                    // are the same place for a bar that ends
                                    // at scaleX(1) — which is why the accent
                                    // bar and the clock's span looked right
                                    // and this one did not: it is the only
                                    // bar whose final scale is not 1, so it
                                    // rendered centred at 20–80% instead of
                                    // filling 0–60%.
                                    style={{ originX: 0, transformBox: "fill-box" }}
                                    initial={false}
                                    animate={{
                                        scaleX:
                                            reduced || inView
                                                ? accent
                                                    ? 1
                                                    : theirShareHigh / 100
                                                : 0,
                                    }}
                                    transition={
                                        reduced
                                            ? { duration: 0 }
                                            : {
                                                  duration: DUR.slow,
                                                  ease: EASE,
                                                  delay: (side + 3) * 0.07,
                                              }
                                    }
                                />
                            </svg>

                            <p className="mt-3 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                                {COPY.receives}
                            </p>
                            {/* **The meaning is never in the colour alone.**
                                The accented figure says "100%" and "of their
                                quoted rate" in words beside it, so the point
                                survives being read in greyscale, by somebody
                                who cannot distinguish the red, or aloud. */}
                            <p
                                data-testid={IDS.feeFlowShare(col.key)}
                                data-unsourced={accent ? undefined : "theirShare"}
                                className={`mt-1 font-serif text-fluid-3xl ${
                                    accent ? "text-primary" : "text-foreground"
                                }`}
                            >
                                {accent ? (
                                    <>
                                        <CountUp value={OUR_SHARE} />%
                                    </>
                                ) : (
                                    <>
                                        <CountUp value={theirShareLow} />–{theirShareHigh}%
                                    </>
                                )}
                            </p>
                            <p className="mt-1 text-sm text-muted-foreground">
                                {col.foot}
                            </p>
                        </Reveal>
                    </div>
                );
            })}
        </div>
    );
}

export default FeeFlow;
