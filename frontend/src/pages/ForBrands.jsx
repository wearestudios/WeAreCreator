// For brands, at the path it has always had. The reader is afraid of wasting
// money and of looking foolish in front of whoever signed off the budget, so
// the page answers in that order: what you get (a scored shortlist), what it
// costs, what you get at the end, what is always true, how it compares with
// running it over DMs, and the questions a brand asks first.
//
// `/how-it-works` and `/why-weare` were folded into this page and redirect
// here. **Every word is in `BRANDS` in `content/marketing.js`**; a value the
// content module does not know yet (`FACTS`) is rendered through `<Known>`,
// which in production renders nothing in its place.
import React from "react";

import Known from "@/components/marketing/Known";
import { MarketingPage } from "@/components/marketing/Sections";
import { ReportCard, ShortlistCard } from "@/components/marketing/siteMocks";
import {
    CardRow,
    Closing,
    CompareTable,
    Cta,
    Faq,
    Label,
    PhotoBand,
    PromiseBand,
    SectionHead,
    Wrap,
} from "@/components/marketing/SiteParts";
import StickyCta from "@/components/marketing/StickyCta";
import { BRANDS_PAGE as IDS } from "@/constants/testIds";
import { ASK, BRANDS, FACTS, platformFeeText } from "@/content/marketing";

/** An FAQ item gated on a fact renders only when that fact is true. */
const visibleFaq = (items) => items.filter((item) => !item.showIf || FACTS[item.showIf] === true);

export default function ForBrands() {
    const { meta, hero, shortlist, pricing, report, promises, compare, faq, close } = BRANDS;
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/for-brands">
            <section id="hero" data-track-section="hero" data-testid={IDS.hero}>
                <Wrap className="pb-20 pt-10 md:pb-28 md:pt-16">
                    <Label>{hero.label}</Label>
                    <h1 className="mkt-h1 mt-6 max-w-5xl text-heading">{hero.title}</h1>
                    <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">{hero.lead}</p>
                    <div className="mt-10 flex flex-col gap-3 sm:flex-row">
                        <Cta ask={ASK.postBrief} testid={IDS.ctaTop} />
                        <Cta ask={ASK.talkWhatsapp} variant="outline" testid={IDS.ctaTalkTop} />
                    </div>
                </Wrap>
            </section>

            <section data-track-section="shortlist" data-testid={IDS.shortlist} className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead n={1} label={shortlist.label} title={shortlist.title} lead={shortlist.lead} />
                    <Known value={FACTS.verifiedCreatorCount} name="verifiedCreatorCount">
                        {(n) => <p className="mt-6 text-body text-foreground">{shortlist.countLine(n)}</p>}
                    </Known>
                    <div className="mt-12 max-w-4xl">
                        <ShortlistCard card={shortlist.card} rowTestid={IDS.shortlistRow} />
                        <p className="mkt-body mt-6 text-foreground">{shortlist.closing}</p>
                    </div>
                </Wrap>
            </section>

            <section data-track-section="pricing" data-testid={IDS.pricing} className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead n={2} label={pricing.label} title={pricing.title} />
                    <CardRow
                        items={pricing.cards}
                        testid={IDS.pricingCard}
                        renderExtra={(card) =>
                            card.key === "fee" ? (
                                <Known value={platformFeeText()} name="platformFeePercent">
                                    {(text) => (
                                        <p data-testid={IDS.fee} className="mt-3 text-body font-medium text-foreground">
                                            {text}
                                        </p>
                                    )}
                                </Known>
                            ) : null
                        }
                    />
                    <Known value={FACTS.budgetRangesByCreatorSize} name="budgetRangesByCreatorSize">
                        {(ranges) => (
                            <div data-testid={IDS.budget} className="mt-12">
                                <h3 className="mkt-h3 text-heading">{pricing.budgetTitle}</h3>
                                <dl className="mt-6 grid gap-5 sm:grid-cols-3">
                                    {ranges.map((r) => (
                                        <div key={r.size} className="rounded-lg border border-border bg-card p-6">
                                            <dt className="text-meta text-muted-foreground">{r.size}</dt>
                                            <dd className="mkt-h3 mt-2 text-heading">{r.range}</dd>
                                        </div>
                                    ))}
                                </dl>
                            </div>
                        )}
                    </Known>
                </Wrap>
            </section>

            <section data-track-section="report" data-testid={IDS.report} className="border-t border-border">
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12">
                    <div className="lg:col-span-5">
                        <SectionHead n={3} label={report.label} title={report.title} lead={report.lead} />
                    </div>
                    <div className="lg:col-span-7 lg:pt-16">
                        <ReportCard card={report.card} />
                    </div>
                </Wrap>
            </section>

            <PhotoBand slot="brands-full-room" testid={IDS.band} />

            <PromiseBand n={5} label={promises.label} title={promises.title} items={promises.items} testid={IDS.promises} />

            <section data-track-section="compare" className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead n={6} label={compare.label} title={compare.title} />
                    <CompareTable
                        columns={compare.columns}
                        rows={compare.rows}
                        label={compare.title}
                        testid={IDS.compare}
                        cardsTestid={IDS.compareCards}
                    />
                </Wrap>
            </section>

            <section data-track-section="faq" className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead n={7} label={faq.label} title={faq.title} />
                    <Faq items={visibleFaq(faq.items)} testid={IDS.faq} itemTestid={IDS.faqItem} />
                </Wrap>
            </section>

            <Closing id="close" n={8} label={close.label} title={close.title} line={close.line} testid={IDS.close}>
                <Cta ask={ASK.postBrief} testid={IDS.ctaBottom} />
                <Cta ask={ASK.talkWhatsapp} variant="outline" testid={IDS.ctaTalkBottom} />
            </Closing>
            <StickyCta ask={ASK.postBrief} heroId="hero" closeId="close" />
        </MarketingPage>
    );
}
