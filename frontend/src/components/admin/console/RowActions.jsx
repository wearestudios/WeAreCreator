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

const TONES = {
    bad: "border-state-rejected/30 text-state-rejected hover:bg-state-rejected/10",
    primary: "border-primary/40 bg-primary/10 text-primary-ink hover:bg-primary/20",
    plain: "border-tint/15 text-muted-foreground hover:bg-tint/5",
};

export function RowButton({ children, onClick, disabled, testid, tone = "plain", title }) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            title={title}
            data-testid={testid}
            className={`whitespace-nowrap rounded border px-2 py-0.5 ${TEXT.meta} ${CALM} disabled:opacity-40 ${FOCUS} ${
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
            className={`inline-flex items-center gap-1.5 rounded border px-3 py-1.5 ${TEXT.body} ${CALM} disabled:opacity-40 ${FOCUS} ${
                TONES[tone] || TONES.plain
            }`}
        >
            {children}
        </button>
    );
}

export default RowButton;
