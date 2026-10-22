// The hero deck: four steps of the job, one clock.
//
// **Why it rotates the step and not the sector** is written at the top of
// `lib/heroDeck.js`, so it survives a refactor of this file. In one line: the
// sector is the thing a visitor already knows about themselves; the stage of
// the job is the thing they came to find out.
//
// Four pieces, all reading one provider:
//
//   - `HeroDeckProvider` owns the index, **the only timer**, the pause and the
//     reduced-motion branch. Its state is `deckReducer`, which is pure and
//     run by the tests.
//   - `DeckStage` paints the product screens — at most two at once.
//   - `StepRail` is four real buttons with `aria-pressed`.
//   - `RotatingLine` is the decorative line under the static `h1`.
//
// **One timer, and nothing else in the hero may own one.** The old slider held
// 7000ms and the old headline 4000ms, each with its own clock; they drifted
// apart by the second slide and never recovered. Slides and lines are 1:1 now
// and both read `index` off this context. 7000ms of dwell, a 600ms crossfade.
//
// **No progress bar.** The previous deck drew one under the rail, and it was a
// fourth thing moving on a page allowed three. The active step is marked by a
// red fill, which is what the brand red is for.
import React, { createContext, useCallback, useContext, useEffect, useReducer, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

import { SCREENS } from "@/components/marketing/heroScreens";
import { FADE_MS, HOLD_MS, INITIAL, autoAdvances, deckReducer, pad, painted } from "@/lib/heroDeck";
import { LANDING_HERO as IDS } from "@/constants/testIds";

const DeckContext = createContext(null);

/** The deck, or a throw — the convention `useAdminConsole()` set. */
export function useHeroDeck() {
    const value = useContext(DeckContext);
    if (!value) throw new Error("useHeroDeck must be used inside a HeroDeckProvider");
    return value;
}

/**
 * Owns the index, the timer, the pause and the reduced-motion branch.
 *
 * Renders a positioned wrapper because **the pause listeners bind to it**:
 * hovering anywhere in the hero, or tabbing into it, stops the clock.
 * `focusin`/`focusout` rather than `focus`/`blur`, which do not bubble. The
 * wrapper is also what the visibility observer watches: off screen, the deck
 * holds still.
 */
export function HeroDeckProvider({ steps, className = "relative", children }) {
    const reduced = Boolean(useReducedMotion());
    const [state, dispatch] = useReducer(deckReducer, INITIAL);
    const [held, setHeld] = useState(false);
    const [onScreen, setOnScreen] = useState(true);
    const rootRef = useRef(null);
    const count = steps.length;
    const paused = held || !onScreen;

    const goTo = useCallback((to) => dispatch({ type: "go", to, reduced }), [reduced]);

    // **The one timer.** Under reduced motion `autoAdvances` is false and it
    // never starts: step 01 is the end state, and the rail does the switching.
    useEffect(() => {
        if (!autoAdvances({ reduced, paused })) return undefined;
        const t = setTimeout(() => dispatch({ type: "advance", count, reduced }), HOLD_MS);
        return () => clearTimeout(t);
    }, [state.active, paused, reduced, count]);

    // The crossfade's end takes the outgoing screen back out of the DOM. Not a
    // clock — a one-shot per change, cancelled if another change lands first.
    useEffect(() => {
        if (state.leaving === null) return undefined;
        const t = setTimeout(() => dispatch({ type: "settle" }), FADE_MS);
        return () => clearTimeout(t);
    }, [state.leaving, state.active]);

    useEffect(() => {
        const node = rootRef.current;
        if (!node) return undefined;
        const hold = () => setHeld(true);
        const release = () => setHeld(false);
        node.addEventListener("pointerenter", hold);
        node.addEventListener("pointerleave", release);
        node.addEventListener("focusin", hold);
        node.addEventListener("focusout", release);
        let io;
        if (typeof IntersectionObserver !== "undefined") {
            io = new IntersectionObserver((entries) => setOnScreen(entries.some((e) => e.isIntersecting)));
            io.observe(node);
        }
        return () => {
            node.removeEventListener("pointerenter", hold);
            node.removeEventListener("pointerleave", release);
            node.removeEventListener("focusin", hold);
            node.removeEventListener("focusout", release);
            if (io) io.disconnect();
        };
    }, []);

    const value = { steps, index: state.active, state, paused, reduced, goTo };
    return (
        <DeckContext.Provider value={value}>
            <div ref={rootRef} className={className}>
                {children}
            </div>
        </DeckContext.Provider>
    );
}

/**
 * One screen. The incoming one paints last and fades in over the outgoing
 * one, which stays still underneath until the fade ends and it is removed.
 * **Inactive means hidden from assistive tech.**
 */
function Slide({ step, index, active, incoming, fresh, reduced }) {
    const Screen = SCREENS[step.key];
    const fade =
        reduced || !incoming
            ? undefined
            : {
                  animationName: "mkt-crossfade",
                  animationDuration: `${FADE_MS}ms`,
                  animationTimingFunction: "var(--weare-ease)",
                  animationFillMode: "both",
              };
    return (
        <div
            data-testid={IDS.slide(index)}
            data-step={step.key}
            aria-hidden={active ? undefined : true}
            className="absolute inset-0"
            style={fade}
        >
            <Screen write={fresh} />
        </div>
    );
}

/**
 * The stage. **At most two screens are mounted, ever** — `painted` decides,
 * and it is the outgoing and the incoming during a crossfade and the active
 * one alone otherwise. Four DOM screens with three hidden would pay for all
 * four; an invisible layer still lays out and composites.
 *
 * The box has a fixed height, so swapping screens moves nothing.
 */
export function DeckStage({ className = "" }) {
    const { steps, state, reduced } = useHeroDeck();
    const mounted = painted(state);
    return (
        <div
            data-testid={IDS.slides}
            data-mounted={mounted.length}
            className={`relative h-[24rem] w-full md:h-[23rem] ${className}`}
        >
            {mounted.map((i) => (
                <Slide
                    key={steps[i].key}
                    step={steps[i]}
                    index={i}
                    active={i === state.active}
                    incoming={i === state.active && state.leaving !== null}
                    fresh={i === state.active && state.fresh === i}
                    reduced={reduced}
                />
            ))}
        </div>
    );
}

/**
 * 01 Offer · 02 Agree · 03 Deliver · 04 Get paid.
 *
 * Four real `<button>`s with `aria-pressed`, keyboard-operable, each with a
 * focus ring offset against the ground it sits on. The active one carries the
 * red as a fill — a bar on its leading edge — never as its text.
 */
export function StepRail({ className = "", label }) {
    const { steps, index, goTo } = useHeroDeck();
    return (
        <div
            role="group"
            aria-label={label}
            data-testid={IDS.rail}
            className={`grid grid-cols-2 gap-2 lg:grid-cols-1 ${className}`}
        >
            {steps.map((step, i) => {
                const on = i === index;
                return (
                    <button
                        key={step.key}
                        type="button"
                        aria-pressed={on}
                        data-testid={IDS.railStep(i)}
                        onClick={() => goTo(i)}
                        className={`relative flex min-h-[3rem] items-center gap-3 overflow-hidden rounded-md border px-4 py-2.5 text-left text-body transition-[color,border-color,background-color] [transition-duration:var(--mkt-interactive)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
                            on
                                ? "border-foreground/25 bg-card text-foreground"
                                : "border-border bg-transparent text-muted-foreground hover:border-foreground/25 hover:text-foreground"
                        }`}
                    >
                        <span
                            aria-hidden
                            data-testid={on ? IDS.railMarker : undefined}
                            className={`absolute inset-y-0 left-0 w-1 ${on ? "bg-accent" : "bg-transparent"}`}
                        />
                        <span className="font-serif text-meta tabular-nums text-muted-foreground">{pad(i + 1)}</span>
                        <span>{step.label}</span>
                    </button>
                );
            })}
        </div>
    );
}

/**
 * The rotating line under the static `h1`, set at `mkt-h3` in Fraunces
 * italic and the accent's ink.
 *
 * **Decorative, and hidden from assistive tech**: the four lines are also a
 * visually-hidden static list, so nothing is only available to somebody who
 * can see it change. No `aria-live` — announcing marketing copy every seven
 * seconds is hostile. It does not animate: it appears, because the page is
 * allowed three moments of motion and this is not one of them.
 *
 * **The box is reserved by drawing all four into one grid cell**: a character
 * count is not a width, and only a box the browser draws is the right size.
 */
export function RotatingLine({ className = "" }) {
    const { steps, index } = useHeroDeck();
    return (
        <div className={className}>
            <div aria-hidden className="grid">
                {steps.map((step, i) => (
                    <p
                        key={step.key}
                        data-testid={i === index ? IDS.line : undefined}
                        className={`col-start-1 row-start-1 mkt-h3 italic text-accent-ink ${i === index ? "" : "invisible"}`}
                    >
                        {step.line}
                    </p>
                ))}
            </div>
            <ol data-testid={IDS.stepsList} className="sr-only">
                {steps.map((step, i) => (
                    <li key={step.key}>
                        {pad(i + 1)} {step.label}: {step.line}
                    </li>
                ))}
            </ol>
        </div>
    );
}

export default HeroDeckProvider;
