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
// *not* agencies. WeAre Studios is one, the managed service is the product
// itself, and "without an agency" would be a page arguing against our own
// offering.
//
// **The product is managed-only and the page says so as the offer.** There is
// no self-serve mode to choose between: a brand posts a brief, we cast,
// negotiate and shortlist, they approve, we run it. Any line that reads as
// browsing creators, inviting them, or working an applicant board is
// describing a product that no longer exists.
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
import FloatingCards from "@/components/marketing/FloatingCards";
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
            line: "A person reviews every one, and connected stats are read from Instagram.",
        },
        {
            label: "Every rate, in front of you",
            line: "You see what each creator quoted, with our fee on top.",
        },
        {
            // **The product is managed-only, so this is the offer rather than
            // a choice.** This slot used to say "yours to run, or ours", which
            // described a self-serve mode that no longer exists — a brand
            // reading it would arrive expecting a dashboard to work an
            // applicant board from and find a shortlist instead.
            label: "We run it end to end",
            line: "The WeAre Studios team casts, negotiates and shortlists. You approve the work.",
        },
    ],

    stepsTitle: "Brief to report, in four moves.",
    steps: [
        {
            label: "Post the brief",
            line: "What you want made, the budget, and when your venue can take people.",
        },
        {
            // **Not a directory to browse, and not a pile to sort.** This
            // line used to say applicants arrive ranked alongside verified
            // creators who fit, which read as a roster to shop through —
            // never what a brand could reach, and now not even what exists.
            // It then said applicants arrive with their rate, which was the
            // raw-application reading of the same screen. What a brand
            // receives is a shortlist: people we checked and agreed a fee
            // with. Nobody unshortlisted reaches them on a brief we run.
            //
            // Keep quotation marks out of this block — the word-budget test
            // regexes every double-quoted string inside COPY, so a quoted
            // phrase in a comment is charged to the page.
            label: "We bring the shortlist",
            line: "Creators we checked and negotiated with, each with a rate agreed.",
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

    // **The commercial terms, which are the strongest thing we have to say
    // and appeared nowhere.** This slot used to be "self-serve, or we run
    // it" — a choice the product no longer offers. What replaces it is what
    // a brand is actually deciding on: our fee sits on top of the creator's
    // rate rather than out of it, and it comes back if we cannot fill the
    // brief. Both are checkable, which is the standard this page is held to.
    termsTitle: "Our fee, and when it returns.",
    termsLine: "Charged on top, and refunded if we cannot fill the brief.",
    terms: [
        {
            label: "Creators keep their full rate",
            line: "Our fee is yours to pay, never theirs.",
        },
        {
            label: "Refunded if we cannot fill it",
            line: "Unless you turned down everyone we shortlisted.",
        },
        {
            label: "A named manager, every time",
            line: "Holding the roster and at the door.",
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
            description="Verified creators, every rate visible before you book, approval before anything is published, and a report at the end. The WeAre Studios team runs it end to end."
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
            {/* The proof figures, with two cards floating past the strip's
                edges — the second of the two card clusters. */}
            <div className="relative">
                <FloatingCards set="proof" />
                <ProofStrip />
            </div>

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
                eyebrow="The terms"
                title={COPY.termsTitle}
                line={COPY.termsLine}
                points={COPY.terms}
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
            />
        </MarketingPage>
    );
}
