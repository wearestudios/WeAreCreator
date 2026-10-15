// One clock for the hero's picture and the hero's word.
//
// **This exists because there were two, and two timers cannot be kept in
// step — they can only be replaced by one.** `HeroSlider` held
// `HOLD_MS = 7000` and its own `setTimeout`; `KineticHeadline` held
// `HOLD_MS = 4000` and its own `setInterval`. They start together, drift
// apart by the second slide and never recover, so the headline says "Retail"
// over a photograph of a restaurant for most of the cycle. That is the lag:
// not a slow animation, two animations that disagree about what time it is.
//
// The fix is structural rather than a matter of picking matching numbers.
// Equal constants would still drift — two independent timers accumulate
// their own scheduling error, and a `setInterval` that fires while the tab is
// throttled is not the same clock as a chain of `setTimeout`s. So the cycle
// moves up here, both consumers read `index` off this context, and there is
// one place in the codebase that decides what slide it is.
//
// **6000ms is the one hold**, and it is not either of the old numbers. 7000
// is slow for a word — the sentence has resolved and you are waiting for it —
// and 4000 is frantic for a full-bleed image you are meant to look at. A wipe
// is also a stronger beat than a dissolve, so the word change rides on it and
// reads as one event rather than two.
import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
} from "react";
import { useReducedMotion } from "framer-motion";

import { PHRASES } from "@/components/marketing/KineticHeadline";

/** The one hold, for the picture and the word alike. */
export const HOLD_MS = 6000;

/** How long the wipe takes. Long enough to read as a reveal, not a cut. */
export const WIPE_MS = 700;

const SectorCycleContext = createContext(null);

/**
 * The cycle, or a throw.
 *
 * Throwing outside a provider is the convention `useAdminConsole()` already
 * sets here: a hook that returns `undefined` gets destructured at the call
 * site and fails somewhere else, with a message about a property rather than
 * about the missing provider.
 */
export function useSectorCycle() {
    const value = useContext(SectorCycleContext);
    if (!value) {
        throw new Error("useSectorCycle must be used inside a SectorCycleProvider");
    }
    return value;
}

/**
 * The cycle, or `null`.
 *
 * **For the one consumer that has to survive without a provider.**
 * `KineticHeadline` is exported and mountable on its own, and a headline that
 * throws when it is used outside the hero is a component with a hidden
 * dependency on its parent. It renders phrase one and starts nothing.
 */
export function useOptionalSectorCycle() {
    return useContext(SectorCycleContext);
}

/**
 * Owns the index, the timer, the pause and the reduced-motion branch.
 *
 * Renders a positioned wrapper rather than nothing, because **the pause
 * listeners bind to it** and an element with no box receives no pointer
 * events. It is the hero's positioning context too, so the slider's
 * `absolute inset-0` resolves against the whole band rather than against the
 * content column — which is what makes "hovering the picture pauses it" true
 * of the full-bleed half and not only of the text.
 */
export function SectorCycleProvider({
    phrases = PHRASES,
    className = "relative",
    children,
}) {
    const reduced = useReducedMotion();
    const [index, setIndex] = useState(0);
    // The slide being wiped over. `null` once the wipe has finished, which is
    // what takes the second layer back out of the DOM.
    const [leaving, setLeaving] = useState(null);
    const [paused, setPaused] = useState(false);

    const rootRef = useRef(null);
    // The index as a ref as well as state, so `goTo` can read the current
    // slide without depending on it — a callback that changed every slide
    // would restart the timer effect on every tick.
    const indexRef = useRef(0);
    const timer = useRef(null);
    const wipeTimer = useRef(null);

    const goTo = useCallback((next) => {
        const current = indexRef.current;
        if (next === current) return;
        indexRef.current = next;
        setLeaving(current);
        setIndex(next);
        clearTimeout(wipeTimer.current);
        wipeTimer.current = setTimeout(() => setLeaving(null), WIPE_MS);
    }, []);

    // **The one timer.** Under reduced motion it never starts — slide one is
    // the end state, not the first frame of an animation.
    useEffect(() => {
        if (reduced || paused) return undefined;
        timer.current = setTimeout(
            () => goTo((index + 1) % phrases.length),
            HOLD_MS,
        );
        return () => clearTimeout(timer.current);
    }, [index, paused, reduced, goTo, phrases.length]);

    useEffect(
        () => () => {
            clearTimeout(timer.current);
            clearTimeout(wipeTimer.current);
        },
        [],
    );

    // Pause while somebody is reading. `focusin`/`focusout` rather than
    // `focus`/`blur`, which do not bubble — tabbing to a CTA inside the hero
    // would not reach a handler bound up here.
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

    const value = {
        index,
        leaving,
        paused,
        reduced,
        goTo,
        phrases,
        count: phrases.length,
    };

    return (
        <SectorCycleContext.Provider value={value}>
            <div ref={rootRef} className={className}>
                {children}
            </div>
        </SectorCycleContext.Provider>
    );
}

export default SectorCycleProvider;
