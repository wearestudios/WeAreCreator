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
//   - **The tallest phrase reserves the box.** The line's height is fixed by
//     an invisible copy of the longest phrase, so a shorter one cannot let the
//     second line ride up — a headline that jumps every four seconds is worse
//     than no animation, and it would be a CLS event on every cycle.
//   - **The letters are capped.** The tails are twelve characters at most; a
//     phrase long enough to make this expensive is a phrase too long to be a
//     poster headline anyway.
//
// **Under `prefers-reduced-motion` the first phrase renders and stays.** No
// timer is started, so there is nothing running in the background either.
import React, { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { EASE } from "@/components/marketing/motion";
import { CATEGORY_OPTIONS } from "@/lib/categories";
import { MARKETING as IDS } from "@/constants/testIds";

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

const HOLD_MS = 4000;

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
    const reduced = useReducedMotion();
    const [i, setI] = useState(0);

    useEffect(() => {
        if (reduced) return undefined;
        const t = setInterval(() => setI((n) => (n + 1) % phrases.length), HOLD_MS);
        return () => clearInterval(t);
    }, [reduced, phrases.length]);

    const longest = phrases.reduce((a, b) => (b.length > a.length ? b : a), "");

    // clamp() rather than a Tailwind step: this is poster scale, well past the
    // top of the type ramp, and it is the only element on the site at this
    // size. 11vw keeps it filling the column at every width.
    const poster = {
        fontSize: "clamp(2.5rem, 10.5vw, 8.5rem)",
        lineHeight: 0.94,
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
                {/* The morphing line. `relative` + an invisible copy of the
                    longest phrase reserves the height so nothing below moves;
                    the animated copy sits on top of it. */}
                <span className="relative inline-block align-top">
                    <span className="invisible" aria-hidden>
                        {longest}
                    </span>
                    <span className="absolute inset-0 whitespace-nowrap text-primary">
                        {reduced ? (
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
