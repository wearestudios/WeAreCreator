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
import PayoutClock from "@/components/marketing/PayoutClock";
import { MARKETING as IDS } from "@/constants/testIds";

const ASK = { to: "/signup?role=creator", label: "Join as a creator" };

const COPY = {
    title: "Paid work, your rate agreed up front.",
    line: "Briefs from businesses we have checked. You quote your rate, it goes in writing before you shoot, and you keep every rupee of it.",
    footnote: "Free to join, and we never charge you a fee.",

    props: [
        {
            label: "Real paid briefs",
            line: "Every brand is checked against its paperwork before it can post a brief you can see.",
        },
        {
            label: "Your rate, before you shoot",
            line: "Agreed in writing and recorded against the booking, so there is nothing to argue about afterwards.",
        },
        {
            label: "You keep all of it",
            line: "Our fee is charged to the brand on top, never taken out of yours.",
        },
    ],

    stepsTitle: "From signing up to being paid.",
    steps: [
        {
            label: "Build your profile",
            line: "A name and a WhatsApp number to start. Fill in the rest over as many sittings as you like.",
        },
        {
            label: "Get verified",
            line: "Send it for review. A person reads it and comes back to you, and you can pitch while you wait.",
        },
        {
            label: "Pitch your rate",
            line: "Apply with a note and a figure. It is agreed in writing before anything is booked.",
        },
        {
            label: "Shoot, deliver, get paid",
            line: "Drafts are approved before you publish. Payment follows approval, to your UPI ID or bank account.",
        },
    ],

    askTitle: "What we ask of you.",
    askLine: "Nothing you would not put in a media kit — and saving a half-finished profile never puts you in a queue.",
    asks: [
        {
            label: "A profile worth shortlisting",
            line: "Your city, the formats you post, and links to work a brand can look at.",
        },
        {
            label: "Payout details come later",
            line: "UPI and PAN before your first payment, and never part of being looked at.",
        },
        {
            label: "Connecting Instagram is optional",
            line: "Connect it and your audience is read from Instagram’s official API rather than typed in by you.",
        },
    ],

    costTitle: "It costs nothing.",
    // **"That is not an introductory offer." came out as a duplicate**, not to
    // make room: the hero footnote already says "we never charge you a fee",
    // and `never` is the same promise of permanence in a word rather than a
    // sentence. `PayoutClock` below is what the section gained.
    costLine: "No subscription, no joining fee, and nothing deducted from your rate.",

    closeTitle: "Join as a creator.",
    closeLine: "A name and a WhatsApp number. Everything else can wait.",
};


export default function ForCreators() {
    return (
        <MarketingPage
            testid={IDS.forCreators}
            title="Paid influencer campaigns for creators"
            description="Paid briefs from businesses we have checked, your rate agreed in writing before you shoot, and payment on approved delivery. Free to join, and we never take a cut of your fee."
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
                    // The note names a city because it briefs a shoot; the
                    // alt describes what is in frame, and a café is a café.
                    alt: "A creator filming in a café, phone on a small tripod in window light.",
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

            {/* **When, not how much** — which is why this sits under "What it
                costs" without taking anything out of it. That section answers
                what we deduct (nothing); this answers the question the survey
                found underneath it, which creators asked even when they had
                been paid quickly: nobody had ever told them when. */}
            <section className="border-b border-white/10 py-16 md:py-20">
                <div className="mx-auto max-w-7xl px-6">
                    <PayoutClock />
                </div>
            </section>

            <ClosingSection
                title={COPY.closeTitle}
                line={COPY.closeLine}
                cta={{ ...ASK, testid: IDS.ctaBottom }}
            />
        </MarketingPage>
    );
}
