// The top of the console's overview: what needs a person today (board 27).
//
// **Every count here is the action queue's own rows.** The tiles, the
// heading's total and the card below all come from `loadQueueRows` — the
// function `/admin/queue` draws from — rather than from the sidebar's badges,
// which count a slightly different set (a brand that signed up and never
// submitted is a badge and not a row). The overview and the queue it links to
// therefore agree about what "waiting" means, row for row.
//
// The right-hand column shows only what an endpoint serves, under the window
// the endpoint serves it for. Nothing here is a total added up in the browser.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { api } from "@/lib/api";
import { aiLive } from "@/content/marketing";
import { formatDayLong } from "@/lib/time";
import { formatInr } from "@/lib/compensation";
import { notifyError } from "@/lib/feedback";
import { AiSummaryCard, AppCard, CardHeading, Sparkline, StatTile } from "@/components/app/ui";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ADMIN_TODAY as IDS } from "@/constants/testIds";
import DataTable from "./console/DataTable";
import StatusTag from "./console/StatusTag";
import { CALM, FOCUS } from "./console/tokens";
import { KIND_META, loadQueueRows } from "./ActionQueue";
import { STATE_META } from "./shared";

/**
 * The five queues a person works, in the board's order. Collaborations to move
 * have no tile of their own — they are in the card below and in the total.
 *
 * **"Briefs to approve" is the board's "Drafts to approve".** The queue's
 * campaign rows are briefs a brand submitted (and trusted briefs already live
 * awaiting a read); `draft` is a different campaign status, the one before
 * submission, and calling the queue's rows drafts would name the thing they
 * are not.
 */
export const TILES = [
    { kind: "campaign", label: "Briefs to approve", to: "/admin/campaign-reviews" },
    { kind: "creator", label: "Creators to verify", to: "/admin/creator-reviews", adminOnly: true },
    { kind: "brand", label: "Brands to verify", to: "/admin/brand-reviews" },
    { kind: "payment", label: "Payouts due", to: "/admin/queue" },
    { kind: "question", label: "Unanswered questions", to: "/admin/queue" },
];

/** How many rows the card shows before "See all". */
export const CARD_ROWS = 8;

/** Where each kind of row is decided — the record's own page, which carries
 *  the approval actions (see "Every review opens a full page"). */
const ROW_ACTION = {
    payment: { verb: "Pay", to: (r) => `/admin/collaborations/${r.raw.id}` },
    question: { verb: "Answer", to: (r) => r.link },
    collaboration: { verb: "Open", to: (r) => `/admin/collaborations/${r.raw.id}` },
    campaign: { verb: "Review", to: (r) => `/admin/campaigns/${r.raw.id}` },
    brand: { verb: "Check", to: (r) => `/admin/brands/${r.raw.user_id}` },
    creator: { verb: "Check", to: (r) => `/admin/creators/${r.raw.user_id}` },
};

/**
 * The row's state in words, on its tint — a `STATUS_TONE` key and a label,
 * drawn by the console's one `StatusTag`. Read off the row; nothing worked out.
 */
export function rowState(row) {
    const raw = row.raw || {};
    if (row.kind === "payment") {
        return row.urgent
            ? { tone: "due", label: `Day ${raw.payout_unpaid_days} unpaid` }
            : { tone: "info", label: "To pay" };
    }
    if (row.kind === "collaboration") {
        return { tone: row.urgent ? "due" : "neutral", label: STATE_META[row.state]?.label || "To move" };
    }
    if (row.kind === "campaign") {
        return raw.auto_published_at
            ? { tone: "due", label: "Live, unread" }
            : { tone: "info", label: "Awaiting approval" };
    }
    if (row.kind === "creator") {
        return row.note ? { tone: "due", label: "Edited" } : { tone: "info", label: "New profile" };
    }
    if (row.kind === "brand") return { tone: "info", label: "Submitted" };
    if (row.kind === "question") return { tone: "info", label: "Unanswered" };
    return { tone: "idle", label: "Waiting" };
}

/** Oldest first — the card is "what has waited longest". */
export const oldestFirst = (rows) =>
    [...rows].sort((a, b) => new Date(a.since || 0) - new Date(b.since || 0));

/** A queue tile: a count, its label, and amber when a payout's clock is late. */
function QueueTile({ tile, count, amber, note }) {
    return (
        <Link
            to={tile.to}
            data-testid={IDS.tile(tile.kind)}
            data-tone={amber ? "due" : "calm"}
            className={
                `block min-w-0 rounded-tile px-4 py-3.5 shadow-card ${CALM} ${FOCUS} ` +
                (amber ? "bg-state-due-wash text-state-due" : "bg-card text-heading hover:bg-wash-warm")
            }
        >
            <span className="app-figure block text-[1.75rem] leading-none">{count}</span>
            <span
                className={
                    "mt-1.5 block text-[13px] font-semibold " + (amber ? "text-state-due" : "text-muted-foreground")
                }
            >
                {tile.label}
            </span>
            {note ? <span className="mt-1 block text-label text-state-due">{note}</span> : null}
        </Link>
    );
}

/** The figures beside the queue, under the window each one is served for. */
function Lately({ dashboard, intelligence, allAccess }) {
    const totals = dashboard?.totals || {};
    const tiles = [];
    if (allAccess && intelligence) {
        const { creators, brands } = intelligence;
        if (creators?.active != null) {
            tiles.push(["active", creators.active, `Active creators · ${creators.window_days} days`]);
        }
        if (brands?.total) tiles.push(["repeat", `${brands.repeat} of ${brands.total}`, "Brands who came back"]);
    } else if (totals.active_creators != null) {
        tiles.push(["active", totals.active_creators, "Creators with work"]);
    }
    if (totals.payouts_pending != null) tiles.push(["pending", formatInr(totals.payouts_pending), "Payouts waiting"]);
    if (allAccess && totals.platform_revenue != null) {
        tiles.push(["revenue", formatInr(totals.platform_revenue), "Our fees, all time"]);
    }
    // The fill rate per week, as served — a week with no campaign is `null`
    // and breaks the line rather than being drawn as zero.
    const fill = allAccess ? intelligence?.fill_rate || [] : [];
    const latest = fill.length ? fill[fill.length - 1] : null;

    if (!tiles.length && fill.filter((v) => v != null).length < 2) return null;
    return (
        <AppCard data-testid={IDS.lately}>
            <CardHeading>How it&apos;s going</CardHeading>
            <div className="grid grid-cols-2 gap-2.5">
                {tiles.map(([key, value, label]) => (
                    <StatTile key={key} quiet value={value} label={label} testid={IDS.figure(key)} />
                ))}
            </div>
            {fill.filter((v) => v != null).length >= 2 && (
                <div className="mt-4" data-testid={IDS.fill}>
                    <p className="flex items-baseline justify-between gap-3 text-meta font-semibold text-muted-foreground">
                        <span>Fill rate, last {intelligence?.window_weeks || fill.length} weeks</span>
                        {latest != null && (
                            <span className="app-figure text-foreground">{latest}% this week</span>
                        )}
                    </p>
                    <Sparkline points={fill} label="Fill rate by week" className="mt-2" />
                </div>
            )}
        </AppCard>
    );
}

export default function Today({ allAccess = true }) {
    const [state, setState] = useState(null);

    const load = useCallback(async () => {
        try {
            const [queue, dashboard, intelligence] = await Promise.all([
                loadQueueRows(allAccess),
                api.get("/admin/dashboard", { params: { limit: 50 } }).then((r) => r.data),
                // Platform-wide and admin-only, like the screen it feeds.
                allAccess ? api.get("/admin/intelligence").then((r) => r.data) : null,
            ]);
            // **The AI card is not even asked for with the switch off.** With
            // it on, the most recent finished campaign's summary — the only
            // summary the API writes — and only for an admin, because the
            // route is the owning brand's and an admin's.
            let summary = null;
            if (allAccess && aiLive("campaignSummary")) {
                const done = (dashboard?.campaign_summary || []).find((c) =>
                    ["completed", "closed"].includes(c.status),
                );
                if (done) {
                    const { data } = await api
                        .get(`/brand/campaigns/${done.id}/summary`)
                        .catch(() => ({ data: null }));
                    if (data?.available && data?.summary?.headline) {
                        summary = { campaign: done, headline: data.summary.headline };
                    }
                }
            }
            setState({ ...queue, dashboard, intelligence, summary });
        } catch (e) {
            notifyError(e);
            setState({ rows: [], dashboard: null, intelligence: null, summary: null, failed: true });
        }
    }, [allAccess]);

    useEffect(() => {
        load();
    }, [load]);

    const rows = state?.rows || [];
    const count = (kind) => rows.filter((r) => r.kind === kind).length;
    const atRisk = rows.filter((r) => r.urgent);
    const tiles = TILES.filter((t) => allAccess || !t.adminOnly);
    const total = rows.length;
    const heading =
        total === 0
            ? "Nothing needs a person today"
            : `${total} ${total === 1 ? "thing needs" : "things need"} a person today`;

    const columns = [
        {
            key: "item",
            mobile: "primary",
            header: "Waiting",
            value: (r) => r.since || "",
            cell: (r) => {
                const meta = KIND_META[r.kind];
                return (
                    <span className="flex min-w-0 items-center gap-3">
                        <span
                            aria-hidden="true"
                            className="density-avatar grid h-9 w-9 flex-none place-items-center rounded-[10px] bg-wash-navy text-heading"
                        >
                            <meta.Icon className="h-4 w-4" />
                        </span>
                        <span className="flex min-w-0 flex-col">
                            <span className="truncate font-bold text-heading">{r.primary}</span>
                            <span className="truncate text-meta text-muted-foreground">
                                {meta.label}
                                {r.secondary ? ` · ${r.secondary}` : ""}
                            </span>
                        </span>
                    </span>
                );
            },
        },
        {
            key: "state",
            mobile: "meta",
            header: "State",
            width: "w-40",
            value: (r) => rowState(r).label,
            cell: (r) => {
                const s = rowState(r);
                return <StatusTag chip tone={s.tone} label={s.label} testid={IDS.rowState(r.id)} />;
            },
        },
        {
            key: "action",
            mobile: "action",
            header: <span className="sr-only">Action</span>,
            width: "w-28",
            value: (r) => ROW_ACTION[r.kind]?.verb || "",
            cell: (r) => {
                const action = ROW_ACTION[r.kind];
                return (
                    <Link to={action.to(r)} data-testid={IDS.rowAction(r.id)} onClick={(e) => e.stopPropagation()}>
                        <Button variant="quiet" size="sm">
                            {action.verb}
                        </Button>
                    </Link>
                );
            },
        },
    ];

    const shown = oldestFirst(rows).slice(0, CARD_ROWS);
    const oldestAtRisk = atRisk.reduce(
        (n, r) => Math.max(n, Number(r.raw?.payout_unpaid_days) || 0),
        0,
    );

    return (
        <section data-testid={IDS.section}>
            {/* ⌘K is the console header's own trigger, on every screen —
                not a second button here. */}
            <div>
                <div className="min-w-0">
                    <p className="text-label text-muted-foreground">{formatDayLong(new Date())}</p>
                    {state ? (
                        <h1 data-testid={IDS.heading} className="app-title mt-1">
                            {heading}
                        </h1>
                    ) : (
                        // The heading's own box while the count is in flight:
                        // one line of the title's size, so nothing moves.
                        <Skeleton className="mt-2 h-[2.375rem] w-[min(28rem,80%)] md:h-[2.75rem]" />
                    )}
                </div>
            </div>

            {/* The five queues. Amber on the payouts tile is the server's
                `payout_at_risk` — an approval five days into the seven-day
                promise — never a date worked out here. */}
            <div
                data-testid={IDS.tiles}
                className={
                    // Five in a row from `md`; two by two below, with an odd
                    // last tile taking the row rather than sitting alone.
                    "mt-5 grid grid-cols-2 gap-2.5 sm:gap-3 max-md:[&>*:last-child:nth-child(odd)]:col-span-2 " +
                    (tiles.length === 5 ? "md:grid-cols-5" : "md:grid-cols-4")
                }
            >
                {state
                    ? tiles.map((t) => {
                          const amber = t.kind === "payment" && atRisk.length > 0;
                          return (
                              <QueueTile
                                  key={t.kind}
                                  tile={t}
                                  count={count(t.kind)}
                                  amber={amber}
                                  note={amber ? `Oldest on day ${oldestAtRisk}` : null}
                              />
                          );
                      })
                    : tiles.map((t) => <Skeleton key={t.kind} className="h-[5.5rem] rounded-tile" />)}
            </div>

            <div className="mt-5 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_22rem]">
                <AppCard data-testid={IDS.queue} className="min-w-0 !p-0">
                    <div className="px-5 pt-4 md:px-[22px]">
                        <CardHeading
                            aside={
                                total > 0 && (
                                    <Link
                                        to="/admin/queue"
                                        data-testid={IDS.seeAll}
                                        className={`inline-flex items-center gap-1 hover:text-primary ${FOCUS}`}
                                    >
                                        See all {total}
                                        <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
                                    </Link>
                                )
                            }
                        >
                            Action queue · oldest first
                        </CardHeading>
                    </div>
                    <DataTable
                        columns={columns}
                        rows={shown}
                        rowTestId={(r) => IDS.row(r.id)}
                        loading={!state}
                        minWidth="min-w-[34rem]"
                        maxHeight="max-h-none"
                        testid={IDS.table}
                        rowClass={(r) => (r.urgent ? "bg-state-due-wash/60" : "")}
                        empty={
                            <p className="px-5 pb-5 text-body text-muted-foreground md:px-[22px]">
                                Nothing is waiting on a person. New briefs, profiles, payouts and questions
                                land here as they arrive.
                            </p>
                        }
                    />
                </AppCard>

                <div className="space-y-4">
                    {state ? (
                        <Lately
                            dashboard={state.dashboard}
                            intelligence={state.intelligence}
                            allAccess={allAccess}
                        />
                    ) : (
                        <Skeleton className="h-[17rem] rounded-lg" />
                    )}
                    <AiSummaryCard
                        testid={IDS.ai}
                        title={state?.summary ? `What stood out · ${state.summary.campaign.title}` : undefined}
                        text={state?.summary?.headline}
                    />
                </div>
            </div>
        </section>
    );
}
