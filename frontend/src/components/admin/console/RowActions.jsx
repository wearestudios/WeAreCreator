// The two sizes of an action in a list view.
//
// `RowButton` sits in a table cell: small, quiet, and identical in every row,
// because forty loud buttons down a column compete with the data they are
// attached to. `PeekButton` is the same action in the slide-over, where there
// is room for an icon and a full label.
//
// Both are here rather than per screen so the approve on the review queue and
// the verify on the brand list look like the same kind of act — and so ember
// stays where the tokens say it belongs: on the primary action and nowhere
// else. A destructive action is outlined in rose and never filled, because a
// filled red button beside a filled ember one is two primaries.
import React from "react";

import { CALM, FOCUS, TEXT } from "@/components/admin/console/tokens";

// Quiet tints rather than outlines (board 27): navy-washed for the act, the
// warm ghost for everything else, and a destructive one outlined in rose —
// never filled, so it can never read as a second primary.
const TONES = {
    bad: "border-state-rejected/30 bg-transparent text-state-rejected hover:bg-state-rejected-wash",
    primary: "border-transparent bg-wash-navy text-heading hover:bg-primary hover:text-primary-foreground",
    plain: "border-transparent bg-wash-warm text-muted-foreground hover:text-foreground",
};

export function RowButton({ children, onClick, disabled, testid, tone = "plain", title }) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            title={title}
            data-testid={testid}
            className={`whitespace-nowrap rounded-[10px] border px-2.5 py-1 font-semibold ${TEXT.meta} ${CALM} disabled:opacity-40 ${FOCUS} ${
                TONES[tone] || TONES.plain
            }`}
        >
            {children}
        </button>
    );
}

export function PeekButton({ children, onClick, disabled, testid, tone = "plain" }) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            data-testid={testid}
            className={`inline-flex items-center gap-1.5 rounded-button border px-3.5 py-2 font-bold ${TEXT.body} ${CALM} disabled:opacity-40 ${FOCUS} ${
                TONES[tone] || TONES.plain
            }`}
        >
            {children}
        </button>
    );
}

export default RowButton;
