// Product UI drawn for the two audience pages: the shortlist a brand reads,
// the brief a creator applies to, and a creator's delivery record.
//
// The same rules as `heroScreens.jsx`, for the same reasons: pure functions of
// their props (no state, no effects, no fetching, no context), tokens only, and
// every name and figure invented and supplied by `content/marketing.js`. What
// each one *shows* the product doing is real — a score with its reasons, the
// fee and usage on a brief before applying, a record a shortlist is scored on.
import React from "react";

import { Chip } from "@/components/marketing/heroScreens";

const Monogram = ({ text }) => (
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-border bg-muted font-serif text-body text-foreground">
        {text}
    </span>
);

/** Scored applicants, the match as a number, the reasons beside it. */
export function ShortlistCard({ card, rowTestid }) {
    return (
        <div className="rounded-lg border border-border bg-card">
            <p className="border-b border-border px-6 py-4 text-eyebrow uppercase tracking-eyebrow text-muted-foreground">
                {card.kicker}
            </p>
            <ul>
                {card.rows.map((row, i) => (
                    <li
                        key={row.name}
                        data-testid={rowTestid ? rowTestid(i) : undefined}
                        className="grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-border px-6 py-5 last:border-b-0 md:grid-cols-[auto_1fr_auto_auto] md:gap-6"
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
            <p className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground">{card.kicker}</p>
            <p className="mt-2 font-serif text-2xl leading-tight text-heading">{card.title}</p>
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

/** A creator's delivery record and the band a brand sees for it. */
export function RecordCard({ card }) {
    return (
        <div className="rounded-lg border border-border bg-card p-6 md:p-8">
            <p className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground">{card.kicker}</p>
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
