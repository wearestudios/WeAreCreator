// The draft review window, put into words.
//
// The server ships facts — the deadline, whether it is running, paused or
// frozen by a dispute, and whether it already elapsed — and never a pre-worded
// "in 2 days", because that phrase is stale a minute after it is sent and the
// browser has the clock. So the wording is built here, at render time.
//
// **Days are IST calendar days**, through `daysFromToday`. "Tomorrow" is a
// date somebody reads off a wall calendar, not "within 24 to 48 hours": a
// deadline at 09:00 the day after next is "in 2 days" at 23:00 tonight, which
// is how a person would say it. The exact instant rides in `exact` for the
// hover, so nobody has to trust the rounding.

import { daysFromToday, formatDateTime } from "@/lib/time";

// Mirrors DEFAULT_DRAFT_REVIEW_DAYS / DRAFT_REVIEW_DAYS_MIN / _MAX in
// backend/server.py, so the form's default and bounds are the route's. A unit
// test fails if they drift.
export const DEFAULT_DRAFT_REVIEW_DAYS = 3;
export const DRAFT_REVIEW_DAYS_MIN = 1;
export const DRAFT_REVIEW_DAYS_MAX = 14;

const exactOf = (iso) => formatDateTime(iso, { year: "numeric" });

/**
 * `{ text, exact, tone }` for a window, or `null` when there is nothing to
 * say — no window, or one on a draft that was approved by a person.
 *
 * tone: "calm" | "due" (today or tomorrow) | "paused" | "done".
 */
export function reviewWindowText(reviewWindow, now = new Date()) {
    if (!reviewWindow) return null;

    if (reviewWindow.auto_approved_at && reviewWindow.approved_via === "review_window_elapsed") {
        return {
            text: `Approved automatically when the review window ran out`,
            exact: exactOf(reviewWindow.auto_approved_at),
            tone: "done",
        };
    }
    if (reviewWindow.auto_approved_at && reviewWindow.approved_via === "admin_forced") {
        return {
            text: "Approved by the WeAre team before the window ran out",
            exact: exactOf(reviewWindow.auto_approved_at),
            tone: "done",
        };
    }
    if (reviewWindow.frozen_by_dispute) {
        return {
            text: "Auto-approval is on hold while the dispute is open",
            exact: reviewWindow.deadline_at ? exactOf(reviewWindow.deadline_at) : null,
            tone: "paused",
        };
    }
    if (reviewWindow.paused) {
        return {
            text: "Auto-approval is paused by the WeAre team",
            exact: reviewWindow.deadline_at ? exactOf(reviewWindow.deadline_at) : null,
            tone: "paused",
        };
    }
    if (!reviewWindow.running || !reviewWindow.deadline_at) return null;

    const deadline = new Date(reviewWindow.deadline_at);
    if (Number.isNaN(deadline.getTime())) return null;
    if (deadline.getTime() <= now.getTime()) {
        // Due, and the sweep has not reached it yet. Saying "in 0 days" or
        // counting backwards would both be stranger than the truth.
        return { text: "Auto-approving now", exact: exactOf(reviewWindow.deadline_at), tone: "due" };
    }
    const days = daysFromToday(deadline);
    const text =
        days <= 0
            ? "Auto-approves today"
            : days === 1
              ? "Auto-approves tomorrow"
              : `Auto-approves in ${days} days`;
    return { text, exact: exactOf(reviewWindow.deadline_at), tone: days <= 1 ? "due" : "calm" };
}
