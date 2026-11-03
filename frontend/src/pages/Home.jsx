// The home page. Brands first, eight sections, in this order:
//
//   1 the hero — the h1, one lead, two asks, one quiet line, and the step deck
//   2 the problem — the spreadsheet and the DMs, against the same campaign here
//   3 a full-bleed photograph (or, until there is one, its illustration)
//   4 how it works — the process spine: five steps a side, brands or
//     creators, on a navy band, then the before/after strip and the feature
//     row (`components/marketing/ProcessSpine.jsx`)
//   5 the navy band: three things the code enforces
//   6 who built it: the heading, an illustration and the scroll-inked sentence
//   7 the creator door, on the second navy band
//   8 the close
//
// **Every word is in `HOME` in `content/marketing.js`**; this file is layout.
// **No real business is named on this page**: the only names here are the
// invented ones inside the drawn product UI.
//
// **The look is the pre-revamp site's, brought back over the new content**:
// the drawn illustrations beside the copy, the hero card cycling the four
// steps, a gentle rise on headings and drawings, and bands
// that alternate the page ground, a warm tint and navy. The copy, the claims,
// the structure and the type rules are the new site's and did not move.
//
// **The homepage ships no animation library.** Its LCP is the h1, and 36KB of
// framer-motion in front of it would be the one regression this must not
// cause: the deck reads reduced motion off the media query, `Rise` is CSS,
// and the process spine's motion is CSS transitions driven by two observers.
import React, { useEffect } from "react";

import ComparisonBand from "@/components/marketing/ComparisonBand";
import { DeckStage, HeroDeckProvider, StepRail } from "@/components/marketing/HeroDeck";
import Illustration from "@/components/marketing/Illustration";
import ProcessSpine from "@/components/marketing/ProcessSpine";
import { MarketingPage } from "@/components/marketing/Sections";
import { FillText, Rise, WipeWord } from "@/components/marketing/primitives";
import {
    Band,
    Card,
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
import { ASK, HOME, aiLive } from "@/content/marketing";

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
 * The hero: the Fraunces h1, the Inter Tight lead and Inter Tight UI, and
 * beside them the card — now the four steps, one screen each, on one timer
 * (the old slider's engine, restored from #39). The h1 and its drawn word are
 * exactly as they were.
 */
/** The AI features that are on, in the order the section lists them. Read
 * through `aiLive` per card, never from the switch object. */
function liveAiCards() {
    return HOME.ai.cards.filter((card) => aiLive(card.key));
}

function Hero() {
    const { hero, card, deck } = HOME;
    const aiPowered = liveAiCards().length >= 2;
    const steps = deck.steps.map((step) => ({
        key: step.key,
        label: step.title,
        props: { screen: deck.screen[step.key], card, rowTestid: HERO_IDS.cardRow },
    }));
    return (
        <Band ground="page" id="hero" track="hero" testid={HERO_IDS.section}>
            <Wrap className="grid gap-10 pb-20 pt-8 md:pb-28 md:pt-12 xl:grid-cols-12 xl:items-start xl:gap-12">
                {/* Two columns from xl only, and the text takes eight of them
                    until 2xl: the container stops growing at 1280 while the
                    display size keeps climbing, so at 1440 "Creator
                    campaigns," no longer fit in seven, and below 1280 the h1
                    ran to four lines beside the card. Stacked, it is two. */}
                <div className="xl:col-span-8 2xl:col-span-7">
                    <HeroTitle title={hero.title} accent={hero.accent} />
                    {/* "AI-powered" only while two features back it; the h1
                        never changes. */}
                    {aiPowered ? (
                        <p
                            data-testid={HERO_IDS.lead}
                            data-track-section="hero-ai-lead"
                            className="mkt-lead mt-6 max-w-2xl text-muted-foreground"
                        >
                            {hero.aiLead}
                        </p>
                    ) : (
                        <p data-testid={HERO_IDS.lead} className="mkt-lead mt-6 max-w-2xl text-muted-foreground">
                            {hero.lead}
                        </p>
                    )}
                    <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                        <Cta ask={ASK.postBrief} testid={HERO_IDS.ctaBrand} />
                        <Cta ask={ASK.talkWhatsapp} variant="outline" testid={HERO_IDS.ctaTalk} />
                    </div>
                    <p data-testid={HERO_IDS.note} className="mt-5 text-[0.9375rem] text-muted-foreground">
                        {hero.note}
                    </p>
                </div>
                <div data-testid={HERO_IDS.card} className="max-w-xl xl:col-span-4 xl:max-w-none 2xl:col-span-5">
                    <HeroDeckProvider steps={steps} label={deck.label}>
                        <DeckStage />
                        <StepRail className="mt-3" />
                    </HeroDeckProvider>
                </div>
            </Wrap>
        </Band>
    );
}

function WhoBuiltIt({ n }) {
    const { clients } = HOME;
    return (
        <Band ground="tint" track="who-built-it" testid={IDS.clients}>
            <Wrap className="py-20 md:py-28">
                <SectionHead n={n} label={clients.label} title={clients.title} />
                <div className="mt-12 grid gap-10 md:mt-16 lg:grid-cols-12 lg:items-center lg:gap-16">
                    <div data-testid={IDS.fill} className="lg:col-span-7">
                        <FillText text={clients.fill} className="mkt-h2 text-heading" />
                    </div>
                    <Illustration name="why-production" className="order-first lg:order-none lg:col-span-5" />
                </div>
            </Wrap>
        </Band>
    );
}

function CreatorDoor({ n }) {
    const { creatorDoor } = HOME;
    return (
        <Band ground="navy" track="creator-door" testid={IDS.creatorDoor}>
            <Wrap className="py-20 md:py-28">
                <SectionRule n={n} label={creatorDoor.label} />
                <Rise>
                    <h2 className="mkt-h2 mt-8 max-w-4xl text-heading md:mt-10">{creatorDoor.title}</h2>
                </Rise>
                <p className="mkt-lead mt-5 max-w-2xl text-muted-foreground">{creatorDoor.line}</p>
                <Cta ask={ASK.forCreators} variant="outline" testid={IDS.creatorDoorCta} className="mt-8" />
            </Wrap>
        </Band>
    );
}

/**
 * `/how-it-works` lands on `/#how-it-works`. The browser scrolls to a hash on
 * a page it loaded itself, but not on one a client-side redirect rendered
 * after it had already looked, so the page does it once on arrival.
 */
function useScrollToHash() {
    useEffect(() => {
        const id = window.location.hash.slice(1);
        if (!id) return;
        const el = document.getElementById(id);
        if (el) el.scrollIntoView();
    }, []);
}

/**
 * "What the AI does": one card per feature that is switched on, after How it
 * works. Absent with every switch off. The lead says what none of them does —
 * the fee, the approval and the payment are people's.
 */
function AiSection({ n, cards }) {
    const { ai } = HOME;
    return (
        <Band ground="tint" track="what-the-ai-does" testid={IDS.ai}>
            <Wrap className="py-20 md:py-28">
                <SectionHead n={n} label={ai.label} title={ai.title} lead={ai.lead} />
                <ul className={`mt-12 grid gap-5 md:mt-16 ${cards.length > 1 ? "md:grid-cols-2" : ""} ${cards.length > 2 ? "lg:grid-cols-3" : ""}`}>
                    {cards.map((card, i) => (
                        <li key={card.key}>
                            <Card testid={IDS.aiCard(card.key)} className="h-full">
                                <div data-track-section={`ai-card-${card.key}`}>
                                    <Illustration name={card.art} i={i} ratio="4 / 3" className="mb-6" />
                                    <h3 className="mkt-h3 text-heading">{card.title}</h3>
                                    <p className="mkt-body mt-4 text-muted-foreground">{card.line}</p>
                                </div>
                            </Card>
                        </li>
                    ))}
                </ul>
            </Wrap>
        </Band>
    );
}

export default function Home() {
    const { meta: plainMeta, swap, promises, close } = HOME;
    useScrollToHash();
    const aiCards = liveAiCards();
    // "AI-powered" is claimed only when two features are live.
    const aiPowered = aiCards.length >= 2;
    // The section numbers stay in sequence whether or not the AI section is
    // there: everything after it moves up by one.
    const shift = aiCards.length ? 1 : 0;
    const meta = aiPowered
        ? { title: plainMeta.aiTitle, description: plainMeta.aiDescription }
        : plainMeta;
    // Grounds, top to bottom: page, tint, photograph, navy (the process
    // spine), tint (the AI section), navy, tint, navy, page. See the PR that
    // made "How it works" navy: with every AI switch off the spine would sit
    // directly on the promise band.
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/">
            <Hero />
            <ComparisonBand copy={swap} n={2} ground="bg-muted" />
            <PhotoBand slot="home-on-location" testid={IDS.band} />
            <ProcessSpine n={4} id="how-it-works" />
            {aiCards.length ? <AiSection n={5} cards={aiCards} /> : null}
            <PromiseBand
                n={5 + shift}
                label={promises.label}
                title={promises.title}
                items={promises.items}
                testid={IDS.promises}
                itemTestid={IDS.promise}
            />
            <WhoBuiltIt n={6 + shift} />
            <CreatorDoor n={7 + shift} />
            <Closing id="close" n={8 + shift} label={close.label} title={close.title} line={close.line} testid={LANDING_CLOSING.section}>
                <Cta ask={ASK.postBrief} testid={LANDING_CLOSING.ctaBrand} />
                <Cta ask={ASK.haveUsRunIt} variant="outline" testid={LANDING_CLOSING.ctaTalk} />
            </Closing>
            <StickyCta ask={ASK.postBrief} heroId="hero" closeId="close" />
        </MarketingPage>
    );
}
