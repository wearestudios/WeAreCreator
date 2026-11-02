// For brands, at the path it has always had. The reader is afraid of wasting
// money and of looking foolish in front of whoever signed off the budget, so
// the page answers in that order: what you get (a scored shortlist), what it
// costs, what you get at the end, what is always true, how it compares with
// running it over DMs, and the questions a brand asks first.
//
// `/why-weare` was folded into this page and redirects here (`/how-it-works`
// goes to the homepage's "How it works" now). **Every word is in `BRANDS` in
// `content/marketing.js`**; a value the content module does not know yet
// (`FACTS`) is rendered through `<Known>`, which in production renders
// nothing in its place.
//
// **The pre-revamp look, over the new content**: a drawing beside the hero,
// the shortlist, the report and the guarantees, the fee drawn as it flows
// (`FeeFlow`), and bands alternating the page ground, the warm tint and navy
// — page, tint, page, tint, photograph, navy, page, tint, navy — so no two
// neighbours share a ground and navy appears twice.
import React from "react";

import FeeFlow from "@/components/marketing/FeeFlow";
import Illustration from "@/components/marketing/Illustration";
import Known from "@/components/marketing/Known";
import { MarketingPage } from "@/components/marketing/Sections";
import { ReportCard, ShortlistCard } from "@/components/marketing/siteMocks";
import {
    Band,
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
import { ASK, BRANDS, FACTS, aiLive, platformFeeText } from "@/content/marketing";

/** An FAQ item gated on a fact renders only when that fact is true. */
const visibleFaq = (items) => items.filter((item) => !item.showIf || FACTS[item.showIf] === true);

export default function ForBrands() {
    const { meta, hero, shortlist, pricing, report, promises, compare, faq, close } = BRANDS;
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/for-brands">
            <Band ground="page" id="hero" track="hero" testid={IDS.hero}>
                <Wrap className="grid gap-10 pb-20 pt-10 md:pb-28 md:pt-16 lg:grid-cols-12 lg:items-center lg:gap-16">
                    <div className="lg:col-span-7">
                        <Label>{hero.label}</Label>
                        <h1 className="mkt-h1 mt-6 max-w-5xl text-heading">{hero.title}</h1>
                        <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">{hero.lead}</p>
                        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
                            <Cta ask={ASK.postBrief} testid={IDS.ctaTop} />
                            <Cta ask={ASK.talkWhatsapp} variant="outline" testid={IDS.ctaTalkTop} />
                        </div>
                    </div>
                    {/* Above the fold, so no entrance and no lazy load: it
                        paints with the heading rather than after it. At 390px
                        it stacks above the copy at full width, like every
                        drawing on these pages. */}
                    <Illustration name="brands-city-dusk" eager className="order-first lg:order-none lg:col-span-5" />
                </Wrap>
            </Band>

            <Band ground="tint" track="shortlist" testid={IDS.shortlist}>
                <Wrap className="py-20 md:py-28">
                    <div className="grid gap-10 lg:grid-cols-12 lg:items-end lg:gap-16">
                        <div className="lg:col-span-7">
                            <SectionHead n={1} label={shortlist.label} title={shortlist.title} lead={shortlist.lead} />
                            <Known value={FACTS.verifiedCreatorCount} name="verifiedCreatorCount">
                                {(n) => <p className="mt-6 text-body text-foreground">{shortlist.countLine(n)}</p>}
                            </Known>
                        </div>
                        <Illustration name="why-roster-tablet" className="order-first lg:order-none lg:col-span-5" />
                    </div>
                    <div className="mt-12 max-w-4xl">
                        {/* Only while matching is shipped: the "Why this creator"
                            line and the sentence about it describe what the
                            brand's own applicant board prints. */}
                        {aiLive("nicheMatching") ? (
                            <p
                                data-testid={IDS.shortlistAi}
                                data-track-section="shortlist-ai-matching"
                                className="mkt-body mb-6 text-foreground"
                            >
                                {shortlist.aiLine}
                            </p>
                        ) : null}
                        <ShortlistCard card={shortlist.card} rowTestid={IDS.shortlistRow} showWhy={aiLive("nicheMatching")} />
                        <p className="mkt-body mt-6 text-foreground">{shortlist.closing}</p>
                    </div>
                </Wrap>
            </Band>

            <Band ground="page" track="pricing" testid={IDS.pricing}>
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
                    {/* The money, drawn as it moves. No fee figure while the
                        fee is undecided — the flow is true without one. */}
                    <FeeFlow flow={pricing.flow} className="mt-14" />
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
            </Band>

            <Band ground="tint" track="report" testid={IDS.report}>
                <Wrap className="grid gap-12 py-20 md:py-28 lg:grid-cols-12">
                    <div className="flex flex-col lg:col-span-5">
                        <SectionHead n={3} label={report.label} title={report.title} lead={report.lead} />
                        <Illustration name="how-report-desk" className="order-first mb-10 lg:order-none lg:mb-0 lg:mt-10" />
                    </div>
                    <div className="lg:col-span-7 lg:pt-16">
                        <ReportCard card={report.card} />
                        {/* Only while the summary is shipped to brands: a line
                            about a feature they cannot use is a claim the
                            product does not keep. */}
                        {aiLive("campaignSummary") ? (
                            <p
                                data-testid={IDS.reportAi}
                                data-track-section="report-ai-summary"
                                className="mkt-body mt-6 text-muted-foreground"
                            >
                                {report.aiLine}
                            </p>
                        ) : null}
                    </div>
                </Wrap>
            </Band>

            <PhotoBand slot="brands-full-room" testid={IDS.band} />

            <PromiseBand
                n={5}
                label={promises.label}
                title={promises.title}
                items={promises.items}
                testid={IDS.promises}
                art="brands-door-checkin"
            />

            <Band ground="page" track="compare">
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
            </Band>

            <Band ground="tint" track="faq">
                <Wrap className="py-20 md:py-28">
                    <SectionHead n={7} label={faq.label} title={faq.title} />
                    <Faq items={visibleFaq(faq.items)} testid={IDS.faq} itemTestid={IDS.faqItem} />
                </Wrap>
            </Band>

            <Closing id="close" n={8} label={close.label} title={close.title} line={close.line} testid={IDS.close} ground="navy">
                <Cta ask={ASK.postBrief} testid={IDS.ctaBottom} />
                <Cta ask={ASK.talkWhatsapp} variant="outline" testid={IDS.ctaTalkBottom} />
            </Closing>
            <StickyCta ask={ASK.postBrief} heroId="hero" closeId="close" />
        </MarketingPage>
    );
}
