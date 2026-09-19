// The signature: a headline that morphs at letterform level.
//
// "We run the launch night" → "the fashion drop" → "the travel stay" → "the
// menu tasting", each resolving against the constant close "not just the
// booking." The motion *is* the message — the thing that changes is the kind
// of campaign, and the thing that does not is who runs it.
//
// **The frame is the claim.** It used to be "Your … handled properly", which
// described what we do and made the reader work out what it meant. The frame
// now *is* `CAMPAIGN_CLAIM`, leading with the thing only we do: every
// competitor books a creator, and we run the campaign. A brand can repeat it
// back after one read, which is the test a hero either passes or fails.
//
// **The lead and the tail never move.** Only the middle morphs, which is what
// makes this read as one sentence being re-pointed rather than four unrelated
// headlines cycling. Animating the whole line would say the opposite.
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
import { CAMPAIGN_CLAIM } from "@/lib/promise";
import React, { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { EASE } from "@/components/marketing/motion";
import { MARKETING as IDS } from "@/constants/testIds";

/** Four kinds of campaign, four real categories. Same rule as the hero deck:
 *  a phrase naming a category `CampaignCategory` does not have is an invitation
 *  to filter the brief list and find nothing. */
export const PHRASES = ["launch night", "fashion drop", "travel stay", "menu tasting"];

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
    lead = "We run the",
    tail = "not just the booking.",
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
            // **The accessible name is the canonical claim, not the variant
            // currently on screen.** A screen reader and a crawler should get
            // the sentence we actually make — "the campaign", not whichever of
            // the four kinds the morph happens to be holding. Sighted readers
            // get the same claim re-pointed four ways, which is the whole
            // point of the treatment: what changes is the kind of work, what
            // does not is who runs it.
            aria-label={CAMPAIGN_CLAIM}
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
                    <span className="absolute inset-0 whitespace-nowrap text-ember-500">
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
