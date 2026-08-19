// The landing tab: the numbers, the campaigns behind them, and one campaign's
// applicants when you click through.
//
// Everything on this screen comes from a single /admin/dashboard call. The
// stat cards are not decoration — each one is the filter that produced it, so
// clicking "pending review" shows you exactly the campaigns that number counts.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    ArrowLeft,
    CalendarClock,
    CheckCircle2,
    IndianRupee,
    Sparkles,
    Users,
    Wallet,
    X,
    XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
    ADMIN_CAMPAIGN_DETAIL as DETAIL_IDS,
    ADMIN_OVERVIEW as IDS,
    STICKY_BAR,
} from "@/constants/testIds";
import { FilterChips, ListEmptyState, StickyBar } from "@/components/data/DenseView";
import { ConfirmDialog } from "./dialogs";
import DataTable, { sortRows } from "./console/DataTable";
import StatusTag from "./console/StatusTag";
import { CALM, FOCUS } from "./console/tokens";
import {
    CAMPAIGN_STATUS_META,
    CreatorAvatar,
    DateFilter,
    FilterSelect,
    ListSkeleton,
    SectionHeader,
    endOfDay,
    formatCompact,
    formatDate,
    formatRupees,
} from "./shared";

// Each card names the filter it stands for, so clicking it can just apply that
// filter rather than needing a lookup table somewhere else.
const STAT_CARDS = [
    { key: "live", label: "Live", Icon: Sparkles, filter: { status: "open" } },
    { key: "upcoming", label: "Upcoming", Icon: CalendarClock, filter: { status: "upcoming" } },
    {
        key: "pending_review",
        label: "Pending review",
        Icon: CheckCircle2,
        filter: { status: "pending_review" },
    },
    { key: "active_creators", label: "Active creators", Icon: Users, source: "totals" },
    { key: "gmv", label: "GMV", Icon: IndianRupee, source: "totals", money: true },
    {
        key: "total_paid_out",
        label: "Paid to creators",
        Icon: Wallet,
        source: "totals",
        money: true,
    },
];

const TYPE_OPTIONS = [
    { value: "launch", label: "Launch" },
    { value: "group_event", label: "Group event" },
    { value: "personal_table", label: "Personal table" },
];

const STATUS_OPTIONS = Object.entries(CAMPAIGN_STATUS_META).map(([value, m]) => ({
    value,
    label: m.label,
}));

/** Whichever date the campaign's type actually carries. */
const campaignWhen = (c) => {
    if (c.campaign_type === "personal_table") {
        return c.start_date ? `${formatDate(c.start_date)} – ${formatDate(c.end_date)}` : "—";
    }
    return c.event_date ? formatDate(c.event_date) : "—";
};

export default function Overview({ onChanged }) {
    const [data, setData] = useState(null);
    const [openCampaign, setOpenCampaign] = useState(null);

    // Filters. `statCard` records which card is lit so it can be un-lit.
    const [statCard, setStatCard] = useState("");
    const [brand, setBrand] = useState("");
    const [status, setStatus] = useState("");
    const [type, setType] = useState("");
    const [from, setFrom] = useState(null);
    const [to, setTo] = useState(null);
    // Newest first: the overview is read to see what has happened lately.
    const [sort, setSort] = useState({ key: "created", dir: "desc" });
    const [focused, setFocused] = useState(-1);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: d } = await api.get("/admin/dashboard", {
                params: { limit: 200 },
            });
            setData(d);
        } catch (e) {
            notifyError(e);
            setData({ campaigns: {}, awaiting: {}, totals: {}, campaign_summary: [] });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const refresh = useCallback(async () => {
        await load();
        onChanged?.();
    }, [load, onChanged]);

    const brandOptions = useMemo(() => {
        const seen = new Map();
        for (const c of data?.campaign_summary || []) {
            if (c.brand_id && c.brand_name && !seen.has(c.brand_id)) {
                seen.set(c.brand_id, c.brand_name);
            }
        }
        return [...seen].map(([value, label]) => ({ value, label }));
    }, [data]);

    const rows = useMemo(() => {
        let list = [...(data?.campaign_summary || [])];
        if (brand) list = list.filter((c) => c.brand_id === brand);
        if (status) list = list.filter((c) => c.status === status);
        if (type) list = list.filter((c) => c.campaign_type === type);
        if (from) {
            const t = from.getTime();
            list = list.filter((c) => new Date(c.created_at).getTime() >= t);
        }
        if (to) {
            const t = endOfDay(to).getTime();
            list = list.filter((c) => new Date(c.created_at).getTime() <= t);
        }
        return list;
    }, [data, brand, status, type, from, to]);

    /**
     * The columns.
     *
     * The three counts are the reason this table exists — how many applied,
     * how many got on, how many did not — so they are numeric columns you can
     * sort and compare down, which is what the four sort chips above the list
     * were trying to be.
     */
    const columns = useMemo(
        () => [
            {
                key: "title",
                header: "Campaign",
                sortable: true,
                testid: IDS.sort("title"),
                value: (c) => (c.title || "").toLowerCase(),
                cell: (c) => (
                    <Link
                        to={`/admin/campaigns/${c.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className={`truncate ${CALM} hover:text-ember-500 ${FOCUS}`}
                    >
                        {c.title}
                    </Link>
                ),
            },
            {
                key: "brand_name",
                header: "Brand",
                sortable: true,
                hideBelow: true,
                width: "w-44",
                cell: (c) => (
                    <span className="truncate text-muted-foreground">
                        {c.brand_name || "Unknown brand"}
                    </span>
                ),
            },
            {
                key: "status",
                header: "Status",
                sortable: true,
                width: "w-36",
                cell: (c) => (
                    <StatusTag state={c.status} label={CAMPAIGN_STATUS_META[c.status]?.label} />
                ),
            },
            {
                key: "when",
                header: "When",
                hideBelow: true,
                width: "w-44",
                cell: (c) => (
                    <span className="whitespace-nowrap text-muted-foreground">
                        {campaignWhen(c)}
                    </span>
                ),
            },
            {
                key: "applied",
                header: "Applied",
                sortable: true,
                numeric: true,
                width: "w-24",
                testid: IDS.sort("applied"),
                value: (c) => c.applied ?? 0,
                cell: (c) => <span data-testid={IDS.rowApplied(c.id)}>{c.applied ?? 0}</span>,
            },
            {
                key: "approved",
                header: "Approved",
                sortable: true,
                numeric: true,
                width: "w-28",
                testid: IDS.sort("approved"),
                value: (c) => c.approved ?? 0,
                cell: (c) => (
                    <span data-testid={IDS.rowApproved(c.id)} className="text-emerald-300">
                        {c.approved ?? 0}
                    </span>
                ),
            },
            {
                key: "rejected",
                header: "Rejected",
                sortable: true,
                numeric: true,
                width: "w-28",
                value: (c) => c.rejected ?? 0,
                cell: (c) => (
                    <span data-testid={IDS.rowRejected(c.id)} className="text-rose-300">
                        {c.rejected ?? 0}
                    </span>
                ),
            },
            {
                key: "created",
                header: "Created",
                sortable: true,
                numeric: true,
                width: "w-28",
                hideBelow: true,
                testid: IDS.sort("created"),
                value: (c) => new Date(c.created_at || 0).getTime() || null,
                cell: (c) => (
                    <span className="whitespace-nowrap text-muted-foreground">
                        {formatDate(c.created_at)}
                    </span>
                ),
            },
        ],
        [],
    );

    const sorted = useMemo(() => sortRows(rows, columns, sort), [rows, columns, sort]);

    const filtered = Boolean(brand || status || type || from || to);

    const clearFilters = () => {
        setStatCard("");
        setBrand("");
        setStatus("");
        setType("");
        setFrom(null);
        setTo(null);
    };

    const chips = [
        { key: "brand", label: "Brand", value: brand ? (brandOptions.find((o) => o.value === brand) || {}).label || brand : "", onRemove: () => setBrand("") },
        { key: "status", label: "Status", value: status ? (STATUS_OPTIONS.find((o) => o.value === status) || {}).label || status : "", onRemove: () => { setStatus(""); setStatCard(""); } },
        { key: "type", label: "Type", value: type ? (TYPE_OPTIONS.find((o) => o.value === type) || {}).label || type : "", onRemove: () => setType("") },
        { key: "from", label: "From", value: from ? formatDate(from.toISOString()) : "", onRemove: () => setFrom(null) },
        { key: "to", label: "To", value: to ? formatDate(to.toISOString()) : "", onRemove: () => setTo(null) },
    ];

    const applyCard = (card) => {
        if (statCard === card.key) {
            clearFilters();
            return;
        }
        // A totals card has no campaign filter to apply — it lights up and
        // leaves the table alone rather than pretending to filter.
        setStatCard(card.key);
        if (card.filter) {
            setStatus(card.filter.status || "");
            setBrand("");
            setType("");
            setFrom(null);
            setTo(null);
        }
    };

    if (openCampaign) {
        return (
            <CampaignDetail
                campaignId={openCampaign}
                onBack={() => setOpenCampaign(null)}
                onChanged={refresh}
            />
        );
    }

    return (
        <section data-testid={IDS.section}>
            <SectionHeader
                kicker="Overview"
                title="The marketplace, from the inside"
                blurb="Every number here is a filter. Tap one to see the campaigns behind it."
                onRefresh={load}
                refreshTestId={IDS.refresh}
            />

            {/* Stat cards */}
            {!data ? (
                <div
                    data-testid={IDS.statsSkeleton}
                    className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-6"
                >
                    {STAT_CARDS.map((c) => (
                        <div
                            key={c.key}
                            className="rounded-md border border-white/10 bg-card p-5"
                        >
                            <Skeleton className="h-3 w-16" />
                            <Skeleton className="mt-4 h-7 w-20" />
                        </div>
                    ))}
                </div>
            ) : (
                <div
                    data-testid={IDS.stats}
                    className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-6"
                >
                    {STAT_CARDS.map((card) => {
                        const value =
                            card.source === "totals"
                                ? data.totals?.[card.key]
                                : data.campaigns?.[card.key];
                        const on = statCard === card.key;
                        return (
                            <button
                                key={card.key}
                                type="button"
                                aria-pressed={on}
                                onClick={() => applyCard(card)}
                                data-testid={IDS.stat(card.key)}
                                className={
                                    "rounded-md border p-5 text-left transition-colors duration-150 " +
                                    (on
                                        ? "border-ember-500 bg-ember-500/10"
                                        : "border-white/10 bg-card hover:border-ember-500/40")
                                }
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                        {card.label}
                                    </p>
                                    <card.Icon
                                        className={
                                            "h-3.5 w-3.5 flex-none " +
                                            (on ? "text-ember-500" : "text-muted-foreground")
                                        }
                                    />
                                </div>
                                <p
                                    className={
                                        "mt-3 flex items-baseline font-serif text-2xl leading-none " +
                                        (on ? "text-ember-500" : "")
                                    }
                                >
                                    {card.money && <IndianRupee className="h-4 w-4" />}
                                    {card.money
                                        ? formatCompact(Math.round(value ?? 0))
                                        : (value ?? 0)}
                                </p>
                            </button>
                        );
                    })}
                </div>
            )}

            {/* Filters, and the sort row that doubles as the table header:
                both stay on screen, because the column you sorted by is the
                thing you most need labelled forty rows down. */}
            <StickyBar level="headerFromMd" testid={STICKY_BAR.adminSection} className="mt-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                <FilterSelect
                    label="Any brand"
                    value={brand}
                    onChange={setBrand}
                    options={brandOptions}
                    testid={IDS.filterBrand}
                />
                <FilterSelect
                    label="Any status"
                    value={status}
                    onChange={(v) => {
                        setStatus(v);
                        setStatCard("");
                    }}
                    options={STATUS_OPTIONS}
                    testid={IDS.filterStatus}
                />
                <FilterSelect
                    label="Any type"
                    value={type}
                    onChange={setType}
                    options={TYPE_OPTIONS}
                    testid={IDS.filterType}
                />
                <DateFilter label="From" value={from} onChange={setFrom} testid={IDS.filterDateFrom} />
                <DateFilter label="To" value={to} onChange={setTo} testid={IDS.filterDateTo} />
                {filtered && (
                    <button
                        type="button"
                        onClick={clearFilters}
                        data-testid={IDS.filterClear}
                        className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-150 hover:text-ember-500"
                    >
                        <X className="h-3.5 w-3.5" />
                        Clear
                    </button>
                )}
            </div>

            <FilterChips chips={chips} onClearAll={clearFilters} className="mt-3" />

            </StickyBar>

            <DataTable
                columns={columns}
                rows={sorted}
                rowKey={(c) => c.id}
                rowTestId={(c) => IDS.row(c.id)}
                sort={sort}
                onSortChange={setSort}
                focused={focused}
                onFocus={setFocused}
                onOpen={(i) => sorted[i] && setOpenCampaign(sorted[i].id)}
                loading={!data}
                testid={IDS.table}
                empty={
                    <ListEmptyState
                        Icon={Sparkles}
                        testid={IDS.empty}
                        filtered={filtered}
                        onClearFilters={clearFilters}
                        emptyTitle="No campaigns yet."
                        emptyBody="Every brief a brand drafts appears here, from draft through to closed, with its applicant counts."
                        filteredTitle="No campaign matches those filters."
                        filteredBody="Widen the brand, status, type or date range."
                    />
                }
            />

            {data && rows.length > 0 && (
                <p
                    data-testid={IDS.count}
                    className="mt-4 text-xs uppercase tracking-[0.18em] text-muted-foreground"
                >
                    {rows.length} of {data.campaign_summary.length} campaigns
                    {data.summary_truncated ? " · list capped at 200" : ""}
                </p>
            )}
        </section>
    );
}

// ---------------------------------------------------------------------------
// One campaign's applicants, in three columns
// ---------------------------------------------------------------------------

const COLUMNS = [
    { key: "applied", label: "Applied", empty: "Nobody has applied yet." },
    { key: "approved", label: "Approved", empty: "Nobody taken on yet." },
    { key: "rejected", label: "Rejected", empty: "Nobody turned away." },
];

function CampaignDetail({ campaignId, onBack, onChanged }) {
    const [data, setData] = useState(null);
    const [busyId, setBusyId] = useState(null);
    const [confirm, setConfirm] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: d } = await api.get(`/admin/campaigns/${campaignId}/applicants`);
            setData(d);
        } catch (e) {
            notifyError(e);
            onBack();
        }
    }, [campaignId, onBack]);

    useEffect(() => {
        load();
    }, [load]);

    const run = async (entry, request, message) => {
        setBusyId(entry.collaboration_id);
        try {
            await request();
            notifySuccess(message);
            setConfirm(null);
            await load();
            onChanged?.();
        } catch (e) {
            notifyError(e);
        } finally {
            setBusyId(null);
            setSubmitting(false);
        }
    };

    const advance = (entry) =>
        run(
            entry,
            () =>
                api.post(`/admin/collaborations/${entry.collaboration_id}/advance`, {
                    from_state: entry.state,
                }),
            "Moved forward",
        );

    const decline = (entry) =>
        setConfirm({
            kicker: "Decline applicant",
            title: `Turn down ${entry.name || "this creator"}?`,
            description: "They're told why. Nothing was agreed, so nothing is owed.",
            confirmLabel: "Decline",
            onSubmit: (body) => {
                setSubmitting(true);
                run(
                    entry,
                    () =>
                        api.post(`/admin/collaborations/${entry.collaboration_id}/decline`, body),
                    "Application declined",
                );
            },
        });

    const cancel = (entry) =>
        setConfirm({
            kicker: "Cancel collaboration",
            title: `Cancel ${entry.name || "this creator"}'s collaboration?`,
            description:
                "The creator is told and any pending payout is voided. If they were already paid, refund it instead.",
            confirmLabel: "Cancel collaboration",
            onSubmit: (body) => {
                setSubmitting(true);
                run(
                    entry,
                    () =>
                        api.post(`/admin/collaborations/${entry.collaboration_id}/cancel`, body),
                    "Collaboration cancelled",
                );
            },
        });

    return (
        <section data-testid={DETAIL_IDS.panel}>
            <button
                type="button"
                onClick={onBack}
                data-testid={DETAIL_IDS.back}
                className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-150 hover:text-ember-500"
            >
                <ArrowLeft className="h-3.5 w-3.5" />
                All campaigns
            </button>

            {!data ? (
                <div data-testid={DETAIL_IDS.skeleton} className="mt-6 space-y-6">
                    <Skeleton className="h-8 w-2/3" />
                    <div className="grid gap-4 lg:grid-cols-3">
                        {COLUMNS.map((c) => (
                            <div key={c.key} className="rounded-md border border-white/10 bg-card">
                                <ListSkeleton rows={3} />
                            </div>
                        ))}
                    </div>
                </div>
            ) : (
                <>
                    <div className="mt-6">
                        <div className="flex flex-wrap items-center gap-2">
                            <StatusTag
                                state={data.campaign.status}
                                label={CAMPAIGN_STATUS_META[data.campaign.status]?.label}
                                chip
                            />
                            <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                                {(data.campaign.campaign_type || "").replace(/_/g, " ")} ·{" "}
                                {campaignWhen(data.campaign)}
                            </span>
                        </div>
                        <h2
                            data-testid={DETAIL_IDS.title}
                            className="mt-3 font-serif text-fluid-4xl leading-none tracking-tight"
                        >
                            {data.campaign.title}
                        </h2>
                        <p className="mt-3 text-sm text-muted-foreground">
                            {data.campaign.brand_name} · ₹
                            {formatRupees(data.campaign.budget_per_creator)} per creator ·{" "}
                            {data.campaign.filled_slots}/{data.campaign.creators_needed} filled
                        </p>
                    </div>

                    <div className="mt-8 grid gap-4 lg:grid-cols-3">
                        {COLUMNS.map((col) => {
                            const entries = data[col.key] || [];
                            return (
                                <div
                                    key={col.key}
                                    data-testid={DETAIL_IDS.column(col.key)}
                                    className="rounded-md border border-white/10 bg-card"
                                >
                                    <div className="flex items-baseline justify-between border-b border-white/10 px-5 py-4">
                                        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            {col.label}
                                        </p>
                                        <span
                                            data-testid={DETAIL_IDS.columnCount(col.key)}
                                            className="font-serif text-lg leading-none"
                                        >
                                            {entries.length}
                                        </span>
                                    </div>

                                    {entries.length === 0 ? (
                                        <p
                                            data-testid={DETAIL_IDS.columnEmpty(col.key)}
                                            className="px-5 py-8 text-center text-sm text-muted-foreground"
                                        >
                                            {col.empty}
                                        </p>
                                    ) : (
                                        <ul className="divide-y divide-white/10">
                                            {entries.map((e) => (
                                                <ApplicantRow
                                                    key={e.collaboration_id}
                                                    entry={e}
                                                    column={col.key}
                                                    busy={busyId === e.collaboration_id}
                                                    onAdvance={advance}
                                                    onDecline={decline}
                                                    onCancel={cancel}
                                                />
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </>
            )}

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                destructive
                kicker={confirm?.kicker}
                title={confirm?.title || ""}
                description={confirm?.description}
                confirmLabel={confirm?.confirmLabel}
                placeholder="What should they know?"
                onSubmit={(body) => confirm?.onSubmit(body)}
            />
        </section>
    );
}

function ApplicantRow({ entry, column, busy, onAdvance, onDecline, onCancel }) {
    // Only offer the move that is actually ours; the brand owns accepting and
    // approving content, and the server refuses those from here.
    const adminCanMove = ["applied", "commercial_agreed", "slot_booked", "content_approved"]
        .includes(entry.state);

    return (
        <li
            data-testid={DETAIL_IDS.creator(entry.collaboration_id)}
            className="px-5 py-4"
        >
            <div className="flex items-start gap-3">
                <CreatorAvatar creator={entry} size="h-10 w-10" />
                <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{entry.name || "Unnamed"}</p>
                    <p className="truncate text-sm text-muted-foreground">
                        {entry.instagram_handle ? `@${entry.instagram_handle}` : "No handle"}
                        {typeof entry.follower_count === "number"
                            ? ` · ${formatCompact(entry.follower_count)}`
                            : ""}
                    </p>
                </div>
                <StatusTag state={entry.state} />
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                <span className="inline-flex items-baseline">
                    Quoted
                    <IndianRupee className="ml-1.5 h-3 w-3" />
                    {formatRupees(entry.quoted_rate)}
                </span>
                <span className="inline-flex items-baseline">
                    Agreed
                    <IndianRupee className="ml-1.5 h-3 w-3" />
                    {entry.agreed_amount != null ? formatRupees(entry.agreed_amount) : "—"}
                </span>
            </div>

            {entry.exit_reason && (
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {entry.exit_reason}
                </p>
            )}

            {column !== "rejected" && (
                <div className="mt-3 flex flex-wrap gap-2">
                    {adminCanMove && (
                        <Button
                            type="button"
                            disabled={busy}
                            onClick={() => onAdvance(entry)}
                            data-testid={DETAIL_IDS.creatorAdvance(entry.collaboration_id)}
                            className="h-9 rounded-full bg-ember-500 px-3 text-sm text-black hover:bg-ember-400"
                        >
                            Move forward
                        </Button>
                    )}
                    {column === "applied" ? (
                        <Button
                            type="button"
                            variant="outline"
                            disabled={busy}
                            onClick={() => onDecline(entry)}
                            data-testid={DETAIL_IDS.creatorDecline(entry.collaboration_id)}
                            className="h-9 rounded-full border-red-500/30 bg-transparent px-3 text-sm text-red-300 hover:bg-red-500/10"
                        >
                            <XCircle className="mr-1.5 h-3.5 w-3.5" />
                            Decline
                        </Button>
                    ) : (
                        <Button
                            type="button"
                            variant="outline"
                            disabled={busy}
                            onClick={() => onCancel(entry)}
                            data-testid={DETAIL_IDS.creatorCancel(entry.collaboration_id)}
                            className="h-9 rounded-full border-red-500/30 bg-transparent px-3 text-sm text-red-300 hover:bg-red-500/10"
                        >
                            <XCircle className="mr-1.5 h-3.5 w-3.5" />
                            Cancel
                        </Button>
                    )}
                </div>
            )}
        </li>
    );
}
