// The two entrances a public page may have.
//
// **Once, and then never again.** Each plays exactly one time per mount: a
// headline that re-animates whenever it scrolls back into view is a page
// performing for itself. The keyframes, the duration bands and the
// reduced-motion rule are in the motion block of `index.css`, and the
// reduced-motion rule lives there only — so these carry no motion branch of
// their own, and a reader who asked for none gets the end state on first
// paint.
//
// Import them through `components/marketing/primitives.js`, which is the
// whole marketing motion vocabulary.
import React, { useEffect, useRef, useState } from "react";

/** The gap between rows, as a number for the inline delay. Mirrors
 * `--mkt-row-gap`; the test reads both. */
export const ROW_GAP_MS = 70;

/**
 * One word, revealed left to right, once, at load (520ms).
 *
 * **The word is in the DOM, whole, from the first paint** — the reveal is a
 * `clip-path` on an inline box, so the heading's text and accessible name are
 * complete before and during it, and a crawler or a screen reader never meets
 * a partial sentence. The fill mode is `backwards`, so once the reveal ends the
 * clip is gone entirely rather than held at its last frame: an italic's
 * overhang is never trimmed by a box that has finished its job.
 *
 * @param {{ children: React.ReactNode, className?: string, delayMs?: number }} props
 */
export function WipeWord({ children, className = "", delayMs = 0 }) {
    return (
        <span className={`mkt-wipe ${className}`} style={delayMs ? { animationDelay: `${delayMs}ms` } : undefined}>
            {children}
        </span>
    );
}

/**
 * Rows written in sequence, once, the first time the block is in view: 70ms
 * apart, 400ms each, and the row marked `final` landing with a scale from 0.96
 * rather than a slide.
 *
 * The rows are transparent until then and already occupy their boxes, so
 * arriving moves nothing. Where `IntersectionObserver` is missing the rows are
 * written at once — the content matters more than its entrance.
 *
 * @param {{ rows: Array<{ key: string, node: React.ReactNode, final?: boolean }>,
 *           className?: string, rowClassName?: string, as?: string, rowAs?: string }} props
 */
export function RowWriter({ rows, className = "", rowClassName = "", as: Tag = "div", rowAs: Row = "div" }) {
    const ref = useRef(null);
    const [written, setWritten] = useState(false);

    useEffect(() => {
        if (written) return undefined;
        const node = ref.current;
        if (!node || typeof IntersectionObserver === "undefined") {
            setWritten(true);
            return undefined;
        }
        const io = new IntersectionObserver(
            (entries) => {
                if (entries.some((e) => e.isIntersecting)) {
                    setWritten(true);
                    io.disconnect();
                }
            },
            { rootMargin: "0px 0px -10% 0px" },
        );
        io.observe(node);
        return () => io.disconnect();
    }, [written]);

    return (
        <Tag ref={ref} className={className} data-written={written ? "true" : "false"}>
            {rows.map((row, i) => (
                <Row
                    key={row.key}
                    className={`mkt-row ${row.final ? "mkt-row-final" : ""} ${rowClassName}`}
                    style={{ animationDelay: `${i * ROW_GAP_MS}ms` }}
                >
                    {row.node}
                </Row>
            ))}
        </Tag>
    );
}
