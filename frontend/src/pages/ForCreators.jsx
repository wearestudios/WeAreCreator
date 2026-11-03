// For creators, at the path it has always had. The reader's fear is being
// used — the number handed over, the fee changed after the shoot, the money
// late — so the page opens on the number, then the fee before applying, then
// the money, then what is on their side, then how they are paid, then what
// moves them up a list.
//
// **Every word is in `CREATORS` in `content/marketing.js`**; this file is
// layout. The one moving number on the page counts once, in the navy band,
// beside the payout clock that draws the 7 days.
//
// **The pre-revamp look, over the new content**: a drawing beside the hero,
// the briefs and the payouts, the payout window drawn (`PayoutClock`), and
// bands alternating the page ground, the warm tint and navy — page, tint,
// navy, page, photograph, tint, page, navy — so no two neighbours share a
// ground and navy appears twice.
import React from "react";

import Illustration from "@/components/marketing/Illustration";
import PayoutClock from "@/components/marketing/PayoutClock";
import { MarketingPage } from "@/components/marketing/Sections";
import { CountUp } from "@/components/marketing/primitives";
import { BriefCard, Chip, RecordCard } from "@/components/marketing/siteMocks";
import {
    Band,
    CardRow,
    Closing,
    Cta,
    Label,
    PhotoBand,
    SectionHead,
    Wrap,
} from "@/components/marketing/SiteParts";
import StickyCta from "@/components/marketing/StickyCta";
import { CREATORS_PAGE as IDS } from "@/constants/testIds";
import { ASK, CREATORS, aiLive } from "@/content/marketing";

/** The navy band: the three states the record moves through, the payout
 * window drawn, and the figure. */
function MoneyBand({ money }) {
    return (
        <Band ground="navy" track="money" testid={IDS.money}>
            <Wrap className="py-20 md:py-28">
                <SectionHead label={money.label} title={money.title} />
                <ol className="mt-14 grid gap-6 md:grid-cols-3">
                    {money.states.map((s, i) => (
                        <li key={s.key} data-testid={IDS.moneyState(i)} className="border-t border-border pt-6">
                            {/* The red as a mark on the step reached last. */}
                            <span aria-hidden className={`block h-1 w-10 ${i === money.states.length - 1 ? "bg-accent" : "bg-border"}`} />
                            <h3 className="mkt-h3 mt-6 text-heading">{s.title}</h3>
                            <p className="mkt-body mt-3 text-muted-foreground">{s.line}</p>
                        </li>
                    ))}
                </ol>
                {/* "Paid within 7 days of approval", drawn: approval to paid,
                    a day per tick. */}
                <PayoutClock clock={money.clock} className="mt-14 max-w-3xl" />
                <p data-testid={IDS.moneyAmount} className="mt-14 flex flex-wrap items-baseline gap-x-4 gap-y-2">
                    {/* Read once, whole; the counting figure is decoration. */}
                    <span className="sr-only">
                        ₹{money.amount.toLocaleString("en-IN")} {money.amountSuffix}
                    </span>
                    <span aria-hidden className="mkt-display text-heading">
                        ₹<CountUp value={money.amount} />
                    </span>
                    <span aria-hidden className="text-body text-muted-foreground">
                        {money.amountSuffix}
                    </span>
                </p>
            </Wrap>
        </Band>
    );
}

export default function ForCreators() {
    const { meta, hero, briefs, money, protections, payouts, record, close } = CREATORS;
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/for-creators">
            <Band ground="page" id="hero" track="hero" testid={IDS.hero}>
                <Wrap className="grid gap-10 pb-20 pt-10 md:pb-28 md:pt-16 lg:grid-cols-12 lg:items-center lg:gap-16">
                    <div className="lg:col-span-7">
                        <Label>{hero.label}</Label>
                        <h1 className="mkt-h1 mt-6 max-w-5xl text-heading">{hero.title}</h1>
                        <p className="mkt-lead mt-6 max-w-3xl text-muted-foreground">{hero.lead}</p>
                        {aiLive("nicheMatching") ? (
                            <p
                                data-testid={IDS.heroAi}
                                data-track-section="hero-ai-matching"
                                className="mkt-lead mt-4 max-w-3xl text-foreground"
                            >
                                {hero.aiLine}
                            </p>
                        ) : null}
                        <ul data-testid={IDS.chips} className="mt-8 flex flex-wrap gap-2">
                            {hero.chips.map((c) => (
                                <li key={c}>
                                    <Chip>{c}</Chip>
                                </li>
                            ))}
                        </ul>
                        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
                            <Cta ask={ASK.joinFree} testid={IDS.ctaTop} />
                            <Cta ask={ASK.howItWorks} variant="outline" testid={IDS.ctaHow} />
                        </div>
                    </div>
                    {/* Above the fold: no entrance, no lazy load. Stacked
                        above the copy at 390px, like every drawing here. */}
                    <Illustration name="creators-profile-phone" eager className="order-first lg:order-none lg:col-span-5" />
                </Wrap>
            </Band>

            <Band ground="tint" id="briefs" track="briefs" testid={IDS.briefs} className="scroll-mt-20">
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12 lg:gap-16">
                    <div className="flex flex-col lg:col-span-5">
                        <SectionHead label={briefs.label} title={briefs.title} lead={briefs.lead} />
                        {aiLive("nicheMatching") ? (
                            <p
                                data-testid={IDS.briefsAi}
                                data-track-section="briefs-ai-matching"
                                className="mkt-body mt-6 text-foreground"
                            >
                                {briefs.aiLine}
                            </p>
                        ) : null}
                        <Illustration name="creators-cafe-shoot" className="order-first mb-10 lg:order-none lg:mb-0 lg:mt-10" />
                    </div>
                    <div className="lg:col-span-7 lg:pt-16">
                        <BriefCard card={briefs.card} />
                    </div>
                </Wrap>
            </Band>

            <MoneyBand money={money} />

            <Band ground="page" track="protections" testid={IDS.protections}>
                <Wrap className="py-20 md:py-28">
                    <SectionHead label={protections.label} title={protections.title} />
                    <CardRow items={protections.items} />
                </Wrap>
            </Band>

            <PhotoBand slot="creators-on-shoot" testid={IDS.band} />

            <Band ground="tint" track="payouts" testid={IDS.payouts}>
                <Wrap className="py-20 md:py-28">
                    <div className="grid gap-10 lg:grid-cols-12 lg:items-end lg:gap-16">
                        <SectionHead label={payouts.label} title={payouts.title} className="lg:col-span-7" />
                        <Illustration name="why-fees-closeup" className="order-first lg:order-none lg:col-span-5" />
                    </div>
                    <CardRow items={payouts.items} columns={4} />
                </Wrap>
            </Band>

            <Band ground="page" track="record" testid={IDS.record}>
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12 lg:gap-16">
                    <div className="lg:col-span-6">
                        <SectionHead label={record.label} title={record.title} lead={record.lead} />
                    </div>
                    <div className="lg:col-span-6 lg:pt-16">
                        <RecordCard card={record.card} />
                    </div>
                </Wrap>
            </Band>

            <Closing id="close" label={close.label} title={close.title} line={close.line} testid={IDS.close} ground="navy">
                <Cta ask={ASK.joinFree} testid={IDS.ctaBottom} />
            </Closing>
            <StickyCta ask={ASK.joinFree} heroId="hero" closeId="close" />
        </MarketingPage>
    );
}
