// How the console renders numbers and time.
//
// One formatter per kind of value, so a rupee figure is grouped the same way
// in a table cell, a peek panel and a stat tile. The console previously had
// three rupee formatters and two follower formatters, which is how the same
// campaign showed ₹1,20,000 on one screen and ₹120,000 on the next.
import React from "react";

import { TEXT } from "@/components/admin/console/tokens";

/**
 * Rupees, in Indian grouping — 12,00,000 rather than 1,200,000.
 *
 * `en-IN` does the lakh/crore grouping natively. It is the grouping the person
 * reading this reconciles a bank statement in, so it is the one to use even
 * though the rest of the app's numbers are small enough not to care.
 */
export const rupees = (n) =>
    n == null || Number.isNaN(Number(n))
        ? "—"
        : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

/** A follower count, compacted: 24k, 1.2M. Never a bare six-digit number in a
 *  column somebody is scanning. */
export const compact = (n) => {
    if (n == null || Number.isNaN(Number(n))) return "—";
    const v = Number(n);
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v >= 10_000_000 ? 0 : 1)}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(v >= 10_000 ? 0 : 1)}k`;
    return String(v);
};

/** A plain integer with thousands separators — counts, not money. */
export const count = (n) =>
    n == null || Number.isNaN(Number(n)) ? "—" : Number(n).toLocaleString("en-IN");

/** A percentage to one place. */
export const percent = (n) =>
    n == null || Number.isNaN(Number(n)) ? "—" : `${Number(n).toFixed(1)}%`;

const ABSOLUTE = new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
});

/** The full stamp, for the tooltip and for anywhere precision matters. */
export const absolute = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "—" : ABSOLUTE.format(d);
};

/**
 * "3h ago", "2d ago", "just now".
 *
 * Relative is what a person actually reasons about when triaging a queue —
 * "this has been sitting two days" is the judgement, not the calendar date.
 * The exact stamp is a hover away, which is the right way round.
 */
export const relative = (iso) => {
    if (!iso) return "—";
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return "—";
    const mins = Math.round((Date.now() - t) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.round(hrs / 24);
    if (days < 30) return `${days}d ago`;
    const months = Math.round(days / 30);
    if (months < 12) return `${months}mo ago`;
    return `${Math.round(months / 12)}y ago`;
};

/**
 * A timestamp cell: relative in the flow, absolute on hover.
 *
 * `<time>` with a `dateTime` and a `title`, so the precise value is available
 * to a mouse, to a screen reader and to anybody who copies the cell.
 */
export function TimeAgo({ iso, className = "" }) {
    if (!iso) return <span className="text-muted-foreground">—</span>;
    return (
        <time
            dateTime={iso}
            title={absolute(iso)}
            className={`${TEXT.meta} text-muted-foreground ${className}`}
        >
            {relative(iso)}
        </time>
    );
}

/**
 * A numeric cell.
 *
 * **Right-aligned and tabular.** Digits that do not line up cannot be compared
 * down a column, which is the entire reason for putting them in one.
 */
export function Num({ children, className = "" }) {
    return (
        <span className={`tabular-nums ${className}`}>{children}</span>
    );
}
