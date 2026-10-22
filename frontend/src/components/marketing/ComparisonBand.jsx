// "A campaign is not a spreadsheet and sixty DMs" — the band under the hero.
//
// Two panels: the campaign as it runs today (a spreadsheet with unresolved
// cells, and two chat bubbles asking the questions a spreadsheet cannot
// answer) and the same campaign as it runs here (three rows, each with a
// number and a state). **Drawn in the DOM, not as images**, so the type stays
// crisp at any density and the panels follow whichever surface they sit on —
// tokens only, no palette class and no colour literal.
//
// Every word and name comes from `HOME.swap` in `content/marketing.js`, and
// every name is invented: a real brand in product UI on a public page reads as
// an endorsement.
//
// **Below the fold, so it must not cost first paint.** No fetch, no state, no
// effect; `content-visibility: auto` lets the browser skip its layout and
// paint until it is near the viewport, with an intrinsic size reserved so the
// scrollbar does not jump when it is. Panels stack at phone width with the
// spreadsheet first — "today" has to be read before "here" means anything.
import React from "react";
import { ArrowDown, ArrowRight } from "lucide-react";

import { Chip } from "@/components/marketing/heroScreens";
import { Wrap } from "@/components/marketing/SiteParts";
import { LANDING_COMPARE as IDS } from "@/constants/testIds";

const Panel = ({ label, testid, children }) => (
    <div data-testid={testid} className="min-w-0">
        <p className="mkt-eyebrow text-muted-foreground">{label}</p>
        <div className="mt-5">{children}</div>
    </div>
);

const SHEET_COLS = "grid-cols-[1.2fr_0.9fr_1.2fr_0.6fr]";

function Spreadsheet({ head, rows, bubbles }) {
    return (
        <div className="relative pb-20 pr-2 sm:pb-14">
            <div className="overflow-hidden rounded-md border border-border bg-card font-mono text-meta">
                <div className={`grid ${SHEET_COLS} border-b border-border bg-muted text-muted-foreground`}>
                    {head.map((h) => (
                        <span key={h} className="border-r border-border px-2 py-2 last:border-r-0">
                            {h}
                        </span>
                    ))}
                </div>
                {rows.map((row, r) => (
                    <div key={r} className={`grid ${SHEET_COLS} border-b border-border last:border-b-0`}>
                        {row.map((cell, c) => (
                            <span
                                key={c}
                                className="min-h-[2.25rem] truncate border-r border-border px-2 py-2 text-foreground last:border-r-0"
                            >
                                {cell}
                            </span>
                        ))}
                    </div>
                ))}
            </div>
            {/* The questions a spreadsheet cannot answer, overlapping its
                corner at a slight angle — messages arriving on top of it. */}
            <div aria-hidden className="absolute bottom-0 right-0 flex flex-col items-end gap-2">
                {bubbles.map((b, i) => (
                    <span
                        key={b}
                        className={`max-w-[15rem] rounded-lg rounded-br-sm border border-border px-3 py-2 text-meta text-foreground ${
                            i % 2 ? "rotate-1 bg-muted" : "-rotate-2 bg-card"
                        }`}
                    >
                        {b}
                    </span>
                ))}
            </div>
        </div>
    );
}

function Board({ rows }) {
    return (
        <div className="rounded-md border border-border bg-card">
            {rows.map((row) => (
                <div
                    key={row.name}
                    className="flex items-center justify-between gap-3 border-b border-border px-5 py-4 last:border-b-0"
                >
                    <span className="truncate text-body text-foreground">{row.name}</span>
                    <span className="flex items-center gap-3">
                        <span className="text-body text-foreground">{row.amount}</span>
                        <Chip tone={row.tone}>{row.state}</Chip>
                    </span>
                </div>
            ))}
        </div>
    );
}

/** @param {{ copy: typeof import("@/content/marketing").HOME.swap }} props */
export default function ComparisonBand({ copy }) {
    return (
        <section
            data-testid={IDS.section}
            className="border-y border-border bg-background [contain-intrinsic-size:auto_720px] [content-visibility:auto]"
        >
            <Wrap className="py-20 md:py-28">
                <h2 data-testid={IDS.title} className="mkt-h2 max-w-4xl text-heading">
                    {copy.title}
                </h2>

                <div className="mt-14 grid grid-cols-1 items-center gap-8 md:grid-cols-[1fr_auto_1fr] md:gap-12">
                    <Panel label={copy.todayLabel} testid={IDS.today}>
                        <Spreadsheet head={copy.sheetHead} rows={copy.sheetRows} bubbles={copy.bubbles} />
                    </Panel>

                    <div aria-hidden className="flex justify-center text-muted-foreground">
                        <ArrowDown className="h-7 w-7 md:hidden" />
                        <ArrowRight className="hidden h-7 w-7 md:block" />
                    </div>

                    <Panel label={copy.hereLabel} testid={IDS.here}>
                        <Board rows={copy.hereRows} />
                    </Panel>
                </div>
            </Wrap>
        </section>
    );
}
