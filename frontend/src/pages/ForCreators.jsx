// For creators, at the path it has always had. The reader's fear is being
// used — the number handed over, the fee changed after the shoot, the money
// late — so the page opens on the number, then the fee before applying, then
// the money, then what is on their side, then how they are paid, then what
// moves them up a list.
//
// **Every word is in `CREATORS` in `content/marketing.js`**; this file is
// layout. The one moving number on the page counts once, in the navy band.
import React from "react";

import { MarketingPage } from "@/components/marketing/Sections";
import { CountUp } from "@/components/marketing/primitives";
import { BriefCard, Chip, RecordCard } from "@/components/marketing/siteMocks";
import {
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
import { ASK, CREATORS } from "@/content/marketing";

/** The navy band: the three states the record moves through, and the figure. */
function MoneyBand({ n, money }) {
    return (
        <section data-track-section="money" data-testid={IDS.money} data-surface="dark" className="bg-background text-foreground">
            <Wrap className="py-20 md:py-28">
                <SectionHead n={n} label={money.label} title={money.title} />
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
                <p data-testid={IDS.moneyAmount} className="mt-14 flex flex-wrap items-baseline gap-x-4 gap-y-2">
                    {/* Read once, whole; the counting figure is decoration. */}
                    <span className="sr-only">
                        ₹{money.amount.toLocaleString("en-IN")} {money.amountSuffix}
                    </span>
                    <span aria-hidden className="mkt-display text-heading">
                        ₹<CountUp value={money.amount} />
                    </span>
                    <span aria-hidden className="mkt-label text-muted-foreground">
                        {money.amountSuffix}
                    </span>
                </p>
            </Wrap>
        </section>
    );
}

export default function ForCreators() {
    const { meta, hero, briefs, money, protections, payouts, record, close } = CREATORS;
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/for-creators">
            <section id="hero" data-track-section="hero" data-testid={IDS.hero}>
                <Wrap className="pb-20 pt-10 md:pb-28 md:pt-16">
                    <Label>{hero.label}</Label>
                    <h1 className="mkt-h1 mt-6 max-w-5xl text-heading">{hero.title}</h1>
                    <p className="mkt-lead mt-6 max-w-3xl text-muted-foreground">{hero.lead}</p>
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
                </Wrap>
            </section>

            <section id="briefs" data-track-section="briefs" data-testid={IDS.briefs} className="scroll-mt-20 border-t border-border">
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12 lg:gap-16">
                    <div className="lg:col-span-5">
                        <SectionHead n={1} label={briefs.label} title={briefs.title} lead={briefs.lead} />
                    </div>
                    <div className="lg:col-span-7 lg:pt-16">
                        <BriefCard card={briefs.card} />
                    </div>
                </Wrap>
            </section>

            <MoneyBand n={2} money={money} />

            <section data-track-section="protections" data-testid={IDS.protections} className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead n={3} label={protections.label} title={protections.title} />
                    <CardRow items={protections.items} />
                </Wrap>
            </section>

            <PhotoBand slot="creators-on-shoot" testid={IDS.band} />

            <section data-track-section="payouts" data-testid={IDS.payouts} className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead n={5} label={payouts.label} title={payouts.title} />
                    <CardRow items={payouts.items} columns={4} />
                </Wrap>
            </section>

            <section data-track-section="record" data-testid={IDS.record} className="border-t border-border">
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12 lg:gap-16">
                    <div className="lg:col-span-6">
                        <SectionHead n={6} label={record.label} title={record.title} lead={record.lead} />
                    </div>
                    <div className="lg:col-span-6 lg:pt-16">
                        <RecordCard card={record.card} />
                    </div>
                </Wrap>
            </section>

            <Closing id="close" n={7} label={close.label} title={close.title} line={close.line} testid={IDS.close}>
                <Cta ask={ASK.joinFree} testid={IDS.ctaBottom} />
            </Closing>
            <StickyCta ask={ASK.joinFree} heroId="hero" closeId="close" />
        </MarketingPage>
    );
}
