// "A campaign is not a spreadsheet and sixty DMs" — section 2 of home.
//
// Two panels: the campaign as it runs today (a spreadsheet with unresolved
// cells, and two chat bubbles asking what a spreadsheet cannot answer) and the
// same campaign as it runs here (three rows, each with a number and a state).
// **Drawn in the DOM, not as images**, so the type stays crisp at any density
// and the panels follow the surface they sit on — tokens only.
//
// Every word and name comes from `HOME.swap` in `content/marketing.js`, and
// every name is invented.
//
// **On a phone the spreadsheet keeps three columns and the bubbles sit under
// it**, in the flow. Four columns at 390px is a sheet of ellipses, and a
// bubble positioned over the table covers the cells it is complaining about.
// From `md` up the bubbles overlap the sheet's corner at a slight angle —
// messages arriving on top of it.
//
// **Below the fold, so it must not cost first paint.** No fetch, no state, no
// effect; `content-visibility: auto` lets the browser skip its layout until it
// is near, with an intrinsic size reserved so the scrollbar does not jump.
import React from "react";
import { ArrowDown, ArrowRight } from "lucide-react";

import { Chip } from "@/components/marketing/siteMocks";
import { SectionHead, Wrap } from "@/components/marketing/SiteParts";
import { LANDING_COMPARE as IDS } from "@/constants/testIds";

const Panel = ({ label, testid, children }) => (
    <div data-testid={testid} className="min-w-0">
        <p className="mkt-label text-muted-foreground">{label}</p>
        <div className="mt-5">{children}</div>
    </div>
);

const COLS = "grid-cols-[1.2fr_0.9fr_1.3fr] md:grid-cols-[1.2fr_0.9fr_1.2fr_0.6fr]";
// The fourth column is a desktop luxury.
const cellClass = (c) => (c === 3 ? "hidden md:block" : "");

function Spreadsheet({ head, rows, bubbles }) {
    return (
        <div className="relative md:pb-14 md:pr-2">
            <div className="overflow-hidden rounded-md border border-border bg-card font-mono text-meta">
                <div className={`grid ${COLS} border-b border-border bg-muted text-muted-foreground`}>
                    {head.map((h, c) => (
                        <span key={h} className={`border-r border-border px-2 py-2 last:border-r-0 ${cellClass(c)}`}>
                            {h}
                        </span>
                    ))}
                </div>
                {rows.map((row, r) => (
                    <div key={r} className={`grid ${COLS} border-b border-border last:border-b-0`}>
                        {row.map((cell, c) => (
                            <span
                                key={c}
                                className={`min-h-[2.25rem] truncate border-r border-border px-2 py-2 text-foreground last:border-r-0 ${cellClass(c)}`}
                            >
                                {cell}
                            </span>
                        ))}
                    </div>
                ))}
            </div>
            <div
                aria-hidden
                className="mt-4 flex flex-col items-end gap-2 md:absolute md:bottom-0 md:right-0 md:mt-0"
            >
                {bubbles.map((b, i) => (
                    <span
                        key={b}
                        className={`max-w-[15rem] rounded-lg rounded-br-sm border border-border px-3 py-2 text-meta text-foreground ${
                            i % 2 ? "bg-muted md:rotate-1" : "bg-card md:-rotate-2"
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
                    className="flex items-center justify-between gap-3 border-b border-border px-4 py-4 last:border-b-0 sm:px-5"
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

/** @param {{ copy: typeof import("@/content/marketing").HOME.swap, n: number }} props */
export default function ComparisonBand({ copy, n }) {
    return (
        <section
            data-track-section="problem"
            data-testid={IDS.section}
            className="bg-background [contain-intrinsic-size:auto_760px] [content-visibility:auto]"
        >
            <Wrap className="py-20 md:py-28">
                <SectionHead n={n} label={copy.label} title={<span data-testid={IDS.title}>{copy.title}</span>} />
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
