// Product UI drawn for the public pages: the deal in the hero, the four step
// screens, the shortlist a brand reads, the brief a creator applies to, the
// report at the end and a creator's record.
//
// **Drawn in the DOM, never screenshotted.** A screenshot dates the moment
// somebody moves a button, and a real component would drag the app's data,
// API calls and auth onto a page that has none of them. These are pure
// functions of their props — no state, no effects, no fetching — tokens only,
// and every name and figure is invented and supplied by
// `content/marketing.js`. What each one *shows* the product doing is real.
import React from "react";

import { RowWriter } from "@/components/marketing/primitives";

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

/**
 * The hero's product card: one deal, its history written in as it scrolls into
 * view — once. **The agreed figure is the only large number on it**, in
 * Fraunces; every other figure is body size. Day labels are Inter Tight in
 * sentence case, like everything on the public pages that is not a section
 * rule.
 */
export function DealCard({ card, testid, rowTestid }) {
    const rows = card.rows.map((row, i) => ({
        key: `${row.day}-${i}`,
        final: Boolean(row.final),
        node: (
            <div
                data-testid={rowTestid ? rowTestid(i) : undefined}
                className={`grid grid-cols-[2.5rem_1fr_auto] items-baseline gap-3 py-3 ${row.final ? "" : "border-b border-border"}`}
            >
                <span className="text-meta text-muted-foreground">{row.day}</span>
                <span className={`text-body ${row.final ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                    {row.who}
                </span>
                {row.final ? (
                    <span className="font-serif text-[2rem] leading-none text-heading">{row.amount}</span>
                ) : (
                    <span className="text-body text-foreground">{row.amount}</span>
                )}
            </div>
        ),
    }));
    return (
        <div data-testid={testid} className="rounded-lg border border-border bg-card p-5 sm:p-6">
            <p className="font-serif text-[1.75rem] leading-tight text-heading">{card.title}</p>
            <p className="mt-1 text-[0.9375rem] text-muted-foreground">{card.subline}</p>
            <RowWriter rows={rows} className="mt-4" />
            <p className="mt-4 border-t border-border pt-4 text-[0.9375rem] text-muted-foreground">{card.note}</p>
        </div>
    );
}

/** One of the four step screens: a kicker and three short rows. */
export function StepScreen({ screen, final = "" }) {
    return (
        <div className="rounded-md border border-border bg-card p-4">
            <p className="text-meta font-medium text-foreground">{screen.kicker}</p>
            <ul className="mt-3 space-y-2">
                {screen.rows.map((r, i) => (
                    <li
                        key={r}
                        className={`flex items-center justify-between gap-3 text-meta ${
                            i === screen.rows.length - 1 ? "text-foreground" : "text-muted-foreground"
                        }`}
                    >
                        <span>{r}</span>
                        {i === screen.rows.length - 1 && final ? <Chip tone="good">{final}</Chip> : null}
                    </li>
                ))}
            </ul>
        </div>
    );
}

/** Scored applicants, the match as a number, the reasons beside it. */
export function ShortlistCard({ card, rowTestid }) {
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
    return (
        <div className="rounded-lg border border-border bg-card p-6 md:p-8">
            <p className="text-meta font-medium text-muted-foreground">{card.kicker}</p>
            <p className="mt-2 font-serif text-fluid-2xl leading-tight text-heading">{card.title}</p>
            <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
                {card.totals.map((t) => (
                    <div key={t.label}>
                        <dt className="text-meta text-muted-foreground">{t.label}</dt>
                        <dd className="mkt-h3 mt-1 text-heading">{t.value}</dd>
                    </div>
                ))}
            </dl>
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
