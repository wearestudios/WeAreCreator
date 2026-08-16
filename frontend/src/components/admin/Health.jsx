// What is going wrong, what the business is doing, and how to get the data out.
//
// Three sections that sit above the overview's own numbers, because they answer
// the question somebody opens the console with: is anything on fire.
//
// The charts here are hand-drawn SVG on purpose. Four small shapes do not
// justify a charting dependency — the library would be larger than the whole
// admin bundle, and none of its axes, tooltips or legends would survive the
// design brief anyway.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
    AlertTriangle,
    ArrowRight,
    CheckCircle2,
    Download,
    Loader2,
} from "lucide-react";

import { api, API_BASE } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
    ADMIN_EXPORTS as EXPORT_IDS,
    ADMIN_HEALTH as IDS,
    ADMIN_INTEL as INTEL_IDS,
} from "@/constants/testIds";
import { Panel, Section, Stat } from "@/components/admin/DetailPage";
import { DateFilter, endOfDay, formatCompact } from "@/components/admin/shared";

// How many rows of a check to show before folding the rest away. Six is about
// what fits without the panel becoming the page.
const VISIBLE_ROWS = 6;

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function HealthPanel() {
    const [data, setData] = useState(null);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/admin/health");
            setData(data);
        } catch {
            // A failed health check must not take the overview down with it.
            setData({ checks: [], total: 0, critical: 0 });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    if (!data) {
        return (
            <Section id="health" title="Needs attention">
                <div data-testid={IDS.skeleton} aria-hidden="true" className="grid gap-4 md:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-40 rounded-md" />
                    ))}
                </div>
            </Section>
        );
    }

    const withItems = data.checks.filter((c) => c.count > 0);

    return (
        <Section
            id="health"
            title="Needs attention"
            count={data.total || undefined}
            action={
                data.critical > 0 && (
                    <span
                        data-testid={IDS.total}
                        className="inline-flex items-center gap-1.5 rounded-full border border-destructive/30 bg-destructive/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-destructive"
                    >
                        <AlertTriangle className="h-3 w-3" />
                        {data.critical} urgent
                    </span>
                )
            }
        >
            {withItems.length === 0 ? (
                <div
                    data-testid={IDS.allClear}
                    className="flex items-center gap-4 rounded-md border border-emerald-500/25 bg-emerald-500/[0.07] px-6 py-8 grain-surface"
                >
                    <CheckCircle2 className="h-5 w-5 flex-none text-emerald-400" />
                    <p className="text-sm leading-relaxed text-muted-foreground">
                        Nothing is overdue. Every campaign is filling, every accepted
                        creator has a slot, and nobody is waiting on us.
                    </p>
                </div>
            ) : (
                <div className="grid gap-4 md:grid-cols-2">
                    {withItems.map((check) => (
                        <HealthCheck key={check.key} check={check} />
                    ))}
                </div>
            )}
        </Section>
    );
}

function HealthCheck({ check }) {
    const [expanded, setExpanded] = useState(false);
    const shown = expanded ? check.items : check.items.slice(0, VISIBLE_ROWS);
    const hidden = check.items.length - shown.length;

    // min-w-0 because a grid item defaults to min-width:auto, so a child that
    // will not shrink — a long campaign title, a wide row — widens the whole
    // track past its container and the page scrolls sideways. Measured: without
    // it the console overflowed 24px at 375px.
    return (
        <Panel data-testid={IDS.check(check.key)} className="min-w-0 overflow-hidden p-0">
            <div className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
                <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        {check.label}
                        <span
                            data-testid={IDS.checkCount(check.key)}
                            className={
                                "ml-2 " + (check.critical ? "text-destructive" : "text-ember-500")
                            }
                        >
                            {check.count}
                        </span>
                    </p>
                    {/* The threshold, said out loud. Otherwise the only way to
                        know why something is on this list is to read the
                        server. */}
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                        {check.blurb}
                    </p>
                </div>
            </div>

            <ul className="divide-y divide-white/5">
                {shown.map((item) => (
                    <li key={item.id}>
                        <Link
                            to={item.href}
                            data-testid={IDS.item(item.id)}
                            className="group flex items-center gap-3 px-5 py-3 transition-colors duration-200 hover:bg-white/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ember-500"
                        >
                            <span
                                aria-hidden="true"
                                className={
                                    "h-1.5 w-1.5 flex-none rounded-full " +
                                    (item.severity === "critical"
                                        ? "bg-destructive"
                                        : "bg-amber-400/70")
                                }
                            />
                            <span className="min-w-0 flex-1">
                                <span className="block truncate text-sm">{item.label}</span>
                                <span className="block truncate text-xs text-muted-foreground">
                                    {item.detail}
                                </span>
                            </span>
                            <ArrowRight className="h-3.5 w-3.5 flex-none text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-ember-500" />
                        </Link>
                    </li>
                ))}
            </ul>

            {hidden > 0 && (
                <button
                    type="button"
                    onClick={() => setExpanded(true)}
                    data-testid={IDS.more(check.key)}
                    className="min-h-[2.75rem] w-full border-t border-white/10 px-5 py-3 text-left text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 md:min-h-0"
                >
                    {hidden} more
                </button>
            )}
        </Panel>
    );
}

// ---------------------------------------------------------------------------
// Intelligence
// ---------------------------------------------------------------------------

/** A sparkline. Nulls break the line rather than being drawn as zero. */
function Spark({ points, height = 48 }) {
    const known = points.map((p, i) => [i, p]).filter(([, p]) => p != null);
    if (known.length < 2) return null;
    const max = Math.max(...known.map(([, p]) => p), 1);
    const w = 100;
    const x = (i) => (i / Math.max(1, points.length - 1)) * w;
    const y = (v) => height - (v / max) * (height - 6) - 3;

    // Segments, so a gap in the data is a gap in the line. A single path
    // through the known points would draw straight across a missing week and
    // assert something we do not know.
    const segments = [];
    let run = [];
    for (const [i, p] of points.entries()) {
        if (p == null) {
            if (run.length > 1) segments.push(run);
            run = [];
        } else {
            run.push([x(i), y(p)]);
        }
    }
    if (run.length > 1) segments.push(run);

    return (
        <svg
            viewBox={`0 0 ${w} ${height}`}
            preserveAspectRatio="none"
            className="mt-4 h-12 w-full"
            aria-hidden="true"
        >
            {segments.map((seg, i) => (
                <polyline
                    key={i}
                    points={seg.map(([px, py]) => `${px},${py}`).join(" ")}
                    fill="none"
                    stroke="hsl(var(--primary))"
                    strokeWidth="1.5"
                    vectorEffect="non-scaling-stroke"
                    strokeLinejoin="round"
                />
            ))}
        </svg>
    );
}

/** Stacked weekly bars. */
function StackedBars({ series, weeks, height = 48 }) {
    if (!weeks.length) return null;
    const totals = weeks.map((_, i) => series.reduce((n, s) => n + (s.points[i] || 0), 0));
    const max = Math.max(...totals, 1);
    const bw = 100 / weeks.length;
    const tones = ["hsl(var(--primary))", "#7dd3a0", "#7cc4e8", "#c4a5e8", "#e8c97c"];

    return (
        <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="mt-4 h-12 w-full" aria-hidden="true">
            {weeks.map((_, i) => {
                let acc = 0;
                return series.map((s, si) => {
                    const v = s.points[i] || 0;
                    if (!v) return null;
                    const h = (v / max) * (height - 4);
                    const yPos = height - acc - h;
                    acc += h;
                    return (
                        <rect
                            key={`${i}-${si}`}
                            x={i * bw + bw * 0.15}
                            y={yPos}
                            width={bw * 0.7}
                            height={h}
                            fill={tones[si % tones.length]}
                            opacity={0.85}
                        />
                    );
                });
            })}
        </svg>
    );
}

/** Two numbers as one bar. Reads faster than a pie at this size. */
function SplitBar({ a, b, labelA, labelB }) {
    const total = a + b;
    const pct = total ? (a / total) * 100 : 0;
    return (
        <>
            <div className="mt-4 flex h-2 w-full overflow-hidden rounded-full bg-white/10">
                <div className="bg-ember-500" style={{ width: `${pct}%` }} />
            </div>
            <div className="mt-3 flex items-baseline justify-between text-xs">
                <span className="text-ember-500">
                    {formatCompact(a)} {labelA}
                </span>
                <span className="text-muted-foreground">
                    {formatCompact(b)} {labelB}
                </span>
            </div>
        </>
    );
}

const Card = ({ title, sub, testid, children }) => (
    <Panel data-testid={testid}>
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{title}</p>
        {children}
        {sub && <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{sub}</p>}
    </Panel>
);

export function IntelligencePanel() {
    const [d, setD] = useState(null);

    useEffect(() => {
        api
            .get("/admin/intelligence")
            .then(({ data }) => setD(data))
            .catch(() => setD(false));
    }, []);

    if (d === false) return null;
    if (!d) {
        return (
            <Section id="intel" title="Activity">
                <div data-testid={INTEL_IDS.skeleton} aria-hidden="true" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-36 rounded-md" />
                    ))}
                </div>
            </Section>
        );
    }

    const latestFill = [...d.fill_rate].reverse().find((v) => v != null);

    return (
        <Section id="intel" title="Activity" >
            <div data-testid={INTEL_IDS.section} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    testid={INTEL_IDS.chart("campaigns")}
                    title={`Campaigns posted · ${d.window_weeks}w`}
                    sub={`${d.campaigns_by_status.reduce((n, s) => n + s.points.reduce((a, b) => a + b, 0), 0)} in the window, by where they are now.`}
                >
                    <StackedBars series={d.campaigns_by_status} weeks={d.weeks} />
                </Card>

                <Card
                    testid={INTEL_IDS.chart("fill")}
                    title="Fill rate"
                    sub={
                        latestFill != null
                            ? `${latestFill}% of briefed places booked, most recent week.`
                            : "No campaigns with places to fill in the window."
                    }
                >
                    <Spark points={d.fill_rate} />
                </Card>

                <Card
                    testid={INTEL_IDS.chart("brands")}
                    title="Brands"
                    sub="Repeat is a brand on its second campaign or later — the only question that matters about the brand side."
                >
                    <SplitBar
                        a={d.brands.repeat}
                        b={d.brands.new}
                        labelA="repeat"
                        labelB="one-off"
                    />
                </Card>

                <Card
                    testid={INTEL_IDS.chart("creators")}
                    title="Verified creators"
                    sub={`Active = moved on something in the last ${d.creators.window_days} days.`}
                >
                    <SplitBar
                        a={d.creators.active}
                        b={d.creators.dormant}
                        labelA="active"
                        labelB="dormant"
                    />
                </Card>
            </div>
        </Section>
    );
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

const EXPORTS = [
    { key: "creators", label: "Creators", note: "with contact details" },
    { key: "brands", label: "Brands", note: "with contact details" },
    { key: "campaigns", label: "Campaigns", note: "fill rates and budgets" },
    { key: "collaborations", label: "Collaborations", note: "with performance" },
    { key: "payments", label: "Payments", note: "for accounting" },
    { key: "audit", label: "Audit log", note: "who did what" },
];

export function ExportsPanel() {
    const [from, setFrom] = useState(null);
    const [to, setTo] = useState(null);

    const href = useMemo(
        () => (kind) => {
            const params = new URLSearchParams();
            if (from) params.set("date_from", from.toISOString());
            if (to) params.set("date_to", endOfDay(to).toISOString());
            const q = params.toString();
            return `${API_BASE}/admin/exports/${kind}${q ? `?${q}` : ""}`;
        },
        [from, to],
    );

    return (
        <Section
            id="exports"
            title="Export"
            action={
                <div className="flex flex-wrap items-center gap-2">
                    <DateFilter value={from} onChange={setFrom} label="From" testid={EXPORT_IDS.dateFrom} />
                    <DateFilter value={to} onChange={setTo} label="To" testid={EXPORT_IDS.dateTo} />
                    {(from || to) && (
                        <button
                            type="button"
                            onClick={() => {
                                setFrom(null);
                                setTo(null);
                            }}
                            data-testid={EXPORT_IDS.clearDates}
                            className="min-h-[2.75rem] text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 md:min-h-0"
                        >
                            Clear dates
                        </button>
                    )}
                </div>
            }
        >
            <div data-testid={EXPORT_IDS.section} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {EXPORTS.map((e) => (
                    // Plain anchors: the browser should fetch the file itself
                    // rather than axios pulling bytes into memory for us to
                    // hand straight back to it.
                    <a
                        key={e.key}
                        href={href(e.key)}
                        data-testid={EXPORT_IDS.kind(e.key)}
                        className="group flex min-h-[2.75rem] items-center gap-3 rounded-md border border-white/10 bg-card px-4 py-3.5 transition-colors duration-200 hover:border-ember-500/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background grain-surface"
                    >
                        <Download className="h-4 w-4 flex-none text-muted-foreground transition-colors duration-200 group-hover:text-ember-500" />
                        <span className="min-w-0 flex-1">
                            <span className="block text-sm">{e.label}</span>
                            <span className="block truncate text-xs text-muted-foreground">
                                {e.note}
                            </span>
                        </span>
                    </a>
                ))}
            </div>

            {/* Said where somebody is about to download one. These files leave
                the building; the person clicking should know what is in them. */}
            <p
                data-testid={EXPORT_IDS.note}
                className="mt-4 text-xs leading-relaxed text-muted-foreground"
            >
                {from || to
                    ? "Filtered to the dates above. "
                    : "Everything, unless you set a date range. "}
                Creator and brand contact details are included in these — they're
                internal files. Nothing a brand receives ever carries them, the campaign
                report included. Every download is written to the audit log.
            </p>
        </Section>
    );
}
