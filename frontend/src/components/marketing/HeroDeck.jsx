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
// apart by the second slide and never recovered. Slides and lines are 1:1 now,
// so both read `index` off this context, and the progress bar under the rail
// is a CSS animation over the same `HOLD_MS` rather than a second interval.
import React, { createContext, useCallback, useContext, useEffect, useReducer, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

import { EASE } from "@/components/marketing/motion";
import { SCREENS } from "@/components/marketing/heroScreens";
import {
    HOLD_MS,
    INITIAL,
    WIPE_MS,
    autoAdvances,
    deckReducer,
    pad,
    painted,
} from "@/lib/heroDeck";
import { LANDING_HERO as IDS } from "@/constants/testIds";

/** One curve, built from `EASE` rather than retyped. */
const EASE_CSS = `cubic-bezier(${EASE.join(", ")})`;

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
 * `focusin`/`focusout` rather than `focus`/`blur`, which do not bubble.
 */
export function HeroDeckProvider({ steps, className = "relative", children }) {
    const reduced = Boolean(useReducedMotion());
    const [state, dispatch] = useReducer(deckReducer, INITIAL);
    const [paused, setPaused] = useState(false);
    const rootRef = useRef(null);
    const count = steps.length;

    const goTo = useCallback((to) => dispatch({ type: "go", to, reduced }), [reduced]);

    // **The one timer.** Under reduced motion `autoAdvances` is false and it
    // never starts: step 01 is the end state, and the rail does the switching.
    useEffect(() => {
        if (!autoAdvances({ reduced, paused })) return undefined;
        const t = setTimeout(() => dispatch({ type: "advance", count, reduced }), HOLD_MS);
        return () => clearTimeout(t);
    }, [state.active, paused, reduced, count]);

    // The wipe's end takes the outgoing screen back out of the DOM. Not a
    // clock — a one-shot per change, cancelled if another change lands first.
    useEffect(() => {
        if (state.leaving === null) return undefined;
        const t = setTimeout(() => dispatch({ type: "settle" }), WIPE_MS);
        return () => clearTimeout(t);
    }, [state.leaving, state.active]);

    useEffect(() => {
        const node = rootRef.current;
        if (!node) return undefined;
        const hold = () => setPaused(true);
        const release = () => setPaused(false);
        node.addEventListener("pointerenter", hold);
        node.addEventListener("pointerleave", release);
        node.addEventListener("focusin", hold);
        node.addEventListener("focusout", release);
        return () => {
            node.removeEventListener("pointerenter", hold);
            node.removeEventListener("pointerleave", release);
            node.removeEventListener("focusin", hold);
            node.removeEventListener("focusout", release);
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
 * One screen, with the wipe on its way in.
 *
 * The incoming screen paints last and opens over the outgoing one, which
 * stays still and is simply uncovered — two nested transforms that cancel, so
 * the screen holds still while the window opens (`heroWipeWindow` /
 * `heroWipeHold` in index.css). No `clip-path`, which is not reliably
 * composited. **Inactive means hidden from assistive tech**: the outgoing
 * screen is `aria-hidden` while it is uncovered.
 */
function Slide({ step, index, active, incoming, reduced }) {
    const Screen = SCREENS[step.key];
    const wipe = (name) =>
        reduced || !incoming
            ? undefined
            : {
                  animationName: name,
                  animationDuration: `${WIPE_MS}ms`,
                  animationTimingFunction: EASE_CSS,
                  animationFillMode: "both",
                  willChange: "transform",
              };
    return (
        <div
            data-testid={IDS.slide(index)}
            data-step={step.key}
            aria-hidden={active ? undefined : true}
            className="absolute inset-0 overflow-hidden"
            style={wipe("heroWipeWindow")}
        >
            <div className="absolute inset-0" style={wipe("heroWipeHold")}>
                <Screen />
            </div>
        </div>
    );
}

/**
 * The stage. **At most two screens are mounted, ever** — `painted` decides,
 * and it is the outgoing and the incoming during a wipe and the active one
 * alone otherwise. Four DOM screens with three hidden would pay for all four;
 * an invisible layer still lays out and composites.
 *
 * The box is reserved by its aspect ratio, so swapping screens moves nothing.
 */
export function DeckStage({ className = "" }) {
    const { steps, state, reduced } = useHeroDeck();
    const mounted = painted(state);
    return (
        <div
            data-testid={IDS.slides}
            data-mounted={mounted.length}
            className={`relative aspect-[5/4] w-full sm:aspect-[4/3] ${className}`}
        >
            {mounted.map((i) => (
                <Slide
                    key={steps[i].key}
                    step={steps[i]}
                    index={i}
                    active={i === state.active}
                    incoming={i === state.active && state.leaving !== null}
                    reduced={reduced}
                />
            ))}
        </div>
    );
}

/**
 * 01 Offer · 02 Agree · 03 Deliver · 04 Get paid.
 *
 * Four real `<button>`s with `aria-pressed`, keyboard-operable, with a focus
 * ring offset against whatever ground they sit on. Under the active one, a 2px
 * bar fills over `HOLD_MS` — a CSS animation on the same hold the timer uses,
 * so it is visible proof of one clock rather than a second one. It does not
 * render under reduced motion, where nothing advances on its own.
 */
export function StepRail({ className = "" }) {
    const { steps, index, goTo, paused, reduced } = useHeroDeck();
    return (
        <div
            role="group"
            aria-label="The four steps"
            data-testid={IDS.rail}
            className={`grid grid-cols-2 gap-2 sm:grid-cols-4 ${className}`}
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
                        className={`group relative flex min-h-[2.75rem] items-baseline gap-2 overflow-hidden rounded-md border px-3 py-2 text-left text-sm transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
                            on
                                ? "border-primary/50 bg-primary/10 text-foreground"
                                : "border-tint/10 bg-card text-muted-foreground hover:border-tint/25 hover:text-foreground"
                        }`}
                    >
                        <span className="font-serif text-xs tabular-nums text-primary-ink">
                            {pad(i + 1)}
                        </span>
                        <span>{step.label}</span>
                        {on && !reduced && (
                            <span
                                aria-hidden
                                key={`bar-${index}`}
                                data-testid={IDS.progress}
                                className="absolute inset-x-0 bottom-0 h-0.5 origin-left bg-primary"
                                style={{
                                    animationName: "heroProgress",
                                    animationDuration: `${HOLD_MS}ms`,
                                    animationTimingFunction: "linear",
                                    animationFillMode: "both",
                                    animationPlayState: paused ? "paused" : "running",
                                }}
                            />
                        )}
                    </button>
                );
            })}
        </div>
    );
}

/**
 * The rotating line and its support, under the static `h1`.
 *
 * **Decorative, and hidden from assistive tech**: the four lines are also a
 * visually-hidden static list, so nothing is only available to somebody who
 * can see it change. No `aria-live` — announcing marketing copy every six
 * seconds is hostile.
 *
 * **The box is reserved by drawing all four into one grid cell**, the rule
 * the old headline learned: a character count is not a width, and only a
 * box the browser draws is the right size. Only the active one is visible.
 */
export function RotatingLine() {
    const { steps, index, reduced } = useHeroDeck();
    return (
        <div>
            <div aria-hidden className="grid">
                {steps.map((step, i) => {
                    const on = i === index;
                    return (
                        <div
                            key={step.key}
                            className={`col-start-1 row-start-1 ${on ? "" : "invisible"}`}
                            style={
                                on && !reduced
                                    ? {
                                          animationName: "weare-settle",
                                          animationDuration: "420ms",
                                          animationTimingFunction: EASE_CSS,
                                          animationFillMode: "both",
                                      }
                                    : undefined
                            }
                        >
                            <p
                                data-testid={on ? IDS.line : undefined}
                                className="font-serif text-2xl leading-snug text-foreground md:text-3xl"
                            >
                                {step.line}
                            </p>
                            <p
                                data-testid={on ? IDS.subheading : undefined}
                                className="mt-3 max-w-xl text-base leading-relaxed text-muted-foreground md:text-lg"
                            >
                                {step.support}
                            </p>
                        </div>
                    );
                })}
            </div>
            <ol data-testid={IDS.stepsList} className="sr-only">
                {steps.map((step, i) => (
                    <li key={step.key}>
                        {pad(i + 1)} {step.label}: {step.line} {step.support}
                    </li>
                ))}
            </ol>
        </div>
    );
}

export default HeroDeckProvider;
