// Was this campaign worth it?
//
// A brand could see what a campaign did only on a printable report an admin
// generated and sent them. Nothing in their own console answered it — and the
// question they actually ask at renewal is not about one campaign at all, it
// is "is this better than the last one we ran".
//
// **So the comparison against their own history leads.** It is the first thing
// on the panel rather than a line at the bottom of a table, because a brand
// cannot check an industry benchmark and can check its own last brief. That is
// the number it will act on, and burying it would be burying the only argument
// for a second campaign.
//
// Dark-only, deliberately: the light theme is scoped to the admin console, and
// `data-theme` is never written on a brand route. These read the same semantic
// tokens everything else does, so they would work if that ever changed — but
// nothing here depends on it.
import React, { useCallback, useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Download, Minus } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { downloadCsv } from "@/lib/download";
import { Button } from "@/components/ui/button";

const num = (v) =>
    v === null || v === undefined ? "—" : Number(v).toLocaleString("en-IN");
const money = (v) =>
    v === null || v === undefined ? "—" : `₹${Number(v).toLocaleString("en-IN")}`;
const pct = (v) => (v === null || v === undefined ? "—" : `${v}%`);

/**
 * The brand's own range picker.
 *
 * **It leads with "All time" where the admin console's leads with 6 months**,
 * and that is the difference rather than an oversight: this section is the
 * argument for a second campaign, and the argument is the first one. A window
 * applied without being asked for would hide the campaign a brand is proudest
 * of on the day it turned six months old.
 *
 * Written here rather than imported from `components/admin/` — a brand screen
 * reaching into the console kit is a dependency pointing the wrong way, and
 * the option sets genuinely differ.
 */
const BRAND_WINDOWS = [
    { days: null, label: "All time" },
    { days: 365, label: "1 year" },
    { days: 180, label: "6 months" },
    { days: 90, label: "90 days" },
];

function RangePicker({ value, onChange }) {
    return (
        <div
            role="radiogroup"
            aria-label="Date range"
            data-testid="brand-analytics-range"
            className="inline-flex rounded-lg border border-tint/10 bg-tint/[0.03] p-0.5"
        >
            {BRAND_WINDOWS.map((w) => (
                <button
                    key={w.label}
                    type="button"
                    role="radio"
                    aria-checked={value === w.days}
                    data-testid={`brand-analytics-range-${w.days ?? "all"}`}
                    onClick={() => onChange(w.days)}
                    className={
                        "rounded-md px-3 py-1.5 text-sm transition-colors " +
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

function Figure({ label, value, note }) {
    return (
        <div className="rounded-lg border border-tint/10 bg-card grain-surface p-5">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {label}
            </p>
            <p className="mt-2 font-serif text-fluid-2xl leading-none tracking-tight">
                {value}
            </p>
            {note && <p className="mt-1.5 text-xs text-muted-foreground">{note}</p>}
        </div>
    );
}

/**
 * One line of the comparison.
 *
 * **`better` comes from the server**, not from the sign of the change. A cost
 * per thousand going *down* is the good direction, and a panel that coloured
 * every fall red would be telling a brand its best campaign went badly —
 * decided once in `_against_their_own_history` rather than three times here.
 */
function Change({ label, block, format = num }) {
    if (!block) return null;
    const { value, previous, change_percent: change, better } = block;
    const Icon = change === 0 ? Minus : change > 0 ? ArrowUpRight : ArrowDownRight;
    return (
        <div className="flex items-baseline justify-between gap-4 py-2.5">
            <span className="text-sm text-muted-foreground">{label}</span>
            <span className="flex items-baseline gap-2">
                <span className="tabular-nums">{format(value)}</span>
                <span
                    className={
                        "inline-flex items-center gap-0.5 text-xs tabular-nums " +
                        (change === 0
                            ? "text-muted-foreground"
                            : better
                            ? "text-state-approved"
                            : "text-state-rejected")
                    }
                >
                    <Icon className="h-3 w-3" aria-hidden="true" />
                    {Math.abs(change)}%
                </span>
                <span className="text-xs text-muted-foreground">
                    was {format(previous)}
                </span>
            </span>
        </div>
    );
}

/** The comparison, as its own band. Absent on a first campaign, never zeroed. */
export function VersusHistory({ comparison, heading = "Against your last campaigns" }) {
    if (!comparison) return null;
    return (
        <section
            data-testid="brand-analytics-comparison"
            className="rounded-lg border border-primary/30 bg-primary/[0.06] p-6"
        >
            <p className="text-[10px] uppercase tracking-[0.2em] text-primary-ink">
                {heading}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
                Measured against your previous{" "}
                {comparison.campaigns_before === 1
                    ? "campaign"
                    : `${comparison.campaigns_before} campaigns`}
                .
            </p>
            <div className="mt-4 divide-y divide-tint/10">
                <Change label="People reached" block={comparison.reach} />
                <Change label="Engagement rate" block={comparison.engagement_rate} format={pct} />
                <Change
                    label="Cost per 1,000 reached"
                    block={comparison.cost_per_thousand_reach}
                    format={money}
                />
            </div>
        </section>
    );
}

/** The whole panel for one campaign. */
export default function CampaignAnalytics({
    campaignId,
    className = "",
}) {
    const [data, setData] = useState(null);
    const [failed, setFailed] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/brand/campaigns/${campaignId}/analytics`);
            setData(data);
        } catch (e) {
            setFailed(true);
            notifyError(e);
        }
    }, [campaignId]);

    useEffect(() => {
        load();
    }, [load]);

    if (failed) return null;
    if (!data) {
        return (
            <div className={`grid gap-4 sm:grid-cols-4 ${className}`} aria-hidden="true">
                {[0, 1, 2, 3].map((i) => (
                    <div key={i} className="h-28 animate-pulse rounded-lg bg-tint/5" />
                ))}
            </div>
        );
    }

    const t = data.totals;
    const d = data.deliverables;

    // **Absent on a brief nobody is working on yet, not a panel of zeros.**
    // A campaign with no accepted creators has nothing to report, and four
    // tiles reading "—" under a heading about results says we measured and
    // found nothing rather than that there is nothing to measure. The same
    // judgement `BrandAnalyticsSummary` makes, and the same one the proof
    // strip makes about its floor.
    if (!data.creators.length && !t.creators_delivered) return null;

    return (
        <div className={`space-y-6 ${className}`} data-testid="brand-campaign-analytics">
            <VersusHistory comparison={data.versus_their_own_history} />

            <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Figure
                    label="People reached"
                    value={num(t.total_reach)}
                    note={`${num(t.with_reach)} of ${num(t.creators_delivered)} posts measured`}
                />
                <Figure label="Engagement rate" value={pct(t.engagement_rate)} />
                <Figure
                    label="Cost per 1,000 reached"
                    value={money(t.cost_per_thousand_reach)}
                    // Said rather than left to be inferred: a barter brief has
                    // reach and no spend, and its reach is deliberately out of
                    // this denominator.
                    note={t.barter_deliveries ? "Paid work only" : null}
                />
                <Figure label="Spent" value={money(t.total_spend)} />
            </section>

            {/* **No budget bar here, deliberately.** `BudgetMeter` already
                carries total, committed and remaining above the Accept button
                on the one screen this mounts on — which is where that number
                belongs, since it is an input to a decision rather than a
                result of one. A second bar three sections lower reads as a
                second budget. If this panel ever mounts somewhere without
                one, that is the moment to add it, not before. */}

            {d.counted && (
                <section data-testid="brand-analytics-deliverables">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Promised against delivered
                    </p>
                    <div className="mt-3 space-y-2">
                        {d.rows.map((r) => (
                            <div
                                key={r.type}
                                className="flex items-center justify-between rounded-md border border-tint/10 bg-tint/[0.03] px-3 py-2 text-sm"
                            >
                                <span>{r.label}</span>
                                <span className="tabular-nums text-muted-foreground">
                                    {num(r.delivered)} of {num(r.promised)}
                                    {r.outstanding > 0 && (
                                        <span className="ml-2 text-state-pending">
                                            {num(r.outstanding)} outstanding
                                        </span>
                                    )}
                                </span>
                            </div>
                        ))}
                    </div>
                    {/* A brand reading "18 of 18 delivered" deserves to know
                        whether anybody counted. */}
                    {d.creators_counted < d.creators_taken && (
                        <p className="mt-2 text-xs text-muted-foreground">
                            {d.creators_counted} of {d.creators_taken} counted; the rest
                            are taken from the approval.
                        </p>
                    )}
                </section>
            )}

            {data.creators.length > 0 && (
                <section data-testid="brand-analytics-creators">
                    <div className="flex items-baseline justify-between">
                        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            Who performed
                        </p>
                        <Button
                            variant="ghost"
                            data-testid="brand-analytics-export"
                            onClick={() =>
                                downloadCsv(
                                    `/brand/analytics/export?campaign_id=${campaignId}`,
                                    "campaign-analytics.csv",
                                ).catch(notifyError)
                            }
                        >
                            <Download className="mr-2 h-4 w-4" />
                            CSV
                        </Button>
                    </div>
                    <div className="mt-3 overflow-x-auto">
                        <table className="w-full min-w-[34rem] text-sm">
                            <thead>
                                <tr className="border-b border-tint/10 text-left text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    <th className="py-2 pr-4 font-normal">Creator</th>
                                    <th className="py-2 pr-4 text-right font-normal">Reach</th>
                                    <th className="py-2 pr-4 text-right font-normal">Engagement</th>
                                    <th className="py-2 pr-4 text-right font-normal">Cost</th>
                                    <th className="py-2 text-right font-normal">Per 1,000</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-tint/5">
                                {data.creators.map((c) => (
                                    <tr key={c.creator_id}>
                                        <td className="py-2.5 pr-4">
                                            <span className="block">{c.name}</span>
                                            {c.instagram_handle && (
                                                <span className="block text-xs text-muted-foreground">
                                                    @{c.instagram_handle}
                                                </span>
                                            )}
                                        </td>
                                        {/* Unmeasured draws an em dash, never a
                                            zero: we did not measure them, which
                                            is not the same as them reaching
                                            nobody. */}
                                        <td className="py-2.5 pr-4 text-right tabular-nums">
                                            {num(c.reach)}
                                        </td>
                                        <td className="py-2.5 pr-4 text-right tabular-nums">
                                            {pct(c.engagement_rate)}
                                        </td>
                                        <td className="py-2.5 pr-4 text-right tabular-nums">
                                            {money(c.cost)}
                                        </td>
                                        <td className="py-2.5 text-right tabular-nums">
                                            {money(c.cost_per_thousand_reach)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
        </div>
    );
}

/** Everything this brand has run, for the dashboard. */
export function BrandAnalyticsSummary() {
    const [data, setData] = useState(null);
    const [failed, setFailed] = useState(false);
    const [days, setDays] = useState(null);

    useEffect(() => {
        api.get("/brand/analytics", { params: days ? { days } : undefined })
            .then(({ data }) => setData(data))
            .catch(() => setFailed(true));
    }, [days]);

    // A brand with nothing finished has nothing to roll up, and an empty
    // panel of dashes is worse than no panel. **Narrowing to a window that
    // happens to be empty keeps the panel**, because the picker is on screen
    // and the honest answer to "90 days" is that nothing ran in it — which is
    // a different statement from having run nothing at all.
    if (failed || !data) return null;
    if (!data.rollup.campaigns && days === null) return null;

    const r = data.rollup;
    return (
        <section data-testid="brand-analytics-summary" className="mt-14 space-y-6">
            {/* `flex-wrap` on the outer row, not only on the controls: a
                `justify-between` row that cannot wrap pushes the picker past
                the viewport, which measured as 9px of horizontal page scroll
                at 390. */}
            <div className="flex flex-wrap items-baseline justify-between gap-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-primary-ink">
                        Your results
                    </p>
                    <h2 className="mt-3 font-serif text-fluid-4xl leading-none tracking-tight">
                        Everything you've run.
                    </h2>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    <RangePicker value={days} onChange={setDays} />
                    <Button
                        variant="outline"
                        data-testid="brand-analytics-rollup-export"
                        onClick={() =>
                            downloadCsv(
                                days
                                    ? `/brand/analytics/export?days=${days}`
                                    : "/brand/analytics/export",
                                "campaign-analytics.csv",
                            ).catch(notifyError)
                        }
                    >
                        <Download className="mr-2 h-4 w-4" />
                        CSV
                    </Button>
                </div>
            </div>

            {r.campaigns ? (
                <>
                    <VersusHistory
                        comparison={data.latest_versus_history}
                        heading="Your latest campaign against the ones before"
                    />

                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <Figure label="Campaigns run" value={num(r.campaigns)} />
                        <Figure label="People reached" value={num(r.total_reach)} />
                        <Figure
                            label="Cost per 1,000"
                            value={money(r.cost_per_thousand_reach)}
                        />
                        <Figure label="Total spend" value={money(r.total_spend)} />
                    </div>
                </>
            ) : (
                // "Nothing matches your filters", not "nothing here yet" — the
                // distinction `ListEmptyState` draws, and the reader narrowed
                // the range themselves a second ago.
                <p
                    data-testid="brand-analytics-empty-window"
                    className="rounded-lg border border-tint/10 bg-card grain-surface p-6 text-sm text-muted-foreground"
                >
                    No campaigns finished in this window. Widen the range to see
                    everything you've run.
                </p>
            )}
        </section>
    );
}
