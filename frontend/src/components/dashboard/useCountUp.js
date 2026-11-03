// The one small hook the dashboard's motion needs: a number counting up.
//
// **Writes `textContent` on a ref, never `setState` per frame** — the lesson
// `CampaignFilm` and `AnimatedNumber` record: sixty React renders a second
// next to a chart drawing is where a mid-range phone drops frames. Every frame
// is formatted with Indian grouping, so the number is never seen as
// "148932.4" on its way to "1,48,932".
//
// Once per load. The first non-null value counts up over 900ms; any later
// value (a background refresh) is written straight in, silently. Under
// reduced motion the first paint is the final value.
import { useEffect, useRef } from "react";
import { prefersReducedMotion } from "@/lib/motion";

export const COUNT_MS = 900;

const easeOut = (t) => 1 - Math.pow(1 - t, 3);

export function useCountUp(value, format, { animate = true } = {}) {
    const ref = useRef(null);
    const played = useRef(false);

    useEffect(() => {
        const node = ref.current;
        if (!node) return undefined;
        if (value === null || value === undefined) {
            node.textContent = format(value);
            return undefined;
        }
        if (played.current || !animate || prefersReducedMotion()) {
            played.current = true;
            node.textContent = format(value);
            return undefined;
        }
        played.current = true;
        let frame = 0;
        const start = performance.now();
        const tick = (now) => {
            const t = Math.min(1, (now - start) / COUNT_MS);
            node.textContent = format(value * easeOut(t));
            if (t < 1) frame = requestAnimationFrame(tick);
        };
        node.textContent = format(0);
        frame = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frame);
    }, [value, format, animate]);

    return ref;
}
