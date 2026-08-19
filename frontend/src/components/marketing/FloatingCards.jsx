// Tilted photo cards floating behind the hero, drifting on scroll.
//
// The hero's argument is range — launch night, fashion, travel, fitness — and
// four cards at four angles say it faster than a sentence can. They sit behind
// and around the headline rather than beside it, so the page reads as one
// composition rather than a column of text with a picture next to it.
//
// **The shadow here is deliberate and is the only place the marketing site has
// one.** The design foundations reserve `box-shadow` for things that genuinely
// float above the page — dialogs, popovers, toasts — and everything inline
// uses a hairline border plus a surface tint instead. A tilted card drifting
// at a different rate from the page behind it is the one inline element that
// really is floating, and without the shadow the tilt reads as a mistake. It
// is a soft black shadow, per the same rules, never the default grey.
//
// Performance, because this is the front door on mobile data:
//
//   - **Transform and opacity only.** Rotation is a static transform set once;
//     the drift is `y`, driven by `useTransform` off the scroll position, so
//     the browser composites it without touching layout.
//   - **Nothing is fetched.** Each card is a `PlaceholderImage` — a warm tint
//     with the site's grain — in a container that already occupies the space
//     the photograph will.
//   - **Two cards below `md`, four above.** Four overlapping cards on a 390px
//     screen is four compositing layers behind text nobody can read through
//     them, and the two that survive are the two furthest from the headline.
//   - **`prefers-reduced-motion` freezes the drift**, keeping the composition:
//     the tilt and the shadow are static design, not animation.
import React from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";

import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import { MARKETING as IDS } from "@/constants/testIds";

// Position, tilt and drift rate per card. `depth` is how far it travels over
// the scroll — the far cards move most, which is what reads as depth.
//
// `phone` marks the two that survive below `md`. They are the outer pair, so
// the composition stays balanced rather than lopsided.
//
// `set` picks which cluster: the hero's four, or the two that sit behind a
// proof strip. The proof pair is quieter and further out — the figures are the
// thing being read there, and a card behind a number is a card competing with
// the one element on the page that has to be believed.
const CARDS = [
    {
        key: "launch",
        // PLACEHOLDER IMAGE: a restaurant on opening night, tables full, warm
        // service light, shot from the pass. Portrait 4:5.
        note: "Restaurant on opening night, tables full, warm service light, portrait 4:5",
        ratio: "4/3",
        className: "left-[2%] top-[14%] w-[26%] md:left-[3%] md:top-[16%] md:w-[19%]",
        rotate: -7,
        depth: 90,
        phone: true,
    },
    {
        key: "fashion",
        // PLACEHOLDER IMAGE: a fashion creator mid-shoot against a plain wall,
        // outfit in motion. Portrait 4:5.
        note: "Fashion creator mid-shoot against a plain wall, outfit in motion, portrait 4:5",
        ratio: "4/3",
        className: "hidden md:block md:left-[19%] md:top-[58%] md:w-[15%]",
        rotate: 5,
        depth: 46,
    },
    {
        key: "travel",
        // PLACEHOLDER IMAGE: a hotel balcony at first light, coffee on the
        // rail, city beyond. Landscape 3:2.
        note: "Hotel balcony at first light, coffee on the rail, city beyond, landscape 3:2",
        ratio: "3/2",
        className: "hidden md:block md:right-[4%] md:top-[12%] md:w-[20%]",
        rotate: 6,
        depth: 108,
    },
    {
        key: "fitness",
        // PLACEHOLDER IMAGE: a fitness class mid-session, one participant
        // filming from the back of the room. Landscape 3:2.
        note: "Fitness class mid-session, one participant filming from the back, landscape 3:2",
        ratio: "3/2",
        className: "right-[3%] bottom-[8%] w-[28%] md:right-[15%] md:bottom-[10%] md:w-[17%]",
        rotate: -5,
        depth: 64,
        phone: true,
    },
];

const SHADOW = "shadow-[0_28px_70px_-24px_rgba(0,0,0,0.85)]";

function Card({ card, progress, reduced }) {
    // Hooks cannot be called conditionally, so the transform is always built
    // and simply pinned to 0 when motion is reduced.
    const y = useTransform(progress, [0, 1], [0, reduced ? 0 : -card.depth]);

    return (
        <motion.div
            aria-hidden
            data-testid={IDS.floatingCard(card.key)}
            style={{ y, rotate: card.rotate }}
            className={`absolute ${card.className} ${SHADOW} rounded-lg`}
        >
            <PlaceholderImage note={card.note} ratio={card.ratio} />
        </motion.div>
    );
}

// The proof cluster: two cards, hugging the edges, at a shallower tilt.
const PROOF_CARDS = [
    {
        key: "proof-left",
        // PLACEHOLDER IMAGE: a creator's contact sheet or camera roll of a
        // finished shoot, spread on a table. Landscape 3:2.
        note: "Contact sheet from a finished shoot spread on a table, landscape 3:2",
        ratio: "3/2",
        className: "hidden md:block md:-left-[6%] md:top-[-18%] md:w-[16%]",
        rotate: -4,
        depth: 40,
    },
    {
        key: "proof-right",
        // PLACEHOLDER IMAGE: a venue's own screen showing a campaign report,
        // somebody pointing at the reach figure. Landscape 3:2.
        note: "Venue screen showing a campaign report, somebody pointing at the reach figure, 3:2",
        ratio: "3/2",
        className: "hidden md:block md:-right-[6%] md:bottom-[-18%] md:w-[16%]",
        rotate: 4,
        depth: 56,
    },
];

/**
 * Mount inside a `relative` container. The cards are decorative and absolutely
 * positioned, so they never affect the layout of what they sit behind.
 *
 * @param {"hero"|"proof"} set  which cluster to draw
 */
export function FloatingCards({ set = "hero", className = "" }) {
    const reduced = useReducedMotion();
    // Progress through the section this sits in, rather than the whole page —
    // so the drift is spent by the time the section leaves, instead of the
    // cards accelerating away for the rest of the scroll.
    const { scrollYProgress } = useScroll();

    return (
        <div
            aria-hidden
            data-testid={IDS.floatingCards}
            // The proof cluster deliberately does not clip: the two cards
            // hang past the strip's edges, which is what makes them read as
            // floating over it rather than pasted inside it.
            className={`pointer-events-none absolute inset-0 ${
                set === "proof" ? "" : "overflow-hidden"
            } ${className}`}
        >
            {(set === "proof" ? PROOF_CARDS : CARDS).map((card) => (
                <Card
                    key={card.key}
                    card={card}
                    progress={scrollYProgress}
                    reduced={reduced}
                />
            ))}
        </div>
    );
}

export default FloatingCards;
