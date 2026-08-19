// A number that counts up when it arrives.
//
// Only on the proof strip, and only because those figures are the one thing on
// the marketing site a stranger is being asked to believe — the count draws the
// eye to them for about a third of a second and then stops. It runs **once**,
// on scroll into view, and never again.
//
// **Under `prefers-reduced-motion` the first paint is the final value.** Not a
// faster count: no count. A number ticking is motion whatever its duration,
// and somebody who asked for less of it did not ask for a shorter version.
import React, { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "framer-motion";

import { VIEWPORT } from "@/components/marketing/motion";

// Longer than the site's 200–400ms entrances on purpose: a count is read
// rather than perceived, and at 320ms a four-digit figure is a blur.
const COUNT_MS = 900;

export function CountUp({ value, className = "" }) {
    const reduced = useReducedMotion();
    const ref = useRef(null);
    const inView = useInView(ref, VIEWPORT);
    const [n, setN] = useState(reduced ? value : 0);

    useEffect(() => {
        if (reduced) {
            setN(value);
            return undefined;
        }
        if (!inView) return undefined;

        let frame;
        const start = performance.now();
        const tick = (now) => {
            const t = Math.min(1, (now - start) / COUNT_MS);
            // Ease-out cubic: most of the distance early, so the number is
            // legible for most of the time it is moving.
            setN(Math.round(value * (1 - Math.pow(1 - t, 3))));
            if (t < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frame);
    }, [inView, value, reduced]);

    return (
        <span ref={ref} className={className}>
            {n.toLocaleString("en-IN")}
        </span>
    );
}

export default CountUp;
