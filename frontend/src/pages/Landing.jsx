// Home — a router, not a story.
//
// Four screens: what this is, the counted proof, what is wrong with the
// alternative, and two doors. **Under 120 words of body copy**, which is the
// constraint that made the rest of the decisions — every sentence here has to
// earn the click, and the detail it wants to add lives on the audience pages,
// in onboarding, and in the product.
//
// The slider is four category labels and nothing else now. Each slide used to
// carry its own headline as well ("A full room on opening night"), which is a
// second idea on a screen that already has one, and four of them meant the
// page appeared to be selling four products.
//
// **Nothing here is fetched from a third party.** The slider hotlinked four
// stock photographs until the image slots replaced them.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
    AnimatePresence,
    motion,
    useReducedMotion,
    useScroll,
    useTransform,
} from "framer-motion";
import { ArrowRight } from "lucide-react";

import MarketingNavbar from "@/components/marketing/MarketingNavbar";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { Button } from "@/components/ui/button";
import PageMeta from "@/components/marketing/PageMeta";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import ProofStrip from "@/components/marketing/ProofStrip";
import Reveal from "@/components/marketing/Reveal";
import { Eyebrow, Points, TwoPaths } from "@/components/marketing/Sections";
import { StudioEndorsement } from "@/components/StudioEndorsement";
import {
    LANDING_HERO as HERO_IDS,
    LANDING_PAGE as PAGE_IDS,
    LANDING_CLOSING as CLOSING_IDS,
    LANDING_STUDIO as STUDIO_IDS,
    MARKETING as IDS,
} from "@/constants/testIds";

// ---------------------------------------------------------------------------
// Copy
// ---------------------------------------------------------------------------
//
// Kept together so the word budget can be read in one place rather than
// counted across a file. A unit test enforces it — headlines to eight words,
// lines to twenty, and the page total under 120.

const COPY = {
    title: "Your creator campaigns, handled properly.",
    line: "Verified creators, the rate agreed before anyone shoots, and results you can show.",

    problemTitle: "Most campaigns run on DMs and spreadsheets.",
    problems: [
        {
            label: "Nobody checked",
            line: "A follower count in a DM is a number somebody typed.",
        },
        {
            label: "No rate in writing",
            line: "Settled on the day, or argued about three weeks later.",
        },
        {
            label: "No proof",
            line: "It ends, and nobody can say what it actually did.",
        },
    ],
    promise: "We built the boring parts.",

    closeTitle: "Which side are you on?",
    closeLine: "Creators join free. We check a brand before it reaches anyone.",
};

// **Every kicker is a real campaign category.** There was a "Tech & gadgets"
// slide once; `CampaignCategory` has no such value, so a creator arriving off
// it could filter the brief list and find the category does not exist.
const SLIDES = [
    {
        key: "launch",
        kicker: "Restaurant launch",
        // PLACEHOLDER IMAGE: a packed Bengaluru restaurant on opening night,
        // shot wide and warm, a creator filming at a table mid-ground. 16:9.
        note: "Packed restaurant on opening night, creator filming at a table, 16:9",
    },
    {
        key: "fashion",
        kicker: "Fashion",
        // PLACEHOLDER IMAGE: a rail of clothes and a creator shooting a
        // try-on in a Bengaluru boutique, daylight. 16:9.
        note: "Creator shooting a try-on beside a clothes rail in a boutique, 16:9",
    },
    {
        key: "travel",
        kicker: "Hotels & travel",
        // PLACEHOLDER IMAGE: a hotel room opening onto a balcony at first
        // light, a phone on a tripod framing it. 16:9.
        note: "Hotel room opening onto a balcony at first light, phone on a tripod, 16:9",
    },
    {
        key: "wellness",
        kicker: "Wellness",
        // PLACEHOLDER IMAGE: a fitness or yoga class mid-session, shot from
        // the back of the room, one participant filming. 16:9.
        note: "Fitness class mid-session shot from the back of the room, 16:9",
    },
];

const SLIDE_INTERVAL_MS = 7000;

function Hero() {
    const reduced = useReducedMotion();
    const [index, setIndex] = useState(0);
    const [paused, setPaused] = useState(false);

    // Parallax on the deck, not on any one slide, so crossfades don't fight it.
    const { scrollY } = useScroll();
    const imgY = useTransform(scrollY, [0, 400], [0, 60]);
    const imgOpacity = useTransform(scrollY, [0, 400], [0.85, 0.3]);

    // Reduced motion gets the first slide and nothing else: no timer, no
    // crossfade, no dots to imply something is moving.
    const animated = !reduced;

    useEffect(() => {
        if (!animated || paused) return undefined;
        const t = setInterval(
            () => setIndex((i) => (i + 1) % SLIDES.length),
            SLIDE_INTERVAL_MS,
        );
        return () => clearInterval(t);
    }, [animated, paused]);

    const slides = animated ? SLIDES : SLIDES.slice(0, 1);
    const current = slides[Math.min(index, slides.length - 1)];

    // Pausing covers focus as well as hover: somebody tabbing through the CTAs
    // shouldn't have the thing they're reading swapped out from under them.
    const hold = useCallback(() => setPaused(true), []);
    const release = useCallback(() => setPaused(false), []);

    return (
        <section
            data-testid={HERO_IDS.section}
            aria-roledescription={animated ? "carousel" : undefined}
            aria-label={animated ? "Campaign types" : undefined}
            onMouseEnter={hold}
            onMouseLeave={release}
            onFocusCapture={hold}
            onBlurCapture={release}
            className="relative overflow-hidden"
        >
            <motion.div
                style={animated ? { y: imgY, opacity: imgOpacity } : { opacity: 0.6 }}
                data-testid={HERO_IDS.slides}
                className="absolute inset-0"
            >
                <AnimatePresence initial={false}>
                    <motion.div
                        key={current.key}
                        data-testid={HERO_IDS.slide(SLIDES.indexOf(current))}
                        initial={animated ? { opacity: 0 } : false}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        // Slow enough to read as a dissolve rather than a cut.
                        transition={{ duration: animated ? 1.6 : 0, ease: "linear" }}
                        className="absolute inset-0"
                    >
                        <PlaceholderImage
                            note={current.note}
                            fill
                            testid={HERO_IDS.slideImage(SLIDES.indexOf(current))}
                        />
                    </motion.div>
                </AnimatePresence>
            </motion.div>

            {/* Two overlays doing two jobs: the vertical one lands the image
                into the page, the horizontal one is a scrim behind the text so
                the headline stays readable whatever is behind it. */}
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/40 via-background/55 to-background" />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-background/85 via-background/45 to-transparent" />

            <div className="relative mx-auto max-w-7xl px-6 pb-12 pt-10 md:pb-14 md:pt-14">
                <Reveal onView={false}>
                    <p
                        data-testid={HERO_IDS.eyebrow}
                        className="mb-6 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.22em] text-muted-foreground backdrop-blur"
                    >
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-ember-500" />
                        Bengaluru · Influencer studio
                    </p>
                </Reveal>

                <Reveal i={1} onView={false}>
                    <h1
                        data-testid={HERO_IDS.heading}
                        className="max-w-4xl font-serif text-fluid-hero tracking-tightest"
                    >
                        Your creator campaigns,{" "}
                        <span className="italic text-muted-foreground">
                            handled properly.
                        </span>
                    </h1>
                </Reveal>

                <Reveal i={2} onView={false}>
                    <p
                        data-testid={HERO_IDS.subheading}
                        className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground md:text-lg"
                    >
                        {COPY.line}
                    </p>
                </Reveal>

                {/* The category, and nothing else. The slide used to carry a
                    headline of its own beneath this. */}
                <div className="mt-6 min-h-[1.75rem]">
                    <AnimatePresence mode="wait">
                        <motion.p
                            key={current.key}
                            data-testid={HERO_IDS.kicker}
                            initial={animated ? { opacity: 0, y: 6 } : false}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            transition={{ duration: animated ? 0.32 : 0, ease: [0.22, 1, 0.36, 1] }}
                            className="text-xs uppercase tracking-[0.2em] text-ember-500"
                        >
                            {current.kicker}
                        </motion.p>
                    </AnimatePresence>
                </div>

                {/* Two paths, not three asks. Home routes; the audience pages
                    sell — so these go to the pages, not to signup. */}
                <Reveal i={3} onView={false}>
                    <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
                        <Link to="/for-creators" data-testid={HERO_IDS.ctaCreator}>
                            <Button
                                size="lg"
                                className="group h-12 w-full rounded-full bg-ember-500 px-7 text-black transition-colors duration-200 hover:bg-ember-400 sm:w-auto"
                            >
                                I&apos;m a creator
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                            </Button>
                        </Link>
                        <Link to="/for-brands" data-testid={HERO_IDS.ctaBrand}>
                            <Button
                                size="lg"
                                variant="outline"
                                className="group h-12 w-full rounded-full border-white/15 bg-transparent px-7 text-foreground transition-colors duration-200 hover:bg-white/5 sm:w-auto"
                            >
                                I&apos;m a brand
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                            </Button>
                        </Link>
                    </div>
                </Reveal>

                {animated && (
                    <div
                        data-testid={HERO_IDS.dots}
                        role="tablist"
                        aria-label="Choose a campaign type"
                        className="mt-8 flex items-center gap-3"
                    >
                        {SLIDES.map((s, i) => {
                            const on = i === index;
                            return (
                                <button
                                    key={s.key}
                                    type="button"
                                    role="tab"
                                    aria-selected={on}
                                    aria-label={s.kicker}
                                    data-testid={HERO_IDS.dot(i)}
                                    onClick={() => setIndex(i)}
                                    className="group -m-2 grid h-11 w-11 place-items-center rounded-full p-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:h-auto md:w-auto"
                                >
                                    <span
                                        className={
                                            "block h-1 rounded-full transition-[width,background-color] duration-300 ease-out " +
                                            (on
                                                ? "w-10 bg-ember-500"
                                                : "w-4 bg-white/20 group-hover:bg-white/40")
                                        }
                                    />
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        </section>
    );
}

/**
 * The problem, and the promise — one screen, one idea.
 *
 * **What is named is disorganisation, never agencies.** WeAre Studios is one
 * and the managed service is a real offering, so "without an agency" would be
 * home arguing against a thing /why-weare sells two clicks away.
 */
function Problem() {
    return (
        <section data-testid={PAGE_IDS.problem} className="border-t border-white/10">
            <div className="mx-auto max-w-7xl px-6 py-14 md:py-16">
                <Reveal>
                    <Eyebrow>The problem</Eyebrow>
                </Reveal>
                <Reveal i={1}>
                    <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        {COPY.problemTitle}
                    </h2>
                </Reveal>

                <div className="mt-8">
                    <Points items={COPY.problems} />
                </div>

                <Reveal i={1}>
                    <p
                        data-testid={PAGE_IDS.promise}
                        className="mt-10 font-serif text-fluid-3xl leading-snug"
                    >
                        {COPY.promise}{" "}
                        <Link
                            to="/how-it-works"
                            data-testid={PAGE_IDS.howItWorksLink}
                            className="text-ember-500 underline-offset-4 transition-colors duration-200 hover:underline"
                        >
                            See how
                        </Link>
                    </p>
                </Reveal>
            </div>
        </section>
    );
}

export default function Landing() {
    return (
        <div
            data-testid={PAGE_IDS.page}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <PageMeta
                title="Creator campaigns, handled properly"
                description="Verified creators, the rate agreed in writing before anyone shoots, and a report at the end. Paid brand campaigns in Bengaluru."
                path="/"
            />
            <MarketingNavbar />

            <Hero />

            {/* Counted, never written down. The hero carried a hardcoded
                "500+ verified creators" until this replaced it. */}
            <ProofStrip only={["creators", "campaigns", "cities"]} />

            <Problem />

            <section
                data-testid={CLOSING_IDS.section}
                className="group relative overflow-hidden border-t border-white/10"
            >
                <div aria-hidden className="absolute inset-0 opacity-40">
                    <PlaceholderImage
                        // PLACEHOLDER IMAGE: a WeAre manager and a creator at a
                        // check-in desk on a shoot day — the boring part,
                        // working. Busy centre, dark edges.
                        note="WeAre manager and creator at a check-in desk on a shoot day, dark edges, banner"
                        fill
                    />
                </div>
                <div
                    aria-hidden
                    className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background via-background/85 to-background"
                />
                <div className="relative mx-auto max-w-7xl px-6 py-14 md:py-16">
                    <Reveal>
                        <h2 className="max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                            {COPY.closeTitle}
                        </h2>
                    </Reveal>
                    <Reveal i={1}>
                        <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                            {COPY.closeLine}
                        </p>
                    </Reveal>
                    <div className="mt-8">
                        <TwoPaths testid={IDS.twoPaths} />
                    </div>
                    <div className="mt-8">
                        <StudioEndorsement testid={STUDIO_IDS.landing} />
                    </div>
                </div>
            </section>

            <MarketingFooter />
        </div>
    );
}
