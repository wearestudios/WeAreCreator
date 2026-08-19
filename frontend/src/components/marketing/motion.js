// The marketing site's motion, defined once.
//
// The brief is "quiet": entrances a few frames apart, numbers that count up
// when they arrive, cards that lift a little and warm toward ember, images
// that ease in about 2%. Nothing loops, nothing bounces, nothing announces
// itself. The failure mode this guards against is a page where each section
// was animated by whoever wrote it, so six easings and four durations read as
// six different sites.
//
// **Transforms and opacity only.** Animating height, width, top or a colour
// forces layout or paint on every frame; transform and opacity are composited,
// which is what keeps this smooth on the mid-range Android most creators
// arrive on. The hover border warm is the one colour change, and it is a CSS
// transition on a single property rather than an animated value.
//
// **Everything here is entrance-only and interaction-only.** A marketing page
// that keeps moving after you have finished reading it is a page you leave.

/** One curve for the whole site. A gentle deceleration — fast out of the
 *  gate, settling rather than stopping. */
export const EASE = [0.22, 1, 0.36, 1];

/** 200–400ms. Below 200 an entrance reads as a flicker; above 400 the reader
 *  is waiting for the page rather than reading it. */
export const DUR = {
    fast: 0.2,
    base: 0.32,
    slow: 0.4,
};

/** The gap between staggered children — "a few frames apart" at 60fps. */
export const STAGGER = 0.07;

/**
 * Rise and fade, the one entrance.
 *
 * `custom` is the child's index, which is what turns a list into a stagger
 * without a parent orchestrator — so a single card in a section and the fourth
 * card in a grid use the identical variant.
 */
export const rise = {
    hidden: { opacity: 0, y: 14 },
    show: (i = 0) => ({
        opacity: 1,
        y: 0,
        transition: { delay: i * STAGGER, duration: DUR.base, ease: EASE },
    }),
};

/** The same, without the travel — for things whose position is load-bearing,
 *  like an image already occupying its slot. */
export const fade = {
    hidden: { opacity: 0 },
    show: (i = 0) => ({
        opacity: 1,
        transition: { delay: i * STAGGER, duration: DUR.slow, ease: EASE },
    }),
};

/** Reduced motion: present, in place, immediately. Not "no animation" — the
 *  end state, with nothing in between. */
export const still = {
    hidden: { opacity: 1, y: 0 },
    show: { opacity: 1, y: 0, transition: { duration: 0 } },
};

/** How far into the viewport something must come before it enters. A margin
 *  of -60px means it animates while arriving rather than after it has already
 *  been read, and `once` means scrolling back up does not replay the page. */
export const VIEWPORT = { once: true, margin: "-60px" };

/**
 * The hover treatment for a card: a slight lift and a border warming toward
 * ember.
 *
 * A class string rather than a motion variant because both properties are
 * cheap CSS transitions and the design guidelines are explicit that hover
 * states are explicit colour shifts on named properties — never
 * `transition-all`, which would also animate the background, the shadow and
 * anything a future edit adds.
 */
export const CARD_HOVER =
    "transition-[transform,border-color] duration-200 ease-out " +
    "hover:-translate-y-0.5 hover:border-ember-500/40 " +
    "motion-reduce:transform-none motion-reduce:transition-none";

/**
 * The hover treatment for an image inside its frame: a slow ~1.02x zoom.
 *
 * Goes on the image, and the frame must clip. `group-hover` so hovering the
 * card moves the picture — hovering the picture alone would mean an image that
 * only responds when you are already looking at it.
 *
 * Written as `[transition-duration:400ms]` rather than the arbitrary
 * `duration-*` form, which matches both transition-duration and
 * animation-duration — Tailwind cannot tell which was meant and warns on
 * every build. The warning is emitted for the string wherever it appears,
 * including inside a comment, so the ambiguous form is not written here
 * either.
 */
export const IMAGE_ZOOM =
    "transition-transform [transition-duration:400ms] ease-out group-hover:scale-[1.02] " +
    "motion-reduce:transform-none motion-reduce:transition-none";
