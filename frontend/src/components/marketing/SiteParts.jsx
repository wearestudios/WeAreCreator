// The furniture the three public pages — home, /brands, /creators — share.
//
// **Layout only.** Every word arrives as a prop from `content/marketing.js`;
// nothing here holds copy of its own, so the copy can be rewritten without
// opening this file.
//
// **No motion.** The site is allowed three moments (the hero headline, the
// counter history, the money count) and none of them is here. Hover is a
// colour, border or transform change at `--mkt-interactive` (200ms), and
// everything else simply appears: no section reveals, no card lifts on scroll.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import PhotoSlot from "@/components/marketing/PhotoSlot";

/** The one transition a public control may have. */
const HOVER =
    "transition-[color,background-color,border-color,transform] [transition-duration:var(--mkt-interactive)] [transition-timing-function:var(--weare-ease)]";

const FOCUS =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

/** A page-width container. */
export function Wrap({ children, className = "" }) {
    return <div className={`mx-auto w-full max-w-7xl px-6 md:px-10 ${className}`}>{children}</div>;
}

export function Eyebrow({ children, className = "", testid }) {
    if (!children) return null;
    return (
        <p data-testid={testid} className={`mkt-eyebrow text-muted-foreground ${className}`}>
            {children}
        </p>
    );
}

/** An eyebrow, an `h2` and an optional line — the head of most sections. */
export function SectionHead({ eyebrow, title, line, className = "" }) {
    return (
        <div className={`max-w-5xl ${className}`}>
            <Eyebrow>{eyebrow}</Eyebrow>
            <h2 className="mkt-h2 mt-4 text-heading">{title}</h2>
            {line ? <p className="mkt-lead mt-5 max-w-2xl text-muted-foreground">{line}</p> : null}
        </div>
    );
}

/**
 * The primary ask. **Navy on a light ground, never red** — a red button on a
 * light page reads as destructive. `primary` is navy on the light surface,
 * which is where every one of these sits.
 */
export function PrimaryButton({ to, label, testid, className = "" }) {
    return (
        <Link
            to={to}
            data-testid={testid}
            className={`inline-flex min-h-[3rem] items-center justify-center gap-2 rounded-md bg-primary px-6 text-body font-medium text-primary-foreground hover:bg-primary-hover ${HOVER} ${FOCUS} ${className}`}
        >
            {label}
            <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
    );
}

export function OutlineButton({ to, label, testid, className = "" }) {
    return (
        <Link
            to={to}
            data-testid={testid}
            className={`inline-flex min-h-[3rem] items-center justify-center gap-2 rounded-md border border-foreground/25 px-6 text-body font-medium text-foreground hover:border-foreground/60 ${HOVER} ${FOCUS} ${className}`}
        >
            {label}
        </Link>
    );
}

/**
 * The page's one inverted band: navy ground, white display type, three
 * claims each with the mechanism that makes it true.
 *
 * `data-surface="dark"` swaps the tokens for the section, so everything inside
 * resolves from the navy set without a class of its own.
 */
export function PromiseBand({ eyebrow, title, items, testid, itemTestid }) {
    return (
        <section data-testid={testid} data-surface="dark" className="bg-background text-foreground">
            <Wrap className="py-20 md:py-28">
                <SectionHead eyebrow={eyebrow} title={title} />
                <ul className="mt-14 grid gap-10 md:grid-cols-3 md:gap-12">
                    {items.map((item, i) => (
                        <li key={item.title} data-testid={itemTestid ? itemTestid(i) : undefined}>
                            <span aria-hidden className="block h-1 w-10 bg-accent" />
                            <h3 className="mkt-h3 mt-6 text-heading">{item.title}</h3>
                            <p className="mkt-body mt-4 text-muted-foreground">{item.line}</p>
                        </li>
                    ))}
                </ul>
            </Wrap>
        </section>
    );
}

/**
 * A full-bleed photograph with a heading over it.
 *
 * The heading sits on its own panel rather than straight on the picture, so it
 * is legible over the empty slot today and over whatever photograph replaces
 * it — no scrim tuned to an image nobody has taken. Full bleed: the slot is
 * the width of the window.
 */
export function PhotoBand({ slot, title, testid }) {
    return (
        <section data-testid={testid} className="relative">
            <PhotoSlot id={slot} />
            {/* Over the picture from `md` up; below it on a phone, where a 2:1
                frame is 195px tall and a 40px heading would cover it. */}
            <div className="md:absolute md:inset-x-0 md:bottom-0">
                <Wrap className="pt-6 md:pb-10 md:pt-0">
                    <h2 className="mkt-h2 max-w-3xl text-heading md:inline-block md:rounded-md md:bg-background/95 md:px-8 md:py-6">
                        {title}
                    </h2>
                </Wrap>
            </div>
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

/** Three titled cards in a row. */
export function CardRow({ items, testid, renderExtra }) {
    return (
        <ul className="mt-12 grid gap-5 md:grid-cols-3">
            {items.map((item, i) => (
                <li key={item.title}>
                    <Card testid={testid ? testid(i) : undefined} className="h-full">
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
 * A comparison table. Real `<table>` markup, so a screen reader reads each
 * cell against its column and row headers. Scrolls inside its own box on a
 * phone rather than pushing the page sideways.
 */
export function CompareTable({ columns, rows, testid, label }) {
    return (
        // A scrolling region on a phone, so it is focusable to the keyboard
        // and gets a name to be announced by rather than "group".
        <div
            data-testid={testid}
            role="region"
            aria-label={label}
            tabIndex={0}
            className="mt-12 overflow-x-auto rounded-lg border border-border bg-card"
        >
            <table className="w-full min-w-[40rem] border-collapse text-left">
                <thead>
                    <tr className="border-b border-border">
                        {columns.map((c, i) => (
                            <th
                                key={c || "row"}
                                scope="col"
                                className={`px-5 py-4 align-bottom mkt-eyebrow ${i === 2 ? "text-foreground" : "text-muted-foreground"}`}
                            >
                                {c}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map(([head, ...cells]) => (
                        <tr key={head} className="border-b border-border last:border-b-0">
                            <th scope="row" className="w-1/5 px-5 py-4 align-top text-body font-medium text-foreground">
                                {head}
                            </th>
                            {cells.map((cell, i) => (
                                <td
                                    key={`${head}-${i}`}
                                    className={`px-5 py-4 align-top text-body ${i === 1 ? "text-foreground" : "text-muted-foreground"}`}
                                >
                                    {cell}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
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
                <details key={item.q} data-testid={itemTestid ? itemTestid(i) : undefined} className="group">
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

/** The closing band: one big line, one small one, and the asks. */
export function Closing({ title, line, children, testid }) {
    return (
        <section data-testid={testid} className="border-t border-border">
            <Wrap className="py-20 md:py-32">
                <h2 className="mkt-display max-w-5xl text-heading">{title}</h2>
                {line ? <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">{line}</p> : null}
                <div className="mt-10 flex flex-col gap-3 sm:flex-row">{children}</div>
            </Wrap>
        </section>
    );
}
