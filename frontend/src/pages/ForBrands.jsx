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
import CaseStudyStrip from "@/components/marketing/CaseStudyStrip";
import CountedGeography from "@/components/marketing/CountedGeography";
import { MARKETING as IDS } from "@/constants/testIds";

const ASK = { to: "/signup?role=brand", label: "Post a campaign" };

// All of the page's words, in one place, so the budget can be read rather
// than counted across a file. A unit test enforces it.
const COPY = {
    title: "Influencer marketing, run end to end.",
    line: "You post the brief. We cast the creators, agree every rate in writing, schedule the shoots, run the day and send you the report.",
    footnote: "No retainer. No markup on creator fees.",

    props: [
        {
            label: "Every creator is verified",
            line: "A person reviews each profile, and audience numbers are read from Instagram’s official API rather than typed in.",
        },
        {
            label: "Every rate, in front of you",
            line: "You see what each creator quoted and what our fee adds, before you confirm anything.",
        },
        {
            label: "You never chase a creator",
            line: "Casting, negotiation, scheduling and delivery sit with the WeAre Studios team. You approve the work.",
        },
    ],

    stepsTitle: "Brief to report, in four steps.",
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
            // What a brand receives is a shortlist: people we verified and
            // agreed a fee with. Nobody unshortlisted reaches them on a brief
            // we run.
            //
            // Keep quotation marks out of this block — the word-budget test
            // regexes every double-quoted string inside COPY, so a quoted
            // phrase in a comment is charged to the page.
            label: "We bring the shortlist",
            line: "Creators we verified and negotiated with, each one arriving with a rate already agreed.",
        },
        {
            label: "The creators shoot",
            line: "On slots they booked, inside the days and hours your venue set.",
        },
        {
            label: "Approve, then read the numbers",
            line: "Nothing goes live until you say yes. Reach and cost per thousand afterwards.",
        },
    ],

    // **The commercial terms, which are the strongest thing we have to say
    // and appeared nowhere.** This slot used to be a choice between running
    // it yourself and handing it over, which the product no longer offers.
    // What replaces it is what a brand is actually deciding on: our fee sits
    // on top of the creator rate rather than out of it, and it comes back if
    // we cannot fill the brief. Both are checkable, which is the standard
    // this page is held to.
    termsTitle: "What we charge, and what comes back.",
    termsLine: "Our fee is charged on top of the creator rate, and the campaign fee is refunded if we cannot fill the brief.",
    terms: [
        {
            label: "Creators keep their full rate",
            line: "A creator who quotes a fee is paid that fee. Our margin is yours to pay, never theirs.",
        },
        {
            label: "Refunded if we cannot fill it",
            line: "The campaign fee comes back, unless you turned down everyone we shortlisted.",
        },
        {
            label: "A named manager, every time",
            line: "One person holds the roster, briefs the creators and is at the door on the day.",
        },
    ],

    // **Rendered, not typed.** The city is counted off verified supply at
    // request time (`CountedGeography`), so this sentence stays true if the
    // deepest city ever changes — and says nothing at all below the proof
    // floor. The scope claim beside it is a fact about the operation; the
    // depth claim is the one that needs a count behind it, which is why only
    // this half is rendered.
    reachTitle: (city) => `Deepest in ${city}, running across India.`,
    reachLine: "Briefs fill fastest where supply is deepest, and we run campaigns in every sector on this page.",

    closeTitle: "Post your first brief.",
    closeLine: "About ten minutes. We check your business before anything reaches a creator.",
};


export default function ForBrands() {
    return (
        <MarketingPage
            testid={IDS.forBrands}
            title="Influencer marketing for brands, run end to end"
            description="Post a brief and the WeAre Studios team runs the campaign: verified creators, every rate visible before you book, approval before anything is published, and a report at the end. Across India, in every sector we run."
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

            {/* **The evidence, directly after the claim.** The steps above
                say what we do; this says we have done it, with a brand name
                and a real number on each card. It sits here rather than at
                the bottom because a brand deciding whether to read on is
                deciding at exactly this point.

                Its copy is not charged to the page's word budget, the same
                treatment `ProofStrip` and `CreatorLeaderboard` already get:
                what it renders is fetched rather than written, and the
                heading that frames it belongs to the component that draws
                every instance of it. */}
            <CaseStudyStrip />

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

            {/* The whole section is behind the counted city, not just the
                noun in its title: an eyebrow reading "Where we are" above a
                sentence with the place removed is a worse answer than no
                section. */}
            <CountedGeography>
                {(city) => (
                    <TextImageSection
                        eyebrow="Where we are"
                        title={COPY.reachTitle(city)}
                        line={COPY.reachLine}
                        image={{
                            // PLACEHOLDER IMAGE: shopfronts in the deepest-supply
                            // city at dusk, lit up, landscape 3:2. Deliberately
                            // not a named neighbourhood — the city this section
                            // names is counted at request time, so a note
                            // naming Indiranagar would brief a photograph for
                            // a city the page may not be talking about.
                            note: "City shopfronts at dusk, lit up, people on the street, landscape 3:2",
                            ratio: "3/2",
                        }}
                    />
                )}
            </CountedGeography>

            <ClosingSection
                title={COPY.closeTitle}
                line={COPY.closeLine}
                cta={{ ...ASK, testid: IDS.ctaBottom }}
            />
        </MarketingPage>
    );
}
