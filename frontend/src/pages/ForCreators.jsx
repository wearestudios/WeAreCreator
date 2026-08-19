// /for-creators — the full creator narrative, one reader, one ask.
//
// Copy carried over from the server-rendered version this replaces. The six
// things a creator has to come away knowing are pinned by tests: real paid
// briefs in one place; the rate agreed in writing before they shoot; they keep
// 100% because our fee sits on the brand; payment follows approved delivery;
// brands are checked; joining is free and stays free.
//
// Nothing on this page asks for the other audience. A "post a campaign" link
// here is the competing second door the single-CTA rule exists to stop — the
// footer is where somebody in the wrong place finds the right one.
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

const ASK = { to: "/signup?role=creator", label: "Join as a creator" };

const VALUE_PROPS = [
    {
        title: "Real paid briefs, in one place",
        body:
            "Every brief on the platform comes from a business we have checked — the " +
            "legal entity, the paperwork, the person asking on its behalf. You can see " +
            "who is posting before you spend an evening on a pitch, and a brand that has " +
            "not been through that cannot reach you at all.",
    },
    {
        title: "Your rate, in writing, before you shoot",
        body:
            "You quote your own rate when you apply. It is agreed and recorded against " +
            "the booking before the shoot happens, so nobody is negotiating on the day " +
            "and there is no argument afterwards about what was said in a DM three weeks " +
            "ago.",
    },
    {
        title: "You keep all of it, and you are paid on delivery",
        body:
            "The rate you agreed is the amount you are paid. Our fee is charged to the " +
            "brand on top, never taken out of yours. Payment goes out once the brand " +
            "approves what you delivered — you are not chasing an invoice, and you are " +
            "not waiting on somebody to remember.",
    },
];

const STEPS = [
    {
        title: "Build your profile",
        body:
            "Name and a WhatsApp number to start. The rest — your city, what you make, " +
            "your rate, links to your work — you fill in over as many sittings as it " +
            "takes. Connect Instagram if you want your follower count and engagement read " +
            "from Instagram itself rather than typed in.",
    },
    {
        title: "Get verified",
        body:
            "Send it for review when it is complete. Somebody on our team reads it and " +
            "comes back to you. Once you are verified you can pitch on anything open.",
    },
    {
        title: "Pitch, and agree the rate",
        body:
            "Apply with a note and the rate you want. If the brand takes you on, the " +
            "figure is agreed and written down before anything is booked. Then you pick a " +
            "slot that suits you, inside the hours the venue can take people.",
    },
    {
        title: "Shoot, deliver, get paid",
        body:
            "Turn up and make the thing. On campaigns that review drafts you send yours " +
            "first and publish once it is approved — which means no request to take down " +
            "a post that is already live. Payment follows approval, to the UPI ID on your " +
            "profile.",
    },
];

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
                title="Paid work, agreed in writing."
                standfirst="Briefs from businesses we have checked. You quote your rate, it is recorded before you shoot, and you keep all of it — our fee is charged to the brand, never taken out of yours."
                cta={{ ...ASK, testid: IDS.ctaTop }}
                image={{
                    // PLACEHOLDER IMAGE: a creator mid-shoot at a Bengaluru
                    // café — phone on a small tripod, natural window light,
                    // their hands in frame. Landscape 16:9.
                    note: "Creator mid-shoot at a Bengaluru cafe, phone on a tripod, window light, 16:9",
                    ratio: "16/9",
                }}
                footnote="Free to join, and it stays free."
            />

            <ProofStrip />

            <ValueProps items={VALUE_PROPS} testid={IDS.valueProps} />

            <Steps
                eyebrow="How it works"
                title="From signing up to being paid."
                items={STEPS}
                testid={IDS.steps}
            />

            <TextImageSection
                eyebrow="What we ask of you"
                title="A profile somebody can shortlist from."
                body="Nothing you would not put in a media kit, and you build it over as many sittings as you like — saving never puts you in a queue. Only when you send it for review does anybody look."
                points={[
                    "Your city, what you make, the platforms you post on, and links to your work.",
                    "Payout details before your first payment — UPI and PAN, because tax is deducted at source. They are never part of being looked at.",
                    "Connect Instagram if you want your numbers read from Instagram itself. If you do not, your self-reported count stands and says so.",
                ]}
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
                title="Nothing, and that is not an introductory offer."
                body="Joining is free, applying is free, and there is no subscription. Our fee is charged to the brand on top of your rate, so the figure you agreed is the figure that reaches your account."
                image={{
                    // PLACEHOLDER IMAGE: a creator checking a payment
                    // confirmation on their phone, warm interior, candid. 3:2.
                    note: "Creator checking a payment confirmation on their phone, candid, 3:2",
                    ratio: "3/2",
                }}
            />

            <ClosingSection
                title="Join as a creator."
                body="A name and a WhatsApp number to start. Everything else can wait for the next sitting."
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
