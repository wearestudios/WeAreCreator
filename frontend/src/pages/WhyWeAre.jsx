// /why-weare — the standalone case, under 300 words.
//
// This reader is not asking what the product does; /how-it-works answers that.
// They are comparing options with another tab open, which means every line has
// to be checkable. So the page argues on four things — who is behind it, that
// the managed option is real, that both sides are verified people, and that
// the money and the results are where you can see them — and it argues in
// labels and single lines, because a page of paragraphs is a page a sceptic
// skims.
//
// **It never argues against agencies.** WeAre Studios is one and the managed
// service is a genuine offering — "without an agency" here would be a page
// arguing against the thing two sections down. What is named as the problem is
// disorganisation: DMs, spreadsheets, handshake deals.
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
import { MARKETING as IDS } from "@/constants/testIds";

const ASK = { to: "/signup?role=brand", label: "Post a campaign" };

const COPY = {
    title: "Your creator campaigns, handled properly.",
    line: "A studio that runs campaigns for a living, behind a platform you can run yourself.",

    pedigreeTitle: "Built by the people who do the work.",
    pedigreeLine: "WeAre Studios briefs creators, staffs shoots and writes the report. This is that operation, handed to you.",
    pedigree: [
        {
            label: "Built on real campaigns",
            line: "Every screen answers a question somebody had mid-shoot.",
        },
        {
            label: "Deepest in Bengaluru",
            line: "Which is why briefs fill fast here. Creators sign up from anywhere in India.",
        },
    ],

    choiceTitle: "Run it yourself, or hand it over.",
    choiceLine: "You pick per campaign, and choosing once does not commit the next one.",
    choice: [
        {
            label: "No retainer, no markup",
            line: "On creator fees, either way.",
        },
        {
            label: "A named manager",
            line: "On a managed campaign, at the door on the day.",
        },
        {
            label: "Not a fee you are locked into",
            line: "It is an option you choose.",
        },
    ],

    problemTitle: "Badly organised, not badly judged.",
    problemLine: "Each of these has a mechanism here rather than a good intention.",
    problems: [
        {
            label: "Nobody checked",
            line: "A person reviews every creator. Connected stats are read from Instagram.",
        },
        {
            label: "No rate in writing",
            line: "Agreed and recorded against the booking before anyone shoots.",
        },
        {
            label: "No proof",
            line: "Reach and cost per thousand, collected from the posts that ran.",
        },
    ],

    moneyTitle: "Nobody is guessing what it costs.",
    moneyLine: "The creator keeps their rate. You pay us that plus our fee, and we release on approved delivery.",

    closeTitle: "Post your first brief.",
    closeLine: "About ten minutes. We check your business before anything reaches a creator.",
};

export default function WhyWeAre() {
    return (
        <MarketingPage
            testid={IDS.whyWeAre}
            title="Why WeAre"
            description="A studio that runs campaigns for a living, behind a platform you can run yourself. Verified people on both sides, rates and fees in the open, and a report at the end."
            path="/why-weare"
        >
            <MarketingHero
                eyebrow="Why WeAre"
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
                points={COPY.pedigree}
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
                eyebrow="The choice"
                title={COPY.choiceTitle}
                line={COPY.choiceLine}
                points={COPY.choice}
                image={{
                    // PLACEHOLDER IMAGE: split-feeling shot — a brand manager
                    // working on a laptop dashboard, with a live shoot visible
                    // beyond. 3:2.
                    note: "Brand manager on a laptop dashboard with a live shoot visible beyond, 3:2",
                    ratio: "3/2",
                }}
                flip
                testid={IDS.choice}
            />

            <section className="border-b border-white/10 py-16 md:py-20">
                <div className="mx-auto max-w-7xl px-6">
                    <Reveal>
                        <Eyebrow>What we are fixing</Eyebrow>
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
