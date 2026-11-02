// The hero deck: four steps of the job, one clock.
//
// **Why it rotates the step and not the sector** is written at the top of
// `lib/heroDeck.js`, so it survives a refactor of this file. In one line: the
// sector is the thing a visitor already knows about themselves; the stage of
// the job is the thing they came to find out.
//
// Three pieces, all reading one provider:
//
//   - `HeroDeckProvider` owns the index, **the only timer**, the pause and the
//     reduced-motion branch. Its state is `deckReducer`, which is pure and
//     run by the tests.
//   - `DeckStage` paints the product screens — at most two at once.
//   - `StepRail` is four real buttons with `aria-pressed`.
//
// **Restored from the four-step hero (#39), which was never merged, as the
// card beside the homepage `h1`.** The `h1` and its drawn word are untouched;
// only the card cycles. #39 also rotated a line under a new `h1`
// (`RotatingLine`); the homepage keeps its own heading, so that piece is not
// carried back. And it reads reduced motion off the media query directly
// rather than through framer-motion: the homepage ships no animation library,
// and one hook was the only thing this file used it for.
//
// **One timer, and nothing else in the hero may own one.** The old slider held
// 7000ms and the old headline 4000ms, each with its own clock; they drifted
// apart by the second slide and never recovered. Slides and lines are 1:1 now,
// so both read `index` off this context, and the progress bar under the rail
// is a CSS animation over the same `HOLD_MS` rather than a second interval.
import React, {
    Suspense,
    createContext,
    lazy,
    useCallback,
    useContext,
    useEffect,
    useReducer,
    useRef,
    useState,
} from "react";

import { EASE } from "@/components/marketing/motion";
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
import { retryImport } from "@/lib/lazyRoute";

/**
 * **The screens are their own chunk, fetched as the hero mounts.** The h1 is
 * the homepage's LCP, and everything in the first paint's bundle is between a
 * visitor and it; the four drawn screens and their icons are not needed to
 * paint the heading, so they arrive a moment after it, into a frame that is
 * already the right size. Measured with Lighthouse mobile behind gzip: with
 * the screens in the page's own chunk, the restored homepage's median LCP was
 * 18ms behind main's; this is what takes that back.
 */
const loadScreens = () =>
    retryImport(() => import(/* webpackChunkName: "hero-screens" */ "@/components/marketing/heroScreens"));
const lazyScreens = {};
function screenFor(key) {
    if (!lazyScreens[key]) {
        lazyScreens[key] = lazy(() => loadScreens().then((m) => ({ default: m.SCREENS[key] })));
    }
    return lazyScreens[key];
}

/** The frame a screen sits in, empty — what shows for the moment before the
 * screens' chunk lands. The same box and the same border, so nothing moves
 * when the screen fills it. */
const EmptyFrame = () => <div aria-hidden className="h-full rounded-lg border border-border bg-card" />;

/**
 * Whether the reader asked for less motion, kept current if they change it.
 * Read synchronously on the first render, so a reader who asked never sees a
 * frame of the wipe.
 */
function usePrefersReducedMotion() {
    const query = "(prefers-reduced-motion: reduce)";
    const read = () => typeof window !== "undefined" && Boolean(window.matchMedia?.(query).matches);
    const [reduced, setReduced] = useState(read);
    useEffect(() => {
        const mq = window.matchMedia?.(query);
        if (!mq) return undefined;
        const sync = () => setReduced(mq.matches);
        mq.addEventListener("change", sync);
        return () => mq.removeEventListener("change", sync);
    }, []);
    return reduced;
}

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
export function HeroDeckProvider({ steps, label, className = "relative", children }) {
    const reduced = usePrefersReducedMotion();
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

    const value = { steps, label, index: state.active, state, paused, reduced, goTo };
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
    const Screen = screenFor(step.key);
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
                <Suspense fallback={<EmptyFrame />}>
                    <Screen {...step.props} />
                </Suspense>
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
export function DeckStage({ className = "", testid }) {
    const { steps, state, reduced } = useHeroDeck();
    const mounted = painted(state);
    return (
        // A fixed height rather than #39's ratio: these screens are text, and
        // a ratio shrinks with the column until the tallest one is clipped at
        // 390px. The box is the tallest screen's, at every width, so swapping
        // screens moves nothing — measured: Get paid needs 325px at 360 wide
        // and 308 from 768 up, and 21rem is 336.
        <div
            data-testid={testid || IDS.slides}
            data-mounted={mounted.length}
            className={`relative h-[21rem] w-full ${className}`}
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
    const { steps, label, index, goTo, paused, reduced } = useHeroDeck();
    return (
        <div
            role="group"
            aria-label={label}
            data-testid={IDS.rail}
            // Two by two where the card is a narrow column beside the h1
            // (xl until 2xl), four across where it has the width.
            className={`grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2 2xl:grid-cols-4 ${className}`}
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
                        className={`group relative flex min-h-[2.75rem] items-baseline gap-2 overflow-hidden whitespace-nowrap rounded-md border px-3 py-2 text-left text-meta transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
                            on
                                ? "border-primary/50 bg-primary/10 text-foreground"
                                : "border-border bg-card text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                        }`}
                    >
                        <span className="font-serif tabular-nums text-muted-foreground">
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

export default HeroDeckProvider;
