// The home page. Brands first, eight sections, in this order:
//
//   1 the hero — the h1, one lead, two asks, one quiet line, and the card
//   2 the problem — the spreadsheet and the DMs, against the same campaign here
//   3 a full-bleed photograph (or, until there is one, its headline)
//   4 the four steps
//   5 the navy band: three things the code enforces
//   6 who built it: the heading and the one scroll-inked sentence
//   7 the creator door
//   8 the close
//
// **Every word is in `HOME` in `content/marketing.js`**; this file is layout.
// Each section is its numbered rule, one heading, at most one lead and its
// one component — nothing else. **No real business is named on this page**:
// the client marquee and cards were removed, and the only names here are the
// invented ones inside the drawn product UI.
//
// Motion here is the primitives and nothing else: the wipe on "chasing", the
// card's rows written once in view, and the one FillText sentence on the
// site.
import React from "react";

import ComparisonBand from "@/components/marketing/ComparisonBand";
import { MarketingPage } from "@/components/marketing/Sections";
import { FillText, WipeWord } from "@/components/marketing/primitives";
import { DealCard, StepScreen } from "@/components/marketing/siteMocks";
import {
    Closing,
    Cta,
    PhotoBand,
    PromiseBand,
    SectionHead,
    SectionRule,
    Wrap,
} from "@/components/marketing/SiteParts";
import StickyCta from "@/components/marketing/StickyCta";
import { LANDING_CLOSING, LANDING_HERO as HERO_IDS, LANDING_PAGE as IDS } from "@/constants/testIds";
import { ASK, HOME } from "@/content/marketing";

/** The h1 with its one accented word, whole in the DOM from the first paint. */
function HeroTitle({ title, accent }) {
    const at = title.lastIndexOf(accent);
    return (
        <h1 data-testid={HERO_IDS.heading} className="mkt-display text-heading">
            {title.slice(0, at)}
            {/* The padding keeps the italic g's overhang inside the wipe's
                clip; the matching negative margin keeps it from opening a
                gap before the full stop. */}
            <WipeWord className="-mr-[0.08em] pr-[0.08em]">
                {/* Fraunces true italic at 400, in the accent's ink. */}
                <em data-testid={HERO_IDS.accent} className="font-normal italic text-accent-ink">
                    {accent}
                </em>
            </WipeWord>
            {title.slice(at + accent.length)}
        </h1>
    );
}

/**
 * The hero: three type styles and nothing else — the Fraunces h1, the Inter
 * Tight lead and Inter Tight UI. The card's top sits level with the h1's
 * first line, and the section ends one ordinary section gap under the asks.
 */
function Hero() {
    const { hero, card } = HOME;
    return (
        <section id="hero" data-track-section="hero" data-testid={HERO_IDS.section}>
            <Wrap className="grid gap-10 pb-20 pt-8 md:pb-28 md:pt-12 xl:grid-cols-12 xl:items-start xl:gap-12">
                {/* Two columns from xl only, and the text takes eight of them
                    until 2xl: the container stops growing at 1280 while the
                    display size keeps climbing, so at 1440 "Creator
                    campaigns," no longer fit in seven, and below 1280 the h1
                    ran to four lines beside the card. Stacked, it is two. */}
                <div className="xl:col-span-8 2xl:col-span-7">
                    <HeroTitle title={hero.title} accent={hero.accent} />
                    <p data-testid={HERO_IDS.lead} className="mkt-lead mt-6 max-w-2xl text-muted-foreground">
                        {hero.lead}
                    </p>
                    <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                        <Cta ask={ASK.postBrief} testid={HERO_IDS.ctaBrand} />
                        <Cta ask={ASK.talkWhatsapp} variant="outline" testid={HERO_IDS.ctaTalk} />
                    </div>
                    <p data-testid={HERO_IDS.note} className="mt-5 text-[0.9375rem] text-muted-foreground">
                        {hero.note}
                    </p>
                </div>
                <div className="max-w-xl xl:col-span-4 xl:max-w-none 2xl:col-span-5">
                    <DealCard card={card} testid={HERO_IDS.card} rowTestid={HERO_IDS.cardRow} />
                </div>
            </Wrap>
        </section>
    );
}

function HowItWorks({ n }) {
    const { how } = HOME;
    return (
        <section data-track-section="how" data-testid={IDS.how} className="border-t border-border">
            <Wrap className="py-20 md:py-28">
                <SectionHead n={n} label={how.label} title={how.title} />
                <ol className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                    {how.items.map((step) => (
                        <li key={step.key} data-testid={IDS.step(step.key)} className="flex flex-col">
                            <h3 className="mkt-h3 text-heading">{step.title}</h3>
                            {/* The one quiet label the spec asked for, on step 03. */}
                            {step.weHandle ? (
                                <p data-testid={IDS.stepTag} className="mt-2 text-meta text-muted-foreground">
                                    {how.weHandle}
                                </p>
                            ) : null}
                            <p className="mkt-body mt-3 text-muted-foreground">{step.line}</p>
                            <div className="mt-6">
                                <StepScreen screen={step.screen} />
                            </div>
                        </li>
                    ))}
                </ol>
            </Wrap>
        </section>
    );
}

function WhoBuiltIt({ n }) {
    const { clients } = HOME;
    return (
        <section data-track-section="who-built-it" data-testid={IDS.clients} className="border-t border-border">
            <Wrap className="py-20 md:py-28">
                <SectionHead n={n} label={clients.label} title={clients.title} />
                <div data-testid={IDS.fill} className="mt-12 max-w-5xl md:mt-16">
                    <FillText text={clients.fill} className="mkt-h2 text-heading" />
                </div>
            </Wrap>
        </section>
    );
}

function CreatorDoor({ n }) {
    const { creatorDoor } = HOME;
    return (
        <section data-track-section="creator-door" data-testid={IDS.creatorDoor} className="border-t border-border bg-muted/40">
            <Wrap className="py-20 md:py-28">
                <SectionRule n={n} label={creatorDoor.label} />
                <h2 className="mkt-h2 mt-8 max-w-4xl text-heading md:mt-10">{creatorDoor.title}</h2>
                <p className="mkt-lead mt-5 max-w-2xl text-muted-foreground">{creatorDoor.line}</p>
                <Cta ask={ASK.forCreators} variant="outline" testid={IDS.creatorDoorCta} className="mt-8" />
            </Wrap>
        </section>
    );
}

export default function Home() {
    const { meta, swap, promises, close } = HOME;
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/">
            <Hero />
            <ComparisonBand copy={swap} n={2} />
            <PhotoBand slot="home-on-location" testid={IDS.band} />
            <HowItWorks n={4} />
            <PromiseBand
                n={5}
                label={promises.label}
                title={promises.title}
                items={promises.items}
                testid={IDS.promises}
                itemTestid={IDS.promise}
            />
            <WhoBuiltIt n={6} />
            <CreatorDoor n={7} />
            <Closing id="close" n={8} label={close.label} title={close.title} line={close.line} testid={LANDING_CLOSING.section}>
                <Cta ask={ASK.postBrief} testid={LANDING_CLOSING.ctaBrand} />
                <Cta ask={ASK.haveUsRunIt} variant="outline" testid={LANDING_CLOSING.ctaTalk} />
            </Closing>
            <StickyCta ask={ASK.postBrief} heroId="hero" closeId="close" />
        </MarketingPage>
    );
}
