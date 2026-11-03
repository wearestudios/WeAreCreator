// The homepage's "How it works": a scroll-driven process spine.
//
// A navy band. The head on the left — the numbered rule, the heading with
// its italic phrase, one line — then a switch between the brand's five steps
// and the creator's, a 1px spine down the middle with a numbered node per
// step, and the steps alternating sides: odd steps have the mockup on the
// left and the words on the right, even steps the other way round. Under the
// spine, the row of what is built in. (The before/after strip that sat
// between them went when the hero slider's "The problem" slide took over
// telling it.)
//
// **On the homepage this is the last section, and it sits directly on the
// navy footer.** Same ground, deliberately: the beam footer's 1px accent rule
// is the divider.
//
// **Every word is in `HOME.processSpine` in `content/marketing.js`**; the
// mockups are drawn by `process/StepCard*.jsx` from each step's `card`.
//
// Motion, and what it costs:
//   - **The active step is the one crossing the viewport's centre line**,
//     found by one IntersectionObserver whose root margin shrinks the
//     viewport to that line. No scroll handler reads anything for it.
//   - **The spine fills as the section is read.** A scroll listener, only
//     while the section is near the screen, schedules one rAF; the frame
//     reads the steps' box once and writes one `transform: scaleY()`. Read,
//     then write, once per frame — nothing interleaved.
//   - Each card slides in 24px from its own side the first time it is seen,
//     and the glow behind the active step moves by `transform`. Opacity and
//     transform only, so nothing here can shift the layout.
//   - **Reduced motion: everything at its end state.** Every step full
//     strength, the spine full, no slide, the figures at their final value.
//
// The switch keeps its side of the deal in the hash (`#brands` /
// `#creators`), written with `replaceState` so it neither scrolls the page
// nor adds a history entry; a link to `/#creators` opens on the creators'
// steps with the section on screen.
import React, { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import FeatureRow from "@/components/marketing/FeatureRow";
import { Band, SectionRule, Wrap } from "@/components/marketing/SiteParts";
import { Rise } from "@/components/marketing/primitives";
import { STEP_CARDS } from "@/components/marketing/process";
import { PROCESS as IDS } from "@/constants/testIds";
import { HOME } from "@/content/marketing";
import { EVENTS, track } from "@/lib/track";

const TABS = ["brands", "creators"];
const ENTER_MS = 600;
const ENTER_EASE = "cubic-bezier(.2,.7,.1,1)";
const FADE_MS = 100; // out, then in: a 200ms crossfade
const REDUCED = "(prefers-reduced-motion: reduce)";

const pad = (n) => String(n).padStart(2, "0");

/** The side of the deal a hash asks for, or null. */
export function tabFromHash(hash) {
    const key = (hash || "").replace(/^#/, "");
    return TABS.includes(key) ? key : null;
}

/** How far through the steps the reader is: 0 at the top, 1 at the bottom,
 * measured at the viewport's centre line. Pure, for the tests. */
export function spineProgress(top, height, viewport) {
    if (!(height > 0)) return 0;
    return Math.min(1, Math.max(0, (viewport / 2 - top) / height));
}

function useReducedMotion() {
    const [reduced, setReduced] = useState(
        () => typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(REDUCED).matches,
    );
    useEffect(() => {
        if (!window.matchMedia) return undefined;
        const mq = window.matchMedia(REDUCED);
        const on = () => setReduced(mq.matches);
        on();
        if (mq.addEventListener) mq.addEventListener("change", on);
        else if (mq.addListener) mq.addListener(on);
        return () => {
            if (mq.removeEventListener) mq.removeEventListener("change", on);
            else if (mq.removeListener) mq.removeListener(on);
        };
    }, []);
    return reduced;
}

/** The two-way switch. A tablist, so arrow keys move between the sides. */
function Switch({ copy, tab, onChange }) {
    const refs = useRef({});
    const onKey = (e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        const next = TABS[(TABS.indexOf(tab) + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
        onChange(next);
        if (refs.current[next]) refs.current[next].focus();
    };
    return (
        <div
            role="tablist"
            aria-label={copy.tabsLabel}
            data-testid={IDS.switch}
            onKeyDown={onKey}
            className="inline-flex rounded-pill border border-brand-white/15 bg-brand-navy p-1"
        >
            {copy.tabs.map((t) => {
                const on = t.key === tab;
                return (
                    <button
                        key={t.key}
                        ref={(el) => {
                            refs.current[t.key] = el;
                        }}
                        type="button"
                        role="tab"
                        id={`process-tab-${t.key}`}
                        aria-selected={on}
                        aria-controls="process-steps"
                        tabIndex={on ? 0 : -1}
                        data-testid={IDS.tab(t.key)}
                        onClick={() => onChange(t.key)}
                        className={`min-h-[2.5rem] rounded-pill px-5 text-[0.9375rem] font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red focus-visible:ring-offset-2 focus-visible:ring-offset-brand-navy ${
                            on ? "bg-brand-white text-brand-navy" : "text-brand-white/65 hover:text-brand-white/90"
                        }`}
                    >
                        {t.label}
                    </button>
                );
            })}
        </div>
    );
}

/** One step: its node on the spine, its words, its mockup. Memoised, so a
 * change of active step re-renders the two steps it touches and nothing
 * else — the active step changes as somebody scrolls. */
const Step = memo(function Step({ step, i, active, entered, reduced, playKpis, setRef }) {
    const Card = STEP_CARDS[step.card.kind];
    const odd = i % 2 === 0; // step 01, 03, 05: the card on the left
    const n = i + 1;
    const state = reduced ? "full" : active ? "active" : "dim";
    // On the words and the card, not the step: the node stays opaque, or
    // the spine would show through a dimmed one.
    const strength = `transition-opacity duration-500 ${state === "dim" ? "opacity-[0.7] md:opacity-[0.35]" : "opacity-100"}`;
    // The slide: 24px from the card's own side, cleared once.
    const from = odd ? -24 : 24;
    const cardStyle = reduced
        ? undefined
        : {
              transform: entered ? "none" : `translate3d(${from}px,0,0)`,
              opacity: entered ? 1 : 0,
              transition: `transform ${ENTER_MS}ms ${ENTER_EASE}, opacity ${ENTER_MS}ms ${ENTER_EASE}`,
          };
    return (
        <li
            ref={setRef}
            data-index={i}
            data-testid={IDS.step(n)}
            data-state={state}
            className="relative grid grid-cols-1 gap-6 pl-12 md:grid-cols-[minmax(0,1fr)_52px_minmax(0,1fr)] md:items-center md:gap-x-12 md:pl-0"
        >
            <span
                data-testid={IDS.node(n)}
                data-active={active || reduced ? "true" : "false"}
                className={`mkt-label absolute -left-3 top-0 z-[1] grid h-10 w-10 place-items-center rounded-full border tabular-nums transition-colors duration-300 md:static md:col-start-2 md:row-start-1 md:h-[52px] md:w-[52px] ${
                    active && !reduced
                        ? "border-brand-red bg-brand-red text-brand-white"
                        : "border-brand-white/20 bg-brand-navy text-brand-white/65"
                }`}
            >
                {pad(n)}
            </span>
            <div
                data-strength={state}
                className={`md:row-start-1 ${strength} ${odd ? "md:col-start-3" : "md:col-start-1 md:text-right"}`}
            >
                <h3 className="mkt-h3 text-brand-white/90">{step.title}</h3>
                <p className={`mkt-body mt-3 max-w-md text-brand-white/65 ${odd ? "" : "md:ml-auto"}`}>{step.line}</p>
            </div>
            <div
                data-strength={state}
                className={`w-full max-w-[26rem] md:row-start-1 ${strength} ${odd ? "md:col-start-1 md:justify-self-end" : "md:col-start-3"}`}
            >
                <div style={cardStyle}>
                    <Card
                        card={step.card}
                        active={active && !reduced}
                        testid={IDS.card(n)}
                        play={playKpis}
                        reduced={reduced}
                        kpiTestid={IDS.kpi}
                    />
                </div>
            </div>
        </li>
    );
});

export default function ProcessSpine({ n, id = "how-it-works" }) {
    const copy = HOME.processSpine;
    const reduced = useReducedMotion();
    const [tab, setTab] = useState(() =>
        typeof window === "undefined" ? "brands" : tabFromHash(window.location.hash) || "brands",
    );
    // The tab whose steps are on screen: lags `tab` by the fade-out.
    const [shown, setShown] = useState(tab);
    const [fading, setFading] = useState(false);
    const [active, setActive] = useState(0);
    const [entered, setEntered] = useState(() => new Set());
    const [kpisPlayed, setKpisPlayed] = useState(false);

    const sectionRef = useRef(null);
    const listRef = useRef(null);
    const fillRef = useRef(null);
    const glowRef = useRef(null);
    const stepEls = useRef([]);
    const steps = copy.steps[shown];
    // One stable ref callback per step, so `memo` holds across renders.
    const setRefs = useMemo(
        () =>
            Array.from({ length: 8 }, (_, i) => (el) => {
                stepEls.current[i] = el;
            }),
        [],
    );

    // ---- the switch -------------------------------------------------------

    const choose = useCallback(
        (next, { fromUser = true } = {}) => {
            if (!TABS.includes(next) || next === tab) return;
            setTab(next);
            if (fromUser) {
                try {
                    window.history.replaceState(window.history.state, "", `#${next}`);
                } catch {
                    /* a sandboxed frame may refuse; the switch still works */
                }
                // `target` carries the side into the recorder's event name.
                track(EVENTS.processTabChange, { tab: next, target: next });
            }
        },
        [tab],
    );

    // Out, swap, in — or straight across under reduced motion.
    useEffect(() => {
        if (tab === shown) return undefined;
        if (reduced) {
            setShown(tab);
            return undefined;
        }
        setFading(true);
        const t = setTimeout(() => {
            setShown(tab);
            setFading(false);
        }, FADE_MS);
        return () => clearTimeout(t);
    }, [tab, shown, reduced]);

    // A new side starts its own entrance and its own active step.
    useEffect(() => {
        setEntered(new Set());
        setActive(0);
    }, [shown]);

    // A hash written by somebody else — a link, the back button.
    useEffect(() => {
        const onHash = () => {
            const next = tabFromHash(window.location.hash);
            if (next) choose(next, { fromUser: false });
        };
        window.addEventListener("hashchange", onHash);
        return () => window.removeEventListener("hashchange", onHash);
    }, [choose]);

    // Arriving on `/#brands` or `/#creators`: bring the section on screen.
    useEffect(() => {
        if (tabFromHash(window.location.hash) && sectionRef.current && sectionRef.current.scrollIntoView) {
            sectionRef.current.scrollIntoView({ block: "start" });
        }
    }, []);

    // ---- which step is active, and which cards have entered ---------------

    useEffect(() => {
        if (reduced || typeof IntersectionObserver === "undefined") return undefined;
        const els = stepEls.current.filter(Boolean);
        // The viewport shrunk to its centre line: whatever crosses it is the
        // step being read.
        const centre = new IntersectionObserver(
            (entries) => {
                entries.forEach((e) => {
                    if (e.isIntersecting) setActive(Number(e.target.dataset.index));
                });
            },
            { rootMargin: "-50% 0px -50% 0px", threshold: 0 },
        );
        const enter = new IntersectionObserver(
            (entries) => {
                const seen = entries.filter((e) => e.isIntersecting).map((e) => Number(e.target.dataset.index));
                if (!seen.length) return;
                setEntered((prev) => {
                    const next = new Set(prev);
                    seen.forEach((i) => next.add(i));
                    return next;
                });
                entries.forEach((e) => e.isIntersecting && enter.unobserve(e.target));
            },
            { rootMargin: "0px 0px -15% 0px", threshold: 0.15 },
        );
        els.forEach((el) => {
            centre.observe(el);
            enter.observe(el);
        });
        return () => {
            centre.disconnect();
            enter.disconnect();
        };
    }, [reduced, shown]);

    // The figures on the results card count once, the first time it is read.
    useEffect(() => {
        if (shown === "brands" && active === steps.length - 1) setKpisPlayed(true);
    }, [active, shown, steps.length]);

    // ---- the spine's fill -------------------------------------------------

    useEffect(() => {
        const fill = fillRef.current;
        const list = listRef.current;
        if (!fill || !list) return undefined;
        if (reduced) {
            fill.style.transform = "scaleY(1)";
            return undefined;
        }
        let raf = 0;
        let listening = false;
        const frame = () => {
            raf = 0;
            // One read, then one write.
            const r = list.getBoundingClientRect();
            fill.style.transform = `scaleY(${spineProgress(r.top, r.height, window.innerHeight).toFixed(4)})`;
        };
        const onScroll = () => {
            if (!raf) raf = requestAnimationFrame(frame);
        };
        const listen = (on) => {
            if (on === listening) return;
            listening = on;
            if (on) {
                window.addEventListener("scroll", onScroll, { passive: true });
                window.addEventListener("resize", onScroll);
                onScroll();
            } else {
                window.removeEventListener("scroll", onScroll);
                window.removeEventListener("resize", onScroll);
            }
        };
        let io = null;
        if (typeof IntersectionObserver === "undefined") {
            listen(true);
        } else {
            // Listen only while the section is within a screen of view.
            io = new IntersectionObserver(([e]) => listen(e.isIntersecting), { rootMargin: "100% 0px 100% 0px" });
            io.observe(list);
        }
        return () => {
            if (io) io.disconnect();
            listen(false);
            if (raf) cancelAnimationFrame(raf);
        };
    }, [reduced]);

    // The glow follows the active step. Measured when the step changes, never
    // on scroll.
    useLayoutEffect(() => {
        const glow = glowRef.current;
        const el = stepEls.current[active];
        if (!glow || !el || reduced) return;
        glow.style.transform = `translate3d(-50%, ${Math.round(el.offsetTop + el.offsetHeight / 2)}px, 0) translateY(-50%)`;
    }, [active, reduced, shown]);

    const panelStyle = reduced
        ? undefined
        : { opacity: fading ? 0 : 1, transition: `opacity ${FADE_MS}ms linear` };

    return (
        <Band ground="navy" id={id} track="how" testid={IDS.section} className="scroll-mt-16 overflow-x-clip">
            <div ref={sectionRef} className="py-20 md:py-[120px]">
                <Wrap>
                    <SectionRule n={n} label={copy.label} />
                    <Rise>
                        <h2 className="mkt-h2 mt-8 max-w-4xl text-brand-white/90 md:mt-10">
                            {copy.title}{" "}
                            <em className="font-normal italic text-accent-ink">{copy.accent}</em>
                        </h2>
                    </Rise>
                    <p className="mkt-lead mt-5 max-w-2xl text-brand-white/65">{copy.lead}</p>

                    <div className="relative mt-12 md:mt-16">
                        {/* Sticky under the header on a phone, while the
                            steps it switches are on screen. */}
                        <div className="sticky top-16 z-30 -mx-4 bg-brand-navy/95 px-4 py-3 md:static md:mx-0 md:bg-transparent md:px-0 md:py-0">
                            <Switch copy={copy} tab={tab} onChange={choose} />
                        </div>

                        <div
                            id="process-steps"
                            role="tabpanel"
                            aria-labelledby={`process-tab-${tab}`}
                            style={panelStyle}
                            className="relative mt-10 md:mt-16"
                        >
                            {/* The glow behind the active step. */}
                            {reduced ? null : (
                                <div
                                    ref={glowRef}
                                    aria-hidden
                                    className="pointer-events-none absolute left-6 top-0 h-[520px] w-[520px] opacity-60 transition-transform duration-700 md:left-1/2"
                                    style={{
                                        background:
                                            "radial-gradient(closest-side, hsl(var(--brand-red) / 0.22), transparent)",
                                        filter: "blur(40px)",
                                        willChange: "transform",
                                    }}
                                />
                            )}
                            <ol ref={listRef} data-testid={IDS.steps} className="relative space-y-20 md:space-y-28">
                                {/* The spine, and its fill from the top. */}
                                <span
                                    aria-hidden
                                    data-testid={IDS.spine}
                                    className="absolute bottom-0 left-2 top-0 w-px bg-brand-white/10 md:left-1/2 md:-translate-x-1/2"
                                >
                                    <span
                                        ref={fillRef}
                                        data-testid={IDS.spineFill}
                                        data-full={reduced ? "true" : "false"}
                                        className="absolute inset-0 origin-top bg-brand-red"
                                        style={{ transform: reduced ? "scaleY(1)" : "scaleY(0)", willChange: "transform" }}
                                    />
                                </span>
                                {steps.map((step, i) => (
                                    <Step
                                        key={`${shown}-${step.key}`}
                                        step={step}
                                        i={i}
                                        active={i === active}
                                        entered={entered.has(i)}
                                        reduced={reduced}
                                        playKpis={step.card.kind === "kpis" && kpisPlayed}
                                        setRef={setRefs[i]}
                                    />
                                ))}
                            </ol>
                        </div>
                    </div>

                    <FeatureRow features={copy.features} reduced={reduced} className="mt-20 md:mt-28" />
                </Wrap>
            </div>
        </Band>
    );
}
