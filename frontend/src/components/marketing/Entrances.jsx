// The two entrances a public page may have, besides a number counting.
//
// **Once, and then never again.** Both play exactly one time per mount and
// neither is wired to scroll position: a headline that re-animates every time
// it scrolls back into view is a page performing for itself. See the motion
// block in `index.css` for the keyframes, the two duration bands and the
// reduced-motion rule — which lives there and only there, so these components
// carry no motion branch of their own and a reader who asked for none gets
// the end state on first paint.
//
// Import these through `components/marketing/primitives.js`, which is the
// whole marketing motion vocabulary.
import React, { useEffect, useRef, useState } from "react";

/** The gap between lines and between rows, as numbers for the inline delay.
 * Mirrors `--mkt-line-gap` / `--mkt-row-gap`; the test reads both. */
export const LINE_GAP_MS = 90;
export const ROW_GAP_MS = 70;

/**
 * A headline arriving, once, at mount: each line rises 24px with opacity over
 * 520ms, 90ms after the one before.
 *
 * It is only the *presentation* of the lines. The element that carries the
 * accessible name is the caller's — pass the whole sentence as the heading's
 * text by wrapping this inside it, and the lines read as one heading because
 * they are spans inside it.
 *
 * @param {{ lines: string[], as?: string, className?: string, lineClassName?: string }} props
 */
export function LineEntrance({ lines, as: Tag = "span", className = "", lineClassName = "" }) {
    return (
        <Tag className={className}>
            {lines.map((line, i) => (
                <span
                    key={line}
                    className={`mkt-line ${lineClassName}`}
                    style={{ animationDelay: `${i * LINE_GAP_MS}ms` }}
                >
                    {line}
                </span>
            ))}
        </Tag>
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
 * Two ways to drive it. Left alone it watches for itself. Given `written`,
 * the caller decides — which is how a block that is only mounted once it is on
 * screen (a slide in the hero deck) writes on mount without an observer of its
 * own. `animate={false}` draws the rows already written: the second time the
 * same block is shown, it is not written again.
 *
 * @param {{ rows: Array<{ key: string, node: React.ReactNode, final?: boolean }>,
 *           written?: boolean, animate?: boolean,
 *           className?: string, rowClassName?: string, as?: string, rowAs?: string }} props
 */
export function RowWriter({
    rows,
    written: controlled,
    animate = true,
    className = "",
    rowClassName = "",
    as: Tag = "div",
    rowAs: Row = "div",
}) {
    const ref = useRef(null);
    const [seen, setSeen] = useState(false);
    const watching = animate && controlled === undefined;
    const written = controlled === undefined ? seen : controlled;

    useEffect(() => {
        if (!watching || seen) return undefined;
        const node = ref.current;
        if (!node || typeof IntersectionObserver === "undefined") {
            setSeen(true);
            return undefined;
        }
        const io = new IntersectionObserver(
            (entries) => {
                if (entries.some((e) => e.isIntersecting)) {
                    setSeen(true);
                    io.disconnect();
                }
            },
            { rootMargin: "0px 0px -15% 0px" },
        );
        io.observe(node);
        return () => io.disconnect();
    }, [watching, seen]);

    if (!animate) {
        return (
            <Tag className={className}>
                {rows.map((row) => (
                    <Row key={row.key} className={rowClassName}>
                        {row.node}
                    </Row>
                ))}
            </Tag>
        );
    }
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
