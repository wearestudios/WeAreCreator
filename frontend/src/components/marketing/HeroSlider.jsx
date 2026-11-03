// The homepage hero: one slider, four slides, one timer.
//
// The deal (the page's only h1), the problem, the shoot, and — while any AI
// switch is on — what the AI does. **The CTAs and the quiet line under them
// never change per slide**: they sit outside the stage, so the ask a visitor
// is reaching for does not move under their thumb.
//
// **The old hero deck's engine, generalised rather than written twice.** The
// state is `deckReducer` in `lib/heroDeck.js` — pure, and driven by the
// tests — and the provider is the one the four-step card had: the only timer,
// pause on hover and on focus anywhere inside, reduced motion read off the
// media query. What it gained is `stopped`: a tab click or an arrow key ends
// the auto-advance for good.
//
// **How the stage holds still.** Every slide's words are in one grid cell, so
// the text column is as tall as the tallest slide's at every width and the
// visual below or beside it never moves; the inactive ones are
// `visibility: hidden`, so they lay out and never paint. The visuals are
// heavier, and **at most two are mounted**: `painted(state)`, the outgoing
// and the incoming during the 400ms crossfade, the active one alone
// otherwise. Each sits in a frame of fixed size, so a visual still arriving
// in its chunk occupies the box it will fill.
//
// **The homepage ships no animation library.** The crossfade is two CSS
// keyframes (`heroSlideIn`, `heroSlideOut` in index.css) on the site's one
// curve; the tab's progress fill is `heroProgress` over the same hold the
// timer uses, so it is proof of one clock rather than a second one.
import React, { Suspense, lazy, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Sparkles } from "lucide-react";

import { EASE } from "@/components/marketing/motion";
import { WipeWord } from "@/components/marketing/primitives";
import { Band, Cta, SectionRule, Wrap } from "@/components/marketing/SiteParts";
import { DealCard } from "@/components/marketing/siteMocks";
import { LANDING_HERO as IDS } from "@/constants/testIds";
import { ASK, HOME } from "@/content/marketing";
import { photoSlot } from "@/content/photoSlots";
import { HOLD_MS, INITIAL, SWAP_MS, autoAdvances, deckReducer, painted, stepFrom } from "@/lib/heroDeck";
import { retryImport } from "@/lib/lazyRoute";

/**
 * **Slides B–D are their own chunk, asked for once the hero has painted.**
 * The h1 is the LCP; nothing it does not need is in front of it. The request
 * starts when the browser is idle — never on a timer, because the slider's
 * one clock is the only one the hero may own — so the visuals have the rest
 * of the first hold to arrive.
 */
const loadSlides = () =>
    retryImport(() => import(/* webpackChunkName: "hero-slides" */ "@/components/marketing/heroSlides"));
const lazyVisuals = {};
function visualFor(key) {
    if (!lazyVisuals[key]) {
        lazyVisuals[key] = lazy(() => loadSlides().then((m) => ({ default: m.VISUALS[key] })));
    }
    return lazyVisuals[key];
}

/** The frame a visual sits in, empty — what shows for the moment before the
 * chunk lands. The same box and the same border, so nothing moves. */
const EmptyFrame = () => <div aria-hidden className="h-full rounded-lg border border-border bg-card" />;

/**
 * Whether the reader asked for less motion, kept current if they change it.
 * Read synchronously on the first render, so a reader who asked never sees a
 * frame of the crossfade.
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

/** A headline with its one accented word in Fraunces italic. */
function Accented({ text, accent }) {
    const at = accent ? text.lastIndexOf(accent) : -1;
    if (at < 0) return text;
    return (
        <>
            {text.slice(0, at)}
            <em className="font-normal italic text-accent-ink">{accent}</em>
            {text.slice(at + accent.length)}
        </>
    );
}

/** The h1 with its one accented word, whole in the DOM from the first paint. */
function HeroTitle({ title, accent }) {
    const at = title.lastIndexOf(accent);
    return (
        <h1 data-testid={IDS.heading} className="mkt-display text-heading">
            {title.slice(0, at)}
            {/* The padding keeps the italic g's overhang inside the wipe's
                clip; the matching negative margin keeps it from opening a
                gap before the full stop. */}
            <WipeWord className="-mr-[0.08em] pr-[0.08em]">
                {/* Fraunces true italic at 400, in the accent's ink. */}
                <em data-testid={IDS.accent} className="font-normal italic text-accent-ink">
                    {accent}
                </em>
            </WipeWord>
            {title.slice(at + accent.length)}
        </h1>
    );
}

const H2 = "mkt-display text-heading";
const LEAD = "mkt-lead mt-6 max-w-xl text-muted-foreground";

/**
 * The words of each slide. Slide A carries the page's only h1; the others are
 * h2s at the same size. "AI-powered" in the lead only while two switches back
 * it — the same rule the badge and the page title follow.
 */
function SlideWords({ slide, aiPowered }) {
    const { hero, swap, ai, slides } = HOME;
    switch (slide.key) {
        case "deal":
            return (
                <>
                    <HeroTitle title={hero.title} accent={hero.accent} />
                    {aiPowered ? (
                        <p data-testid={IDS.lead} data-track-section="hero-ai-lead" className={LEAD}>
                            {hero.aiLead}
                        </p>
                    ) : (
                        <p data-testid={IDS.lead} className={LEAD}>
                            {hero.lead}
                        </p>
                    )}
                </>
            );
        case "problem":
            return (
                <>
                    <h2 className={H2}>
                        <Accented text={swap.title} accent={swap.accent} />
                    </h2>
                    <p className={LEAD}>{swap.line}</p>
                </>
            );
        case "onLocation": {
            const slot = photoSlot(slides.onLocation.slot);
            return (
                <>
                    <h2 className={H2}>
                        <Accented text={slot.fallbackHeadline} accent={slot.fallbackAccent} />
                    </h2>
                    <p className={LEAD}>{slot.fallbackLine}</p>
                </>
            );
        }
        case "ai":
            return (
                <div data-track-section="hero-ai-slide">
                    <h2 className={H2}>
                        <Accented text={ai.title} accent={ai.accent} />
                    </h2>
                    <p className={LEAD}>{ai.lead}</p>
                </div>
            );
        default:
            return null;
    }
}

/** Slide A's visual is in the page; B–D come from the "hero-slides" chunk. */
function SlideVisual({ slide, aiCards }) {
    if (slide.key === "deal") {
        return <DealCard card={HOME.card} rowTestid={IDS.cardRow} testid={IDS.card} />;
    }
    const Visual = visualFor(slide.key);
    const props = {
        problem: { swap: HOME.swap },
        onLocation: { slide: HOME.slides.onLocation },
        ai: { ai: HOME.ai, cards: aiCards },
    }[slide.key];
    return (
        <Suspense fallback={<EmptyFrame />}>
            <Visual {...props} />
        </Suspense>
    );
}

/**
 * The slides, in order: the three that are always there, then the AI slide
 * while any switch is on — **absent, not hidden**, with every switch off.
 */
export function slidesFor(aiCards) {
    const list = HOME.slides.items.map((item) => ({ key: item.key, tab: item.tab }));
    if (aiCards.length) {
        list.push({ key: "ai", tab: aiCards.length >= 2 ? HOME.ai.aiTab : HOME.ai.tab });
    }
    return list;
}

/** The badge above the stage, on every slide, while two switches are on. */
function AiBadge({ text }) {
    return (
        <p
            data-testid={IDS.badge}
            data-track-section="hero-ai-badge"
            className="inline-flex items-center gap-2 rounded-pill border border-border bg-card px-3 py-1.5 text-meta text-foreground"
        >
            {/* A mark, not a word: the brand red as a stroke, 3.76:1 on white,
                over the 3:1 a graphic needs. */}
            <Sparkles aria-hidden className="h-3.5 w-3.5 stroke-accent" />
            {text}
        </p>
    );
}

/**
 * @param {{ n: number, aiCards: Array, aiPowered: boolean }} props
 *   `aiCards` are the AI features that are on, read through `aiLive` by the
 *   page; `aiPowered` is two or more of them.
 */
export default function HeroSlider({ n, aiCards, aiPowered }) {
    const { slides: copy, hero } = HOME;
    const list = slidesFor(aiCards);
    const count = list.length;
    const reduced = usePrefersReducedMotion();
    const [state, dispatch] = useReducer(deckReducer, INITIAL);
    const [paused, setPaused] = useState(false);
    const rootRef = useRef(null);
    const tabRefs = useRef([]);

    // **The one timer.** Under reduced motion `autoAdvances` is false and it
    // never starts; after a person chooses a slide it never starts again.
    useEffect(() => {
        if (!autoAdvances({ reduced, paused, stopped: state.stopped })) return undefined;
        const t = setTimeout(() => dispatch({ type: "advance", count, reduced }), HOLD_MS);
        return () => clearTimeout(t);
    }, [state.active, state.stopped, paused, reduced, count]);

    // The crossfade's end takes the outgoing slide's visual back out of the
    // DOM. Not a clock — a one-shot per change, cancelled if another lands.
    useEffect(() => {
        if (state.leaving === null) return undefined;
        const t = setTimeout(() => dispatch({ type: "settle" }), SWAP_MS);
        return () => clearTimeout(t);
    }, [state.leaving, state.active]);

    // Ask for slides B–D once the page is idle — after the h1 has painted
    // and the load has settled. **Measured, not assumed**: asked for in a bare
    // effect, the request started before the LCP was recorded and Lighthouse
    // charged its download and parse to the h1 (median LCP 157ms behind
    // main's). The first advance is seven seconds away, which is ample.
    useEffect(() => {
        const fetchSlides = () => loadSlides().catch(() => {});
        if (typeof window.requestIdleCallback === "function") {
            const id = window.requestIdleCallback(fetchSlides, { timeout: 4000 });
            return () => window.cancelIdleCallback(id);
        }
        if (document.readyState === "complete") {
            fetchSlides();
            return undefined;
        }
        window.addEventListener("load", fetchSlides, { once: true });
        return () => window.removeEventListener("load", fetchSlides);
    }, []);

    // Hovering anywhere in the hero, or tabbing into it, holds the clock.
    // `focusin`/`focusout` rather than `focus`/`blur`, which do not bubble.
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

    const choose = useCallback((to) => dispatch({ type: "go", to, reduced, chosen: true }), [reduced]);

    const onKeyDown = (e) => {
        const to = stepFrom(state.active, e.key, count);
        if (to === null) return;
        e.preventDefault();
        choose(to);
        tabRefs.current[to]?.focus();
    };

    const mounted = painted(state);
    const motion = (name) => ({
        animationName: name,
        animationDuration: `${SWAP_MS}ms`,
        animationTimingFunction: EASE_CSS,
        animationFillMode: "both",
    });

    return (
        <Band ground="page" id="hero" track="hero" testid={IDS.section}>
            <Wrap className="pb-16 pt-8 md:pb-24 md:pt-12">
                <div
                    ref={rootRef}
                    role="region"
                    aria-roledescription="carousel"
                    aria-label={copy.carousel}
                    data-testid={IDS.carousel}
                >
                    <SectionRule n={n} label={copy.label} />
                    <div className="mt-8 min-h-[2.125rem] md:mt-10">
                        {aiPowered ? <AiBadge text={copy.aiBadge} /> : null}
                    </div>

                    {/* The stage. Phone and tablet: words, then the visual.
                        From lg: the words beside a fixed-width visual column.
                        Every slide is laid into the same cell through a
                        subgrid, so the words' row is as tall as the tallest
                        slide's and the visual's row never moves. */}
                    <div
                        data-testid={IDS.slides}
                        data-mounted={mounted.length}
                        className="mt-6 grid grid-cols-1 grid-rows-[auto_auto] gap-y-8 lg:grid-cols-[minmax(0,1fr)_28rem] lg:grid-rows-[auto] lg:gap-x-12 xl:grid-cols-[minmax(0,1fr)_33.75rem] xl:gap-x-16"
                    >
                        {list.map((slide, i) => {
                            const active = i === state.active;
                            const shown = mounted.includes(i);
                            const incoming = active && state.leaving !== null && !reduced;
                            const leaving = !active && shown;
                            let style;
                            if (incoming) style = motion("heroSlideIn");
                            else if (leaving) style = motion("heroSlideOut");
                            return (
                                <div
                                    key={slide.key}
                                    id={IDS.slide(i)}
                                    data-testid={IDS.slide(i)}
                                    data-slide={slide.key}
                                    data-state={active ? "active" : leaving ? "leaving" : "idle"}
                                    role="tabpanel"
                                    aria-roledescription="slide"
                                    aria-label={`${i + 1} of ${count}`}
                                    aria-hidden={active ? undefined : true}
                                    inert={active ? undefined : true}
                                    style={style}
                                    className={`col-start-1 row-start-1 row-span-2 grid grid-rows-subgrid lg:col-span-2 lg:col-start-1 lg:row-span-1 lg:row-start-1 lg:grid-cols-subgrid lg:grid-rows-none ${
                                        shown ? "" : "invisible"
                                    } ${leaving ? "pointer-events-none" : "z-10"}`}
                                >
                                    <div className="min-w-0 self-start">
                                        <SlideWords slide={slide} aiPowered={aiPowered} />
                                    </div>
                                    {shown ? (
                                        <div
                                            data-testid={IDS.visual(i)}
                                            className="h-[21rem] w-full max-w-[33.75rem] sm:h-[24rem] lg:h-[26rem] lg:max-w-none lg:self-center xl:h-[24rem]"
                                        >
                                            <SlideVisual slide={slide} aiCards={aiCards} />
                                        </div>
                                    ) : null}
                                </div>
                            );
                        })}
                    </div>

                    {/* The asks and the tabs. The asks never change per slide. */}
                    <div className="mt-10 grid gap-y-10 lg:grid-cols-[minmax(0,1fr)_28rem] lg:items-end lg:gap-x-12 xl:grid-cols-[minmax(0,1fr)_33.75rem] xl:gap-x-16">
                        <div>
                            <div className="flex flex-col gap-3 sm:flex-row">
                                <Cta ask={ASK.postBrief} testid={IDS.ctaBrand} />
                                <Cta ask={ASK.talkWhatsapp} variant="outline" testid={IDS.ctaTalk} />
                            </div>
                            <p data-testid={IDS.note} className="mt-5 text-[0.9375rem] text-muted-foreground">
                                {hero.note}
                            </p>
                        </div>
                        <div
                            role="tablist"
                            aria-label={copy.tabsLabel}
                            data-testid={IDS.tabs}
                            onKeyDown={onKeyDown}
                            className={`grid gap-3 ${count === 4 ? "grid-cols-4" : "grid-cols-3"}`}
                        >
                            {list.map((slide, i) => {
                                const on = i === state.active;
                                const running = on && !reduced && !state.stopped;
                                return (
                                    <button
                                        key={slide.key}
                                        ref={(el) => {
                                            tabRefs.current[i] = el;
                                        }}
                                        type="button"
                                        role="tab"
                                        id={IDS.tab(i)}
                                        data-testid={IDS.tab(i)}
                                        aria-selected={on}
                                        aria-controls={IDS.slide(i)}
                                        tabIndex={on ? 0 : -1}
                                        onClick={() => choose(i)}
                                        className="group flex min-h-[2.75rem] flex-col gap-2.5 rounded-sm pt-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                    >
                                        <span aria-hidden className="relative block h-0.5 w-full overflow-hidden rounded-pill bg-border">
                                            {on ? (
                                                <span
                                                    key={`fill-${state.active}-${state.stopped}`}
                                                    data-testid={IDS.progress}
                                                    data-running={running ? "true" : "false"}
                                                    className="absolute inset-0 origin-left bg-accent"
                                                    style={
                                                        running
                                                            ? {
                                                                  animationName: "heroProgress",
                                                                  animationDuration: `${HOLD_MS}ms`,
                                                                  animationTimingFunction: "linear",
                                                                  animationFillMode: "both",
                                                                  animationPlayState: paused ? "paused" : "running",
                                                              }
                                                            : undefined
                                                    }
                                                />
                                            ) : null}
                                        </span>
                                        <span
                                            className={`text-[0.8125rem] leading-snug transition-colors duration-200 sm:text-meta ${
                                                on ? "font-medium text-heading" : "text-muted-foreground group-hover:text-foreground"
                                            }`}
                                        >
                                            {slide.tab}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </Wrap>
        </Band>
    );
}
