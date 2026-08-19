// /for-creators — one reader, one ask, under 250 words.
//
// A compression of the page that was here, not a repositioning. The six things
// a creator has to come away knowing are unchanged and still pinned by tests:
// real paid briefs in one place; the rate agreed in writing before they shoot;
// they keep all of it because our fee sits on the brand; payment follows
// approved delivery; brands are checked; joining is free.
//
// Nothing here asks for the other audience. A "post a campaign" link on this
// page is the competing second door the single-CTA rule exists to stop — the
// footer is where somebody in the wrong place finds the right page.
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

const ASK = { to: "/signup?role=creator", label: "Join as a creator" };

const COPY = {
    title: "Paid work, agreed in writing.",
    line: "Paid briefs from businesses we checked. You quote your rate and keep all of it.",
    footnote: "Free to join, and it stays free.",

    props: [
        {
            label: "Real paid briefs",
            line: "Every brand is checked before it can reach you.",
        },
        {
            label: "Your rate, before you shoot",
            line: "In writing, recorded against the booking, before you shoot.",
        },
        {
            label: "You keep all of it",
            line: "Our fee is charged to the brand on top, never taken out of yours.",
        },
    ],

    stepsTitle: "Signing up to being paid.",
    steps: [
        {
            label: "Build your profile",
            line: "A name and a WhatsApp number to start. Fill in the rest whenever you like.",
        },
        {
            label: "Get verified",
            line: "Send it for review. Somebody reads it and comes back to you.",
        },
        {
            label: "Pitch your rate",
            line: "Apply with a note and a figure. Agreed in writing before anything is booked.",
        },
        {
            label: "Shoot, deliver, get paid",
            line: "Drafts approved before you publish. Payment follows approval, to your UPI ID.",
        },
    ],

    askTitle: "What we ask of you.",
    askLine: "Nothing you would not put in a media kit — and saving never puts you in a queue.",
    asks: [
        {
            label: "A profile worth shortlisting",
            line: "Your city, what you make, and links to your work.",
        },
        {
            label: "Payout details, later",
            line: "UPI and PAN before your first payment. Never part of being looked at.",
        },
        {
            label: "Instagram, if you want",
            line: "Connect it and your numbers are read from Instagram rather than typed in.",
        },
    ],

    costTitle: "It costs nothing.",
    costLine: "No subscription, and nothing deducted from your rate. That is not an introductory offer.",

    closeTitle: "Join as a creator.",
    closeLine: "A name and a WhatsApp number. Everything else can wait.",
};

export default function ForCreators() {
    return (
        <MarketingPage
            testid={IDS.forCreators}
            title="Paid brand campaigns for creators"
            description="Real paid briefs from businesses we have checked, your rate agreed in writing before you shoot, and payment on approved delivery. Free to join."
            path="/for-creators"
        >
            <MarketingHero
                eyebrow="For creators"
                title={COPY.title}
                line={COPY.line}
                cta={{ ...ASK, testid: IDS.ctaTop }}
                footnote={COPY.footnote}
                image={{
                    // PLACEHOLDER IMAGE: a creator mid-shoot at a Bengaluru
                    // café — phone on a small tripod, natural window light,
                    // their hands in frame. Landscape 16:9.
                    note: "Creator mid-shoot at a Bengaluru cafe, phone on a tripod, window light, 16:9",
                    ratio: "16/9",
                }}
            />

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
                eyebrow="What we ask"
                title={COPY.askTitle}
                line={COPY.askLine}
                points={COPY.asks}
                image={{
                    // PLACEHOLDER IMAGE: over-the-shoulder of a creator filling
                    // in their profile on a phone, café table, evening. 4:3.
                    note: "Over-the-shoulder of a creator filling in their profile on a phone, 4:3",
                    ratio: "4/3",
                }}
                flip
            />

            <TextImageSection
                eyebrow="What it costs"
                title={COPY.costTitle}
                line={COPY.costLine}
                image={{
                    // PLACEHOLDER IMAGE: a creator checking a payment
                    // confirmation on their phone, warm interior, candid. 3:2.
                    note: "Creator checking a payment confirmation on their phone, candid, 3:2",
                    ratio: "3/2",
                }}
            />

            <ClosingSection
                title={COPY.closeTitle}
                line={COPY.closeLine}
                cta={{ ...ASK, testid: IDS.ctaBottom }}
                image={{
                    // PLACEHOLDER IMAGE: a group of creators at a brand event,
                    // shot from behind, phones up. Dark edges, busy centre —
                    // it sits dimmed behind the closing CTA. 21:9.
                    note: "Creators at a brand event shot from behind, phones up, dark edges, 21:9",
                    ratio: "21/9",
                }}
            />
        </MarketingPage>
    );
}
