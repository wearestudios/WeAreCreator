// The signature: a headline that morphs at letterform level.
//
// "Your launch night" → "Your fashion drop" → "Your travel stay" → "Your menu
// tasting", each resolving against the constant second line "handled
// properly." The motion *is* the message — the thing that changes is the kind
// of campaign, and the thing that does not is how it is run.
//
// **"Your" and "handled properly." never move.** Only the tail morphs, which
// is what makes this read as one sentence being re-pointed rather than four
// unrelated headlines cycling. Animating the whole line would say the opposite.
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
    lead = "Your",
    tail = "handled properly.",
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
