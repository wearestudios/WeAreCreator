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
// **The hero rotates the stage of the job, not the sector.** It used to cycle
// eight sectors — Retail, Hospitality, Travel — over eight photographs, and
// the sector is the one thing a visitor already knows about themselves. Four
// fixed steps now, Offer → Agree → Deliver → Get paid, each with the product
// screen that step happens on. The reasoning lives in `lib/heroDeck.js` so a
// later refactor meets it; the budget the old slider earned — at most two
// layers mounted, one clock, nothing at all under reduced motion — is held.
//
// **Every claim on this page is one the product makes today.** The hero's
// three-claim strip and the four step lines were written against the code,
// not the roadmap: nothing is held in escrow before a shoot, so the page says
// the fee is agreed before it; there is no review timer on main yet, so the
// page does not promise one.
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
import { HERO_EYEBROW } from "@/lib/siteNav";
import HeroDeckProvider, {
    DeckStage,
    RotatingLine,
    StepRail,
} from "@/components/marketing/HeroDeck";
import ComparisonBand from "@/components/marketing/ComparisonBand";
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

    // **The `h1` is static, and that is for search and for screen readers.**
    // What moves is the line under it, which is decorative.
    heroTitle: "One place for the whole job",
    ctaBrand: "Post a brief",
    ctaCreator: "I'm a creator",

    // The deck. Four fixed steps; adding a sector touches none of this.
    //
    // **Two support lines differ from the brief that commissioned them, on
    // purpose.** "Matched creators apply, you shortlist" — on main a brand
    // never sees a raw application; we shortlist. "Offers, counters and the
    // final figure are recorded" — the counter history is not on main; the
    // quote, the agreed fee and the frozen terms are. And the payout line
    // said money is "held before the shoot", which nothing does.
    steps: [
        {
            key: "offer",
            label: "Offer",
            line: "Send one brief, not sixty DMs.",
            support: "Post it once. Matched creators apply; we shortlist.",
        },
        {
            key: "agree",
            label: "Agree",
            line: "Agree the number, and it stays agreed.",
            support: "Quote, agreed fee and terms are frozen on the deal.",
        },
        {
            key: "deliver",
            label: "Deliver",
            line: "Get the draft, in one place.",
            support: "Drafts arrive together, with who owes what next.",
        },
        {
            key: "paid",
            label: "Get paid",
            line: "Approve it, and the money moves.",
            support: "Paid when the brief promised, with a record for both sides.",
        },
    ],

    // Three claims, each checked against the code. The second and third are
    // not the ones commissioned: "Money is held before you shoot" is untrue
    // (a payment is raised after approval), and "Reviews can't stall
    // forever" describes a review timer that is not on main.
    claims: [
        {
            label: "A brand never sees your number",
            line: "Your phone and email stay off every brand screen.",
        },
        {
            label: "The fee is agreed before you shoot",
            line: "Recorded on the deal, and paid when the brief promised.",
        },
        {
            label: "Every brand is checked",
            line: "We verify the business before its brief reaches you.",
        },
    ],

    // The band under the hero.
    compareTitle: "A campaign is not a spreadsheet and sixty DMs",
    todayLabel: "How it runs today",
    hereLabel: "How it runs here",
    compareLinkLabel: "What a brand gets",

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
 * The hero — the job in four steps, with the screen each step happens on.
 *
 * **Type left, the product right.** The left column is the static `h1`, the
 * rotating line (decorative, `aria-hidden`, with a static list for screen
 * readers), the two doors and the rail; the right is the deck stage, which
 * reserves its box by aspect ratio so a screen swapping in moves nothing. The
 * three claims run along the foot.
 *
 * `HeroDeckProvider` wraps the whole section's content: it is the one clock,
 * and the element the pause listeners bind to, so hovering or tabbing anywhere
 * in the hero stops it.
 */
function Hero() {
    return (
        <section
            data-testid={HERO_IDS.section}
            data-surface="dark"
            className="relative overflow-hidden border-b border-border bg-background text-foreground"
        >
            {/* Decorative, behind the stage. */}
            <div
                aria-hidden
                className="pointer-events-none absolute right-[6%] top-1/4 h-[420px] w-[420px] rounded-full bg-primary/10 blur-[130px]"
            />

            <HeroDeckProvider steps={COPY.steps} className="relative">
                <div className="mx-auto max-w-7xl px-6 pb-12 pt-14 md:pb-16 md:pt-20">
                    <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-12 lg:gap-12">
                        <div className="lg:col-span-6">
                            <Reveal onView={false}>
                                <p
                                    data-testid={HERO_IDS.eyebrow}
                                    className="mb-8 inline-flex items-center gap-3 rounded-full border border-tint/10 bg-tint/5 px-4 py-1.5 text-xs uppercase tracking-[0.22em] text-muted-foreground backdrop-blur"
                                >
                                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
                                    {HERO_EYEBROW}
                                </p>
                            </Reveal>

                            {/* Static. Poster scale, sized to its column. */}
                            <h1
                                data-testid={HERO_IDS.heading}
                                className="font-serif tracking-tight text-foreground"
                                style={{ fontSize: "clamp(2.25rem, 4.6vw, 4.75rem)", lineHeight: 1.0 }}
                            >
                                {COPY.heroTitle}
                            </h1>

                            <Reveal i={1} onView={false} className="mt-8">
                                <RotatingLine />
                            </Reveal>

                            <Reveal i={2} onView={false}>
                                <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                                    <Link to="/signup?role=brand" data-testid={HERO_IDS.ctaBrand}>
                                        <Button
                                            size="lg"
                                            className="group h-12 w-full rounded-full bg-primary px-7 text-primary-foreground transition-colors duration-200 hover:bg-primary-hover sm:w-auto"
                                        >
                                            {COPY.ctaBrand}
                                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                        </Button>
                                    </Link>
                                    <Link to="/for-creators" data-testid={HERO_IDS.ctaCreator}>
                                        <Button
                                            size="lg"
                                            variant="outline"
                                            className="group h-12 w-full rounded-full border-tint/15 bg-transparent px-7 text-foreground transition-colors duration-200 hover:bg-tint/5 sm:w-auto"
                                        >
                                            {COPY.ctaCreator}
                                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                        </Button>
                                    </Link>
                                </div>
                            </Reveal>
                        </div>

                        <div className="lg:col-span-6">
                            <StepRail />
                            <DeckStage className="mt-4" />
                        </div>
                    </div>

                    <ul
                        data-testid={HERO_IDS.claims}
                        className="mt-14 grid grid-cols-1 gap-6 border-t border-tint/10 pt-8 md:grid-cols-3 md:gap-10"
                    >
                        {COPY.claims.map((c, i) => (
                            <li key={c.label} data-testid={HERO_IDS.claim(i)}>
                                <p className="text-sm font-medium text-foreground">{c.label}</p>
                                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                                    {c.line}
                                </p>
                            </li>
                        ))}
                    </ul>
                </div>
            </HeroDeckProvider>
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
        <section
            data-testid={PAGE_IDS.problem}
            data-surface="light"
            className="border-t border-border bg-background text-foreground"
        >
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
                            src="/img/marketing/home-on-location.svg"
                            alt="A creator shooting on location, a phone on a stand in front of them and venue staff working at the counter behind."
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

            {/* Directly under the hero, and below the fold: static DOM with
                no fetch, and `content-visibility: auto` so it costs nothing
                until it is close. */}
            <ComparisonBand
                copy={{
                    title: COPY.compareTitle,
                    todayLabel: COPY.todayLabel,
                    hereLabel: COPY.hereLabel,
                    linkLabel: COPY.compareLinkLabel,
                }}
                linkTo="/for-brands"
            />

            {/* Counted, never written down. The hero carried a hardcoded
                "500+ verified creators" until this replaced it. */}
            <div data-surface="dark" className="bg-background text-foreground">
                <ProofStrip only={["creators", "campaigns", "cities"]} />
            </div>

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
            <div data-surface="dark" className="bg-background text-foreground">
                <CampaignFilm title={COPY.filmTitle} />
            </div>

            {/* A full-bleed band between the film and the problem — the film
                ends on a drawn interface and the problem opens on type, and
                one photograph between them is the beat that stops the page
                reading as a diagram followed by an argument. No words: the
                120-word budget is the constraint, and this is doing the job
                a sentence would have done badly. */}
            <div
                data-surface="dark"
                className="mx-auto max-w-7xl bg-background px-6 text-foreground"
            >
                {/* PLACEHOLDER IMAGE: Wide shot of a busy venue mid-campaign,
                    creators and guests mixed, shot from above */}
                <PlaceholderImage
                    testid={PAGE_IDS.bandImage}
                    note="Wide shot of a busy venue mid-campaign, creators and guests mixed, shot from above"
                    src="/img/marketing/home-venue-wide.svg"
                    alt="A busy venue mid-campaign seen wide, guests along the tables and a creator filming among them."
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
            <div data-surface="light" className="bg-background text-foreground">
                <CaseStudyStrip />
            </div>

            {/* The creators, with their permission. Below the fold and
                fetched only when it gets close — a marketing page must not
                pay for this on the critical path — and absent entirely when
                too few have opted in to be worth claiming. */}
            <div data-surface="dark" className="bg-background text-foreground">
                <CreatorLeaderboard />
            </div>

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
