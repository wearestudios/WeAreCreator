// Is the business healthy?
//
// `Health.jsx` next door says what is going wrong right now and `Overview`
// says what the numbers are. This says whether the marketplace works, which is
// four ratios rather than four counts — a repeat *rate* rather than a repeat
// count, a fill rate broken down far enough to act on, a margin rather than a
// revenue, and the share of creators who ever get paid at all.
//
// **The charts read the theme tokens**, so they render in both themes — the
// light-theme work established that no console component may name a colour,
// and a chart is where a raw hex hides best because it carries no class for a
// sweep to find. `hsl(var(--state-approved))` here is the same green a status
// pill wears, which also means a series and the state it describes agree.
//
// **The heavy aggregation is not computed here and not on the request.** The
// endpoint serves `analytics_cache` and recomputes when it is stale; the page
// says how old the answer is, because a dashboard that looks live and is an
// hour old is worse than one that admits it.
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Download, RefreshCw } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Section, Stat } from "@/components/admin/DetailPage";
import { TEXT } from "@/components/admin/console/tokens";
import { ListEmptyState } from "@/components/data/DenseView";
import { downloadCsv } from "@/lib/download";

/**
 * The series palette, from the theme.
 *
 * Named for what each series *means* rather than for a colour, so a bar and
 * the status pill describing the same thing are the same green. `--primary` is
 * first because the headline series is the one the eye should land on.
 */
const SERIES = [
    "hsl(var(--primary))",
    "hsl(var(--state-approved))",
    "hsl(var(--state-progress))",
    "hsl(var(--state-done))",
    "hsl(var(--state-pending))",
];

/**
 * The windows the route accepts, mirrored — **a fifth option here would be a
 * 422, not a longer view.** `ANALYTICS_WINDOWS` in `server.py` is the closed
 * set, and a test fails the two if they drift.
 */
export const WINDOWS = [
    { days: 30, label: "30 days" },
    { days: 90, label: "90 days" },
    { days: 180, label: "6 months" },
    { days: 365, label: "1 year" },
];
const DEFAULT_WINDOW = 180;

/**
 * The range picker.
 *
 * Segmented rather than a dropdown: four options, all of them worth seeing at
 * once, and the one that is selected is the heading everything below it is
 * reported under — which is not a fact to hide behind a click.
 */
function RangePicker({ value, onChange, testId }) {
    return (
        <div
            role="radiogroup"
            aria-label="Date range"
            data-testid={testId}
            className="inline-flex rounded-lg border border-tint/10 bg-tint/[0.03] p-0.5"
        >
            {WINDOWS.map((w) => (
                <button
                    key={w.days}
                    type="button"
                    role="radio"
                    aria-checked={value === w.days}
                    data-testid={`${testId}-${w.days}`}
                    onClick={() => onChange(w.days)}
                    className={
                        "rounded-md px-3 py-1.5 text-sm transition-colors duration-150 " +
                        (value === w.days
                            ? "bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:text-foreground")
                    }
                >
                    {w.label}
                </button>
            ))}
        </div>
    );
}

const pct = (v) => (v === null || v === undefined ? "—" : `${v}%`);
const num = (v) =>
    v === null || v === undefined ? "—" : Number(v).toLocaleString("en-IN");
const money = (v) =>
    v === null || v === undefined ? "—" : `₹${Number(v).toLocaleString("en-IN")}`;

/**
 * A line, hand-drawn in SVG.
 *
 * Four small shapes do not justify a charting dependency — the same call
 * `Health.jsx` makes. **A missing month breaks the line rather than being
 * drawn as zero**: a line running straight through a gap asserts something we
 * do not know, and on a repeat rate that gap is usually "this cohort's window
 * has not closed yet", which is the opposite of a bad month.
 */
function Sparkline({ points, height = 44, label }) {
    const known = points.filter((p) => p !== null && p !== undefined);
    if (known.length < 2) return null;
    const max = Math.max(...known, 1);
    const step = 100 / Math.max(points.length - 1, 1);

    const segments = [];
    let run = [];
    points.forEach((p, i) => {
        if (p === null || p === undefined) {
            if (run.length > 1) segments.push(run);
            run = [];
            return;
        }
        run.push(`${i * step},${height - (p / max) * (height - 4) - 2}`);
    });
    if (run.length > 1) segments.push(run);

    return (
        <svg
            viewBox={`0 0 100 ${height}`}
            preserveAspectRatio="none"
            className="mt-3 h-11 w-full"
            role="img"
            aria-label={label}
        >
            {segments.map((seg, i) => (
                <polyline
                    key={i}
                    points={seg.join(" ")}
                    fill="none"
                    stroke="hsl(var(--primary))"
                    strokeWidth="1.5"
                    vectorEffect="non-scaling-stroke"
                />
            ))}
        </svg>
    );
}

/** Horizontal bars, for a breakdown small enough to read at a glance. */
function Bars({ rows, valueKey, format = pct, max }) {
    if (!rows.length) return null;
    const ceiling = max ?? Math.max(...rows.map((r) => Number(r[valueKey]) || 0), 1);
    return (
        <div className="mt-3 space-y-2">
            {rows.map((r, i) => (
                <div key={r.key ?? i} className="flex items-center gap-3">
                    <span className="w-28 shrink-0 truncate text-sm text-muted-foreground">
                        {r.key}
                    </span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-tint/5">
                        <div
                            className="h-full rounded-full"
                            style={{
                                width: `${Math.min(100, ((Number(r[valueKey]) || 0) / ceiling) * 100)}%`,
                                background: SERIES[i % SERIES.length],
                            }}
                        />
                    </div>
                    <span className="w-16 shrink-0 text-right text-sm tabular-nums">
                        {format(r[valueKey])}
                    </span>
                </div>
            ))}
        </div>
    );
}

/**
 * One supply-or-demand row, and a way through to the records behind it.
 *
 * **Naming a problem with nothing to do about it is how a panel becomes a list
 * people scroll past** — the lesson `Health.jsx` records. So each row opens the
 * list it is about, pre-filtered to exactly the set the figure counted.
 *
 * A button rather than an `<a>`: the destination is a list whose filters live
 * in session state rather than in the URL, so arriving is `navigate(..., {
 * state: { savedFilter } })` — the mechanism the sidebar's saved sets already
 * use. An anchor would promise a URL somebody could paste, and that URL would
 * open the list unfiltered.
 */
function SupplyRow({ row, right, onOpen, opens, testId }) {
    return (
        <li>
            <button
                type="button"
                data-testid={testId}
                onClick={onOpen}
                title={`Open the ${opens} this counted`}
                className="flex w-full items-center justify-between gap-3 rounded-md border border-tint/10 bg-tint/[0.03] px-3 py-2 text-left text-sm transition-colors duration-150 hover:border-primary/40 hover:bg-tint/[0.06]"
            >
                <span>
                    {row.category} · {row.city}
                </span>
                <span className="flex shrink-0 items-center gap-2 tabular-nums text-muted-foreground">
                    {right}
                    <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
            </button>
        </li>
    );
}

export default function Analytics() {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    const [days, setDays] = useState(DEFAULT_WINDOW);
    const navigate = useNavigate();

    // **The category goes through as a category, not as a search term.** The
    // creators list resolves it server-side through the same synonym table the
    // count used, so "14 fitness creators" opens those fourteen — a literal
    // search for the word would find whoever typed it, which is nobody.
    const openCreators = (r) =>
        navigate("/admin/creators", {
            state: { savedFilter: { category: r.category, area: r.city, page: 1 } },
        });
    const openCampaigns = (r) =>
        navigate("/admin/campaigns", {
            state: { savedFilter: { category: r.category, city: r.city, page: 1 } },
        });

    const load = useCallback(
        async (refresh = false) => {
            try {
                const { data } = await api.get("/admin/analytics", {
                    params: { days, ...(refresh ? { refresh: true } : {}) },
                });
                setData(data);
                setError(null);
            } catch (e) {
                setError(e);
                notifyError(e);
            }
        },
        [days],
    );

    useEffect(() => {
        load();
    }, [load]);

    const recompute = async () => {
        setBusy(true);
        try {
            await load(true);
            notifySuccess("Recomputed");
        } finally {
            setBusy(false);
        }
    };

    const exportKind = async (kind) => {
        try {
            // **The window rides along.** A file downloaded under a heading
            // that says 30 days and holding 180 is the disagreement between a
            // spreadsheet and the screen it came from.
            await downloadCsv(
                `/admin/analytics/export?kind=${kind}&days=${days}`,
                `analytics-${kind}-${days}d.csv`,
            );
        } catch (e) {
            notifyError(e);
        }
    };

    if (error && !data) {
        return (
            <ListEmptyState
                title="Analytics couldn't load"
                body="The numbers are computed on a schedule. Try again in a moment."
            />
        );
    }
    if (!data) {
        return (
            <div className="space-y-4" aria-hidden="true">
                {[0, 1, 2].map((i) => (
                    <div key={i} className="h-28 animate-pulse rounded-lg bg-tint/5" />
                ))}
            </div>
        );
    }

    const { repeat_rate: repeat, fill_rate: fill, margin, first_payment: first } = data;
    const supply = data.supply_and_demand;

    return (
        <div className="space-y-6" data-testid="admin-analytics">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className={TEXT.eyebrow}>Analytics</p>
                    <h2 className="mt-1 font-serif text-fluid-2xl leading-tight tracking-tight">
                        Is the business healthy?
                    </h2>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    <RangePicker
                        value={days}
                        onChange={setDays}
                        testId="analytics-range"
                    />
                    {/* **Said, not implied.** A dashboard that looks live and is
                        an hour old is worse than one that admits it. Only the
                        default window is cached, so the other three are always
                        worked out for this request and say "Just now" honestly. */}
                    <span className="text-sm text-muted-foreground">
                        {data.cached
                            ? `Worked out ${Math.round((data.age_seconds || 0) / 60)} min ago`
                            : "Just now"}
                    </span>
                    <Button
                        variant="outline"
                        disabled={busy}
                        data-testid="analytics-refresh"
                        onClick={recompute}
                        className="min-h-[2.75rem] sm:min-h-0"
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Recompute
                    </Button>
                </div>
            </div>

            {/* --- The one that matters most ------------------------------- */}
            <Section
                title="Brands coming back"
                action={
                    <Button variant="ghost" onClick={() => exportKind("repeat")}>
                        <Download className="mr-2 h-4 w-4" />
                        CSV
                    </Button>
                }
            >
                <div className="grid gap-4 sm:grid-cols-3">
                    <Stat label={`Repeat rate (${repeat.window_days} days)`} value={pct(repeat.rate)} />
                    {/* The denominator, beside the rate rather than behind a
                        tooltip: 50% over four brands is not the same fact as
                        50% over four hundred. */}
                    <Stat label="Brands judged" value={num(repeat.eligible)} />
                    <Stat label="Came back" value={num(repeat.repeated)} />
                </div>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    A brand is judged once its own {repeat.window_days} days have passed,
                    so a good month of new signups does not drag this down.
                </p>
                <Sparkline
                    points={(data.repeat_rate_trend || []).map((r) => r.rate)}
                    label="Repeat rate by the month the brand first posted"
                />
            </Section>

            {/* --- Fill rate ----------------------------------------------- */}
            <Section
                title="Briefs filled on time"
                action={
                    <Button variant="ghost" onClick={() => exportKind("fill")}>
                        <Download className="mr-2 h-4 w-4" />
                        CSV
                    </Button>
                }
            >
                <div className="grid gap-4 sm:grid-cols-4">
                    <Stat label="Fill rate" value={pct(fill.rate)} />
                    <Stat label="Filled" value={num(fill.filled)} />
                    {/* Late is its own number: a brief that found its people a
                        fortnight after the shoot is a different operational
                        story from one that only ever found four. */}
                    <Stat label="Late" value={num(fill.late)} />
                    <Stat label="Underfilled" value={num(fill.underfilled)} />
                </div>
                <div className="mt-5 grid gap-6 md:grid-cols-2">
                    <div>
                        <p className={TEXT.eyebrow}>By category</p>
                        <Bars rows={fill.by_category} valueKey="rate" />
                    </div>
                    <div>
                        <p className={TEXT.eyebrow}>By city</p>
                        <Bars rows={fill.by_city} valueKey="rate" />
                    </div>
                </div>
            </Section>

            {/* --- Margin --------------------------------------------------- */}
            <Section
                title="What we made"
                action={
                    <Button variant="ghost" onClick={() => exportKind("margin")}>
                        <Download className="mr-2 h-4 w-4" />
                        CSV
                    </Button>
                }
            >
                <div className="grid gap-4 sm:grid-cols-3">
                    <Stat label="Revenue" value={money(margin.revenue)} />
                    <Stat label="Margin" value={money(margin.margin)} />
                    <Stat
                        label="Briefs with a recorded cost"
                        value={`${num(margin.with_recorded_cost)} of ${num(margin.campaigns)}`}
                    />
                </div>
                {/* **Said plainly rather than shown as a confident figure.** A
                    margin computed with no recorded cost is a gross number
                    wearing a net number's name. */}
                {margin.with_recorded_cost < margin.campaigns && (
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                        {margin.campaigns - margin.with_recorded_cost} brief
                        {margin.campaigns - margin.with_recorded_cost === 1 ? " has" : "s have"}{" "}
                        no delivery cost recorded, so their revenue is counted and their
                        margin is not. Record it on the campaign page.
                    </p>
                )}
                <div className="mt-5">
                    <p className={TEXT.eyebrow}>By campaign type</p>
                    <Bars
                        rows={margin.by_campaign_type}
                        valueKey="average_margin"
                        format={money}
                    />
                </div>
            </Section>

            {/* --- Creator first payment ------------------------------------ */}
            <Section title="Creators reaching their first payout">
                <div className="grid gap-4 sm:grid-cols-4">
                    <Stat label="First-payment rate" value={pct(first.rate)} />
                    <Stat label="Paid" value={`${num(first.paid)} of ${num(first.verified)}`} />
                    {/* The median, because one creator who took eleven months
                        should not move the headline. */}
                    <Stat label="Median days" value={num(first.median_days_to_first_payment)} />
                    <Stat
                        label="Range"
                        value={
                            first.fastest_days === null
                                ? "—"
                                : `${first.fastest_days}–${first.slowest_days} days`
                        }
                    />
                </div>
            </Section>

            {/* --- Supply against demand ------------------------------------ */}
            <Section
                title="Where the creators are against where the briefs are"
                action={
                    <Button variant="ghost" onClick={() => exportKind("supply")}>
                        <Download className="mr-2 h-4 w-4" />
                        CSV
                    </Button>
                }
            >
                {/* **The two lists are the point.** A table of counts is
                    something somebody reads and nods at; these are lists a
                    salesperson and a supply person can each work. */}
                <div className="grid gap-6 md:grid-cols-2">
                    <div>
                        <p className={TEXT.eyebrow}>Sell into these</p>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Creators waiting, and nobody has briefed for them.
                        </p>
                        {supply.sell_into.length ? (
                            <ul className="mt-3 space-y-2">
                                {supply.sell_into.slice(0, 8).map((r) => (
                                    <SupplyRow
                                        key={`${r.category}-${r.city}`}
                                        row={r}
                                        testId={`analytics-sell-into-${r.category}-${r.city}`}
                                        right={`${num(r.creators)} creators`}
                                        onOpen={() => openCreators(r)}
                                        opens="creators"
                                    />
                                ))}
                            </ul>
                        ) : (
                            <p className="mt-3 text-sm text-muted-foreground">
                                Every category with creators in it has had a brief.
                            </p>
                        )}
                    </div>
                    <div>
                        <p className={TEXT.eyebrow}>Recruit for these</p>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Briefs we could not fill.
                        </p>
                        {supply.recruit_for.length ? (
                            <ul className="mt-3 space-y-2">
                                {supply.recruit_for.slice(0, 8).map((r) => (
                                    <SupplyRow
                                        key={`${r.category}-${r.city}`}
                                        row={r}
                                        testId={`analytics-recruit-for-${r.category}-${r.city}`}
                                        right={`${num(r.unfilled_campaigns)} unfilled · ${num(r.creators)} creators`}
                                        onOpen={() => openCampaigns(r)}
                                        opens="campaigns"
                                    />
                                ))}
                            </ul>
                        ) : (
                            <p className="mt-3 text-sm text-muted-foreground">
                                Nothing went unfilled.
                            </p>
                        )}
                    </div>
                </div>
            </Section>
        </div>
    );
}
