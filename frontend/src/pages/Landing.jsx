// Home — a router, not a story.
//
// Four screens: what this is, the counted proof, what we run, and two doors.
// The detail it wants to add lives on the audience pages, in onboarding, and
// in the product.
//
// **The word budget was raised from 120 and the reason belongs here**, because
// 120 is what wrote the copy this replaced. A twenty-word line and an
// eight-word heading will not hold "Every creator is verified through
// Instagram's official API before they reach a brief" — so what fitted was the
// aphorism, and the page filled up with sentences that sounded considered and
// named nothing: "A follower count in a DM is a number somebody typed." The
// budget is 260 now and the rule it enforces is the same one: a section that
// wants to say more still has to argue with a number, and the number is just
// no longer set below the length of a specific claim.
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
// four products. The deck is built from `PHRASES` — the sectors the headline
// morphs through — so the picture changes *with* the words rather than beside
// them. One idea, moving.
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
import BrandWall from "@/components/marketing/BrandWall";
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
// counted across a file. A unit test enforces it — see `BUDGET` and the two
// caps beside it in `test_marketing_pages.py`, and the note above on why they
// moved.

const COPY = {
    title: "Influencer marketing, run end to end",
    line: "Brands post a brief. We cast the creators, agree every rate in writing, run the shoot and send the report — across India, in every sector we run.",

    // **This section states the service; it used to open on three failures.**
    // "Most campaigns run on DMs and spreadsheets", then three lines about
    // creators nobody checked and proof nobody had. Every one was true and
    // all three were about the reader: a marketing head evaluating a vendor
    // reads a list of things they are doing wrong as a put-down, and home was
    // spending its first screen on it before saying what this company does.
    //
    // Same three subjects, stated as what the operation runs. The claims are
    // stronger this way round because each one is now checkable rather than
    // knowing: "a follower count in a DM is a number somebody typed" is an
    // observation, "verified through Instagram's official API" is a fact
    // somebody can hold us to.
    serviceTitle: "One team runs the whole campaign.",
    service: [
        {
            label: "Creators are verified",
            line: "A person reviews every creator, and connected accounts report their audience through Instagram's official API.",
        },
        {
            label: "Rates are agreed in writing",
            line: "We negotiate each fee and record it against the booking before anyone shoots.",
        },
        {
            label: "Every campaign ends in a report",
            line: "The posts that ran, the reach they got, and what the campaign cost, in one place.",
        },
    ],
    promise: "Follow one campaign, brief to payment.",

    filmTitle: "One campaign, start to finish.",

    closeTitle: "Where would you like to begin?",
    closeLine: "Creators join free and keep their full rate. Every brand is checked before it reaches anyone.",
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
 * headline morphing through the same sectors.
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
 * What the operation actually does — one screen, one idea.
 *
 * **This was `Problem`, and it opened on three things the reader was getting
 * wrong.** Naming a failure is only worth a screen when the reader has not
 * already lived it; a marketing head who has run a campaign over DMs knows
 * what that cost, and being told reads as a put-down from a vendor they are
 * evaluating. The three subjects survived — verification, the rate, the
 * report — stated as the three things this company runs.
 *
 * **Agencies are still never named.** WeAre Studios is one and the managed
 * service is the product, so "without an agency" would be home arguing
 * against a thing /why-weare sells two clicks away.
 */
function WhatWeRun() {
    return (
        <section data-testid={PAGE_IDS.problem} className="border-t border-white/10">
            <div className="mx-auto max-w-7xl px-6 py-14 md:py-16">
                <Reveal>
                    <Eyebrow>What we run</Eyebrow>
                </Reveal>
                <Reveal i={1}>
                    <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        {COPY.serviceTitle}
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
                    <Points items={COPY.service} />
                    <Reveal i={2}>
                        {/* PLACEHOLDER IMAGE: A creator shooting on location,
                            phone on a gimbal, venue staff visible behind */}
                        <PlaceholderImage
                            testid={PAGE_IDS.problemImage}
                            note="A creator shooting on location, phone on a gimbal, venue staff visible behind"
                            src="/img/marketing/home-on-location.webp"
                            alt="A creator filming on location with a phone on a gimbal, venue staff working behind them."
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
                title="Influencer marketing across India, run end to end"
                // **No city in the meta description.** It named Bengaluru,
                // which was accurate and is the one claim on this page that
                // nothing re-checks — a meta description is written once and
                // read by strangers for years. The geography that *is* said on
                // this site is rendered from counted supply
                // (`CountedGeography`); a description cannot do that, so it
                // says nothing about place rather than something stale.
                description="Influencer marketing across India, run end to end. Brands post a brief; WeAre Creators casts verified creators, agrees every rate in writing, runs the shoot and sends the report."
                path="/"
            />
            <MarketingNavbar />

            <Hero />

            {/* Counted, never written down. The hero carried a hardcoded
                "500+ verified creators" until this replaced it. */}
            <ProofStrip only={["creators", "campaigns", "cities"]} />

            {/* **Directly under the figures and well above the case studies**,
                which is the order a sceptical brand reads in: the figures say
                there is an operation, the logos say businesses like theirs
                use it, and the write-ups further down say it works. Logos
                before the proof would be decoration; logos after the
                write-ups would be a footnote.

                Every brand here has finished at least one campaign and has
                given written permission for its mark — both decided
                server-side, and consent re-read on every request so a
                withdrawal is gone from the next page load. Absent entirely
                below the floor: one withdrawal taking the row down is
                correct, because the floor is about whether the claim is worth
                making at all. */}
            <BrandWall />

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
                    src="/img/marketing/home-venue-wide.webp"
                    alt="A busy venue during a campaign, seen from above, with creators and guests mixed through the room."
                    ratio="21/9"
                />
            </div>

            <WhatWeRun />

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
