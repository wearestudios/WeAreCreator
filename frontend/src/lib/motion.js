/**
 * The authenticated product's motion, defined once.
 *
 * The complaint this answers: the app is *snappy in a bad way*. Screens cut
 * rather than settle, lists appear all at once the instant a fetch lands, a
 * button does nothing until the server answers and then everything changes.
 * None of that is slow — it is abrupt, which reads as cheap and, on a bad
 * connection, as broken.
 *
 * **This is not the marketing site's motion layer and must not become it.**
 * `components/marketing/motion.js` is framer-motion, scroll-driven, and
 * written for a page somebody reads once. This is for screens somebody works
 * in for an hour. Three practical consequences:
 *
 * - **CSS only.** The keyframes live in `index.css`; this file is constants
 *   and the small amount of scheduling that cannot be expressed in a class.
 *   A CSS animation on transform and opacity is composited; a JS tween runs
 *   on the main thread next to React, which is where the jank on a mid-range
 *   Android comes from. It also keeps framer-motion out of the brand,
 *   manager and admin chunks — the code-splitting work took those down
 *   33–58% and a fade is not worth handing that back — and out of
 *   `components/admin/` entirely, where a test bans it.
 *
 * - **180–220ms, one curve.** Below 180 an entrance is a flicker. Above 220
 *   the reader is waiting. The curve is the same deceleration the marketing
 *   site uses, so the two halves of the product feel related without sharing
 *   an implementation.
 *
 * - **Transforms and opacity, never anything else.** Height, top, width and
 *   colour force layout or paint every frame.
 *
 * Reduced motion is handled in `index.css` rather than per component, and the
 * fallback is the end state — present, in place, immediately — not a shorter
 * animation.
 */

/** The stagger between adjacent rows, in milliseconds.
 *
 *  30ms, which is under two frames at 60fps. The marketing site uses 70,
 *  which is right for six sections somebody scrolls past and wrong for
 *  twenty rows somebody is scanning: at 70 the twentieth row is 1.4s late and
 *  the list is unreadable while it assembles. */
export const STAGGER_MS = 30;

/**
 * How many rows may carry a stagger before the rest arrive together.
 *
 * **The cap is the whole reason a stagger is safe on a list.** Without it a
 * 200-row table cascades for six seconds, and the rows at the bottom — the
 * ones somebody scrolled to — are the last to exist. Eight rows is roughly
 * the first screenful on a phone: the part a reader actually watches arrive.
 * Everything past it settles on the same frame as the eighth, so a long list
 * still fades in as one object.
 *
 * 8 × 30ms = 240ms of stagger over a 200ms animation, so the last staggered
 * row finishes at 440ms. That is the number to argue with if this ever feels
 * slow.
 */
export const STAGGER_CAP = 8;

/** Durations, in milliseconds, mirroring the CSS custom properties. Exported
 *  so a test can assert the band rather than read a stylesheet. */
export const DUR = {
    settle: 200,
    route: 190,
};

/** The one curve, mirroring `--weare-ease`. */
export const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";

/**
 * The inline style for a staggered child.
 *
 * A style rather than a class because the delay is per index and Tailwind
 * cannot express an arbitrary runtime value — and a class per index would be
 * eight classes somebody has to keep in step with `STAGGER_CAP`.
 *
 * Returns `undefined` for index 0 rather than `animationDelay: "0ms"`, so the
 * common case adds no inline style attribute at all.
 */
export const settleDelay = (index = 0) => {
    const steps = Math.min(Math.max(index, 0), STAGGER_CAP);
    return steps ? { animationDelay: `${steps * STAGGER_MS}ms` } : undefined;
};

/**
 * Tween a number for display.
 *
 * Pure, so the arithmetic can be tested without a browser. `t` is 0→1 and the
 * easing is the same deceleration as everything else, expressed directly
 * rather than as a bezier — a cubic ease-out is what that curve approximates
 * and evaluating a bezier per frame to animate four characters is work for
 * nothing.
 */
export const tween = (from, to, t) => {
    const clamped = t <= 0 ? 0 : t >= 1 ? 1 : t;
    const eased = 1 - Math.pow(1 - clamped, 3);
    return from + (to - from) * eased;
};

/**
 * How long a count should take to travel.
 *
 * **Not a constant**, because 0→3 and 0→48,000 are different journeys. A flat
 * 600ms makes a three-step counter look broken and a long one look slow. The
 * band is deliberately narrow: this is a number settling, not a slot machine.
 */
export const countDuration = (from, to) => {
    const distance = Math.abs((to || 0) - (from || 0));
    if (distance === 0) return 0;
    if (distance <= 3) return 260;
    return Math.min(700, 300 + distance * 6);
};

/**
 * The two formatters a tweened number needs, so no call site writes its own.
 *
 * **Both round**, and that is the point of exporting them: `value` is a float
 * for every frame but the last, so a formatter that does not round prints
 * "3.7142857" in a badge. Passing `String` is the obvious mistake and it is
 * one somebody makes once per call site.
 */
export const INT = (n) => String(Math.round(n));
export const GROUPED = (n) => Math.round(n).toLocaleString("en-IN");

/**
 * Whether this reader has asked for less motion.
 *
 * Read synchronously so nothing animates for a frame before being told not
 * to — the same reason `useWide` reads `matchMedia` on first render. Safe
 * where `matchMedia` does not exist (a test renderer, an old browser), which
 * reads as "no preference expressed" rather than throwing.
 */
export const prefersReducedMotion = () => {
    try {
        return Boolean(
            window.matchMedia &&
                window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        );
    } catch {
        return false;
    }
};
