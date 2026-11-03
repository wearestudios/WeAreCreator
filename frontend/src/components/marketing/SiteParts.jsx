// The parts the three public pages are built from.
//
// **Layout only.** Every word arrives as a prop from `content/marketing.js`;
// nothing here holds a sentence of its own, so the copy can change without a
// layout change riding along. No motion beyond the 200ms interactive
// transition — the five primitives in `primitives.js` are the whole motion
// vocabulary, and none of them lives in here.
//
// **Every section opens on a labelled rule**: its name in the label face, a
// hairline filling the rest of the line, then the heading. No number — see
// `SectionRule`.
//
// **The grounds alternate**, as the pre-revamp site's did ("band the site
// light and dark", 0dc35ce): the page ground, a warm tint and navy, so no two
// neighbouring sections share one and the page reads as a sequence of
// bands rather than one long sheet. The light base is unchanged — navy is at
// most two bands a page, and it is the existing dark token set
// (`data-surface="dark"`), not a colour of its own. `Band` is the one way a
// section picks its ground.
//
// The section heading and an illustration rise in once (`Rise`, the old
// pages' `Reveal` entrance); body text, tables and the FAQ do not.
// **The rule is the only place the label face (`mkt-label` — JetBrains Mono,
// tracked capitals) appears on a public page**; everything else is sentence
// case in Inter Tight.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import Illustration from "@/components/marketing/Illustration";
import PhotoSlot from "@/components/marketing/PhotoSlot";
import { Rise } from "@/components/marketing/primitives";
import { photoSlot } from "@/content/photoSlots";
import { SITE_PARTS as IDS } from "@/constants/testIds";

/** The one transition a public control may have. */
const HOVER =
    "transition-[color,background-color,border-color,transform] [transition-duration:var(--mkt-interactive)] [transition-timing-function:var(--weare-ease)]";

const FOCUS =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

/**
 * The three grounds a band may sit on. The tint is `--muted`, the warm
 * #F1EEE9 the light set already holds; navy is the dark token set, switched
 * on by `data-surface`, so everything inside resolves without a class of its
 * own.
 */
export const GROUND = {
    page: "bg-background",
    tint: "bg-muted",
    navy: "bg-background",
};

/**
 * One section of a public page on one ground. `track` is the id the
 * `section_view` event reports, so every band is measured by name.
 */
export function Band({ ground = "page", track, id, testid, className = "", children }) {
    return (
        <section
            id={id}
            data-track-section={track}
            data-testid={testid}
            data-ground={ground}
            data-surface={ground === "navy" ? "dark" : undefined}
            className={`${GROUND[ground]} text-foreground ${className}`}
        >
            {children}
        </section>
    );
}

/** A page-width container. 16px gutters on the narrowest phone. */
export function Wrap({ children, className = "" }) {
    return <div className={`mx-auto w-full max-w-7xl px-4 sm:px-6 md:px-10 2xl:max-w-[88rem] ${className}`}>{children}</div>;
}

/**
 * A small line above a heading, in sentence case. **Not the label face**:
 * JetBrains Mono and tracked capitals belong to the section rule and nothing
 * else on the public pages.
 */
export function Label({ children, className = "", testid }) {
    if (!children) return null;
    return (
        <p data-testid={testid} className={`text-body text-muted-foreground ${className}`}>
            {children}
        </p>
    );
}

/**
 * "How it works ────────" — the label, then a hairline filling the rest.
 *
 * **No number.** Sections used to be numbered "(01)", "(02)" down every page,
 * which made the site read as one argument in order — and made every page
 * carry arithmetic (a section added or switched off renumbered everything
 * below it) for furniture that told a reader nothing they could act on.
 * Numbering stays only where it encodes a real sequence: the process spine's
 * steps. This remains the one place the label face appears on a public page.
 */
export function SectionRule({ label, className = "" }) {
    return (
        <div data-testid={IDS.sectionRule(label)} className={`flex items-center gap-4 ${className}`}>
            <span className="mkt-label shrink-0 text-muted-foreground">{label}</span>
            <span aria-hidden className="h-px flex-1 bg-border" />
        </div>
    );
}

/** The rule, an `h2` and an optional lead — the head of every section. The
 * heading rises in once; the rule and the lead do not move. */
export function SectionHead({ label, title, lead, className = "", titleClassName = "" }) {
    return (
        <div className={className}>
            <SectionRule label={label} />
            <Rise>
                <h2 className={`mkt-h2 mt-8 max-w-5xl text-heading md:mt-10 ${titleClassName}`}>{title}</h2>
            </Rise>
            {lead ? <p className="mkt-lead mt-5 max-w-2xl text-muted-foreground">{lead}</p> : null}
        </div>
    );
}

/**
 * An ask. `to` is a route; `href` leaves the site (WhatsApp) and opens in a
 * new tab. **Primary is navy, never red** — a red button on a light page reads
 * as destructive. `data-cta` is what `cta_click` reports.
 */
export function Cta({ ask, variant = "primary", testid, className = "", onClick }) {
    const look =
        variant === "primary"
            ? "bg-primary text-primary-foreground hover:bg-primary-hover"
            : "border border-foreground/25 text-foreground hover:border-foreground/60";
    const cls = `inline-flex min-h-[3rem] items-center justify-center gap-2 rounded-md px-6 text-body font-medium ${look} ${HOVER} ${FOCUS} ${className}`;
    const inner = (
        <>
            {ask.label}
            {variant === "primary" ? <ArrowRight className="h-4 w-4" aria-hidden /> : null}
        </>
    );
    if (ask.href) {
        return (
            <a href={ask.href} target="_blank" rel="noopener noreferrer" data-cta={ask.cta} data-testid={testid} className={cls} onClick={onClick}>
                {inner}
            </a>
        );
    }
    if (ask.to && ask.to.startsWith("#")) {
        return (
            <a href={ask.to} data-cta={ask.cta} data-testid={testid} className={cls} onClick={onClick}>
                {inner}
            </a>
        );
    }
    return (
        <Link to={ask.to} data-cta={ask.cta} data-testid={testid} className={cls} onClick={onClick}>
            {inner}
        </Link>
    );
}

/**
 * A navy band: three claims, each with the mechanism that makes it true.
 * `art` puts an illustration beside the heading — the guarantees band on
 * /for-brands carries the door check-in drawing, as the old page did.
 */
export function PromiseBand({ label, title, items, testid, itemTestid, art }) {
    return (
        // The hairline marks the edge where this band meets a navy photo panel,
        // which otherwise runs straight into it.
        <Band ground="navy" track="promises" testid={testid} className="border-t border-border">
            <Wrap className="py-20 md:py-28">
                {art ? (
                    <div className="grid gap-10 lg:grid-cols-12 lg:items-end lg:gap-16">
                        <SectionHead label={label} title={title} className="lg:col-span-7" />
                        <Illustration name={art} className="order-first lg:order-none lg:col-span-5" />
                    </div>
                ) : (
                    <SectionHead label={label} title={title} />
                )}
                <ul className="mt-14 grid gap-10 md:grid-cols-3 md:gap-12">
                    {items.map((item, i) => (
                        <li key={item.title} data-testid={itemTestid ? itemTestid(i) : undefined}>
                            {/* The red as a mark — a fill, never a word. */}
                            <span aria-hidden className="block h-1 w-10 bg-accent" />
                            <h3 className="mkt-h3 mt-6 text-heading">{item.title}</h3>
                            <p className="mkt-body mt-4 text-muted-foreground">{item.line}</p>
                        </li>
                    ))}
                </ul>
            </Wrap>
        </Band>
    );
}

/**
 * A full-bleed photograph section.
 *
 * Without a photograph the slot *is* the section: in production `PhotoSlot`
 * draws the slot's illustration with its headline on a navy band, and in
 * development the dashed brief. With one, the same headline sits on a panel over the picture
 * — legible over whatever is in the frame, no scrim tuned to an image nobody
 * has taken. A phone gets a taller frame than 2:1, which at 390px would be
 * 195px and could not hold the headline.
 */
export function PhotoBand({ slot: id, testid }) {
    const slot = photoSlot(id);
    return (
        <section
            data-testid={testid}
            data-track-section={`photo-${id}`}
            className="relative min-h-[28rem] md:aspect-[2/1] md:max-h-[52rem] md:min-h-0"
        >
            <div className="absolute inset-0">
                <PhotoSlot id={id} fill sizes="100vw" />
            </div>
            {slot.src ? (
                <div className="absolute inset-x-0 bottom-0">
                    <Wrap className="pb-6 md:pb-12">
                        <div className="max-w-3xl rounded-md bg-background/95 p-6 md:p-10">
                            <h2 className="mkt-h2 text-heading">{slot.fallbackHeadline}</h2>
                            {slot.fallbackLine ? (
                                <p className="mkt-body mt-4 text-muted-foreground">{slot.fallbackLine}</p>
                            ) : null}
                        </div>
                    </Wrap>
                </div>
            ) : null}
        </section>
    );
}

/** A plain card: hairline, card ground, no shadow. */
export function Card({ children, className = "", testid }) {
    return (
        <div data-testid={testid} className={`rounded-lg border border-border bg-card p-6 md:p-8 ${className}`}>
            {children}
        </div>
    );
}

/** Titled cards in a row. `renderExtra` adds a line under a card's title. */
export function CardRow({ items, testid, renderExtra, columns = 3 }) {
    const grid = columns === 4 ? "sm:grid-cols-2 lg:grid-cols-4" : "md:grid-cols-3";
    return (
        <ul className={`mt-12 grid gap-5 ${grid}`}>
            {items.map((item, i) => (
                <li key={item.title}>
                    <Card testid={testid ? testid(item.key || i) : undefined} className="h-full">
                        <h3 className="mkt-h3 text-heading">{item.title}</h3>
                        {renderExtra ? renderExtra(item, i) : null}
                        <p className="mkt-body mt-4 text-muted-foreground">{item.line}</p>
                    </Card>
                </li>
            ))}
        </ul>
    );
}

/**
 * A two-way comparison.
 *
 * **A real `<table>` from `md` up**, so a screen reader reads each cell
 * against its column and row headers. **Below `md` it is two stacked cards**,
 * one per column, each listing every row — a three-column table on a 390px
 * screen is a sideways scroll nobody finds.
 */
export function CompareTable({ columns, rows, testid, cardsTestid, label }) {
    const [, left, right] = columns;
    return (
        <>
            <div data-testid={testid} className="mt-12 hidden overflow-hidden rounded-lg border border-border bg-card md:block">
                <table className="w-full border-collapse text-left">
                    <caption className="sr-only">{label}</caption>
                    <thead>
                        <tr className="border-b border-border">
                            {columns.map((c, i) => (
                                <th
                                    key={c || "row"}
                                    scope="col"
                                    className={`px-6 py-4 align-bottom text-meta font-medium ${i === 2 ? "text-foreground" : "text-muted-foreground"}`}
                                >
                                    {c}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map(([head, a, b]) => (
                            <tr key={head} className="border-b border-border last:border-b-0">
                                <th scope="row" className="w-1/4 px-6 py-5 align-top text-body font-medium text-foreground">
                                    {head}
                                </th>
                                <td className="px-6 py-5 align-top text-body text-muted-foreground">{a}</td>
                                <td className="px-6 py-5 align-top text-body text-foreground">{b}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <div data-testid={cardsTestid} className="mt-10 grid gap-5 md:hidden">
                {[
                    [left, 1, "text-muted-foreground"],
                    [right, 2, "text-foreground"],
                ].map(([title, col, tone]) => (
                    <Card key={title}>
                        <p className="text-body font-medium text-foreground">{title}</p>
                        <dl className="mt-4 divide-y divide-border">
                            {rows.map((row) => (
                                <div key={row[0]} className="py-3">
                                    <dt className="text-meta font-medium text-foreground">{row[0]}</dt>
                                    <dd className={`mt-1 text-body ${tone}`}>{row[col]}</dd>
                                </div>
                            ))}
                        </dl>
                    </Card>
                ))}
            </div>
        </>
    );
}

/**
 * Questions and answers, as native `<details>`: keyboard-operable, readable
 * with no script, and nothing animates open.
 */
export function Faq({ items, testid, itemTestid }) {
    return (
        <div data-testid={testid} className="mt-12 divide-y divide-border border-y border-border">
            {items.map((item, i) => (
                <details
                    key={item.q}
                    data-testid={itemTestid ? itemTestid(i) : undefined}
                    // An item that only shows while a feature is on reports
                    // when it is seen, like every other switched line.
                    data-track-section={item.track || undefined}
                    className="group"
                >
                    <summary
                        className={`flex min-h-[3.5rem] cursor-pointer list-none items-center justify-between gap-6 py-5 text-left mkt-lead text-foreground ${FOCUS} [&::-webkit-details-marker]:hidden`}
                    >
                        {item.q}
                        <span aria-hidden className="text-muted-foreground group-open:rotate-45">
                            +
                        </span>
                    </summary>
                    <p className="mkt-body max-w-3xl pb-6 text-muted-foreground">{item.a}</p>
                </details>
            ))}
        </div>
    );
}

/** The closing band: the rule, one big line, one small one, and the asks. */
export function Closing({ label, title, line, children, testid, id, ground = "page" }) {
    return (
        <Band ground={ground} id={id} track="close" testid={testid}>
            <Wrap className="py-20 md:py-32">
                {label ? <SectionRule label={label} className="mb-10" /> : null}
                <Rise>
                    <h2 className="mkt-display max-w-5xl text-heading">{title}</h2>
                </Rise>
                {line ? <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">{line}</p> : null}
                <div className="mt-10 flex flex-col gap-3 sm:flex-row">{children}</div>
            </Wrap>
        </Band>
    );
}
