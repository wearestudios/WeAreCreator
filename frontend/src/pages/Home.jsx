// The home page, brands first.
//
// Eight sections, in this order: the hero (a static two-line headline, the
// four-step deck and the counter history), the swap from spreadsheet to
// record, a photograph, the four steps expanded, the one navy band of things
// the product enforces, who built it, the creator door, and the close.
//
// **Every word is in `HOME` in `content/marketing.js`.** This file holds
// layout. The three moments of motion the site is allowed are the headline's
// entrance here, the counter history writing itself in the deck, and the
// money count on /creators; everything else appears.
import React from "react";

import ComparisonBand from "@/components/marketing/ComparisonBand";
import HeroDeckProvider, { DeckStage, RotatingLine, StepRail } from "@/components/marketing/HeroDeck";
import PhotoSlot from "@/components/marketing/PhotoSlot";
import { MarketingPage } from "@/components/marketing/Sections";
import {
    Closing,
    Eyebrow,
    OutlineButton,
    PhotoBand,
    PrimaryButton,
    PromiseBand,
    SectionHead,
    Wrap,
} from "@/components/marketing/SiteParts";
import { LineEntrance } from "@/components/marketing/primitives";
import { LANDING, LANDING_CLOSING, LANDING_HERO, LANDING_PAGE } from "@/constants/testIds";
import { ASK_BRAND, ASK_TALK, CLIENTS, HOME } from "@/content/marketing";
import { pad } from "@/lib/heroDeck";
import { HERO_EYEBROW } from "@/lib/siteNav";

/**
 * The hero. **The headline is full width** — at 120px it cannot share a row
 * with anything — then the rotating line beside the asks, then the rail and
 * the card. The `h1` never changes: its two lines rise once at load, and its
 * accessible name is the sentence, set once.
 */
function Hero() {
    const { hero } = HOME;
    return (
        <section data-testid={LANDING_HERO.section} className="relative">
            <HeroDeckProvider steps={hero.steps}>
                <Wrap className="pb-20 pt-14 md:pb-28 md:pt-20">
                    <Eyebrow testid={LANDING_HERO.eyebrow}>{HERO_EYEBROW}</Eyebrow>
                    <h1
                        data-testid={LANDING_HERO.heading}
                        aria-label={hero.titleLines.join(" ")}
                        className="mkt-display mt-6 text-heading"
                    >
                        <LineEntrance as="span" lines={hero.titleLines} className="block" />
                    </h1>

                    <div className="mt-10 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between lg:gap-12">
                        <RotatingLine className="max-w-3xl" />
                        <div className="flex shrink-0 flex-col gap-3 sm:flex-row">
                            <PrimaryButton {...ASK_BRAND} testid={LANDING_HERO.ctaBrand} />
                            <OutlineButton {...ASK_TALK} testid={LANDING_HERO.ctaTalk} />
                        </div>
                    </div>

                    <div className="mt-14 grid gap-4 lg:grid-cols-12 lg:gap-6">
                        <StepRail label={hero.railLabel} className="lg:col-span-3 lg:content-start" />
                        <DeckStage className="lg:col-span-9" />
                    </div>
                </Wrap>
            </HeroDeckProvider>
        </section>
    );
}

/** The four steps, expanded. Step 03 says, quietly, that it is ours. */
function Steps() {
    const { steps } = HOME;
    return (
        <section data-testid={LANDING_PAGE.steps}>
            <Wrap className="py-20 md:py-28">
                <SectionHead eyebrow={steps.eyebrow} title={steps.title} />
                <ol className="mt-14 grid gap-10 sm:grid-cols-2 lg:grid-cols-4 lg:gap-8">
                    {steps.items.map((item, i) => (
                        <li key={item.title} data-testid={LANDING_PAGE.step(i)} className="border-t border-border pt-6">
                            <span className="mkt-h3 block text-accent">{pad(i + 1)}</span>
                            <h3 className="mkt-h3 mt-3 text-heading">{item.title}</h3>
                            {item.tag ? (
                                <p
                                    data-testid={LANDING_PAGE.stepTag}
                                    className="mt-3 inline-block rounded-full border border-border px-3 py-1 text-meta text-muted-foreground"
                                >
                                    {item.tag}
                                </p>
                            ) : null}
                            <p className="mkt-body mt-4 text-muted-foreground">{item.line}</p>
                        </li>
                    ))}
                </ol>
            </Wrap>
        </section>
    );
}

/**
 * Who built it. **Absent until three real client names are supplied** —
 * the "absent rather than short" rule the brand wall holds. A section of
 * three empty cards would be a claim with nothing behind it.
 */
function Clients() {
    if (!CLIENTS.every((c) => c.name)) return null;
    return (
        <section data-testid={LANDING_PAGE.clients}>
            <Wrap className="py-20 md:py-28">
                <SectionHead eyebrow={HOME.clients.eyebrow} title={HOME.clients.title} />
                <ul className="mt-12 grid gap-6 md:grid-cols-3">
                    {CLIENTS.map((c, i) => (
                        <li key={c.slot} data-testid={LANDING_PAGE.client(i)}>
                            <PhotoSlot id={c.slot} className="rounded-lg" />
                            <h3 className="mkt-h3 mt-5 text-heading">{c.name}</h3>
                            {c.line ? <p className="mkt-body mt-2 text-muted-foreground">{c.line}</p> : null}
                        </li>
                    ))}
                </ul>
            </Wrap>
        </section>
    );
}

/** One band for the other audience: a warm inset, one line, one door. */
function CreatorDoor() {
    const { creatorDoor } = HOME;
    return (
        <section data-testid={LANDING_PAGE.creatorDoor}>
            <Wrap className="py-10 md:py-16">
                <div className="flex flex-col gap-8 rounded-xl border border-border bg-wash px-6 py-12 md:flex-row md:items-center md:justify-between md:px-14 md:py-16">
                    <h2 className="mkt-h2 max-w-3xl text-heading">{creatorDoor.title}</h2>
                    <OutlineButton {...creatorDoor.cta} testid={LANDING_PAGE.creatorDoorCta} className="shrink-0" />
                </div>
            </Wrap>
        </section>
    );
}

export default function Home() {
    return (
        <MarketingPage
            testid={LANDING.page}
            title={HOME.meta.title}
            description={HOME.meta.description}
            path="/"
        >
            <Hero />
            <ComparisonBand copy={HOME.swap} />
            <PhotoBand slot="home-band" title={HOME.band.title} testid={LANDING_PAGE.band} />
            <Steps />
            <PromiseBand
                testid={LANDING_PAGE.promises}
                itemTestid={LANDING_PAGE.promise}
                eyebrow={HOME.promises.eyebrow}
                title={HOME.promises.title}
                items={HOME.promises.items}
            />
            <Clients />
            <CreatorDoor />
            <Closing testid={LANDING_CLOSING.section} title={HOME.close.title} line={HOME.close.line}>
                <PrimaryButton {...ASK_BRAND} testid={LANDING_CLOSING.ctaBrand} />
                <OutlineButton {...ASK_TALK} testid={LANDING_CLOSING.ctaTalk} />
            </Closing>
        </MarketingPage>
    );
}
