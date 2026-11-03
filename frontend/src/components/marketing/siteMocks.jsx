// Product UI drawn for the public pages: the deal on the homepage's first
// slide, the shortlist a brand reads, the brief a creator applies to, the
// report at the end and a creator's record. The hero's other slides are
// `heroSlides.jsx`, and they borrow `Chip` and `ExampleCard` from here so the
// two speak one vocabulary of states.
//
// **Drawn in the DOM, never screenshotted.** A screenshot dates the moment
// somebody moves a button, and a real component would drag the app's data,
// API calls and auth onto a page that has none of them. These are pure
// functions of their props — no state, no effects, no fetching — tokens only,
// and every name and figure is invented and supplied by
// `content/marketing.js`. What each one *shows* the product doing is real.
import React from "react";
import { Check } from "lucide-react";

import { RowWriter } from "@/components/marketing/Entrances";

const TONE = {
    warn: "border-state-pending/30 bg-state-pending-wash text-state-pending",
    good: "border-state-approved/30 bg-state-approved-wash text-state-approved",
    info: "border-state-progress/30 bg-state-progress-wash text-state-progress",
    idle: "border-border bg-muted text-muted-foreground",
};

/** A state chip. State tokens only — the brand red is never a status. */
export const Chip = ({ tone = "idle", children }) => (
    <span
        className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-meta ${TONE[tone] || TONE.idle}`}
    >
        {children}
    </span>
);

const Monogram = ({ text }) => (
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-border bg-muted font-serif text-body text-foreground">
        {text}
    </span>
);

/** The small "Example" tag every drawn card on the homepage carries. */
export const ExampleTag = ({ children }) => (
    <span className="shrink-0 rounded-pill border border-border px-2 py-0.5 text-[0.75rem] text-muted-foreground">
        {children}
    </span>
);

/**
 * The card a hero visual sits in: a head, the "Example" tag, and a body that
 * takes the rest of the frame's fixed height. White on the page ground, a
 * hairline, no shadow — it sits in the page rather than floating over it.
 */
export function ExampleCard({ head, sub, tag, className = "", bodyClassName = "", children, testid }) {
    return (
        <div data-testid={testid} className={`flex flex-col overflow-hidden rounded-lg border border-border bg-card ${className}`}>
            <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
                <div className="min-w-0">
                    <p className="truncate text-[0.9375rem] font-medium text-foreground">{head}</p>
                    {sub ? <p className="mt-0.5 truncate text-[0.8125rem] text-muted-foreground">{sub}</p> : null}
                </div>
                <ExampleTag>{tag}</ExampleTag>
            </div>
            <div className={`flex-1 ${bodyClassName}`}>{children}</div>
        </div>
    );
}

/**
 * Slide A's visual: the deal. The brief's budget, the creator's quote, and
 * the fee agreed — **the one large figure** — written in row by row as the
 * slide first comes into view, then the terms frozen at acceptance.
 *
 * In the page's own chunk, because it is on screen at first paint; the other
 * three slides' visuals arrive after it. On a phone the note goes and the
 * padding tightens — a smaller card, not the desktop one scaled down.
 */
export function DealCard({ card, rowTestid, testid }) {
    const rows = card.rows.map((row, i) => ({
        key: `${row.who}-${i}`,
        final: Boolean(row.final),
        node: (
            <div
                data-testid={rowTestid ? rowTestid(i) : undefined}
                className="flex items-center justify-between gap-3 border-b border-border py-2.5 sm:py-3"
            >
                <span className={`text-meta ${row.final ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                    {row.who}
                </span>
                {row.final ? (
                    <span className="font-serif text-[2rem] leading-none text-heading sm:text-[2.5rem]">{row.amount}</span>
                ) : (
                    <span className="text-body text-foreground">{row.amount}</span>
                )}
            </div>
        ),
    }));
    return (
        <ExampleCard
            testid={testid}
            head={card.title}
            sub={card.subline}
            tag={card.tag}
            className="h-full"
            bodyClassName="flex flex-col justify-center px-4 py-2 sm:px-5"
        >
            <RowWriter rows={rows} />
            <div className="flex items-center justify-between gap-3 py-3">
                <span className="text-meta text-muted-foreground">{card.termsLabel}</span>
                <Chip tone="good">
                    <Check aria-hidden className="mr-1 h-3 w-3" />
                    {card.terms}
                </Chip>
            </div>
            <p className="hidden rounded-md bg-muted p-3 text-meta text-muted-foreground sm:block">{card.note}</p>
        </ExampleCard>
    );
}

/** Scored applicants, the match as a number, the reasons beside it. */
export function ShortlistCard({ card, rowTestid, showWhy = false }) {
    return (
        <div className="rounded-lg border border-border bg-card">
            <p className="border-b border-border px-5 py-4 text-meta font-medium text-foreground sm:px-6">{card.kicker}</p>
            <ul>
                {card.rows.map((row, i) => (
                    <li
                        key={row.name}
                        data-testid={rowTestid ? rowTestid(i) : undefined}
                        className="grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-border px-5 py-5 last:border-b-0 sm:px-6 md:grid-cols-[auto_1fr_auto_auto] md:gap-6"
                    >
                        <Monogram text={row.initials} />
                        <div className="min-w-0">
                            <p className="text-body font-medium text-foreground">{row.name}</p>
                            <ul className="mt-2 flex flex-wrap gap-1.5">
                                {row.reasons.map((r) => (
                                    <li key={r}>
                                        <Chip>{r}</Chip>
                                    </li>
                                ))}
                            </ul>
                            {showWhy && row.why ? (
                                <p className="mt-2 text-meta text-muted-foreground">
                                    <span className="font-medium text-foreground">{card.whyLabel}: </span>
                                    {row.why}
                                </p>
                            ) : null}
                        </div>
                        <p className="hidden text-right md:block">
                            <span className="block text-body text-foreground">{row.quote}</span>
                            <span className="text-meta text-muted-foreground">{card.quoteLabel}</span>
                        </p>
                        <p className="text-right">
                            <span className="mkt-h3 block text-heading">{row.match}</span>
                            <span className="text-meta text-muted-foreground">{card.matchLabel}</span>
                        </p>
                    </li>
                ))}
            </ul>
        </div>
    );
}

/** A brief as a creator meets it: the fee and the terms before applying. */
export function BriefCard({ card }) {
    const [apply, quote] = card.actions;
    return (
        <div className="rounded-lg border border-border bg-card p-6 md:p-8">
            <p className="text-meta font-medium text-muted-foreground">{card.kicker}</p>
            <p className="mt-2 font-serif text-fluid-2xl leading-tight text-heading">{card.title}</p>
            <p className="mt-6">
                <span className="mkt-h2 text-heading">{card.fee}</span>{" "}
                <span className="text-body text-muted-foreground">{card.feeLabel}</span>
            </p>
            <ul className="mt-5 flex flex-wrap gap-2">
                {card.chips.map((c) => (
                    <li key={c}>
                        <Chip>{c}</Chip>
                    </li>
                ))}
            </ul>
            {/* Drawn, not wired: a picture of the two buttons a creator has. */}
            <div aria-hidden className="mt-8 flex flex-wrap gap-3">
                <span className="inline-flex min-h-[2.75rem] items-center rounded-md bg-primary px-5 text-body font-medium text-primary-foreground">
                    {apply}
                </span>
                <span className="inline-flex min-h-[2.75rem] items-center rounded-md border border-foreground/25 px-5 text-body font-medium text-foreground">
                    {quote}
                </span>
            </div>
        </div>
    );
}

/** The end-of-campaign report, as an example. */
export function ReportCard({ card }) {
    // The real dashboard, drawn small: the one very large number, the tiles
    // under it, and the wall of posts. Thumbnails are tinted tiles rather than
    // photographs — nothing on the marketing site fetches a third party, and
    // an invented post should not look like somebody's real one.
    return (
        <div className="rounded-lg border border-border bg-card p-6 md:p-8">
            <p className="text-meta font-medium text-muted-foreground">{card.kicker}</p>
            <p className="mt-2 font-serif text-fluid-2xl leading-tight text-heading">{card.title}</p>
            <div className="mt-6">
                <p className="text-meta text-muted-foreground">{card.hero.label}</p>
                <p className="mkt-h1 mt-1 tabular-nums text-heading">{card.hero.value}</p>
                <p className="mt-1 text-meta text-muted-foreground">{card.hero.sub}</p>
            </div>
            <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
                {card.totals.map((t) => (
                    <div key={t.label}>
                        <dt className="text-meta text-muted-foreground">{t.label}</dt>
                        <dd className="mkt-h3 mt-1 tabular-nums text-heading">{t.value}</dd>
                        {t.sub ? <dd className="text-meta text-muted-foreground">{t.sub}</dd> : null}
                    </div>
                ))}
            </dl>
            <p className="mt-7 text-meta font-medium text-foreground">{card.postsLabel}</p>
            <ul className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
                {card.posts.map((p, i) => (
                    <li key={p.name} className="overflow-hidden rounded-md border border-border">
                        <div
                            className="relative aspect-[4/5]"
                            style={{ background: `hsl(${20 + i * 6} 55% ${86 - i * 3}%)` }}
                            aria-hidden
                        >
                            <span className="absolute right-1.5 top-1.5 rounded-pill bg-brand-navy/80 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-brand-white">
                                {p.format === "reel" ? "▶" : `1/${p.count}`}
                            </span>
                        </div>
                        <div className="px-2 py-1.5">
                            <p className="truncate text-[12px] font-medium text-foreground">{p.name}</p>
                            <p className="text-[11px] tabular-nums text-muted-foreground">
                                {p.views} views · {p.shares} shares
                            </p>
                        </div>
                    </li>
                ))}
                <li className="flex aspect-[4/5] items-center justify-center rounded-md border border-dashed border-border text-meta text-muted-foreground sm:aspect-auto">
                    {card.more}
                </li>
            </ul>
            <p className="mt-6 border-t border-border pt-4 text-meta text-muted-foreground">{card.note}</p>
        </div>
    );
}

/** A creator's delivery record and the band a brand sees for it. */
export function RecordCard({ card }) {
    return (
        <div className="rounded-lg border border-border bg-card p-6 md:p-8">
            <p className="text-meta font-medium text-muted-foreground">{card.kicker}</p>
            <dl className="mt-4">
                {card.rows.map((row) => (
                    <div
                        key={row.label}
                        className="flex items-baseline justify-between gap-4 border-b border-border py-4 last:border-b-0"
                    >
                        <dt className="text-body text-muted-foreground">{row.label}</dt>
                        <dd className="mkt-h3 text-heading">{row.value}</dd>
                    </div>
                ))}
            </dl>
            <p className="mt-6">
                <Chip tone="good">{card.band}</Chip>
            </p>
        </div>
    );
}
