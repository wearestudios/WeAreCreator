// The signature: a headline that morphs at letterform level.
//
// "Influencer marketing for F&B" → "...for Hospitality" → "...for Retail", and
// on through the sector list, each resolving against the constant second line
// "We run it end to end." The motion *is* the message — what changes is the
// sector, and what does not is that we run the campaign.
//
// **The lead and the tail never move.** Only the middle morphs, which is what
// makes this read as one sentence being re-pointed rather than eight unrelated
// headlines cycling. Animating the whole line would say the opposite.
//
// **It used to be a possessive on a campaign noun** — "Your launch night",
// "Your menu tasting" — against the tail "handled properly." Three things were
// wrong with it and all three are the reason this changed. "Your travel stay"
// and "your menu tasting" are not phrases anybody says, so they read as
// machine-assembled. The possessive addressed a marketing head as if about
// their own evening rather than their campaign. And "properly" is the hedge
// the register rules ban everywhere else on this site, carrying the whole
// claim.
//
// **"Influencer marketing" is in the H1 because it is the category term**, and
// before this it appeared in no headline anywhere on the site.
//
// **Per character, not per word, and never a plain fade.** Outgoing letters
// rise and dissolve on a stagger; incoming letters arrive from below on the
// same stagger, so the eye follows individual forms swapping rather than a
// block cross-dissolving. The stagger is what turns four transforms into a
// sentence resolving.
//
// Performance, since this runs on the front door on mobile data:
//
//   - **Transforms and opacity only.** Each letter is a `<span>` moved with
//     `y` and `opacity`. No layout property is touched, so nothing reflows and
//     the whole thing composites.
//   - **Every phrase reserves the box, by rendered width.** All eight are
//     drawn invisibly into one grid cell, so the box is as wide and as tall as
//     the widest and tallest phrase the browser actually draws. A shorter one
//     cannot let the second line ride up — a headline that jumps is worse than
//     no animation, and it would be a CLS event on every cycle.
//
//     **It used to reserve with one copy of the "longest" phrase, chosen by
//     character count, and a character count is not a width.** "Hospitality"
//     and "Real Estate" are both eleven characters so the reduce kept the
//     first, and in Fraunces at poster size "Real Estate" renders wider — the
//     animated layer is `absolute whitespace-nowrap`, so on that one slide it
//     overflowed its box to the right and the hero clipped it. Nothing about a
//     font can be inferred from the characters in a string; the only reliable
//     reservation is one the browser draws.
//   - **The letters are capped.** The tails are twelve characters at most; a
//     phrase long enough to make this expensive is a phrase too long to be a
//     poster headline anyway.
//
// **Under `prefers-reduced-motion` the first phrase renders and stays.** No
// timer is started, so there is nothing running in the background either.
//
// **The cycle itself lives in `sectorCycle.jsx` and not here.** This file
// owned a 4000ms `setInterval` while `HeroSlider` owned a 7000ms
// `setTimeout`; they drifted apart by the second slide and never recovered,
// so the word named one sector while the picture showed another. Matching the
// two constants would not have fixed it — two independent timers accumulate
// their own scheduling error — so there is one timer now and both read its
// index. Mounted with no provider this renders phrase one and starts nothing,
// which keeps the component usable on its own.
import React from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { EASE } from "@/components/marketing/motion";
import { CATEGORY_OPTIONS } from "@/lib/categories";
import { MARKETING as IDS } from "@/constants/testIds";
import { useOptionalSectorCycle } from "@/components/marketing/sectorCycle";

/**
 * The sectors, straight off the live category list.
 *
 * **Derived rather than written out, which is the whole point.** The old
 * phrases were four hand-written kinds of work that happened to correspond to
 * categories, held in line by a reviewer noticing — and a phrase naming a
 * sector `CampaignCategory` does not have is an invitation to read the
 * headline, open the brief feed, filter to it and find nothing. Mapping the
 * enum means that cannot be written. `lib/categories.js` is already drift-
 * tested against `CATEGORY_LITERAL`, so this inherits that guarantee.
 *
 * Eight rather than four, so the morph says "every sector" rather than
 * "these four" — every label is inside the twelve-character ceiling the
 * letter animation is budgeted for, "Food & drink" at exactly twelve.
 */
export const PHRASES = CATEGORY_OPTIONS.map((c) => c.label);

// Per-letter timings. The whole swap is well under a second, so the phrase is
// legible and still for most of its four seconds — the point is punctuation,
// not a permanent animation.
const OUT = 0.26;
const IN = 0.34;
const STEP = 0.022;

const letterOut = {
    initial: { opacity: 1, y: 0 },
    exit: (i) => ({
        opacity: 0,
        y: "-0.45em",
        transition: { delay: i * STEP, duration: OUT, ease: EASE },
    }),
};

const letterIn = {
    initial: { opacity: 0, y: "0.55em" },
    animate: (i) => ({
        opacity: 1,
        y: 0,
        transition: { delay: i * STEP, duration: IN, ease: EASE },
    }),
};

/** One phrase, split into animated letters. Spaces keep their width. */
function Letters({ text }) {
    return (
        <>
            {Array.from(text).map((ch, i) => (
                <motion.span
                    key={`${ch}-${i}`}
                    custom={i}
                    variants={{ ...letterIn, ...letterOut }}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    // inline-block so `y` has something to move; a bare span is
                    // inline and ignores a transform.
                    className="inline-block will-change-transform"
                >
                    {ch === " " ? " " : ch}
                </motion.span>
            ))}
        </>
    );
}

/**
 * @param {string} lead   the word that never changes, before the morph
 * @param {string} tail   the line that never changes, after it
 */
export function KineticHeadline({
    lead = "Influencer marketing for",
    tail = "We run it end to end.",
    phrases = PHRASES,
}) {
    const ownReduced = useReducedMotion();
    // **The cycle is not this component's any more.** It owned a 4000ms
    // `setInterval` while the slider owned a 7000ms `setTimeout`, and the
    // two drifted apart by the second slide — the word naming one sector
    // over a picture of another. `sectorCycle` owns the index now and both
    // read it, so there is nothing left to go out of step.
    //
    // Read optionally, because this is exported and mountable on its own: a
    // headline that throws outside the hero is a component with a hidden
    // dependency on its parent. With no provider it renders phrase one and
    // starts nothing, which is also the reduced-motion state.
    const cycle = useOptionalSectorCycle();
    const reduced = cycle ? cycle.reduced : ownReduced;
    const i = cycle ? cycle.index % phrases.length : 0;
    const still = reduced || !cycle;

    // clamp() rather than a Tailwind step: this is still poster scale, well
    // past `fluid-hero`'s 4.25rem top step, and it is the only element on the
    // site at this size. **The ceiling came down from 8.5rem because the
    // headline is sized to a column now rather than to the window** — it sits
    // in six of the hero's twelve, where 8.5rem resolved to 136px against a
    // lead roughly 1700px wide and ran the h1 to four lines, putting the CTAs
    // under the fold on a laptop. The vw term is measured, not guessed.
    const poster = {
        fontSize: "clamp(2.25rem, 4.6vw, 4.75rem)",
        lineHeight: 1.0,
    };

    return (
        <h1
            data-testid={IDS.kineticHeadline}
            // One accessible name, stable across the morph. A screen reader
            // reading four letters at a time as they animate in would be
            // gibberish, so the animated spans are hidden from it entirely.
            aria-label={`${lead} ${phrases[0]}, ${tail}`}
            className="font-serif tracking-tightest"
            style={poster}
        >
            <span aria-hidden className="block">
                <span className="text-foreground">{lead} </span>
                {/* The morphing line. **Every phrase is rendered invisibly
                    into one grid cell**, so the box is as wide and as tall as
                    the widest and tallest phrase the browser actually draws,
                    and the animated copy sits on top of it.

                    It used to reserve the box with a single invisible copy of
                    the longest phrase, picked by character count — and a
                    character count is not a width. "Hospitality" and "Real
                    Estate" are both eleven characters, the reduce kept the
                    first on a tie, and in Fraunces at this size "Real Estate"
                    renders wider: the animated layer is `absolute
                    whitespace-nowrap`, so on that one slide it ran past its
                    own box and the hero's `overflow-hidden` clipped it.
                    Stacking them all means the box cannot be narrower than
                    the phrase in it whatever the font does, and it still
                    cannot change height between phrases — which is the CLS
                    property the old version was protecting and this one
                    keeps. */}
                <span className="relative inline-grid align-top">
                    {phrases.map((p) => (
                        <span
                            key={p}
                            className="invisible col-start-1 row-start-1 whitespace-nowrap"
                            aria-hidden
                        >
                            {p}
                        </span>
                    ))}
                    <span className="absolute inset-0 whitespace-nowrap text-primary">
                        {still ? (
                            phrases[0]
                        ) : (
                            <AnimatePresence mode="wait" initial={false}>
                                <motion.span
                                    key={phrases[i]}
                                    data-testid={IDS.kineticPhrase}
                                    className="inline-block"
                                >
                                    <Letters text={phrases[i]} />
                                </motion.span>
                            </AnimatePresence>
                        )}
                    </span>
                </span>
            </span>
            <span aria-hidden className="block italic text-muted-foreground">
                {tail}
            </span>
        </h1>
    );
}

export default KineticHeadline;
