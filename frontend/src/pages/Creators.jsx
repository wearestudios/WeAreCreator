// For creators. The reader is afraid of being used — of a brand that takes
// their number, a fee that moves after the shoot, a payment that never comes —
// so the page answers in that order: the brief shows the fee before you apply,
// where the money is at every step, what protects you, how you get paid, and
// what moves you up a shortlist.
//
// **Every word is in `CREATORS` in `content/marketing.js`.** The page asks
// once, in the same words, top and bottom — both buttons spread
// `ASK_CREATOR`. The money band is the page's one navy section and carries the
// third and last moment of motion the site is allowed: the amount counting,
// once.
import React from "react";

import { MarketingPage } from "@/components/marketing/Sections";
import {
    CardRow,
    Closing,
    Eyebrow,
    PhotoBand,
    PrimaryButton,
    SectionHead,
    Wrap,
} from "@/components/marketing/SiteParts";
import { BriefCard, RecordCard } from "@/components/marketing/siteMocks";
import { Chip } from "@/components/marketing/heroScreens";
import { CountUp } from "@/components/marketing/primitives";
import { CREATORS_PAGE as IDS } from "@/constants/testIds";
import { ASK_CREATOR, CREATORS } from "@/content/marketing";
import { pad } from "@/lib/heroDeck";

/** Where the fee is, at every step. Navy, and the amount counts once. */
function MoneyBand() {
    const { money } = CREATORS;
    return (
        <section data-testid={IDS.money} data-surface="dark" className="bg-background text-foreground">
            <Wrap className="py-20 md:py-28">
                <SectionHead eyebrow={money.eyebrow} title={money.title} />
                {/* The figure's name is the final amount, said once; the count
                    is what a sighted reader watches arrive. */}
                <p data-testid={IDS.moneyAmount} className="mkt-display mt-12 text-heading">
                    <span className="sr-only">₹{money.amount.toLocaleString("en-IN")}</span>
                    <span aria-hidden>
                        ₹<CountUp value={money.amount} />
                    </span>
                </p>
                <ol className="mt-12 grid gap-8 md:grid-cols-3 md:gap-10">
                    {money.states.map((s, i) => (
                        <li key={s.title} data-testid={IDS.moneyState(i)} className="border-t border-border pt-6">
                            <span className="mkt-h3 block text-accent">{pad(i + 1)}</span>
                            <h3 className="mkt-h3 mt-3 text-heading">{s.title}</h3>
                            <p className="mkt-body mt-3 text-muted-foreground">{s.line}</p>
                        </li>
                    ))}
                </ol>
                <p className="mkt-lead mt-12 max-w-3xl text-foreground">{money.closing}</p>
            </Wrap>
        </section>
    );
}

export default function Creators() {
    const { hero, brief, protections, band, payout, record, close } = CREATORS;
    return (
        <MarketingPage
            testid={IDS.page}
            title={CREATORS.meta.title}
            description={CREATORS.meta.description}
            path="/creators"
        >
            <section data-testid={IDS.hero}>
                <Wrap className="pb-20 pt-14 md:pb-28 md:pt-20">
                    <Eyebrow>{hero.eyebrow}</Eyebrow>
                    <h1 className="mkt-h1 mt-6 max-w-5xl text-heading">{hero.title}</h1>
                    <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">{hero.line}</p>
                    <PrimaryButton {...ASK_CREATOR} testid={IDS.ctaTop} className="mt-10" />
                </Wrap>
            </section>

            <section data-testid={IDS.brief} className="border-t border-border">
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12 lg:gap-16">
                    <div className="lg:col-span-5">
                        <SectionHead eyebrow={brief.eyebrow} title={brief.title} line={brief.line} />
                    </div>
                    <div className="lg:col-span-7">
                        <BriefCard card={brief.card} />
                    </div>
                </Wrap>
            </section>

            <MoneyBand />

            <section data-testid={IDS.protections}>
                <Wrap className="py-20 md:py-28">
                    <SectionHead eyebrow={protections.eyebrow} title={protections.title} />
                    <CardRow
                        items={protections.cards}
                        renderExtra={(card) => (
                            <p className="mt-4">
                                <Chip>{card.detail}</Chip>
                            </p>
                        )}
                    />
                </Wrap>
            </section>

            <PhotoBand slot="creators-band" title={band.title} testid={IDS.band} />

            <section data-testid={IDS.payout}>
                <Wrap className="py-20 md:py-28">
                    <SectionHead eyebrow={payout.eyebrow} title={payout.title} />
                    <CardRow items={payout.items} />
                </Wrap>
            </section>

            <section data-testid={IDS.record} className="border-t border-border">
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12 lg:gap-16">
                    <div className="lg:col-span-6">
                        <SectionHead eyebrow={record.eyebrow} title={record.title} line={record.line} />
                    </div>
                    <div className="lg:col-span-6">
                        <RecordCard card={record.card} />
                    </div>
                </Wrap>
            </section>

            <Closing testid={IDS.close} title={close.title} line={close.line}>
                <PrimaryButton {...ASK_CREATOR} testid={IDS.ctaBottom} />
            </Closing>
        </MarketingPage>
    );
}
