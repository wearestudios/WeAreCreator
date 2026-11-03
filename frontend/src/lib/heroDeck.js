// The hero slider's state, as pure functions.
//
// **One engine, generalised rather than written twice.** This drove the old
// hero card's four step screens (Offer, Agree, Deliver, Get paid); it now
// drives the homepage's hero slider — the deal, the problem, the shoot and,
// while any AI switch is on, the AI — which is the whole hero rather than a
// card beside it. The rules carried over unchanged, and one was added:
//
//   - **At most two slides are painted, ever.** `painted` is the outgoing slide
//     and the incoming one during a crossfade, and the active one alone
//     otherwise. The drawn visuals are DOM, heavier than the pictures they
//     replaced, so the two-layer budget the old slider earned is held.
//   - **One timer.** The provider runs a single `setTimeout` chain off
//     `autoAdvances`; nothing else in the hero may own a clock. The 7000ms /
//     4000ms split between a slider and a headline is the sync defect this
//     arrangement exists to have removed.
//   - **Reduced motion never auto-advances.** Slide one, and the tabs do the
//     switching — with no crossfade, so there is never a second layer either.
//   - **A person choosing a slide stops the clock for good** (`stopped`). A
//     tab click or an arrow key is somebody reading on purpose; moving the
//     page out from under them seven seconds later is the slider arguing with
//     its reader. Hover and focus only *pause* it; a choice ends it.
//
// Pure and dependency-free so the rules that matter can be *run* rather than
// read — `test_hero_slider.py` loads this file into node and drives it.

/** The one hold: how long each slide is on before the next. 7000ms, the old
 *  slider's dwell — long enough to read a slide, short enough that a visitor
 *  who stays sees the whole story go round. */
export const HOLD_MS = 7000;

/** How long the crossfade between two slides takes: the entrance band's
 *  400ms, on the site's one curve. */
export const SWAP_MS = 400;

/** The resting state: slide one, nothing leaving, the clock running. */
export const INITIAL = { active: 0, leaving: null, stopped: false };

/**
 * The next state.
 *
 *   { type: "go", to, reduced, chosen }   a tab or an arrow key (`chosen`),
 *                                         or the timer
 *   { type: "advance", count, reduced }   the timer
 *   { type: "settle" }                    the crossfade finished
 *
 * Going to the slide already showing is a no-op, not a crossfade of a slide
 * over itself — though choosing it still stops the clock, because the reader
 * said where they want to be. Under reduced motion a change replaces the
 * slide outright, so `leaving` is never set and there is never a second layer
 * to paint.
 */
export function deckReducer(state, action) {
    switch (action.type) {
        case "go": {
            const stopped = Boolean(state.stopped || action.chosen);
            if (action.to === state.active) {
                return stopped === Boolean(state.stopped) ? state : { ...state, stopped };
            }
            return {
                active: action.to,
                leaving: action.reduced ? null : state.active,
                stopped,
            };
        }
        case "advance":
            if (state.stopped) return state;
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
 * Which slides are painted: the outgoing one under the incoming one while a
 * crossfade runs, and only the active one otherwise. **Never more than two.**
 */
export function painted(state) {
    if (state.leaving === null || state.leaving === state.active) return [state.active];
    return [state.leaving, state.active];
}

/** Whether the timer may run at all. */
export function autoAdvances({ reduced, paused, stopped = false }) {
    return !reduced && !paused && !stopped;
}

/** The slide an arrow key lands on, wrapping at both ends. */
export function stepFrom(index, key, count) {
    if (key === "ArrowRight" || key === "ArrowDown") return (index + 1) % count;
    if (key === "ArrowLeft" || key === "ArrowUp") return (index - 1 + count) % count;
    if (key === "Home") return 0;
    if (key === "End") return count - 1;
    return null;
}
