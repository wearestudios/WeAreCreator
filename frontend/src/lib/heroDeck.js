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
//     and the incoming one during a wipe, and the active one alone otherwise.
//     The DOM product screens are heavier than the images they replaced, so
//     the two-layer budget the old slider earned is held, not relaxed.
//   - **One timer.** The provider runs a single `setTimeout` chain off
//     `autoAdvances`; nothing else in the hero may own a clock. The 7000ms /
//     4000ms split between a slider and a headline is the sync defect this
//     whole arrangement exists to have removed.
//   - **Reduced motion never auto-advances.** Step 01, and the rail does the
//     switching — with no wipe, so there is never a second layer either.

/** The one hold, for the screen and the line alike. */
export const HOLD_MS = 6000;

/** How long the wipe between two screens takes. */
export const WIPE_MS = 700;

/** The deck's resting state: step 01, nothing leaving. */
export const INITIAL = { active: 0, leaving: null };

/**
 * The next state.
 *
 *   { type: "go", to, reduced }      the rail, or the timer
 *   { type: "advance", count, reduced }
 *   { type: "settle" }               the wipe finished
 *
 * Going to the slide already showing is a no-op, not a wipe of a slide over
 * itself. Under reduced motion a change replaces the slide outright, so
 * `leaving` is never set and there is never a second layer to paint.
 */
export function deckReducer(state, action) {
    switch (action.type) {
        case "go": {
            if (action.to === state.active) return state;
            return {
                active: action.to,
                leaving: action.reduced ? null : state.active,
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
 * a wipe runs, and only the active one otherwise. **Never more than two.**
 */
export function painted(state) {
    if (state.leaving === null || state.leaving === state.active) return [state.active];
    return [state.leaving, state.active];
}

/** Whether the timer may run at all. */
export function autoAdvances({ reduced, paused }) {
    return !reduced && !paused;
}

/** `01`–`04`. The rail's numbers are read, so they are zero-padded. */
export const pad = (n) => String(n).padStart(2, "0");
