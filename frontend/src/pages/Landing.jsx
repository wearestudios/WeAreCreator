// Home — a router, not a story.
//
// This page was 1,200 lines and eight sections: hero, problem, reach, a
// how-it-works ladder, a live brief feed, a trust panel, a verticals strip and
// a closing toggle. It was the whole pitch on one scroll because it was the
// only marketing page there was, so everything anybody might want to say had
// nowhere else to go.
//
// There are five pages now. Home's job is to say what this is and send you to
// the right one, in about two screens: the hero and its slider, the counted
// proof strip, one problem-and-promise section, and the close. **Everything
// that used to live below has its own page** — the how-it-works ladder is
// /how-it-works, the trust panel is /why-weare, the audience arguments are the
// audience pages, and the live brief feed is /campaigns, which is a better
// version of it and was always one tap away.
//
// **Nothing here is fetched from a third party.** The slider used to hotlink
// four stock photographs from a CDN; every image slot on the marketing site is
// now a `PlaceholderImage` waiting on owned photography. See that component.
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

import { Navbar } from "@/components/Navbar";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import PageMeta from "@/components/marketing/PageMeta";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import ProofStrip from "@/components/marketing/ProofStrip";
import { TwoPaths } from "@/components/marketing/Sections";
import { StudioEndorsement } from "@/components/StudioEndorsement";
import {
    LANDING_HERO as HERO_IDS,
    LANDING_PAGE as PAGE_IDS,
    LANDING_CLOSING as CLOSING_IDS,
    LANDING_STUDIO as STUDIO_IDS,
    MARKETING as IDS,
} from "@/constants/testIds";

// ---------------------------------------------------------------------------
// Hero deck
// ---------------------------------------------------------------------------
//
// Four slides spanning the kinds of work briefs are actually posted for. The
// deck used to be four food shots, which quietly told a fashion or travel
// creator this wasn't for them — the range is the argument, so the deck has to
// carry it.
//
// **Every kicker is a real campaign category.** There was a "Tech & gadgets"
// slide once; `CampaignCategory` has no such value, so a tech creator arriving
// off it could filter the brief list and find the category does not exist.
// Widening the deck is only an argument for range if the range is there.
//
// Only the image and the kicker line change between slides. The headline, the
// standfirst and both paths are fixed, so the page never appears to be selling
// four different products.
const SLIDES = [
    {
        key: "launch",
        kicker: "Restaurant launch",
        headline: ["A full room", "on opening night."],
        // PLACEHOLDER IMAGE: a packed Bengaluru restaurant on opening night,
        // shot wide and warm, a creator filming at a table mid-ground. 16:9.
        note: "Packed restaurant on opening night, creator filming at a table, 16:9",
    },
    {
        key: "fashion",
        kicker: "Fashion",
        headline: ["The lookbook that moves", "the whole collection."],
        // PLACEHOLDER IMAGE: a rail of clothes and a creator shooting a
        // try-on in a Bengaluru boutique, daylight. 16:9.
        note: "Creator shooting a try-on beside a clothes rail in a boutique, 16:9",
    },
    {
        key: "travel",
        kicker: "Hotels & travel",
        headline: ["Two nights away.", "A season of bookings."],
        // PLACEHOLDER IMAGE: a hotel room opening onto a balcony at first
        // light, a phone on a tripod framing it. 16:9.
        note: "Hotel room opening onto a balcony at first light, phone on a tripod, 16:9",
    },
    {
        key: "wellness",
        kicker: "Wellness",
        headline: ["One class filmed.", "Six weeks booked out."],
        // PLACEHOLDER IMAGE: a fitness or yoga class mid-session, shot from
        // the back of the room, one participant filming. 16:9.
        note: "Fitness class mid-session shot from the back of the room, 16:9",
    },
];

const SLIDE_INTERVAL_MS = 7000;

function Hero() {
    const still = useReducedMotion();
    const [index, setIndex] = useState(0);
    const [paused, setPaused] = useState(false);

    // Parallax on the deck, not on any one slide, so crossfades don't fight it.
    const { scrollY } = useScroll();
    const imgY = useTransform(scrollY, [0, 400], [0, 60]);
    const imgOpacity = useTransform(scrollY, [0, 400], [0.85, 0.3]);

    // Reduced motion gets the first slide and nothing else: no timer, no
    // crossfade, no dots to imply something is moving.
    const animated = !still;

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
                style={{ y: imgY, opacity: imgOpacity }}
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
                the headline stays readable whatever is behind it on the left. */}
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/40 via-background/55 to-background" />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-background/85 via-background/45 to-transparent" />

            <motion.div
                aria-hidden
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.55 }}
                transition={{ duration: still ? 0 : 2 }}
                className="pointer-events-none absolute -right-40 top-24 h-[520px] w-[520px] rounded-full bg-ember-500/15 blur-[120px]"
            />

            <div className="relative mx-auto max-w-7xl px-6 pb-12 pt-10 md:pb-14 md:pt-14">
                <p
                    data-testid={HERO_IDS.eyebrow}
                    className="mb-6 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.22em] text-muted-foreground backdrop-blur"
                >
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-ember-500 animate-pulse" />
                    <span className="text-ember-500/90">Vol. 01</span>
                    <span className="h-3 w-px bg-white/15" />
                    Bengaluru · Influencer studio
                </p>

                <h1
                    data-testid={HERO_IDS.heading}
                    className="max-w-4xl font-serif text-fluid-hero tracking-tightest"
                >
                    Your creator campaigns,{" "}
                    <span className="italic text-muted-foreground">handled properly.</span>
                </h1>

                <p
                    data-testid={HERO_IDS.subheading}
                    className="mt-7 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg"
                >
                    Verified creators, rates agreed before anyone shoots, and results
                    you can show. Run it yourself, or hand it to our team.
                </p>

                {/* The line that changes per slide, demoted beneath the fixed
                    headline: it is a example of the work, not the promise. */}
                <div className="mt-6 min-h-[3.25rem]">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={current.key}
                            initial={animated ? { opacity: 0, y: 8 } : false}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            transition={{ duration: animated ? 0.7 : 0, ease: [0.22, 1, 0.36, 1] }}
                            className="flex flex-wrap items-baseline gap-x-4 gap-y-1"
                        >
                            <span
                                data-testid={HERO_IDS.kicker}
                                className="text-xs uppercase tracking-[0.2em] text-ember-500"
                            >
                                {current.kicker}
                            </span>
                            <span className="font-serif text-fluid-2xl leading-tight text-muted-foreground">
                                {current.headline[0]}{" "}
                                <span className="italic">{current.headline[1]}</span>
                            </span>
                        </motion.div>
                    </AnimatePresence>
                </div>

                {/* Two paths, not three asks. Home routes; the audience pages
                    sell — so these go to the pages, not to signup. Ordinary
                    <Link>s: the audience pages are routes now. */}
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
                            className="group h-12 w-full rounded-full border-white/15 bg-transparent px-7 text-foreground hover:bg-white/5 sm:w-auto"
                        >
                            I&apos;m a brand
                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                        </Button>
                    </Link>
                </div>

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
                                            "block h-1 rounded-full transition-all duration-500 " +
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

// ---------------------------------------------------------------------------
// The problem, and the promise
// ---------------------------------------------------------------------------
//
// The one section of argument home keeps. **What is named is disorganisation,
// never agencies** — WeAre Studios is one and the managed service is a real
// offering, so "without an agency" would be this page arguing against a thing
// /why-weare sells two clicks away.

const PROBLEMS = [
    {
        title: "Nobody checked",
        body:
            "A follower count in a DM is a number somebody typed, and a brand in a DM " +
            "is a name somebody chose.",
    },
    {
        title: "No rate in writing",
        body:
            "The fee gets settled on the day, or afterwards, or in an argument about " +
            "what was said three weeks ago.",
    },
    {
        title: "No proof it worked",
        body:
            "The campaign ends and the only record is a folder of screenshots and " +
            "somebody's impression of how it went.",
    },
];

function Problem() {
    return (
        <section
            data-testid={PAGE_IDS.problem}
            className="border-t border-white/10"
        >
            <div className="mx-auto max-w-7xl px-6 py-12 md:py-14">
                <div className="grid gap-8 md:grid-cols-12 md:items-end">
                    <div className="md:col-span-7">
                        <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                            <span className="h-px w-8 bg-ember-500" />
                            The problem
                        </p>
                        <h2 className="mt-5 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                            Most creator campaigns run on{" "}
                            <span className="italic">DMs and a spreadsheet.</span>
                        </h2>
                    </div>
                    <p className="text-sm leading-relaxed text-muted-foreground md:col-span-5">
                        It works right up until it doesn&apos;t — and when it
                        doesn&apos;t, it is somebody&apos;s day, somebody&apos;s money,
                        or somebody&apos;s opening night.
                    </p>
                </div>

                <ul className="mt-8 grid gap-4 md:grid-cols-3">
                    {PROBLEMS.map((p, i) => (
                        <li
                            key={p.title}
                            data-testid={`landing-problem-${i}`}
                            className="rounded-lg border border-white/10 bg-card grain-surface p-5"
                        >
                            <h3 className="font-serif text-fluid-xl leading-tight">
                                {p.title}
                            </h3>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                {p.body}
                            </p>
                        </li>
                    ))}
                </ul>

                {/* The promise, as the answer to what was just described —
                    the same words as the hero, because a promise reworded on
                    every screen is three promises. */}
                <p
                    data-testid={PAGE_IDS.promise}
                    className="mt-9 max-w-3xl font-serif text-fluid-3xl leading-snug"
                >
                    We built the boring parts: creators checked by a person, the rate
                    agreed and written down before anyone shoots, the content approved
                    before it is public, and a report at the end that says what it did.
                </p>

                <p className="mt-6 text-sm text-muted-foreground">
                    <Link
                        to="/how-it-works"
                        data-testid={PAGE_IDS.howItWorksLink}
                        className="text-ember-500 underline-offset-4 transition-colors duration-200 hover:underline"
                    >
                        See the whole journey, from both sides
                    </Link>
                </p>
            </div>
        </section>
    );
}

// ---------------------------------------------------------------------------

export default function Landing() {
    return (
        <div
            data-testid={PAGE_IDS.page}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <PageMeta
                title="Creator campaigns, handled properly"
                description="WeAre Creators connects verified creators with brands running paid campaigns in Bengaluru. Rates agreed in writing before anyone shoots, content approved before it goes live, and a report at the end."
                path="/"
            />
            <Navbar />

            <Hero />

            {/* Counted, never written down. The hero used to carry "500+
                verified creators" as a hardcoded figure beside "48h" and "₹0",
                on the page whose whole job is to be believed by a stranger. */}
            <ProofStrip only={["creators", "campaigns", "cities"]} />

            <Problem />

            {/* The close carries home's second deliberate image slot, dimmed
                behind the copy — the same shape the audience pages use, which
                keeps the placement without paying for it in height. */}
            <section
                data-testid={CLOSING_IDS.section}
                className="relative overflow-hidden border-t border-white/10"
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
                <div className="relative mx-auto max-w-7xl px-6 py-12 md:py-14">
                    <h2 className="max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        Which side are you on?
                    </h2>
                    <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                        Creators join free. Brands post a brief, and we check the
                        business before anything reaches a creator.
                    </p>
                    <div className="mt-8">
                        <TwoPaths testid={IDS.twoPaths} />
                    </div>
                    <div className="mt-8">
                        <StudioEndorsement testid={STUDIO_IDS.landing} />
                    </div>
                </div>
            </section>

            <Footer />
        </div>
    );
}
