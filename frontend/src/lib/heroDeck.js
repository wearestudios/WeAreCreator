// The hero deck's state, as pure functions.
//
// **The deck rotates the stage of the job, never the sector.** It used to
// rotate the sector — eight slides reading Retail, Hospitality, Travel, drawn
// from `CATEGORY_OPTIONS` — and the sector is the one thing a visitor already
// knows about themselves, so watching it change taught them nothing. Four
// fixed steps now, Offer → Agree → Deliver → Get paid, which is what they came
// to find out. Adding a sector touches nothing here, which is the point: this
// file imports no category list and never will.
//
// Pure and dependency-free so the rules that matter can be *run* rather than
// read — `test_hero_deck.py` loads this file into node and drives it:
//
//   - **At most two slides are mounted, ever.** `painted` is the outgoing slide
//     and the incoming one during a crossfade, and the active one alone otherwise.
//     The DOM product screens are heavier than the images they replaced, so
//     the two-layer budget the old slider earned is held, not relaxed.
//   - **One timer.** The provider runs a single `setTimeout` chain off
//     `autoAdvances`; nothing else in the hero may own a clock. The 7000ms /
//     4000ms split between a slider and a headline is the sync defect this
//     whole arrangement exists to have removed.
//   - **Reduced motion never auto-advances.** Step 01, and the rail does the
//     switching — with no crossfade, so there is never a second layer either.

/** The one dwell, for the screen and the line alike. */
export const HOLD_MS = 7000;

/** The crossfade between two screens — inside the marketing entrance band
 * (450–600ms), and the one curve, `--weare-ease`. */
export const FADE_MS = 600;

/**
 * The deck's resting state: step 01, nothing leaving.
 *
 * `seen` is every step that has been shown and `fresh` is the step that has
 * just been shown *for the first time*, or null. The Agree screen writes its
 * rows in only while it is fresh, so the counter history writes itself once
 * and is simply there on every lap after.
 */
export const INITIAL = { active: 0, leaving: null, seen: [0], fresh: null };

/**
 * The next state.
 *
 *   { type: "go", to, reduced }      the rail, or the timer
 *   { type: "advance", count, reduced }
 *   { type: "settle" }               the crossfade finished
 *
 * Going to the slide already showing is a no-op, not a crossfade of a slide
 * over itself. Under reduced motion a change replaces the slide outright, so
 * `leaving` is never set and there is never a second layer to paint.
 */
export function deckReducer(state, action) {
    switch (action.type) {
        case "go": {
            if (action.to === state.active) return state;
            const seen = state.seen || [state.active];
            const first = !seen.includes(action.to);
            return {
                active: action.to,
                leaving: action.reduced ? null : state.active,
                seen: first ? [...seen, action.to] : seen,
                fresh: first ? action.to : null,
            };
        }
        case "advance":
            return deckReducer(state, {
                type: "go",
                to: (state.active + 1) % action.count,
                reduced: action.reduced,
            });
        case "settle":
            return state.leaving === null ? state : { ...state, leaving: null };
        default:
            return state;
    }
}

/**
 * Which slides are in the DOM: the outgoing one under the incoming one while
 * the crossfade runs, and only the active one otherwise. **Never more than two.**
 */
export function painted(state) {
    if (state.leaving === null || state.leaving === state.active) return [state.active];
    return [state.leaving, state.active];
}

/**
 * Whether the timer may run at all. `paused` covers a pointer over the hero,
 * focus inside it, and the hero being off screen — a deck nobody can see has
 * no reason to advance, and the step a reader scrolls back to should be the
 * one they left.
 */
export function autoAdvances({ reduced, paused }) {
    return !reduced && !paused;
}

/** `01`–`04`. The rail's numbers are read, so they are zero-padded. */
export const pad = (n) => String(n).padStart(2, "0");
