// The hero slider's visuals for slides B, C and D — the problem, the shoot
// and the AI. Slide A's visual, the deal, is `DealCard` in `siteMocks.jsx`.
//
// **Their own chunk ("hero-slides"), fetched after first paint.** The h1 is
// the homepage's LCP, and everything in the first paint's bundle is between a
// visitor and it. Slide A is on screen at first paint and ships with the
// page; these three are not needed until the first advance, seven seconds
// later, so they arrive in the meantime into frames that are already the
// right size (`HeroSlider.jsx`).
//
// **Drawn, never screenshotted, and pure.** Each is a function of its props:
// no state, no effects, no data, no context — `test_hero_slider.py` greps
// this file for every hook. Every word arrives from `content/marketing.js`,
// every name and number is invented, and every card carries "Example".
//
// **A compact variant below `sm`, not the desktop card shrunk.** At 0.64× the
// desktop card's text is 9px; the phone's cards drop rows and padding
// instead, and nothing on them is set under 12px. Done in CSS (`max-sm:`) so
// one tree serves both widths and there is nothing to measure.
import React from "react";
import { ArrowDown, ArrowRight, BadgeCheck, CalendarCheck, Sparkles } from "lucide-react";

import PhotoSlot from "@/components/marketing/PhotoSlot";
import { Chip, ExampleCard, ExampleTag } from "@/components/marketing/siteMocks";

const COLS = "grid-cols-[1.2fr_0.9fr_1.1fr] sm:grid-cols-[1.2fr_0.8fr_1.1fr_0.6fr]";
// The fourth column ("Paid?") and the empty last row are a desktop luxury.
const cell = (c) => (c === 3 ? "hidden sm:block" : "");

/**
 * Slide B: the campaign as it runs today — a spreadsheet, tilted and dashed,
 * with the DMs piling onto it — then a round arrow, then the same campaign
 * here, every row with a state.
 */
export function ProblemVisual({ swap }) {
    const rows = swap.sheetRows;
    return (
        <div className="relative h-full">
            <div className="absolute left-0 top-1 w-[68%] -rotate-2 sm:top-2 sm:w-[60%]">
                <div className="overflow-hidden rounded-md border border-dashed border-foreground/30 bg-card">
                    <div className="flex items-center justify-between gap-2 border-b border-dashed border-foreground/20 px-3 py-2">
                        <span className="truncate text-[0.75rem] text-muted-foreground sm:text-[0.8125rem]">
                            {swap.card.sheet}
                        </span>
                        <ExampleTag>{swap.card.tag}</ExampleTag>
                    </div>
                    <div className={`grid ${COLS} border-b border-border bg-muted text-[0.75rem] text-muted-foreground sm:text-[0.8125rem]`}>
                        {swap.sheetHead.map((h, c) => (
                            <span key={h} className={`border-r border-border px-2 py-1.5 last:border-r-0 ${cell(c)}`}>
                                {h}
                            </span>
                        ))}
                    </div>
                    {rows.map((row, r) => (
                        <div
                            key={r}
                            className={`grid ${COLS} border-b border-border last:border-b-0 ${r === rows.length - 1 ? "max-sm:hidden" : ""}`}
                        >
                            {row.map((value, c) => (
                                <span
                                    key={c}
                                    className={`min-h-[1.75rem] truncate border-r border-border px-2 py-1.5 text-[0.75rem] text-foreground last:border-r-0 sm:min-h-[2rem] sm:text-[0.8125rem] ${cell(c)}`}
                                >
                                    {value}
                                </span>
                            ))}
                        </div>
                    ))}
                </div>
                {/* The DMs, piling onto the sheet. On a phone the board below
                    would cover them, so the sheet carries the mess alone. */}
                <div aria-hidden className="mt-3 flex flex-col items-start gap-2 pl-6 max-sm:hidden">
                    {swap.bubbles.map((b, i) => (
                        <span
                            key={b}
                            className={`rounded-lg rounded-bl-sm border border-border px-3 py-1.5 text-[0.8125rem] text-foreground ${
                                i % 2 ? "bg-muted rotate-1" : "bg-card -rotate-1"
                            }`}
                        >
                            {b}
                        </span>
                    ))}
                </div>
            </div>

            {/* The board, with the round arrow on its top-left corner: from
                the sheet, to here. On the corner rather than between the two
                cards, because the cards overlap on purpose and a gap between
                them is not there to hold it. */}
            <div className="absolute bottom-0 right-0 w-[74%] sm:bottom-1 sm:w-[54%]">
                <span
                    aria-hidden
                    className="absolute -left-4 -top-4 z-10 grid h-9 w-9 place-items-center rounded-full bg-primary text-primary-foreground sm:-left-5 sm:-top-5 sm:h-11 sm:w-11"
                >
                    <ArrowRight className="hidden h-5 w-5 sm:block" />
                    <ArrowDown className="h-4 w-4 sm:hidden" />
                </span>
                <ExampleCard head={swap.card.here} tag={swap.card.tag}>
                    {swap.hereRows.map((row) => (
                        <div
                            key={row.name}
                            className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5 last:border-b-0 sm:px-5 sm:py-3"
                        >
                            <span className="min-w-0">
                                <span className="block truncate text-meta text-foreground">{row.name}</span>
                                <span className="block text-[0.8125rem] text-muted-foreground max-sm:hidden">{row.amount}</span>
                            </span>
                            <Chip tone={row.tone}>{row.state}</Chip>
                        </div>
                    ))}
                </ExampleCard>
            </div>
        </div>
    );
}

/**
 * Slide C: the shoot. The photo slot (its drawing until a photograph arrives)
 * in a rounded 3:2 frame, with the booking drawn over it — who, verified, and
 * when — and the one fact a creator wants before travelling: the fee was
 * agreed first. True of every collaboration: `commercial_agreed` comes before
 * `slot_booked` on every ladder.
 */
export function OnLocationVisual({ slide }) {
    const { card } = slide;
    return (
        <div className="flex h-full items-center">
            <div className="relative aspect-[3/2] w-full overflow-hidden rounded-lg border border-border">
                {/* Never wider than the stage's visual column: 540px from
                    `lg`, the full width below it. */}
                <PhotoSlot id={slide.slot} fill bare sizes="(min-width: 1024px) 540px, 100vw" />
                <span className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-pill border border-border bg-card px-3 py-1 text-[0.8125rem] text-foreground sm:right-4 sm:top-4">
                    <CalendarCheck aria-hidden className="h-3.5 w-3.5 text-muted-foreground" />
                    {card.chip}
                </span>
                <div className="absolute bottom-3 left-3 max-w-[78%] rounded-md border border-border bg-card px-3 py-2.5 sm:bottom-4 sm:left-4 sm:px-4 sm:py-3">
                    <div className="flex items-center gap-2">
                        <span className="text-meta font-medium text-foreground">{card.name}</span>
                        <span className="inline-flex items-center gap-1 text-[0.8125rem] text-state-approved">
                            <BadgeCheck aria-hidden className="h-3.5 w-3.5" />
                            {card.badge}
                        </span>
                        <span className="ml-1 max-sm:hidden">
                            <ExampleTag>{card.tag}</ExampleTag>
                        </span>
                    </div>
                    <p className="mt-1 text-[0.8125rem] text-muted-foreground">{card.line}</p>
                </div>
            </div>
        </div>
    );
}

/** The sparkle chip each AI row leads with. A graphic, not text: the brand
 * red as a stroke is 3.76:1 on white, over the 3:1 a non-text mark needs. */
const Spark = () => (
    <span aria-hidden className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-border bg-muted max-sm:hidden">
        <Sparkles className="h-4 w-4 stroke-accent" />
    </span>
);

/** One example per feature, keyed by its switch. */
const EXAMPLES = {
    briefWriter: (card) => (
        <p className="text-[0.8125rem] text-muted-foreground">
            <span className="text-foreground">{card.quote}</span>
            <span aria-hidden> → </span>
            {card.result}
        </p>
    ),
    nicheMatching: (card) => (
        <div className="flex flex-wrap gap-1.5">
            {card.chips.map((c, i) => (
                <span key={c} className={i > 0 ? "max-sm:hidden" : ""}>
                    <Chip>{c}</Chip>
                </span>
            ))}
            <Chip tone="good">{card.fit}</Chip>
        </div>
    ),
    campaignSummary: (card) => (
        <p className="rounded-md bg-muted px-3 py-2 text-[0.8125rem] leading-snug text-foreground max-sm:line-clamp-2">
            {card.summary}
        </p>
    ),
};

/**
 * Slide D: what the AI does, one row per feature that is switched on — the
 * caller passes only the live ones, read through `aiLive`. No match
 * percentage anywhere: the scorer's number ranks a shortlist, and it is not a
 * figure a brand is shown.
 */
export function AiVisual({ ai, cards }) {
    return (
        <ExampleCard head={ai.card.head} tag={ai.card.tag} className="h-full" bodyClassName="flex flex-col">
            <ul className="flex-1 divide-y divide-border">
                {cards.map((c) => (
                    <li
                        key={c.key}
                        data-track-section={`hero-ai-${c.key}`}
                        className="flex gap-3 px-4 py-2.5 sm:px-5 sm:py-3"
                    >
                        <Spark />
                        <div className="min-w-0 flex-1 space-y-1.5">
                            <p className="text-meta font-medium text-foreground">{c.title}</p>
                            {EXAMPLES[c.key] ? EXAMPLES[c.key](c.card) : null}
                        </div>
                    </li>
                ))}
            </ul>
            <p className="border-t border-border px-4 py-2.5 text-[0.8125rem] text-muted-foreground sm:px-5">{ai.card.foot}</p>
        </ExampleCard>
    );
}

/** Keyed by slide, so the stage reads the visual off the slide it shows. */
export const VISUALS = {
    problem: ProblemVisual,
    onLocation: OnLocationVisual,
    ai: AiVisual,
};
