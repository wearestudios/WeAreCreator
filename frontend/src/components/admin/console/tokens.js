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
// **Row height is fixed at 44px.** Fixed rather than content-driven because a
// table whose rows change height cannot be scanned — the eye tracks a rhythm
// down the left edge and a row that grows breaks it. It is also what makes
// virtualisation possible without measuring anything.
//
// **Base text is `text-sm`.** The console had 160 uses of `text-xs`, most of
// them on primary content, which is what made it feel like a settings screen
// rather than a tool. `text-xs` is now for true metadata only: timestamps,
// ids, column headers, unit labels.

/** Vertical rhythm. Nothing in the console picks its own padding. */
export const DENSITY = {
    /** Inside a cell, a chip, a compact control. */
    tight: "px-2 py-1",
    /** The default: table cells, list rows, form fields. */
    row: "px-3 py-2",
    /** A panel's inner padding, a dialog's body. */
    panel: "p-4",
    /** The gap between panels, and a section's own top margin. */
    section: "gap-4",
};

/** 44px. Every table row, every list row, every toolbar control. */
export const ROW_H = "h-11";
export const ROW_PX = 44;

/** The one type ramp the console uses. */
export const TEXT = {
    /** Primary content: names, titles, amounts, states. */
    body: "text-sm",
    /** True metadata only — timestamps, ids, column headers, units. */
    meta: "text-xs",
    /** A panel or page heading. */
    heading: "text-base font-medium",
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
        chip: "border-state-pending/30 bg-state-pending/10 text-state-pending",
    },
    good: {
        label: "Approved",
        dot: "bg-state-approved",
        text: "text-state-approved",
        chip: "border-state-approved/30 bg-state-approved/10 text-state-approved",
    },
    bad: {
        label: "Rejected",
        dot: "bg-state-rejected",
        text: "text-state-rejected",
        chip: "border-state-rejected/30 bg-state-rejected/10 text-state-rejected",
    },
    active: {
        label: "In progress",
        dot: "bg-state-progress",
        text: "text-state-progress",
        chip: "border-state-progress/30 bg-state-progress/10 text-state-progress",
    },
    idle: {
        label: "—",
        dot: "bg-tint/30",
        text: "text-muted-foreground",
        chip: "border-tint/15 bg-tint/5 text-muted-foreground",
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
    "focus-visible:ring-offset-1 focus-visible:ring-offset-background";

/** A panel: hairline border, flat surface, no grain, no shadow. */
export const PANEL = "rounded-md border border-tint/10 bg-card";
