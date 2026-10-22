// For brands. The reader is afraid of wasting money and of looking foolish
// in front of whoever signed off the budget, so the page answers in that
// order: what you get (a scored shortlist), what it costs (three lines), what
// is always true, how it compares with running it over DMs, and the six
// questions a brand asks first.
//
// **Every word is in `BRANDS` in `content/marketing.js`.** The page asks once,
// in the same words, top and bottom — both buttons spread `ASK_BRAND`.
import React from "react";

import { MarketingPage } from "@/components/marketing/Sections";
import {
    CardRow,
    Closing,
    CompareTable,
    Eyebrow,
    Faq,
    PhotoBand,
    PrimaryButton,
    PromiseBand,
    SectionHead,
    Wrap,
} from "@/components/marketing/SiteParts";
import { ShortlistCard } from "@/components/marketing/siteMocks";
import { BRANDS_PAGE as IDS } from "@/constants/testIds";
import { ASK_BRAND, BRANDS, platformFeeLabel } from "@/content/marketing";

export default function Brands() {
    const { hero, shortlist, pricing, band, promises, compare, faq, close } = BRANDS;
    return (
        <MarketingPage testid={IDS.page} title={BRANDS.meta.title} description={BRANDS.meta.description} path="/brands">
            <section data-testid={IDS.hero}>
                <Wrap className="pb-20 pt-14 md:pb-28 md:pt-20">
                    <Eyebrow>{hero.eyebrow}</Eyebrow>
                    <h1 className="mkt-h1 mt-6 max-w-5xl text-heading">{hero.title}</h1>
                    <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">{hero.line}</p>
                    <PrimaryButton {...ASK_BRAND} testid={IDS.ctaTop} className="mt-10" />
                </Wrap>
            </section>

            <section data-testid={IDS.shortlist} className="border-t border-border">
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12 lg:gap-16">
                    <div className="lg:col-span-5">
                        <SectionHead eyebrow={shortlist.eyebrow} title={shortlist.title} line={shortlist.line} />
                    </div>
                    <div className="lg:col-span-7">
                        <ShortlistCard card={shortlist.card} rowTestid={IDS.shortlistRow} />
                        <p className="mkt-body mt-6 text-foreground">{shortlist.closing}</p>
                    </div>
                </Wrap>
            </section>

            <section data-testid={IDS.pricing} className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead eyebrow={pricing.eyebrow} title={pricing.title} />
                    <CardRow
                        items={pricing.cards}
                        testid={IDS.pricingCard}
                        renderExtra={(card) =>
                            card.feeFromConstant ? (
                                <p data-testid={IDS.fee} className="mt-3 text-body font-medium text-foreground">
                                    {platformFeeLabel()}
                                </p>
                            ) : null
                        }
                    />
                </Wrap>
            </section>

            <PhotoBand slot="brands-band" title={band.title} testid={IDS.band} />

            <PromiseBand testid={IDS.promises} eyebrow={promises.eyebrow} title={promises.title} items={promises.items} />

            <section data-testid={IDS.compare}>
                <Wrap className="py-20 md:py-28">
                    <SectionHead eyebrow={compare.eyebrow} title={compare.title} />
                    <CompareTable columns={compare.columns} rows={compare.rows} label={compare.title} />
                </Wrap>
            </section>

            <section className="border-t border-border">
                <Wrap className="py-20 md:py-28">
                    <SectionHead eyebrow={faq.eyebrow} title={faq.title} />
                    <Faq items={faq.items} testid={IDS.faq} itemTestid={IDS.faqItem} />
                </Wrap>
            </section>

            <Closing testid={IDS.close} title={close.title} line={close.line}>
                <PrimaryButton {...ASK_BRAND} testid={IDS.ctaBottom} />
            </Closing>
        </MarketingPage>
    );
}
