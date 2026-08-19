// /for-brands — the full brand narrative, one reader, one ask.
//
// The copy is carried over from the server-rendered version this replaces
// rather than rewritten: it was written to the positioning and pinned by
// tests, and a restructure is not a licence to re-argue settled wording.
//
// **The positioning, since it governs every line here:** what we are against
// is disorganisation — campaigns run over DMs and spreadsheets, nobody
// checked, no rate in writing, no proof of what it achieved. It is
// deliberately *not* agencies. WeAre Studios is one, the managed service is a
// real offering somebody chooses, and "without an agency" would be a page
// arguing against our own product.
//
// Bengaluru appears as evidence of network depth, never as identity: the
// network is deepest there, which is a fact about how much we can do rather
// than a statement about who we are.
import React from "react";

import {
    MarketingPage,
    MarketingHero,
    ValueProps,
    Steps,
    TextImageSection,
    ClosingSection,
} from "@/components/marketing/Sections";
import ProofStrip from "@/components/marketing/ProofStrip";
import { MARKETING as IDS } from "@/constants/testIds";

const ASK = { to: "/signup?role=brand", label: "Post a campaign" };

const VALUE_PROPS = [
    {
        title: "Creators we have actually checked",
        body:
            "Every creator is reviewed by a person before a brand can see them — the " +
            "account, the work, whether the audience looks real. Where a creator has " +
            "connected Instagram, the follower count and engagement rate on their " +
            "profile are read from Instagram itself, and the ones we could not measure " +
            "say so rather than quietly passing as verified.",
    },
    {
        title: "Every creator, every rate, in front of you",
        body:
            "You see who applied and what each of them quoted, and the rate is recorded " +
            "against the booking before anybody turns up. No retainer, and no markup on " +
            "what the creator charges — our fee sits on top and is shown to you before " +
            "you confirm, so the number the creator quoted is the number the creator gets.",
    },
    {
        title: "Run it yourself, or hand it to the team",
        body:
            "WeAre Studios runs campaigns for a living. Post the brief and manage it " +
            "from your own dashboard, or hand it over and we will staff it, book the " +
            "slots, stand at the door on the day and send you the numbers afterwards. " +
            "You choose per campaign, and you can choose differently next time.",
    },
];

const STEPS = [
    {
        title: "Post your brief",
        body:
            "What you want made, the budget per creator, the dates, and which days and " +
            "hours your venue can actually take people. Ten minutes.",
    },
    {
        title: "Review applicants, or our suggestions",
        body:
            "Creators apply with a pitch and a rate. Alongside them we rank the verified " +
            "creators who fit the brief, with the reason on every card so you can argue " +
            "with it. Accept who you want, or invite them directly.",
    },
    {
        title: "They shoot on slots they booked",
        body:
            "Inside the days and hours you set. Your campaign manager holds the roster " +
            "and the phone numbers, and you are told what changes.",
    },
    {
        title: "Approve it, then see what it did",
        body:
            "Turn on draft review and nothing is published until you have said yes — or " +
            "asked for a change. Afterwards: reach, engagement and cost per thousand, on " +
            "one report you can send on.",
    },
];

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
                title="Fill the room. Launch the thing."
                standfirst="Creators we have checked, rates agreed in writing before anyone shoots, nothing published until you have approved it, and a report at the end showing what it achieved. Run it yourself, or hand it to our team."
                cta={{ ...ASK, testid: IDS.ctaTop }}
                image={{
                    // PLACEHOLDER IMAGE: a full restaurant on opening night in
                    // Bengaluru, shot wide from the back of the room, warm
                    // service lighting, a creator filming at a table in the
                    // mid-ground. Landscape 16:9.
                    note: "Full restaurant on opening night, creator filming at a table, landscape 16:9",
                    ratio: "16/9",
                }}
                footnote="No retainer. No markup on creator fees."
            />

            {/* Counted, never written down — and absent entirely below the
                floors, because a small number is not proof. */}
            <ProofStrip />

            <ValueProps items={VALUE_PROPS} testid={IDS.valueProps} />

            <Steps
                eyebrow="How it works"
                title="From brief to report, in four moves."
                items={STEPS}
                testid={IDS.steps}
            />

            <TextImageSection
                eyebrow="The choice"
                title="Self-serve, or we run it."
                body="Both are real offerings and you pick per campaign. Self-serve is the dashboard: you post, you shortlist, you approve. Managed is the WeAre Studios team doing the same work with our people — an option you choose, never a fee you are locked into."
                points={[
                    "Hand over one campaign and keep the next one yourself.",
                    "A managed campaign gets a named manager, a booked roster and somebody at the door on the day.",
                    "Either way you approve the content and you get the report.",
                ]}
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
                title="Deepest in Bengaluru."
                body="That is where the network is thickest and where most campaigns run today — which is a fact about how quickly we can fill a brief, not a statement about who we are. Creators sign up from anywhere in India."
                image={{
                    // PLACEHOLDER IMAGE: a recognisable Bengaluru neighbourhood
                    // at dusk — Indiranagar or Koramangala shopfronts lit up.
                    // Landscape 3:2.
                    note: "Bengaluru shopfronts at dusk, Indiranagar or Koramangala, landscape 3:2",
                    ratio: "3/2",
                }}
            />

            <ClosingSection
                title="Post your first brief."
                body="It takes about ten minutes, and nothing reaches a creator until we have checked your business."
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
