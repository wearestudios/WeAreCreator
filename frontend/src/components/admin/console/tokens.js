// The console's density and colour system, defined once.
//
// This is a working surface for one person doing one job for an hour at a
// time, not a page anybody is being sold to. It reads as a data tool: calm,
// dense, and identical from screen to screen so the eye stops re-learning the
// layout at every route.
//
// ---------------------------------------------------------------------------
// ONE DENSITY SCALE
//
// The console had `py-1` through `py-8` scattered across twenty files, so no
// two panels shared a rhythm and every screen looked hand-built. Four steps
// now, and nothing outside them.
//
// **Row height is fixed, and the fixed value lives in CSS.** Fixed rather
// than content-driven because a table whose rows change height cannot be
// scanned — the eye tracks a rhythm down the left edge and a row that grows
// breaks it — and because it is what makes virtualisation possible without
// measuring each row. It is `--row-h` in index.css: 70px comfortable, 42px
// compact, each above what a row's content plus its 22px / 9px padding can
// reach. `DataTable` reads the number off the element for its windowing
// arithmetic, so the CSS is the one place it is written.
//
// **Two text roles, both density-aware.** `text-body` (16px, 14 compact) is
// primary content; `text-meta` (14px, 13 compact) is true metadata —
// timestamps, ids, column headers, unit labels. Both read custom properties
// that `data-density="compact"` redefines on its wrapper, so nothing in the
// console branches on density to pick a class.

/** Vertical rhythm. Nothing in the console picks its own padding. */
export const DENSITY = {
    /** Inside a cell, a chip, a compact control. */
    tight: "px-2 py-1",
    /** Toolbars, filter bars, form fields, sidebar links — controls. */
    row: "px-3 py-2",
    /** A list or table row's cell: 22px vertical, 9px in compact. */
    cell: "px-3 py-row",
    /** A panel's inner padding, a dialog's body. */
    panel: "p-inner",
    /** The gap between panels, and a section's own top margin. */
    section: "gap-section",
};

/** Every table and list row: `--row-h`, 70px comfortable, 42px compact. */
export const ROW_H = "h-list-row";
/** What the windowing math falls back to before the element can be read. */
export const ROW_PX = 70;

/** The one type ramp the console uses. */
export const TEXT = {
    /** Primary content: names, titles, amounts, states. */
    body: "text-body",
    /** True metadata only — timestamps, ids, column headers, units. */
    meta: "text-meta",
    /** A panel or page heading. */
    heading: "text-body font-medium",
};

// ---------------------------------------------------------------------------
// ONE SEMANTIC COLOUR PER STATE
//
// Five meanings, one colour each, used identically everywhere — and **never
// colour alone**. Every status renders as a dot plus a word, because roughly
// one man in twelve cannot separate the amber from the green, and because a
// screenshot pasted into a message loses the legend either way.
//
// **Ember is not in this list.** It is reserved for primary actions — the one
// button on a screen that does the thing. A status that borrowed it would make
// every row look like a call to action.

export const STATUS_TONE = {
    pending: {
        label: "Pending",
        dot: "bg-state-pending",
        text: "text-state-pending",
        chip: "border-state-pending/30 bg-state-pending-wash text-state-pending",
    },
    good: {
        label: "Approved",
        dot: "bg-state-approved",
        text: "text-state-approved",
        chip: "border-state-approved/30 bg-state-approved-wash text-state-approved",
    },
    bad: {
        label: "Rejected",
        dot: "bg-state-rejected",
        text: "text-state-rejected",
        chip: "border-state-rejected/30 bg-state-rejected-wash text-state-rejected",
    },
    active: {
        label: "In progress",
        dot: "bg-state-progress",
        text: "text-state-progress",
        chip: "border-state-progress/30 bg-state-progress-wash text-state-progress",
    },
    idle: {
        label: "—",
        dot: "bg-tint/30",
        text: "text-muted-foreground",
        chip: "border-border bg-muted text-muted-foreground",
    },
};

/**
 * Every state string the console can show, mapped to one of the five tones.
 *
 * One table rather than a `meta` object per screen: the reason the console had
 * a campaign "closed" reading grey in one place and red in another is that two
 * files each decided for themselves.
 */
const TONE_BY_STATE = {
    // Verification, both sides.
    pending: "pending",
    pending_review: "pending",
    pending_verification: "pending",
    unsubmitted: "idle",
    verified: "good",
    approved: "good",
    rejected: "bad",
    suspended: "bad",

    // Campaigns.
    draft: "idle",
    in_review: "pending",
    upcoming: "active",
    open: "active",
    in_progress: "active",
    paused: "pending",
    completed: "good",
    closed: "idle",

    // Collaborations.
    applied: "pending",
    accepted: "active",
    commercial_agreed: "active",
    slot_booked: "active",
    attended: "active",
    draft_submitted: "pending",
    draft_approved: "active",
    content_submitted: "pending",
    content_approved: "good",
    in_payment: "pending",
    paid: "good",
    declined: "bad",
    cancelled: "bad",
    // **Neither of these is a rejection, and neither wears red.** A withdrawal
    // is the creator's own decision, taken before anybody was committed; an
    // expiry is a decision nobody ever made. Drawing either in the colour a
    // decline uses puts a black mark on a record where there is none.
    withdrawn: "idle",
    expired: "idle",
};

/** The tone for a state string, defaulting to neutral rather than guessing. */
export const toneFor = (state) => STATUS_TONE[TONE_BY_STATE[state] || "idle"];

/**
 * The word a state shows.
 *
 * Wire values are snake_case; nobody says "commercial_agreed" out loud.
 */
export const labelFor = (state) =>
    !state
        ? "—"
        : String(state)
              .replace(/_/g, " ")
              .replace(/^./, (c) => c.toUpperCase());

// ---------------------------------------------------------------------------
// MOTION
//
// **150ms, colour and opacity, and nothing that enters on its own.** The
// marketing site's staggered entrances are right there and wrong here: a list
// that animates in is a list you cannot read until it has finished, and an
// admin loads it forty times a day. Skeletons still stand in while data is in
// flight — that is shape, not motion.

export const CALM = "transition-colors duration-150";

/** The focus ring, identical on every focusable thing in the console. */
export const FOCUS =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
    "focus-visible:ring-offset-2 focus-visible:ring-offset-background";

/** A panel: hairline border, flat surface, no grain, no shadow. */
export const PANEL = "rounded-md border border-border bg-card";
