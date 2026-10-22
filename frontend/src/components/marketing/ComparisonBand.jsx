// "A campaign is not a spreadsheet and sixty DMs" — the band under the hero.
//
// Two panels: the campaign as it runs today (a spreadsheet with unresolved
// cells and two chat bubbles asking the questions a spreadsheet cannot answer)
// and the same campaign as it runs here (three rows, each with a number and a
// state). **Drawn in the DOM, not as images**, so the type stays crisp at any
// density and the panels follow whichever theme is live — tokens only, no
// palette class and no colour literal.
//
// **The words a reader is meant to read are the page's**, passed in from
// `COPY` in `Landing.jsx` so they count against home's word budget. The
// spreadsheet's cells and the bubbles are illustration, the way the scroll
// film's drawn interfaces are, and every name in them is invented: a real
// brand in product UI on a public page reads as an endorsement.
//
// **Below the fold, so it must not cost first paint.** No fetch, no state,
// no effect; `content-visibility: auto` lets the browser skip its layout and
// paint until it is near the viewport, with an intrinsic size reserved so the
// scrollbar does not jump when it is. Panels stack at phone width with the
// spreadsheet first — the "today" has to be read before the "here" means
// anything.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowDown, ArrowRight } from "lucide-react";

import { Chip } from "@/components/marketing/heroScreens";
import { LANDING_COMPARE as IDS } from "@/constants/testIds";

const SHEET = [
    ["Aarav K.", "12k?", "no reply 6d", "—"],
    ["Nisha R.", "15,000", "reel wrong?", "?"],
    ["Kabir S.", "barter", "shot, no link", "no"],
    ["Tanvi M.", "18k / 15k?", "draft???", ""],
    ["", "", "", ""],
];

const HERE = [
    { name: "Aarav K.", amount: "₹12,000", tone: "pending", state: "In review · 2d" },
    { name: "Nisha R.", amount: "₹15,000", tone: "active", state: "Your call" },
    { name: "Kabir S.", amount: "₹9,500", tone: "good", state: "Paid" },
];

const Panel = ({ label, testid, children }) => (
    <div data-testid={testid} className="min-w-0">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
        <div className="mt-4">{children}</div>
    </div>
);

function Spreadsheet() {
    return (
        <div className="relative pb-16 pr-4 sm:pb-12">
            <div className="overflow-hidden rounded-md border border-tint/15 bg-card font-mono text-[12px]">
                <div className="grid grid-cols-[1.2fr_0.9fr_1.2fr_0.6fr] border-b border-tint/15 bg-muted text-muted-foreground">
                    {["Creator", "Rate", "Status", "Paid?"].map((h) => (
                        <span key={h} className="border-r border-tint/10 px-2 py-1.5 last:border-r-0">
                            {h}
                        </span>
                    ))}
                </div>
                {SHEET.map((row, r) => (
                    <div
                        key={r}
                        className="grid grid-cols-[1.2fr_0.9fr_1.2fr_0.6fr] border-b border-tint/10 last:border-b-0"
                    >
                        {row.map((cell, c) => (
                            <span
                                key={c}
                                className="min-h-[1.9rem] truncate border-r border-tint/10 px-2 py-1.5 text-foreground last:border-r-0"
                            >
                                {cell}
                            </span>
                        ))}
                    </div>
                ))}
            </div>
            {/* The two questions a spreadsheet cannot answer, overlapping its
                corner at a slight angle — messages arriving on top of it. */}
            <div aria-hidden className="absolute bottom-0 right-0 flex flex-col items-end gap-2">
                <span className="max-w-[14rem] -rotate-2 rounded-lg rounded-br-sm border border-tint/15 bg-card px-3 py-2 text-[12px] text-foreground">
                    Hi! Did the brief come through?
                </span>
                <span className="max-w-[14rem] rotate-1 rounded-lg rounded-br-sm border border-tint/15 bg-muted px-3 py-2 text-[12px] text-foreground">
                    Sorry, what was the amount again?
                </span>
            </div>
        </div>
    );
}

function Board() {
    return (
        <div className="rounded-md border border-tint/15 bg-card">
            {HERE.map((row) => (
                <div
                    key={row.name}
                    className="flex items-center justify-between gap-3 border-b border-tint/10 px-4 py-3.5 last:border-b-0"
                >
                    <span className="truncate text-sm text-foreground">{row.name}</span>
                    <span className="flex items-center gap-3">
                        <span className="text-sm tabular-nums text-foreground">{row.amount}</span>
                        <Chip tone={row.tone}>{row.state}</Chip>
                    </span>
                </div>
            ))}
        </div>
    );
}

/**
 * @param {{ title: string, todayLabel: string, hereLabel: string, linkLabel: string }} copy
 * @param {string} linkTo  where the link goes — the page decides its routing
 */
export default function ComparisonBand({ copy, linkTo }) {
    return (
        <section
            data-testid={IDS.section}
            data-surface="light"
            className="border-b border-border bg-background text-foreground [contain-intrinsic-size:auto_640px] [content-visibility:auto]"
        >
            <div className="mx-auto max-w-7xl px-6 py-14 md:py-20">
                <h2
                    data-testid={IDS.title}
                    className="max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight"
                >
                    {copy.title}
                </h2>

                <div className="mt-10 grid grid-cols-1 items-center gap-6 md:grid-cols-[1fr_auto_1fr] md:gap-10">
                    <Panel label={copy.todayLabel} testid={IDS.today}>
                        <Spreadsheet />
                    </Panel>

                    <div aria-hidden className="flex justify-center text-muted-foreground">
                        <ArrowDown className="h-6 w-6 md:hidden" />
                        <ArrowRight className="hidden h-6 w-6 md:block" />
                    </div>

                    <Panel label={copy.hereLabel} testid={IDS.here}>
                        <Board />
                    </Panel>
                </div>

                <Link
                    to={linkTo}
                    data-testid={IDS.link}
                    className="mt-10 inline-flex min-h-[2.75rem] items-center gap-2 rounded-sm text-sm text-primary-ink underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                    {copy.linkLabel}
                    <ArrowRight className="h-4 w-4" />
                </Link>
            </div>
        </section>
    );
}
