// /why-weare — the standalone case, under 300 words.
//
// This reader is not asking what the product does; /how-it-works answers that.
// They are comparing options with another tab open, which means every line has
// to be checkable. So the page argues on four things — who is behind it, what
// handing a campaign over costs, that both sides are verified people, and that
// the money and the results are where you can see them — and it argues in
// labels and single lines, because a page of paragraphs is a page a sceptic
// skims.
//
// **It never argues against agencies.** WeAre Studios is one and running the
// campaign is the product — "without an agency" here would be a page arguing
// against the thing two sections down. What is named as the problem is
// disorganisation: DMs, spreadsheets, handshake deals.
//
// **There is no self-serve half to argue for any more.** The section below the
// pedigree used to offer a choice between running it yourself and handing it
// over; managed is the whole product now, so it states the commercial terms
// instead — the fee on top of the creator rate, and the refund if we cannot
// fill the brief.
//
// One audience, so one ask, stated top and bottom in the same words.
import React from "react";

import {
    MarketingPage,
    MarketingHero,
    Points,
    TextImageSection,
    ClosingSection,
    Eyebrow,
} from "@/components/marketing/Sections";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import ProofStrip from "@/components/marketing/ProofStrip";
import FloatingCards from "@/components/marketing/FloatingCards";
import Reveal from "@/components/marketing/Reveal";
import { useDeepestCity } from "@/components/marketing/CountedGeography";
import { MARKETING as IDS } from "@/constants/testIds";

const ASK = { to: "/signup?role=brand", label: "Post a campaign" };

const COPY = {
    title: "Influencer marketing, run end to end.",
    line: "A studio that runs campaigns for a living, running yours on a platform you can see into.",

    pedigreeTitle: "Built by the people who do the work.",
    pedigreeLine: "WeAre Studios briefs creators, staffs shoots and writes the report. This is that operation, handed to you.",
    pedigree: [
        {
            label: "Built on real campaigns",
            line: "Every screen here answers a question somebody actually had mid-shoot.",
        },
    ],

    // **The geography point is counted, so it is a function of the city.**
    // Unlike `/for-brands`, only the *point* drops below the proof floor here
    // rather than the whole section — the pedigree claim stands on its own,
    // and the other point is not about a place.
    pedigreeReach: (city) => ({
        label: `Deepest supply in ${city}`,
        line: "Which is why briefs fill fastest there. We run campaigns across India, in every sector we list.",
    }),

    // **This was the self-serve choice and the product no longer has one.**
    // It read as run it yourself or hand it over, with a third point insisting
    // the managed service was an option rather than a fee. Managed is the
    // product now, so the section argues what that costs instead — which is
    // the thing a sceptic with another tab open is actually weighing.
    termsTitle: "What handing it over costs.",
    termsLine: "Our fee sits on top of the creator rate rather than coming out of it, and the campaign fee comes back if we cannot fill the brief.",
    terms: [
        {
            label: "No retainer, no markup",
            line: "You pay per campaign and nothing between them. We add no margin to a creator fee.",
        },
        {
            label: "Creators keep their full rate",
            line: "Our fee is charged to you, never taken out of theirs. A squeezed creator is one who leaves.",
        },
        {
            label: "A named manager",
            line: "One person holds the roster, briefs the creators and is at the door on the day.",
        },
        {
            label: "Refunded if we cannot fill it",
            line: "The campaign fee comes back, unless you turned down everyone we shortlisted.",
        },
    ],

    problemTitle: "Three things we run, rather than hope for.",
    problemLine: "Each of these is a mechanism in the product rather than a good intention.",
    problems: [
        {
            label: "Creators are verified",
            line: "A person reviews every creator, and connected accounts report their audience through Instagram’s official API.",
        },
        {
            label: "Rates are agreed in writing",
            line: "Negotiated and recorded against the booking before anyone shoots.",
        },
        {
            label: "Results are collected",
            line: "Reach and cost per thousand, taken from the posts that actually ran.",
        },
    ],

    moneyTitle: "Nobody is guessing what it costs.",
    moneyLine: "The creator keeps their rate. You pay us that plus our fee, and we release the money on approved delivery.",

    closeTitle: "Post your first brief.",
    closeLine: "About ten minutes. We check your business before anything reaches a creator.",
};


export default function WhyWeAre() {
    const deepestCity = useDeepestCity();
    return (
        <MarketingPage
            testid={IDS.whyWeAre}
            title="Why brands choose WeAre Creators"
            description="A studio that runs influencer campaigns for a living, running yours end to end across India. Verified people on both sides, rates and fees in the open, and a report at the end."
            path="/why-weare"
        >
            <MarketingHero
                eyebrow="Why WeAre Creators"
                title={COPY.title}
                line={COPY.line}
                cta={{ ...ASK, testid: IDS.ctaTop }}
                image={{
                    // PLACEHOLDER IMAGE: the WeAre Studios team mid-production
                    // at a venue — lighting being set, a creator briefed in the
                    // background. Landscape 16:9.
                    note: "WeAre Studios team mid-production at a venue, lighting being set, 16:9",
                    ratio: "16/9",
                }}
            />

            {/* The proof figures, with two cards floating past the strip's
                edges — the second of the two card clusters. */}
            <div className="relative">
                <FloatingCards set="proof" />
                <ProofStrip />
            </div>

            <TextImageSection
                eyebrow="The pedigree"
                title={COPY.pedigreeTitle}
                line={COPY.pedigreeLine}
                points={
                    deepestCity
                        ? [...COPY.pedigree, COPY.pedigreeReach(deepestCity)]
                        : COPY.pedigree
                }
                image={{
                    // PLACEHOLDER IMAGE: the WeAre Studios office or a
                    // production meeting — whiteboard with a campaign plan,
                    // people mid-conversation. 4:3.
                    note: "WeAre Studios production meeting, whiteboard with a campaign plan, 4:3",
                    ratio: "4/3",
                }}
                testid={IDS.pedigree}
            />

            <TextImageSection
                eyebrow="The terms"
                title={COPY.termsTitle}
                line={COPY.termsLine}
                points={COPY.terms}
                image={{
                    // PLACEHOLDER IMAGE: a WeAre manager and a brand owner
                    // side by side at the venue before doors, going through
                    // the roster on a tablet. 3:2.
                    note: "WeAre manager and brand owner going through the roster on a tablet before doors, 3:2",
                    ratio: "3/2",
                }}
                flip
                testid={IDS.choice}
            />

            <section className="border-b border-white/10 py-16 md:py-20">
                <div className="mx-auto max-w-7xl px-6">
                    <Reveal>
                        <Eyebrow>What we run</Eyebrow>
                    </Reveal>
                    <Reveal i={1}>
                        <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                            {COPY.problemTitle}
                        </h2>
                    </Reveal>
                    <Reveal i={2}>
                        <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
                            {COPY.problemLine}
                        </p>
                    </Reveal>
                    <div className="mt-10">
                        <Points items={COPY.problems} />
                    </div>
                    <Reveal noTravel className="group mt-10">
                        <PlaceholderImage
                            // PLACEHOLDER IMAGE: a wide, calm shot of a shoot
                            // day running to plan — creators queuing at a
                            // check-in desk, manager with a tablet. Banner
                            // proportions, 21:9.
                            note="Shoot day running to plan, creators at a check-in desk, manager with a tablet, 21:9"
                            ratio="21/9"
                            zoom
                        />
                    </Reveal>
                </div>
            </section>

            <TextImageSection
                eyebrow="The money"
                title={COPY.moneyTitle}
                line={COPY.moneyLine}
                image={{
                    // PLACEHOLDER IMAGE: close crop of a printed campaign
                    // summary with fees and payouts itemised, pen resting on
                    // it. 5:4.
                    note: "Close crop of a printed campaign summary with fees itemised, pen resting on it, 5:4",
                    ratio: "5/4",
                }}
            />

            <ClosingSection
                title={COPY.closeTitle}
                line={COPY.closeLine}
                cta={{ ...ASK, testid: IDS.ctaBottom }}
            />
        </MarketingPage>
    );
}
