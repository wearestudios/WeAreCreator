// /for-brands — one reader, one ask, under 250 words.
//
// This is a compression, not a repositioning. Every claim here was on the page
// before at four times the length; what changed is that a fifty-word paragraph
// became a four-word label and one line, because the second half of the
// paragraph was being skipped anyway. The detail it used to carry lives in
// onboarding and in the product, which is where somebody who has clicked
// actually needs it.
//
// **The positioning, since it governs every line:** what we are against is
// disorganisation — DMs, spreadsheets, handshake deals. It is deliberately
// *not* agencies. WeAre Studios is one, the managed service is a real offering
// somebody chooses, and "without an agency" would be a page arguing against
// our own product.
//
// Bengaluru appears as evidence of network depth, never as identity: it is a
// fact about how fast a brief fills rather than a statement about who we are.
import React from "react";

import {
    MarketingPage,
    MarketingHero,
    Points,
    Steps,
    TextImageSection,
    ClosingSection,
} from "@/components/marketing/Sections";
import ProofStrip from "@/components/marketing/ProofStrip";
import { MARKETING as IDS } from "@/constants/testIds";

const ASK = { to: "/signup?role=brand", label: "Post a campaign" };

// All of the page's words, in one place, so the budget can be read rather
// than counted across a file. A unit test enforces it.
const COPY = {
    title: "Fill the room. Launch the thing.",
    line: "Creators we have checked, the rate agreed before anyone shoots, and nothing published until you approve it.",
    footnote: "No retainer. No markup on creator fees.",

    props: [
        {
            label: "Creators we checked",
            line: "A person reviews every one, and connected Instagram stats are read from Instagram.",
        },
        {
            label: "Every rate, in front of you",
            line: "You see what each creator quoted. Our fee sits on top, shown before you confirm.",
        },
        {
            label: "Yours to run, or ours",
            line: "Manage it from your dashboard, or hand it to the WeAre Studios team. You choose per campaign.",
        },
    ],

    stepsTitle: "Brief to report, in four moves.",
    steps: [
        {
            label: "Post the brief",
            line: "What you want made, the budget, and the hours your venue can take people.",
        },
        {
            label: "Pick your creators",
            line: "Applicants arrive with their rate, ranked alongside verified creators who fit.",
        },
        {
            label: "They shoot",
            line: "On slots they booked, inside the days and hours you set.",
        },
        {
            label: "Approve, then read the numbers",
            line: "Nothing goes live until you say yes. Reach and cost per thousand afterwards.",
        },
    ],

    choiceTitle: "Self-serve, or we run it.",
    choiceLine: "An option you choose per campaign, never a fee you are locked into.",
    choice: [
        {
            label: "No retainer",
            line: "And no markup on what the creator charges, either way.",
        },
        {
            label: "A named manager",
            line: "On a managed campaign, holding the roster and at the door on the day.",
        },
        {
            label: "Same approval, same report",
            line: "Whichever way you run it.",
        },
    ],

    reachTitle: "Deepest in Bengaluru.",
    reachLine: "That is where the network is thickest and briefs fill fastest. Creators sign up from anywhere in India.",

    closeTitle: "Post your first brief.",
    closeLine: "About ten minutes. We check your business before anything reaches a creator.",
};

export default function ForBrands() {
    return (
        <MarketingPage
            testid={IDS.forBrands}
            title="Creator campaigns for brands, handled properly"
            description="Verified creators, every rate visible before you book, approval before anything is published, and a report at the end. Run it yourself or hand it to the WeAre Studios team."
            path="/for-brands"
        >
            <MarketingHero
                eyebrow="For brands"
                title={COPY.title}
                line={COPY.line}
                cta={{ ...ASK, testid: IDS.ctaTop }}
                footnote={COPY.footnote}
                image={{
                    // PLACEHOLDER IMAGE: a full restaurant on opening night in
                    // Bengaluru, shot wide from the back of the room, warm
                    // service lighting, a creator filming at a table in the
                    // mid-ground. Landscape 16:9.
                    note: "Full restaurant on opening night, creator filming at a table, landscape 16:9",
                    ratio: "16/9",
                }}
            />

            {/* Counted, never written down — and absent entirely below the
                floors, because a small number is not proof. */}
            <ProofStrip />

            <section className="border-b border-white/10 py-16 md:py-20">
                <div className="mx-auto max-w-7xl px-6">
                    <Points items={COPY.props} testid={IDS.valueProps} />
                </div>
            </section>

            <Steps
                eyebrow="How it works"
                title={COPY.stepsTitle}
                items={COPY.steps}
                testid={IDS.steps}
            />

            <TextImageSection
                eyebrow="The choice"
                title={COPY.choiceTitle}
                line={COPY.choiceLine}
                points={COPY.choice}
                image={{
                    // PLACEHOLDER IMAGE: a WeAre campaign manager at a venue
                    // with a tablet, checking creators in at the door, evening.
                    // Portrait-ish 4:3 so it sits beside body copy.
                    note: "WeAre manager checking creators in at a venue door with a tablet, 4:3",
                    ratio: "4/3",
                }}
                flip
                testid={IDS.choice}
            />

            <TextImageSection
                eyebrow="Where we are"
                title={COPY.reachTitle}
                line={COPY.reachLine}
                image={{
                    // PLACEHOLDER IMAGE: a recognisable Bengaluru neighbourhood
                    // at dusk — Indiranagar or Koramangala shopfronts lit up.
                    // Landscape 3:2.
                    note: "Bengaluru shopfronts at dusk, Indiranagar or Koramangala, landscape 3:2",
                    ratio: "3/2",
                }}
            />

            <ClosingSection
                title={COPY.closeTitle}
                line={COPY.closeLine}
                cta={{ ...ASK, testid: IDS.ctaBottom }}
                image={{
                    // PLACEHOLDER IMAGE: a creator's phone on a gimbal framing
                    // a plated dish, shallow depth of field. Used as a dimmed
                    // background behind the closing CTA, so it wants a busy
                    // centre and dark edges. Landscape 21:9.
                    note: "Creator's phone on a gimbal framing a plated dish, dark edges, 21:9",
                    ratio: "21/9",
                }}
            />
        </MarketingPage>
    );
}
