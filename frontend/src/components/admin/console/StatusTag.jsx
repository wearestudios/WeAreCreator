// A state, shown the same way everywhere.
//
// **A dot and a word, never a colour on its own.** Roughly one man in twelve
// cannot separate the amber from the green, and a screenshot pasted into a
// message loses whatever legend the screen had. The colour is the fast path
// for everybody who can use it; the word is what the value actually is.
//
// One component rather than the four "meta" objects the console had, which is
// why a closed campaign read grey on one screen and red on the next.
import React from "react";

import { TEXT, labelFor, toneFor } from "@/components/admin/console/tokens";

/**
 * @param {string}  state    a wire value — "pending_review", "in_progress"…
 * @param {string} [label]   an override, where the wire value is not the word
 * @param {boolean}[chip]    draw the pill background as well as the dot
 */
export function StatusTag({ state, label, chip = false, testid, className = "" }) {
    const tone = toneFor(state);
    const text = label ?? labelFor(state);

    if (chip) {
        return (
            <span
                data-testid={testid}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 ${TEXT.meta} ${tone.chip} ${className}`}
            >
                <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
                {text}
            </span>
        );
    }

    // The default in a table cell: a dot and the word, no box. A pill per row
    // in a column of forty is forty boxes competing with the data.
    return (
        <span
            data-testid={testid}
            className={`inline-flex items-center gap-2 whitespace-nowrap ${className}`}
        >
            <span aria-hidden className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} />
            <span className={tone.text}>{text}</span>
        </span>
    );
}

export default StatusTag;
