// One sentence whose words ink in as it is scrolled through.
//
// **For one sentence on the whole site**, and the rule is the point: a fill
// tied to scroll position asks the reader to slow down, and asking twice on a
// page is asking nobody. `test_site_foundations.py` counts the uses.
//
// **Derived from scroll position, never from state.** Each word's ink is a
// function of where the sentence sits in the viewport, so scrolling back up
// un-inks it by the same function — a state machine would look the same going
// down and be wrong going up. Written straight onto each word's style from a
// ref, inside one rAF per scroll, so the sentence never re-renders: the lesson
// the scroll film recorded (`setState` per frame re-renders the stage sixty
// times a second to change a few characters).
//
// The scroll listener exists only while the sentence is on screen.
//
// **The sentence is whole in the DOM and to assistive tech at every moment** —
// only opacity moves. Under `prefers-reduced-motion` every word is fully inked
// from the first paint; that rule is in `index.css`, not here.
import React, { useEffect, useRef } from "react";

/** How faint an un-inked word is. Decoration until it inks, never invisible. */
export const FILL_FLOOR = 0.18;

export function inkFor(progress, index, count) {
    // Words ink one after another across the sentence's travel; each takes
    // the span of about one word to go from faint to full.
    const at = progress * (count + 1) - index;
    return Math.max(FILL_FLOOR, Math.min(1, FILL_FLOOR + at * (1 - FILL_FLOOR)));
}

/**
 * @param {{ text: string, as?: string, className?: string }} props
 */
export function FillText({ text, as: Tag = "p", className = "" }) {
    const ref = useRef(null);
    const words = text.split(/\s+/).filter(Boolean);

    useEffect(() => {
        const node = ref.current;
        if (!node || typeof window === "undefined") return undefined;
        const spans = Array.from(node.querySelectorAll(".mkt-fill-word"));
        let frame = 0;

        const paint = () => {
            frame = 0;
            const rect = node.getBoundingClientRect();
            const vh = window.innerHeight || 1;
            // 0 when the sentence's top reaches 85% of the screen, 1 when its
            // bottom reaches 40%: inked by the time it is comfortably in view.
            const start = vh * 0.85;
            const end = vh * 0.4 - rect.height;
            const progress = Math.max(0, Math.min(1, (start - rect.top) / (start - end || 1)));
            spans.forEach((s, i) => {
                s.style.opacity = String(inkFor(progress, i, spans.length));
            });
        };
        const onScroll = () => {
            if (!frame) frame = requestAnimationFrame(paint);
        };

        let listening = false;
        const listen = (on) => {
            if (on === listening) return;
            listening = on;
            if (on) {
                window.addEventListener("scroll", onScroll, { passive: true });
                window.addEventListener("resize", onScroll);
                paint();
            } else {
                window.removeEventListener("scroll", onScroll);
                window.removeEventListener("resize", onScroll);
            }
        };

        paint();
        let io;
        if (typeof IntersectionObserver !== "undefined") {
            io = new IntersectionObserver((entries) => listen(entries.some((e) => e.isIntersecting)));
            io.observe(node);
        } else {
            listen(true);
        }
        return () => {
            if (io) io.disconnect();
            listen(false);
            if (frame) cancelAnimationFrame(frame);
        };
    }, [text]);

    return (
        <Tag ref={ref} className={`mkt-fill ${className}`}>
            {words.map((w, i) => (
                <React.Fragment key={`${w}-${i}`}>
                    <span className="mkt-fill-word">{w}</span>
                    {i < words.length - 1 ? " " : null}
                </React.Fragment>
            ))}
        </Tag>
    );
}

export default FillText;
