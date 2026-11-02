// The home page. Brands first, eight sections, in this order:
//
//   1 the hero — the h1, one lead, two asks, one quiet line, and the step deck
//   2 the problem — the spreadsheet and the DMs, against the same campaign here
//   3 a full-bleed photograph (or, until there is one, its illustration)
//   4 how it works — the four steps, each illustrated, both sides of the deal,
//     with the campaign film playing beside them
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
// the drawn illustrations beside the copy, the campaign film, the hero card
// cycling the four steps, a gentle rise on headings and drawings, and bands
// that alternate the page ground, a warm tint and navy. The copy, the claims,
// the structure and the type rules are the new site's and did not move.
//
// **The homepage ships no animation library.** Its LCP is the h1, and 36KB of
// framer-motion in front of it would be the one regression this must not
// cause: the deck reads reduced motion off the media query, `Rise` is CSS,
// and the film — which does need framer — is fetched in its own chunk only
// when "How it works" is about to come on screen.
import React, { Suspense, lazy, useEffect, useRef, useState } from "react";

import ComparisonBand from "@/components/marketing/ComparisonBand";
import { DeckStage, HeroDeckProvider, StepRail } from "@/components/marketing/HeroDeck";
import Illustration from "@/components/marketing/Illustration";
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
import { retryImport } from "@/lib/lazyRoute";

// The film is framer-motion, and the homepage's first paint carries none.
const CampaignFilm = lazy(() =>
    retryImport(() => import(/* webpackChunkName: "film" */ "@/components/marketing/CampaignFilm")),
);

/** Each step's drawing, placed by meaning — the pre-revamp pages' own. */
const STEP_ART = {
    offer: "how-briefing",
    agree: "how-table-talk",
    deliver: "why-shoot-day",
    paid: "creators-payment",
};

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
    const { hero, card, deck, how } = HOME;
    const aiPowered = liveAiCards().length >= 2;
    const steps = how.items.map((step) => ({
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

/**
 * Mounts its children once the block is within a screen and a half of the
 * viewport, and never unmounts them. The film's chunk is fetched then and not
 * before: a visitor who reads the hero and leaves never downloads it, and
 * neither does a page-load measurement.
 */
function WhenNear({ children }) {
    const ref = useRef(null);
    const [near, setNear] = useState(false);
    useEffect(() => {
        const node = ref.current;
        if (near || !node) return undefined;
        if (typeof IntersectionObserver === "undefined") {
            setNear(true);
            return undefined;
        }
        const io = new IntersectionObserver(
            (entries) => {
                if (entries.some((e) => e.isIntersecting)) {
                    setNear(true);
                    io.disconnect();
                }
            },
            { rootMargin: "150% 0px 150% 0px" },
        );
        io.observe(node);
        return () => io.disconnect();
    }, [near]);
    return (
        <div ref={ref} className="h-full">
            {near ? <Suspense fallback={null}>{children}</Suspense> : null}
        </div>
    );
}

/**
 * How it works: the four steps, each with its drawing, a line for the brand
 * and a line for the creator — both sides of the deal visible at once, as the
 * old /how-it-works page showed — and the campaign film beside them, playing
 * as the steps are read. `/how-it-works` redirects to this section's anchor.
 */
function HowItWorks({ n }) {
    const { how, film } = HOME;
    const trackRef = useRef(null);
    const titles = Object.fromEntries(how.items.map((s) => [s.key, s.title]));
    return (
        <Band ground="page" id="how-it-works" track="how" testid={IDS.how} className="scroll-mt-16">
            <Wrap className="py-20 md:py-28">
                <SectionHead n={n} label={how.label} title={how.title} />
                <div className="mt-14 grid gap-14 lg:grid-cols-12 lg:gap-16">
                    <ol ref={trackRef} className="space-y-14 lg:col-span-7">
                        {how.items.map((step) => (
                            <li
                                key={step.key}
                                data-testid={IDS.step(step.key)}
                                className="grid gap-6 sm:grid-cols-5 sm:items-start sm:gap-8"
                            >
                                {/* At 390px the drawing stacks above its text,
                                    full width; beside it from `sm`. */}
                                <Illustration name={STEP_ART[step.key]} ratio="4 / 3" className="sm:col-span-2" />
                                <div className="sm:col-span-3">
                                    <Rise>
                                        <h3 className="mkt-h3 text-heading">{step.title}</h3>
                                    </Rise>
                                    {/* The one quiet label the spec asked for, on step 03. */}
                                    {step.weHandle ? (
                                        <p data-testid={IDS.stepTag} className="mt-2 text-meta text-muted-foreground">
                                            {how.weHandle}
                                        </p>
                                    ) : null}
                                    <dl className="mt-4 space-y-4">
                                        <div data-testid={IDS.stepSide(step.key, "brand")}>
                                            <dt className="text-meta font-medium text-foreground">{how.youTouch}</dt>
                                            <dd className="mkt-body mt-1 text-muted-foreground">{step.line}</dd>
                                        </div>
                                        <div data-testid={IDS.stepSide(step.key, "creator")}>
                                            <dt className="text-meta font-medium text-foreground">{how.creatorSide}</dt>
                                            <dd className="mkt-body mt-1 text-muted-foreground">{step.creatorLine}</dd>
                                        </div>
                                    </dl>
                                    {(step.ai || [])
                                        .filter((a) => aiLive(a.key))
                                        .map((a) => (
                                            <p
                                                key={a.key}
                                                data-testid={IDS.stepAi(step.key, a.key)}
                                                data-track-section={`step-${step.key}-ai-${a.key}`}
                                                className="mkt-body mt-4 text-foreground"
                                            >
                                                {a.line}
                                            </p>
                                        ))}
                                </div>
                            </li>
                        ))}
                    </ol>
                    <div className="lg:col-span-5">
                        <WhenNear>
                            <CampaignFilm film={film} steps={titles} trackRef={trackRef} />
                        </WhenNear>
                    </div>
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
    // Grounds, top to bottom: page, tint, photograph, page, navy, tint, navy,
    // page — no two neighbours alike, and navy twice.
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/">
            <Hero />
            <ComparisonBand copy={swap} n={2} ground="bg-muted" />
            <PhotoBand slot="home-on-location" testid={IDS.band} />
            <HowItWorks n={4} />
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
