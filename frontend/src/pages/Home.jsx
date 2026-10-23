// The home page. Brands first, eight sections, in this order:
//
//   1 the hero — one static product card, one drawn word
//   2 the problem — the spreadsheet and the DMs, against the same campaign here
//   3 a full-bleed photograph (or, until there is one, its headline)
//   4 the four steps, which the hero's rail links to
//   5 the navy band: three things the code enforces
//   6 who built it: the clients, three lines, the one scroll-inked sentence
//   7 the creator door
//   8 the close
//
// **Every word is in `HOME` in `content/marketing.js`**; this file is layout.
// The hero slider, its sector phrases and its eight drawings are gone: the
// hero is one product card and one word revealed once.
//
// Motion here is the primitives and nothing else: the wipe on "chasing", the
// card's rows written once in view, the marquee, and the one FillText
// sentence on the site.
import React from "react";

import ComparisonBand from "@/components/marketing/ComparisonBand";
import { MarketingPage } from "@/components/marketing/Sections";
import { FillText, Marquee, WipeWord } from "@/components/marketing/primitives";
import { DealCard, StepScreen } from "@/components/marketing/siteMocks";
import {
    Card,
    Closing,
    Cta,
    Label,
    PhotoBand,
    PromiseBand,
    SectionHead,
    SectionRule,
    Wrap,
} from "@/components/marketing/SiteParts";
import StickyCta from "@/components/marketing/StickyCta";
import { LANDING_CLOSING, LANDING_HERO as HERO_IDS, LANDING_PAGE as IDS } from "@/constants/testIds";
import { ASK, FACTS, HOME } from "@/content/marketing";
import { HERO_EYEBROW } from "@/lib/siteNav";

/** The h1 with its one accented word, whole in the DOM from the first paint. */
function HeroTitle({ title, accent }) {
    const at = title.lastIndexOf(accent);
    return (
        <h1 data-testid={HERO_IDS.heading} className="mkt-display text-heading">
            {title.slice(0, at)}
            <WipeWord className="pr-[0.08em]">
                {/* Fraunces true italic at 400, in the accent's ink. */}
                <em data-testid={HERO_IDS.accent} className="font-normal italic text-accent-ink">
                    {accent}
                </em>
            </WipeWord>
            {title.slice(at + accent.length)}
        </h1>
    );
}

function Hero() {
    const { hero, steps, card } = HOME;
    return (
        <section id="hero" data-track-section="hero" data-testid={HERO_IDS.section}>
            <Wrap className="grid gap-10 pb-16 pt-8 md:pb-24 md:pt-12 lg:grid-cols-12 lg:items-start lg:gap-12">
                <div className="lg:col-span-7">
                    <Label testid={HERO_IDS.eyebrow}>{HERO_EYEBROW}</Label>
                    <div className="mt-5">
                        <HeroTitle title={hero.title} accent={hero.accent} />
                    </div>
                    <p data-testid={HERO_IDS.lead} className="mkt-lead mt-6 max-w-2xl text-muted-foreground">
                        {hero.lead}
                    </p>
                    <p data-testid={HERO_IDS.note} className="mkt-label mt-5 text-foreground">
                        {hero.note}
                    </p>
                    <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                        <Cta ask={ASK.postBrief} testid={HERO_IDS.ctaBrand} />
                        <Cta ask={ASK.talkWhatsapp} variant="outline" testid={HERO_IDS.ctaTalk} />
                    </div>
                    <p data-testid={HERO_IDS.builtFor} className="mkt-label mt-8 max-w-2xl leading-relaxed text-muted-foreground">
                        <span className="text-foreground">{hero.builtForLabel}</span> · {hero.builtFor}
                    </p>
                    {/* Anchors, not a slider: each goes to its step in
                        section 4. */}
                    <nav aria-label={hero.railLabel} data-testid={HERO_IDS.rail} className="mt-8">
                        <ol className="flex flex-wrap gap-2">
                            {steps.map((s) => (
                                <li key={s.key}>
                                    <a
                                        href={`#step-${s.key}`}
                                        data-testid={HERO_IDS.railStep(s.key)}
                                        className="inline-flex min-h-[2.75rem] items-center gap-2 rounded-md border border-border px-3 text-body text-foreground transition-[border-color] [transition-duration:var(--mkt-interactive)] hover:border-foreground/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                    >
                                        <span className="mkt-label text-muted-foreground">{s.n}</span>
                                        {s.label}
                                    </a>
                                </li>
                            ))}
                        </ol>
                    </nav>
                </div>
                <div className="lg:col-span-5 lg:pt-2">
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
                    {how.items.map((step, i) => (
                        <li
                            key={step.key}
                            id={`step-${step.key}`}
                            data-testid={IDS.step(step.key)}
                            className="flex scroll-mt-24 flex-col"
                        >
                            <div className="flex items-center justify-between gap-3">
                                <span className="mkt-label text-muted-foreground">{HOME.steps[i].n}</span>
                                {step.weHandle ? (
                                    <span
                                        data-testid={IDS.stepTag}
                                        className="mkt-label rounded-full border border-border px-2.5 py-1 text-muted-foreground"
                                    >
                                        {how.weHandle}
                                    </span>
                                ) : null}
                            </div>
                            <h3 className="mkt-h3 mt-4 text-heading">{step.title}</h3>
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
            <Wrap className="pt-20 md:pt-28">
                <SectionHead n={n} label={clients.label} title={clients.title} />
            </Wrap>
            {/* Real names, from `confirmedClients` only — the one place on the
                site a real client is named. */}
            <Marquee
                items={FACTS.confirmedClients}
                label={clients.marqueeLabel}
                testid={IDS.clientMarquee}
                className="mt-14 border-y border-border py-6"
                itemClassName="mkt-h2 whitespace-nowrap px-8 text-heading md:px-12"
            />
            <Wrap className="pb-20 md:pb-28">
                <ul className="mt-12 grid gap-5 md:grid-cols-3">
                    {clients.cards.map((line, i) => (
                        <li key={line}>
                            <Card testid={IDS.clientCard(i)} className="h-full">
                                <p className="mkt-lead text-foreground">{line}</p>
                            </Card>
                        </li>
                    ))}
                </ul>
                <div data-testid={IDS.fill} className="mt-16 max-w-5xl md:mt-24">
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
