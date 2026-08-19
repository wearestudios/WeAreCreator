// /how-it-works — the journey, both sides at once, under 300 words.
//
// **Parallel tracks, deliberately.** A creator's step and the brand's step
// opposite it happen at the same moment, and that is the argument: the rate is
// agreed on both sides of one row, the draft is approved on the other side of
// the row where it was submitted. Two separate lists would lose it.
//
// The compression is what made the tracks readable. Each cell used to be a
// forty-word paragraph, which is twelve paragraphs on one page — nobody read
// across a row, they read down one column and left. A label and one line can
// actually be compared to the thing beside it, which is the whole point of the
// layout.
//
// No single ask: this page is read by both sides, and picking one for the
// visitor puts half of them through the wrong door. It routes at the close,
// the same way home does.
import React from "react";

import {
    MarketingPage,
    MarketingHero,
    Points,
    TextImageSection,
    ClosingSection,
    TwoPaths,
    Eyebrow,
} from "@/components/marketing/Sections";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import Reveal from "@/components/marketing/Reveal";
import { CARD_HOVER } from "@/components/marketing/motion";
import { MARKETING as IDS } from "@/constants/testIds";

const COPY = {
    title: "Both sides of the same campaign.",
    line: "A creator from signing up to being paid, and a brand from brief to report.",

    tracksTitle: "Six moments, from both sides.",
    tracks: [
        {
            moment: "Getting on",
            creator: { label: "Build a profile", line: "Reviewed by a person before you can pitch." },
            brand: { label: "Register the business", line: "Checked against your paperwork before you reach anyone." },
        },
        {
            moment: "The brief",
            creator: { label: "Find it and pitch", line: "Ranked by fit, never by what it pays." },
            brand: { label: "Post it, see who applies", line: "Applicants arrive with their rate, ranked alongside suggestions." },
        },
        {
            moment: "The money",
            creator: { label: "Rate agreed first", line: "Recorded against the booking, not left in a DM." },
            brand: { label: "You pay us", line: "Creator's rate plus our fee, both shown before you confirm." },
        },
        {
            moment: "The shoot",
            creator: { label: "Book a slot", line: "Inside the hours the venue can take people." },
            brand: { label: "See the roster", line: "Who is booked, when, and what changes." },
        },
        {
            moment: "Before it is live",
            creator: { label: "Send the draft", line: "Publish once it is approved. Nothing gets taken down." },
            brand: { label: "Approve or ask", line: "Nothing is published until you have said yes." },
        },
        {
            moment: "Afterwards",
            creator: { label: "Paid on delivery", line: "Released once the brand approves. No invoice to chase." },
            brand: { label: "Read the report", line: "Reach, engagement and cost per thousand, in one place." },
        },
    ],

    trustTitle: "What makes it a process.",
    trust: [
        {
            label: "Verified both ways",
            line: "Neither side is taking the other's word for it.",
        },
        {
            label: "Rate in writing",
            line: "Agreed before the shoot, because it is what gets argued about after.",
        },
        {
            label: "Approval before public",
            line: "The brand sees the content before the creator's followers do.",
        },
        {
            label: "Paid on approved delivery",
            line: "The brand pays us; we release once the work is approved.",
        },
    ],

    ownerTitle: "Every brief says who runs it.",
    ownerLine: "The brand, or the WeAre Studios team. That decides who answers you and who reviews the draft.",

    closeTitle: "Start on either side.",
    closeLine: "Creators join free. We check a brand before it reaches anyone.",
};

/** One side of one moment. A label, a line, and nothing else. */
function Track({ side, entry, testid }) {
    return (
        <div
            data-testid={testid}
            className={`h-full rounded-lg border border-white/10 bg-card grain-surface p-5 ${CARD_HOVER}`}
        >
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {side}
            </p>
            <h3 className="mt-2.5 font-serif text-fluid-xl leading-tight tracking-tight">
                {entry.label}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {entry.line}
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
                title={COPY.title}
                line={COPY.line}
                image={{
                    // PLACEHOLDER IMAGE: a brand manager and a creator talking
                    // across a table at a venue before a shoot, both with
                    // phones out. Landscape 16:9.
                    note: "Brand manager and creator talking across a table before a shoot, 16:9",
                    ratio: "16/9",
                }}
            />

            <section className="border-b border-white/10 py-16 md:py-20">
                <div className="mx-auto max-w-7xl px-6">
                    <Reveal>
                        <Eyebrow>The journey</Eyebrow>
                    </Reveal>
                    <Reveal i={1}>
                        <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                            {COPY.tracksTitle}
                        </h2>
                    </Reveal>

                    {/* Column headings on desktop only. Each card names its own
                        side, so a phone loses nothing — and two words pinned
                        above a 390px column would eat the fold. */}
                    <div className="mt-10 hidden grid-cols-12 gap-6 md:grid">
                        <div className="col-span-2" />
                        <p className="col-span-5 text-[10px] uppercase tracking-[0.2em] text-ember-500">
                            Creator
                        </p>
                        <p className="col-span-5 text-[10px] uppercase tracking-[0.2em] text-ember-500">
                            Brand
                        </p>
                    </div>

                    <div className="mt-6 space-y-8 md:mt-4 md:space-y-5">
                        {COPY.tracks.map((row, i) => (
                            <Reveal
                                key={row.moment}
                                i={i % 3}
                                className="grid gap-4 md:grid-cols-12 md:items-stretch md:gap-6"
                            >
                                <p className="font-serif text-fluid-lg leading-tight tracking-tight text-ember-500 md:col-span-2 md:pt-5">
                                    {row.moment}
                                </p>
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
                            </Reveal>
                        ))}
                    </div>
                </div>
            </section>

            <section
                data-testid={IDS.trust}
                className="border-b border-white/10 py-16 md:py-20"
            >
                <div className="mx-auto max-w-7xl px-6">
                    <div className="grid gap-12 md:grid-cols-12 md:items-center">
                        <div className="group md:col-span-5">
                            <Reveal>
                                <Eyebrow>What holds it together</Eyebrow>
                            </Reveal>
                            <Reveal i={1}>
                                <h2 className="mt-4 font-serif text-fluid-4xl leading-tight tracking-tight">
                                    {COPY.trustTitle}
                                </h2>
                            </Reveal>
                            <Reveal i={2} noTravel className="mt-8">
                                <PlaceholderImage
                                    // PLACEHOLDER IMAGE: a printed campaign
                                    // report on a desk beside a phone showing
                                    // the same numbers. Landscape 5:4.
                                    note="Printed campaign report on a desk beside a phone showing the same numbers, 5:4"
                                    ratio="5/4"
                                    zoom
                                />
                            </Reveal>
                        </div>
                        <div className="md:col-span-7">
                            <Points items={COPY.trust} columns={4} />
                        </div>
                    </div>
                </div>
            </section>

            <TextImageSection
                eyebrow="Who runs it"
                title={COPY.ownerTitle}
                line={COPY.ownerLine}
                image={{
                    // PLACEHOLDER IMAGE: a WeAre manager with a clipboard and
                    // a phone, briefing two creators at a venue entrance. 4:3.
                    note: "WeAre manager briefing two creators at a venue entrance, 4:3",
                    ratio: "4/3",
                }}
                flip
            />

            <ClosingSection
                title={COPY.closeTitle}
                line={COPY.closeLine}
            >
                <TwoPaths testid={IDS.twoPaths} tone="coral" />
            </ClosingSection>
        </MarketingPage>
    );
}
