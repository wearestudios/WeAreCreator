// Home — a router, not a story.
//
// Four screens: what this is, the counted proof, what is wrong with the
// alternative, and two doors. **Under 120 words of body copy**, which is the
// constraint that made the rest of the decisions — every sentence here has to
// earn the click, and the detail it wants to add lives on the audience pages,
// in onboarding, and in the product.
//
// **The hero slider is back, and the terms it came back on are the record.**
// It was removed once, on a measurement rather than a taste: four
// full-viewport layers cross-fading every seven seconds, on the page most
// likely to be opened on mobile data. `FloatingCards` replaced it and said
// the same thing better — four categories at once instead of one at a time.
//
// It returns carrying no copy of its own. Each slide used to have a headline
// ("A full room on opening night"), which is a second idea on a screen that
// already has one, and four of them made the page look like it was selling
// four products. The deck is now built from `PHRASES` — the same four kinds
// of work the headline morphs through — so the picture changes *with* the
// words rather than beside them. One idea, moving.
//
// What it costs is written down in `HeroSlider.jsx` and was measured before
// it shipped: at most two layers in the DOM, the pan on the image layer and
// never the container, `will-change` released on `animationend`, and nothing
// at all under `prefers-reduced-motion`.
//
// **Nothing here is fetched from a third party.** The old slider hotlinked
// four stock photographs; every slot on this page is a `PlaceholderImage` — a
// computed tint and a brief somebody could hand to a photographer.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import MarketingNavbar from "@/components/marketing/MarketingNavbar";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { Button } from "@/components/ui/button";
import PageMeta from "@/components/marketing/PageMeta";
import ProofStrip from "@/components/marketing/ProofStrip";
import Reveal from "@/components/marketing/Reveal";
import KineticHeadline from "@/components/marketing/KineticHeadline";
import { HERO_EYEBROW } from "@/lib/siteNav";
import FloatingCards from "@/components/marketing/FloatingCards";
import HeroSlider from "@/components/marketing/HeroSlider";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import HandshakeBand from "@/components/marketing/HandshakeBand";
import CampaignFilm from "@/components/marketing/CampaignFilm";
import CreatorLeaderboard from "@/components/marketing/CreatorLeaderboard";
import CaseStudyStrip from "@/components/marketing/CaseStudyStrip";
import { Eyebrow, Points, TwoPaths } from "@/components/marketing/Sections";
import {
    LANDING_HERO as HERO_IDS,
    LANDING_PAGE as PAGE_IDS,
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
            label: "Creators nobody has checked",
            line: "A follower count in a DM is a number somebody typed.",
        },
        {
            label: "No rate in writing",
            line: "Settled on the day, or argued about three weeks later.",
        },
        {
            label: "No proof it worked",
            line: "It ends, and nobody can say what it actually did.",
        },
    ],
    promise: "We built the process that closes all three.",

    filmTitle: "One campaign, start to finish.",

    closeTitle: "Where would you like to begin?",
    closeLine: "Creators join free. We check a brand before it reaches anyone.",
};

/**
 * The hero — a moving photograph, the kinetic headline, floating cards, two
 * doors.
 *
 * **The slider was removed from here and has been put back.** The reason it
 * went is still the reason it is built the way it is: a full-bleed deck cost
 * four compositing layers cross-fading every seven seconds, and
 * `FloatingCards` said "we do all of these" better by showing four categories
 * at once. So the cards stay, and the slider sits behind them under a budget
 * — see `HeroSlider.jsx`, which holds two layers at most and stops entirely
 * when somebody hovers or tabs in.
 *
 * The two say different things now rather than the same thing twice: the
 * cards are the range, the slider is one of them at a time, in step with the
 * headline morphing through the same four phrases.
 *
 * Everything in the content column is fixed across slides. Only the
 * background moves, which is what keeps this one idea instead of two.
 */
function Hero() {
    return (
        <section
            data-testid={HERO_IDS.section}
            className="relative overflow-hidden border-b border-white/10"
        >
            {/* Behind everything, including the cards. It carries its own
                scrim — on its own layer, not on the slide, because the slide
                already sets `background-image` and one of the two would
                silently win. */}
            <HeroSlider />

            {/* Decorative and absolutely positioned, so they never move the
                headline. Above the slider and below the type. */}
            <FloatingCards />

            <div
                aria-hidden
                className="pointer-events-none absolute -right-40 -top-32 h-[560px] w-[560px] rounded-full bg-primary/10 blur-[130px]"
            />

            <div className="relative mx-auto max-w-7xl px-6 pb-16 pt-14 md:pb-24 md:pt-20">
                <Reveal onView={false}>
                    <p
                        data-testid={HERO_IDS.eyebrow}
                        className="mb-8 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.22em] text-muted-foreground backdrop-blur"
                    >
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
                        {HERO_EYEBROW}
                    </p>
                </Reveal>

                <Reveal i={1} onView={false}>
                    <KineticHeadline />
                </Reveal>

                <Reveal i={2} onView={false}>
                    <p
                        data-testid={HERO_IDS.subheading}
                        className="mt-10 max-w-xl text-base leading-relaxed text-muted-foreground md:text-lg"
                    >
                        {COPY.line}
                    </p>
                </Reveal>

                {/* Two paths, not three asks. Home routes; the audience pages
                    sell — so these go to the pages, not to signup. */}
                <Reveal i={3} onView={false}>
                    <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                        <Link to="/for-creators" data-testid={HERO_IDS.ctaCreator}>
                            <Button
                                size="lg"
                                className="group h-12 w-full rounded-full bg-primary px-7 text-primary-foreground transition-colors duration-200 hover:bg-primary-hover sm:w-auto"
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

                {/* **The points and a picture, side by side.** The strongest
                    claim on the page was three lines of type alone. No copy
                    comes with the slot — home is at 105 words against 120,
                    and a caption here would be the page explaining a
                    photograph instead of showing one.

                    The picture is second in the DOM and first is the text, so
                    a phone reads the claim before the illustration rather
                    than scrolling past a tint to reach it. */}
                <div className="mt-8 grid items-start gap-8 md:grid-cols-[1fr_minmax(0,22rem)] md:gap-12">
                    <Points items={COPY.problems} />
                    <Reveal i={2}>
                        {/* PLACEHOLDER IMAGE: A creator shooting on location,
                            phone on a gimbal, venue staff visible behind */}
                        <PlaceholderImage
                            testid={PAGE_IDS.problemImage}
                            note="A creator shooting on location, phone on a gimbal, venue staff visible behind"
                            ratio="3/2"
                        />
                    </Reveal>
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
                            className="text-primary underline-offset-4 transition-colors duration-200 hover:underline"
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

            {/* The centrepiece: the product performing itself. Pinned and
                scroll-driven where that runs well, the identical seven beats
                as a stepped list everywhere else. */}
            <CampaignFilm title={COPY.filmTitle} />

            {/* A full-bleed band between the film and the problem — the film
                ends on a drawn interface and the problem opens on type, and
                one photograph between them is the beat that stops the page
                reading as a diagram followed by an argument. No words: the
                120-word budget is the constraint, and this is doing the job
                a sentence would have done badly. */}
            <div className="mx-auto max-w-7xl px-6">
                {/* PLACEHOLDER IMAGE: Wide shot of a busy venue mid-campaign,
                    creators and guests mixed, shot from above */}
                <PlaceholderImage
                    testid={PAGE_IDS.bandImage}
                    note="Wide shot of a busy venue mid-campaign, creators and guests mixed, shot from above"
                    ratio="21/9"
                />
            </div>

            <Problem />

            {/* **Three campaigns we actually ran**, which is the strongest
                thing this operation has to say and had been on no page. The
                film above shows how a campaign works; this shows that they
                have. Below the fold and fetched only when it gets close, and
                absent entirely below three — a shelf of one advertises an
                operation that has run one campaign. */}
            <CaseStudyStrip />

            {/* The creators, with their permission. Below the fold and
                fetched only when it gets close — a marketing page must not
                pay for this on the critical path — and absent entirely when
                too few have opted in to be worth claiming. */}
            <CreatorLeaderboard />

            {/* The family handshake. Full-bleed studio coral, white poster
                type, a black block — the one place the studio palette appears
                on the whole site. Home routes rather than asks, so the band
                carries the two doors instead of a single CTA. */}
            <HandshakeBand
                title={COPY.closeTitle}
                line={COPY.closeLine}
            >
                <TwoPaths testid={IDS.twoPaths} tone="coral" />
            </HandshakeBand>

            <MarketingFooter />
        </div>
    );
}
