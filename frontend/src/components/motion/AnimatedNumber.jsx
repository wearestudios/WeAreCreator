/**
 * A number that travels to its new value instead of snapping to it.
 *
 * On a dashboard a count changing is information — a new application, a
 * payment cleared, a filter narrowing a list — and a figure that simply
 * replaces itself is a change the reader misses, because nothing on screen
 * moved. 260–700ms of travel is enough to be noticed and short enough not to
 * be waited on.
 *
 * **It writes `textContent` on a ref and never calls `setState` per frame.**
 * The lesson `CampaignFilm` records: a state update per frame re-renders the
 * whole subtree sixty times a second to change four characters, and on the
 * creator dashboard that subtree is the card the number sits in. React owns
 * the initial render and the final value; the frames in between are this
 * component writing to one text node.
 *
 * **The first paint is the real value, never zero.** Counting up from nothing
 * on first load is the marketing site's `CountUp`, which is right for a proof
 * figure somebody is being sold and wrong for a working screen — an admin
 * opening the queue should not watch "0 of 14" become "14". So the tween runs
 * only when the value *changes* while mounted.
 */
import React, { useEffect, useLayoutEffect, useRef } from "react";

import { GROUPED, countDuration, prefersReducedMotion, tween } from "@/lib/motion";

export default function AnimatedNumber({
    value,
    // Rounds, like every formatter this takes must: `value` is a float on
    // every frame but the last.
    format = GROUPED,
    className = "",
    as: Tag = "span",
    ...rest
}) {
    const node = useRef(null);
    const shown = useRef(typeof value === "number" ? value : null);
    const frame = useRef(0);

    // Layout effect so the text is correct before the browser paints — an
    // effect would let one frame of the previous value through on a
    // re-render, which is a flicker rather than a transition.
    useLayoutEffect(() => {
        if (typeof value !== "number" || !node.current) return undefined;
        const from = shown.current;
        // First paint, a non-numeric previous value, or a reader who asked
        // for less motion: land on the answer.
        if (from === null || from === value || prefersReducedMotion()) {
            shown.current = value;
            node.current.textContent = format(value);
            return undefined;
        }

        const ms = countDuration(from, value);
        const started = performance.now();
        const step = (now) => {
            const t = (now - started) / ms;
            const at = t >= 1 ? value : tween(from, value, t);
            if (node.current) node.current.textContent = format(at);
            shown.current = at;
            if (t < 1) {
                frame.current = requestAnimationFrame(step);
            } else {
                shown.current = value;
            }
        };
        frame.current = requestAnimationFrame(step);
        return () => cancelAnimationFrame(frame.current);
    }, [value, format]);

    // A tab going to the background stops firing rAF, so a tween started
    // before it can be left mid-travel. Nothing else cancels it, because the
    // effect above only re-runs on a value change.
    useEffect(() => () => cancelAnimationFrame(frame.current), []);

    return (
        <Tag ref={node} className={className} {...rest}>
            {/* Server-rendered-equivalent first paint: the real value, so a
                screenshot taken before any effect runs is correct and a
                screen reader is never handed a partial number. */}
            {typeof value === "number" ? format(value) : "—"}
        </Tag>
    );
}
