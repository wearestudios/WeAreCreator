/**
 * Content arriving: a row, a card, a panel.
 *
 * `<Settle index={i}>` is the whole API. It renders a `<div>` (or whatever
 * `as` says) carrying the `weare-settle` class and, past index 0, an inline
 * `animation-delay` — so a list becomes a stagger without a parent
 * orchestrator, and a single card and the fourth row in a table use the
 * identical treatment.
 *
 * **It re-runs on purpose when `settleKey` changes.** Item 10 asks for this on
 * first load *and* on a filter or sort change, and those are the same event as
 * far as a reader is concerned: the set in front of them was replaced. React
 * reuses DOM nodes across a re-render, so without a changing `key` the CSS
 * animation — which fires on element creation — would play once, on mount, and
 * never again. Passing the filter state as `settleKey` remounts the subtree
 * and the new set settles like the first one did.
 *
 * That is also why it must not be keyed on something that changes constantly.
 * Keying a row on its own data would replay the animation every time a count
 * ticked, which is the "content popping in" this exists to remove.
 */
import React, { useCallback } from "react";

import { settleDelay } from "@/lib/motion";

export default function Settle({
    index = 0,
    as: Tag = "div",
    className = "",
    style,
    settleKey,
    children,
    ...rest
}) {
    // `will-change` is a promise to the compositor that costs memory per
    // element. Left on, twenty rows keep twenty layers alive for the life of
    // the screen; released on `animationend`, they cost it for 440ms.
    const release = useCallback((event) => {
        if (event.currentTarget === event.target) {
            event.currentTarget.classList.add("weare-settle-done");
        }
    }, []);

    return (
        <Tag
            key={settleKey}
            className={`weare-settle ${className}`.trim()}
            style={{ ...settleDelay(index), ...style }}
            onAnimationEnd={release}
            {...rest}
        >
            {children}
        </Tag>
    );
}

/**
 * The same thing for a list, so a caller does not write the index by hand.
 *
 * `items.map((x, i) => <Settle index={i} …>)` is three lines every time and
 * one of them is the one somebody forgets. This takes the array and the
 * renderer.
 */
export function SettleList({ items = [], settleKey, children, ...rest }) {
    return items.map((item, i) => (
        <Settle
            key={item?.id ?? item?._id ?? i}
            index={i}
            settleKey={settleKey}
            {...rest}
        >
            {children(item, i)}
        </Settle>
    ));
}
