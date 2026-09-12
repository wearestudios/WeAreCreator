// What a brief has left to spend.
//
// The server decides all of it — `_campaign_budget` in `backend/server.py`
// returns total, committed, remaining, the ratio and the two flags — and this
// file only formats. **Nothing here recomputes a threshold**: a browser that
// worked out for itself whether 80% had been reached would be a second
// definition of "nearly spent", and the console already learned that lesson
// once with `isStale`.
//
// `BUDGET_WARNING_RATIO` is not mirrored here for exactly that reason. The
// block carries `warning`, `exhausted` and `warning_ratio`, so a panel reads
// the answer rather than the arithmetic.

import { formatCompensation } from "@/lib/compensation";

/** The block, or `null` — for a brief with no cap and for a payload that
 *  didn't look, which are the same answer for a screen: draw nothing. */
export function budgetOf(source) {
    const block = source?.budget;
    if (!block || block.total === null || block.total === undefined) return null;
    return block;
}

export function formatMoney(value) {
    if (value === null || value === undefined) return "—";
    return `₹${Math.round(Number(value)).toLocaleString("en-IN")}`;
}

/** 0–100 for a progress bar, clamped: a brief that went over its cap through
 *  an admin override is at 100%, not at 118% of a bar's width. */
export function budgetPercent(block) {
    if (!block) return 0;
    return Math.max(0, Math.min(100, Math.round((block.ratio || 0) * 100)));
}

/** calm | warning | exhausted — read off the server's flags, never derived
 *  from the numbers beside them. */
export function budgetTone(block) {
    if (!block) return "calm";
    if (block.exhausted) return "exhausted";
    if (block.warning) return "warning";
    return "calm";
}

/** One line for a row that has no room for a bar. */
export function budgetSummary(block) {
    if (!block) return null;
    return `${formatMoney(block.remaining)} left of ${formatMoney(block.total)}`;
}

/** Whether this amount fits, for a form that wants to say so before the
 *  button is pressed. `null` when there is no cap or no amount — the same
 *  shape the server's `_budget_refusal` returns, and for the same reason: one
 *  caller labels rather than refusing. */
export function overBudgetBy(block, amount) {
    if (!block || amount === null || amount === undefined || amount === "") return null;
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= block.remaining) return null;
    return Math.round((value - block.remaining) * 100) / 100;
}

/** Barter draws down nothing, so a barter brief has no cap to show — the
 *  server excludes those collaborations from `committed` entirely rather than
 *  counting them as zero, and a bar reading 0% of ₹50,000 on a brief that
 *  will never spend any of it is a bar that means nothing. */
export function budgetApplies(campaign) {
    return campaign?.compensation_type !== "barter" && !!budgetOf(campaign);
}

export { formatCompensation };
