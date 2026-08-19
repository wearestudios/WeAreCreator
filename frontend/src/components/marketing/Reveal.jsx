// Rise and fade, on arrival.
//
// The one entrance on the marketing site. Wrapping is deliberately cheap —
// `<Reveal i={2}>` around anything — because the alternative is each section
// deciding for itself and the page ending up with four different entrances.
//
// **`prefers-reduced-motion` is handled here, once**, rather than at each call
// site. Under `reduce` the element renders at its final state with no
// transition: the content is never withheld, which is the failure mode of
// gating an entrance on a media query and forgetting the fallback.
import React from "react";
import { motion, useReducedMotion } from "framer-motion";

import { VIEWPORT, fade, rise, still } from "@/components/marketing/motion";

/**
 * @param {number}  i        position in a staggered group; sets the delay
 * @param {boolean} onView   animate when scrolled into view rather than on
 *                           mount. Default true — a page's first screen is
 *                           already in view, so the two agree there, and
 *                           everything below it earns its entrance.
 * @param {boolean} noTravel fade only, for something whose position matters
 * @param {string}  as       element to render; "div" by default
 */
export function Reveal({
    i = 0,
    onView = true,
    noTravel = false,
    as = "div",
    className = "",
    children,
    ...rest
}) {
    const reduced = useReducedMotion();
    const Tag = motion[as] || motion.div;
    const variants = reduced ? still : noTravel ? fade : rise;

    // With reduced motion there is nothing to wait for, so the element is
    // simply shown — no viewport observer, no chance of content that never
    // arrives because an observer did not fire.
    const timing = reduced
        ? { animate: "show" }
        : onView
          ? { whileInView: "show", viewport: VIEWPORT }
          : { animate: "show" };

    return (
        <Tag
            initial="hidden"
            custom={i}
            variants={variants}
            className={className}
            {...timing}
            {...rest}
        >
            {children}
        </Tag>
    );
}

export default Reveal;
