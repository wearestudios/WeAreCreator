// /how-it-works — the end-to-end journey, both sides at once.
//
// The audience pages each tell one side's story to that side. This page exists
// for the visitor who wants to see the *whole* thing before choosing a door —
// and for the one who wants to know what the other party is being held to.
//
// **Parallel tracks, deliberately.** A creator's step and the brand's step
// opposite it happen at the same moment, and that is the argument: the rate is
// agreed on both sides of the same row, the draft is approved on the other
// side of the row where it was submitted. Two separate lists would lose it.
//
// The tracks are a two-column grid on desktop and stack on a phone, creator
// first — mobile is where most creators arrive from a WhatsApp link.
import React from "react";

import {
    MarketingPage,
    MarketingHero,
    TextImageSection,
    ClosingSection,
    TwoPaths,
    Eyebrow,
} from "@/components/marketing/Sections";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import { MARKETING as IDS } from "@/constants/testIds";

// No single ask on this page. It is read by both sides, and picking one for
// the visitor puts half of them through the wrong door — so it routes at the
// close, the same way home does. The audience pages are where one ask stated
// twice is the rule.

/**
 * One row is one moment, seen from both sides.
 *
 * Where only one side acts, the other says what it is waiting on rather than
 * being left blank — a gap in a parallel track reads as a step somebody forgot
 * to write, and "nothing is required of you here" is itself worth knowing.
 */
const TRACKS = [
    {
        moment: "Getting on",
        creator: {
            title: "Build a profile, get verified",
            body:
                "A name and a WhatsApp number to start, then your city, what you make, " +
                "your rate and links to your work. Send it for review when it is done; " +
                "somebody reads it and comes back to you.",
        },
        brand: {
            title: "Register the business, get verified",
            body:
                "The legal entity, the registered address, and the person asking on the " +
                "business's behalf — plus one document that proves the business exists. " +
                "Until that is checked, you cannot reach a creator at all.",
        },
    },
    {
        moment: "The brief",
        creator: {
            title: "Find it and pitch",
            body:
                "Briefs are ranked by how well they fit you, never by what they pay. You " +
                "see the deliverable and what it pays before you spend an evening on a " +
                "pitch, and you apply with a note and your own rate.",
        },
        brand: {
            title: "Post it, and see who applies",
            body:
                "What you want made, the budget, the dates, and the days and hours your " +
                "venue can take people. Applicants arrive with their rate; alongside them " +
                "we rank verified creators who fit, with the reason on every card.",
        },
    },
    {
        moment: "The money",
        creator: {
            title: "The rate is agreed before you shoot",
            body:
                "Recorded against the booking, not left in a DM. On a fixed-fee brief it " +
                "is the figure on the brief; on a negotiated one it is what the two of " +
                "you settle on. Barter briefs say so on their face.",
        },
        brand: {
            title: "You see the fee, and the fee on top",
            body:
                "Our platform fee is charged to you, on top of the creator's rate, and " +
                "shown before you confirm. No retainer, and no markup on what the creator " +
                "charges — the number they quoted is the number they get.",
        },
    },
    {
        moment: "The shoot",
        creator: {
            title: "Book a slot that suits you",
            body:
                "Inside the days and hours the venue can take people, so nobody turns up " +
                "during service. Release it up to 24 hours before if you have to. Check " +
                "in at the door from your phone.",
        },
        brand: {
            title: "The roster, and who is at the door",
            body:
                "You see who is booked and when. On a managed campaign one of our people " +
                "holds the roster and stands at the door; on your own, your manager does. " +
                "Either way you are told what changes.",
        },
    },
    {
        moment: "Before it goes live",
        creator: {
            title: "Send the draft first",
            body:
                "On campaigns that review drafts you send a file or an unlisted link and " +
                "publish once it is approved. Which means nobody ever asks you to take " +
                "down a post that is already up.",
        },
        brand: {
            title: "Approve it, or ask for a change",
            body:
                "Nothing is published until you have said yes. A change request carries a " +
                "note saying what to change — a send-back with no reason is a round trip " +
                "wasted, so the note is required.",
        },
    },
    {
        moment: "Afterwards",
        creator: {
            title: "Paid on approved delivery",
            body:
                "You publish, submit the links, and the brand approves the delivery. " +
                "Payment follows that, to the UPI ID on your profile. You are not chasing " +
                "an invoice.",
        },
        brand: {
            title: "A report showing what it did",
            body:
                "Reach, engagement and cost per thousand across the campaign, on one " +
                "report you can send on. Barter deliveries are counted separately, so a " +
                "cost per thousand is never flattered by reach nobody paid for.",
        },
    },
];

const TRUST = [
    {
        title: "Verification, both ways",
        body:
            "A creator is reviewed by a person before a brand can see them. A brand is " +
            "checked against its own paperwork before it can reach a creator. Neither " +
            "side is taking the other's word for it.",
    },
    {
        title: "The rate, in writing, before the shoot",
        body:
            "Agreed and recorded against the booking rather than settled on the day. " +
            "It is the single thing most often argued about afterwards, so it is the " +
            "thing we write down first.",
    },
    {
        title: "Approval before anything is public",
        body:
            "Draft review puts the brand's first sight of the content before the " +
            "creator's followers get theirs. Without it, \"can we change the caption\" " +
            "is a request to delete a post.",
    },
    {
        title: "Payment on approved delivery",
        body:
            "Not on a promise and not on a schedule — on the brand having approved what " +
            "was delivered. The creator keeps 100% of the agreed rate; our fee is " +
            "charged to the brand on top.",
    },
];

function Track({ side, entry, testid }) {
    return (
        <div
            data-testid={testid}
            className="rounded-lg border border-white/10 bg-card grain-surface p-6"
        >
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {side}
            </p>
            <h3 className="mt-3 font-serif text-fluid-2xl leading-tight tracking-tight">
                {entry.title}
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {entry.body}
            </p>
        </div>
    );
}

export default function HowItWorks() {
    return (
        <MarketingPage
            testid={IDS.howItWorks}
            title="How it works, for creators and brands"
            description="The whole journey side by side: a creator from signup to paid, a brand from brief to report, with verification, rates in writing, draft approval and payment on delivery."
            path="/how-it-works"
        >
            <MarketingHero
                eyebrow="How it works"
                title="Both sides of the same campaign."
                standfirst="A creator's path from signing up to being paid, and a brand's from posting a brief to reading the report — shown against each other, because each step is one moment seen from two sides."
                image={{
                    // PLACEHOLDER IMAGE: a brand manager and a creator talking
                    // across a table at a venue before a shoot, both with
                    // phones out. Landscape 16:9.
                    note: "Brand manager and creator talking across a table before a shoot, 16:9",
                    ratio: "16/9",
                }}
            />

            <section className="border-b border-white/10 py-16 md:py-24">
                <div className="mx-auto max-w-7xl px-6">
                    <Eyebrow>The journey</Eyebrow>
                    <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        Six moments, from both sides.
                    </h2>

                    {/* The column headings sit above the grid on desktop and
                        are absent on a phone, where each card names its own
                        side — a sticky two-column header on a 390px screen
                        would eat the fold to label two words. */}
                    <div className="mt-12 hidden grid-cols-12 gap-6 md:grid">
                        <div className="col-span-2" />
                        <p className="col-span-5 text-[10px] uppercase tracking-[0.2em] text-ember-500">
                            Creator
                        </p>
                        <p className="col-span-5 text-[10px] uppercase tracking-[0.2em] text-ember-500">
                            Brand
                        </p>
                    </div>

                    <div className="mt-6 space-y-10 md:mt-4 md:space-y-6">
                        {TRACKS.map((row) => (
                            <div
                                key={row.moment}
                                className="grid gap-4 md:grid-cols-12 md:items-stretch md:gap-6"
                            >
                                <div className="md:col-span-2 md:pt-6">
                                    <p className="font-serif text-fluid-xl leading-tight tracking-tight text-ember-500">
                                        {row.moment}
                                    </p>
                                </div>
                                <div className="md:col-span-5">
                                    <Track
                                        side="Creator"
                                        entry={row.creator}
                                        testid={IDS.creatorTrack}
                                    />
                                </div>
                                <div className="md:col-span-5">
                                    <Track
                                        side="Brand"
                                        entry={row.brand}
                                        testid={IDS.brandTrack}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            <section
                data-testid={IDS.trust}
                className="border-b border-white/10 py-16 md:py-24"
            >
                <div className="mx-auto max-w-7xl px-6">
                    <div className="grid gap-12 md:grid-cols-12 md:items-center">
                        <div className="md:col-span-5">
                            <Eyebrow>What holds it together</Eyebrow>
                            <h2 className="mt-4 font-serif text-fluid-4xl leading-tight tracking-tight">
                                The four things that make it a process rather than a
                                group chat.
                            </h2>
                            <div className="mt-8">
                                <PlaceholderImage
                                    // PLACEHOLDER IMAGE: a printed campaign
                                    // report on a desk beside a phone showing
                                    // the same numbers. Landscape 5:4.
                                    note="Printed campaign report on a desk beside a phone showing the same numbers, 5:4"
                                    ratio="5/4"
                                />
                            </div>
                        </div>
                        <ul className="grid gap-6 md:col-span-7 md:grid-cols-2">
                            {TRUST.map((t) => (
                                <li
                                    key={t.title}
                                    className="rounded-lg border border-white/10 bg-card grain-surface p-6"
                                >
                                    <h3 className="font-serif text-fluid-2xl leading-tight tracking-tight">
                                        {t.title}
                                    </h3>
                                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                        {t.body}
                                    </p>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            </section>

            <TextImageSection
                eyebrow="Who runs it"
                title="Every brief says who you are dealing with."
                body="A campaign is run by the brand or by the WeAre Studios team, and the brief says which. It decides who answers a creator's questions and who reviews the draft — so nobody is guessing who to chase."
                image={{
                    // PLACEHOLDER IMAGE: a WeAre manager with a clipboard and
                    // a phone, briefing two creators at a venue entrance. 4:3.
                    note: "WeAre manager briefing two creators at a venue entrance, 4:3",
                    ratio: "4/3",
                }}
                flip
            />

            <ClosingSection
                title="Start on either side."
                body="Creators join free. Brands post a brief, and we check the business before anything reaches a creator."
                image={{
                    // PLACEHOLDER IMAGE: wide shot of a busy venue mid-shoot,
                    // two creators working, staff in the background. Dark
                    // edges — it sits dimmed behind the CTA. 21:9.
                    note: "Wide shot of a busy venue mid-shoot, two creators working, dark edges, 21:9",
                    ratio: "21/9",
                }}
            >
                <TwoPaths testid={IDS.twoPaths} />
            </ClosingSection>
        </MarketingPage>
    );
}
