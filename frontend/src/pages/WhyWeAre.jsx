// /why-weare — the standalone case, for the brand comparing options.
//
// This reader is not asking what the product does; /how-it-works answers that.
// They are asking why us, with a tab open on somebody else. So the page argues
// rather than explains, and it argues on the four things that are actually
// checkable: who is behind it, that the managed option is real, that both
// sides are verified people, and that the money and the results are handled
// where you can see them.
//
// **It never argues against agencies.** WeAre Studios is one and the managed
// service is a genuine offering — "without an agency" here would be a page
// arguing against the thing three sections down. What is named as the problem
// is disorganisation: campaigns run over DMs and spreadsheets, nobody checked,
// no rate in writing, no proof of what it achieved.
//
// One audience, so one ask, stated top and bottom in the same words.
import React from "react";

import {
    MarketingPage,
    MarketingHero,
    TextImageSection,
    ClosingSection,
    Eyebrow,
} from "@/components/marketing/Sections";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import ProofStrip from "@/components/marketing/ProofStrip";
import { MARKETING as IDS } from "@/constants/testIds";

const ASK = { to: "/signup?role=brand", label: "Post a campaign" };

const AGAINST_DISORGANISATION = [
    {
        title: "Nobody checked",
        body:
            "A follower count in a DM is a number somebody typed. Here a creator is " +
            "reviewed by a person before you can see them, and where they have connected " +
            "Instagram the count and the engagement rate are read from Instagram itself.",
    },
    {
        title: "No rate in writing",
        body:
            "The fee is agreed and recorded against the booking before anyone shoots, so " +
            "the conversation on the day is about the work. Our fee is charged to you on " +
            "top and shown before you confirm.",
    },
    {
        title: "No proof of what it did",
        body:
            "Reach, engagement and cost per thousand, collected against the posts that " +
            "actually went out, on one report you can forward. Barter deliveries are " +
            "counted separately so the cost figure is never flattered.",
    },
];

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
                title="Your creator campaigns, handled properly."
                standfirst="A studio that runs campaigns for a living, behind a platform you can run yourself. Verified people on both sides, every rate in the open, approval before anything is published, and a report at the end."
                cta={{ ...ASK, testid: IDS.ctaTop }}
                image={{
                    // PLACEHOLDER IMAGE: the WeAre Studios team mid-production
                    // at a venue — lighting being set, a creator briefed in the
                    // background. Landscape 16:9.
                    note: "WeAre Studios team mid-production at a venue, lighting being set, 16:9",
                    ratio: "16/9",
                }}
            />

            <ProofStrip />

            <TextImageSection
                eyebrow="The pedigree"
                title="Built by the people who do the work."
                body="WeAre Studios runs influencer campaigns for a living — briefing creators, staffing shoots, standing at the door on the day and writing the report afterwards. WeAre Creators is that operation with the parts you can do yourself handed to you."
                points={[
                    "The platform was built to run our own campaigns, so every screen answers a question somebody actually had mid-shoot.",
                    "The team is in Bengaluru, which is why the network is deepest there — a fact about how fast a brief fills, not a claim about who we are.",
                    "Creators sign up from anywhere in India.",
                ]}
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
                title="Run it yourself, or hand it over."
                body="Both are real, and you pick per campaign. Self-serve is the dashboard: post the brief, shortlist, approve, read the report. Managed is our team doing the same work with our people. It is an option you choose, not a fee you are locked into — and choosing it once does not commit the next one."
                points={[
                    "No retainer, and no markup on creator fees, either way.",
                    "A managed campaign gets a named WeAre manager who holds the roster and is at the door on the day.",
                    "You approve the content and you get the report whichever way you run it.",
                ]}
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

            <section className="border-b border-white/10 py-16 md:py-24">
                <div className="mx-auto max-w-7xl px-6">
                    <Eyebrow>What we are actually fixing</Eyebrow>
                    <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        Most creator campaigns are not badly judged. They are badly
                        organised.
                    </h2>
                    <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground">
                        Run over DMs and spreadsheets: nobody checked, no rate in
                        writing, and no proof of what it achieved. Each of those has a
                        mechanism here rather than a good intention.
                    </p>
                    <div className="mt-12 grid gap-6 md:grid-cols-3">
                        {AGAINST_DISORGANISATION.map((item) => (
                            <div
                                key={item.title}
                                className="rounded-lg border border-white/10 bg-card grain-surface p-7"
                            >
                                <h3 className="font-serif text-fluid-2xl leading-tight tracking-tight">
                                    {item.title}
                                </h3>
                                <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                                    {item.body}
                                </p>
                            </div>
                        ))}
                    </div>
                    <div className="mt-12">
                        <PlaceholderImage
                            // PLACEHOLDER IMAGE: a wide, calm shot of a shoot
                            // day running to plan — creators queuing at a
                            // check-in desk, manager with a tablet. Banner
                            // proportions, 21:9.
                            note="Shoot day running to plan, creators at a check-in desk, manager with a tablet, 21:9"
                            ratio="21/9"
                        />
                    </div>
                </div>
            </section>

            <TextImageSection
                eyebrow="The money"
                title="Nobody is guessing what anything costs."
                body="The creator quotes their rate and keeps all of it. Our fee is charged to you on top and shown before you confirm. Payment goes out after you have approved the delivery, and every figure is on the record — which is the difference between a campaign and a set of favours."
                image={{
                    // PLACEHOLDER IMAGE: close crop of a printed campaign
                    // summary with fees and payouts itemised, pen resting on
                    // it. 5:4.
                    note: "Close crop of a printed campaign summary with fees itemised, pen resting on it, 5:4",
                    ratio: "5/4",
                }}
            />

            <ClosingSection
                title="Post your first brief."
                body="About ten minutes. We check your business before anything reaches a creator, and you decide then whether to run it yourself."
                cta={{ ...ASK, testid: IDS.ctaBottom }}
                image={{
                    // PLACEHOLDER IMAGE: a venue at golden hour just before
                    // opening, tables set, nobody in yet. Dark edges — it sits
                    // dimmed behind the CTA. 21:9.
                    note: "Venue at golden hour just before opening, tables set, dark edges, 21:9",
                    ratio: "21/9",
                }}
            />
        </MarketingPage>
    );
}
