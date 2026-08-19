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
import FloatingCards from "@/components/marketing/FloatingCards";
import HandshakeBand from "@/components/marketing/HandshakeBand";
import CampaignFilm from "@/components/marketing/CampaignFilm";
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

    filmTitle: "One campaign, start to finish.",

    closeTitle: "Which side are you on?",
    closeLine: "Creators join free. We check a brand before it reaches anyone.",
};

/**
 * The hero — the kinetic headline, floating cards, two doors.
 *
 * This replaced a full-bleed photo slider that cross-faded four category
 * images behind the text. The slider's job was to say "we do all of these",
 * and the floating cards now say it better: four categories visible *at once*
 * rather than one at a time behind a scrim heavy enough to keep the headline
 * readable. It also cost a full-viewport compositing layer cross-fading every
 * seven seconds, on the page most likely to be opened on mobile data.
 *
 * What is left is the signature: poster type that morphs at letterform level
 * against a line that never moves.
 */
function Hero() {
    return (
        <section
            data-testid={HERO_IDS.section}
            className="relative overflow-hidden border-b border-white/10"
        >
            {/* Decorative and absolutely positioned, so they never move the
                headline. Behind it in the stacking order for the same reason
                the scrim used to exist — except a tilted card at 26% width
                does not need one. */}
            <FloatingCards />

            <div
                aria-hidden
                className="pointer-events-none absolute -right-40 -top-32 h-[560px] w-[560px] rounded-full bg-ember-500/10 blur-[130px]"
            />

            <div className="relative mx-auto max-w-7xl px-6 pb-16 pt-14 md:pb-24 md:pt-20">
                <Reveal onView={false}>
                    <p
                        data-testid={HERO_IDS.eyebrow}
                        className="mb-8 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.22em] text-muted-foreground backdrop-blur"
                    >
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-ember-500" />
                        Bengaluru · Influencer studio
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

            {/* The centrepiece: the product performing itself. Pinned and
                scroll-driven where that runs well, the identical seven beats
                as a stepped list everywhere else. */}
            <CampaignFilm title={COPY.filmTitle} />

            <Problem />

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
