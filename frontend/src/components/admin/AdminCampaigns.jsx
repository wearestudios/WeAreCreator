// Every brief in every state, with the decision the state allows: approve or
// send back while it's in review, pause/resume/close/edit while it's live.
//
// **The row was the workbench and is now the index.** Six buttons in a row of
// ten is sixty controls on a screen, which is how a list stops being readable
// as a list — so the row keeps the one decision its state is waiting on, and
// the peek panel carries the rest plus who is on the brief. The chevron still
// opens that panel, because that is what it always meant.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
    BadgeCheck,
    ChevronDown,
    Pause,
    Pencil,
    Play,
    Search,
    Send,
    Sparkles,
    Star,
    X,
    XCircle,
} from "lucide-react";

import { notifyError, notifySuccess } from "@/lib/feedback";
import { api } from "@/lib/api";
import { compensationLabel, isBarter } from "@/lib/compensation";
import { EXECUTION_FILTERS } from "@/lib/execution";
import ExecutionBadge from "@/components/ExecutionBadge";
import { EXECUTION_META, executionOwner } from "@/lib/execution";
import { Input } from "@/components/ui/input";
import {
    ADMIN_CAMPAIGNS as IDS,
    ADMIN_PEEK,
    ADMIN_TABLE as TABLE_IDS,
    EXECUTION,
    PERFORMANCE as PERF_IDS,
} from "@/constants/testIds";
import { FilterChips, ListEmptyState } from "@/components/data/DenseView";

import InviteCreatorsDialog from "./InviteCreatorsDialog";
import { CampaignEditDialog, ConfirmDialog } from "./dialogs";
import DataTable, { sortRows } from "./console/DataTable";
import PeekPanel, { PeekField } from "./console/PeekPanel";
import SaveFilter from "./console/SaveFilter";
import { PeekButton, RowButton } from "./console/RowActions";
import StatusTag from "./console/StatusTag";
import { TimeAgo, rupees } from "./console/format";
import { CALM, DENSITY, FOCUS, PANEL, TEXT } from "./console/tokens";
import useListState from "./console/useListState";
import useTableKeys from "./console/useTableKeys";
import {
    CAMPAIGN_STATUS_META,
    DateFilter,
    FilterSelect,
    INVITABLE_STATUSES,
    endOfDay,
    formatDate,
    formatRupees,
} from "./shared";

const PAGE_SIZE = 50;

const STATUS_OPTIONS = Object.entries(CAMPAIGN_STATUS_META).map(([value, m]) => ({
    value,
    label: m.label,
}));

const LIVE_STATUSES = ["upcoming", "open", "in_progress"];

const DEFAULTS = {
    q: "",
    status: "",
    // "" = every campaign, "1" = only the ones we would show a prospect.
    showcase: "",
    execution: "",
    from: null,
    to: null,
    page: 1,
    sort: { key: "created_at", dir: "desc" },
};

const asDate = (v) => (v ? new Date(v) : null);

/** What a brief is worth, said honestly: barter never renders as a figure. */
const money = (c) => (isBarter(c) ? "Barter" : rupees(c.budget_per_creator));

export default function AdminCampaigns({ brandFilter, onClearBrand, onChanged }) {
    const [data, setData] = useState(null);
    const [busyId, setBusyId] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [confirm, setConfirm] = useState(null);
    const [editFor, setEditFor] = useState(null);
    const [inviteFor, setInviteFor] = useState(null);
    const [focused, setFocused] = useState(-1);
    const [peekId, setPeekId] = useState(null);
    const { state, patch, reset, scrollRef, saved, save, apply } = useListState(
        "campaigns",
        DEFAULTS,
    );
    const { q, status, showcase, execution, from, to, page, sort } = state;
    const [typed, setTyped] = useState(q);
    const location = useLocation();

    useEffect(() => {
        if (location.state?.savedFilter) apply(location.state.savedFilter);
    }, [location.state, apply]);

    useEffect(() => {
        const t = setTimeout(() => {
            if (typed.trim() !== q) patch({ q: typed.trim(), page: 1 });
        }, 300);
        return () => clearTimeout(t);
    }, [typed, q, patch]);

    // Arriving from the Brands section resets to their first page — but only
    // when the brand actually changes. Running it on mount too would undo the
    // page the session remembered, which is the one thing coming back from a
    // detail page is supposed to preserve.
    const lastBrand = useRef(brandFilter);
    useEffect(() => {
        if (lastBrand.current === brandFilter) return;
        lastBrand.current = brandFilter;
        patch({ page: 1 });
    }, [brandFilter, patch]);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: d } = await api.get("/admin/campaigns", {
                params: {
                    page,
                    page_size: PAGE_SIZE,
                    ...(q ? { q } : {}),
                    ...(status ? { status } : {}),
                    ...(showcase ? { showcase: true } : {}),
                    ...(execution ? { execution_owner: execution } : {}),
                    ...(brandFilter ? { brand_id: brandFilter } : {}),
                    ...(from ? { date_from: new Date(from).toISOString() } : {}),
                    ...(to ? { date_to: endOfDay(new Date(to)).toISOString() } : {}),
                },
            });
            setData(d);
        } catch (e) {
            notifyError(e);
            setData({ campaigns: [], total: 0, pages: 0 });
        }
    }, [page, q, status, showcase, execution, brandFilter, from, to]);

    useEffect(() => {
        load();
    }, [load]);

    const run = useCallback(
        async (id, fn, msg) => {
            setBusyId(id);
            setSubmitting(true);
            try {
                await fn();
                notifySuccess(msg);
                setConfirm(null);
                setEditFor(null);
                await load();
                onChanged?.();
            } catch (e) {
                notifyError(e);
                // A 409 means somebody else moved it; the list is now wrong.
                if (e?.response?.status === 409) await load();
            } finally {
                setBusyId(null);
                setSubmitting(false);
            }
        },
        [load, onChanged],
    );

    // One table of what can be done to a brief, so the row, the panel and the
    // keyboard cannot offer three different sets.
    const actions = useMemo(
        () => ({
            approve: (c) =>
                run(
                    c.id,
                    () => api.post(`/admin/campaigns/${c.id}/approve`),
                    "Campaign approved — it's live",
                ),
            resume: (c) =>
                run(c.id, () => api.post(`/admin/campaigns/${c.id}/resume`, {}), "Campaign resumed"),
            invite: (c) => setInviteFor(c),
            edit: (c) => setEditFor(c),
            reject: (c) =>
                setConfirm({
                    campaign: c,
                    kicker: "Send back",
                    title: `Send “${c.title}” back?`,
                    description:
                        "It returns to the brand as a draft with your reason attached, so they can fix it and resubmit.",
                    confirmLabel: "Send back",
                    request: (body) => api.post(`/admin/campaigns/${c.id}/reject`, body),
                    success: "Sent back to the brand",
                }),
            pause: (c) =>
                setConfirm({
                    campaign: c,
                    kicker: "Pause campaign",
                    title: `Pause “${c.title}”?`,
                    description:
                        "It comes off the creator feed and stops taking applications. Work already under way carries on. Resume puts it back.",
                    confirmLabel: "Pause campaign",
                    request: (body) => api.post(`/admin/campaigns/${c.id}/pause`, body),
                    success: "Campaign paused",
                }),
            close: (c) =>
                setConfirm({
                    campaign: c,
                    kicker: "Close campaign",
                    title: `Close “${c.title}” for good?`,
                    description:
                        "Applications still waiting are declined with your reason; collaborations under way are untouched. This can't be reopened.",
                    confirmLabel: "Close campaign",
                    request: (body) => api.post(`/admin/campaigns/${c.id}/close`, body),
                    success: "Campaign closed",
                }),
            refund: (row, campaign) =>
                setConfirm({
                    campaign,
                    kicker: "Refund payout",
                    title: `Refund ₹${formatRupees(row.creator_payout)} from ${row.name || "this creator"}?`,
                    description:
                        "Records that the money came back — it doesn't move it. The collaboration is cancelled with it, and if the brand already settled, the amount is flagged as owed back to them.",
                    confirmLabel: "Record refund",
                    extra: {
                        name: "refund_reference",
                        label: "Refund reference (optional)",
                        placeholder: "UTR or transaction id",
                    },
                    request: (body) => api.post(`/admin/payments/${row.payment_id}/refund`, body),
                    success: "Refund recorded — collaboration cancelled",
                }),
        }),
        [run],
    );

    const columns = useMemo(
        () => [
            {
                key: "title",
                mobile: "primary",
                header: "Brief",
                sortable: true,
                value: (c) => c.title || "",
                cell: (c) => (
                    <span className="flex min-w-0 items-center gap-1.5">
                        {/* Kept as its own control: the chevron says "look
                            inside", the title says "go there". One row, two
                            different intentions. */}
                        {/* The table's "look inside" affordance. Hidden on a
                            phone, where the whole row is the tap target and a
                            disclosure caret next to every title is chrome
                            pretending to be a control. */}
                        <ChevronDown
                            data-testid={IDS.expand(c.id)}
                            aria-hidden
                            className="hidden h-3.5 w-3.5 shrink-0 text-muted-foreground/60 md:block"
                        />
                        <Link
                            to={`/admin/campaigns/${c.id}`}
                            onClick={(e) => e.stopPropagation()}
                            data-testid={IDS.open(c.id)}
                            className={`truncate ${CALM} hover:text-ember-500 ${FOCUS}`}
                        >
                            {c.title}
                        </Link>
                        {c.showcase && (
                            <Star
                                data-testid={PERF_IDS.showcaseBadge(c.id)}
                                title={c.showcase_note || "Marked as a showcase campaign"}
                                className="h-3 w-3 shrink-0 fill-current text-ember-500"
                            />
                        )}
                    </span>
                ),
            },
            {
                key: "brand_name",
                mobile: "meta",
                header: "Brand",
                sortable: true,
                hideBelow: true,
                width: "w-44",
                cell: (c) => (
                    <span className="block truncate text-muted-foreground">
                        {c.brand_name || "Unknown brand"}
                    </span>
                ),
            },
            {
                key: "status",
                mobile: "meta",
                header: "Status",
                sortable: true,
                width: "w-36",
                cell: (c) => (
                    <StatusTag
                        state={c.status}
                        label={CAMPAIGN_STATUS_META[c.status]?.label}
                    />
                ),
            },
            {
                key: "execution_owner",
                header: "Run by",
                sortable: true,
                hideBelow: true,
                width: "w-28",
                value: (c) => executionOwner(c),
                // **The same word as `ExecutionBadge`, without the pill.** The
                // shared chip is a rounded, padded, uppercase-tracked badge
                // built for a card — in a 44px row it wrapped to two lines and
                // took the row to 93px, and its ember fill made a fact look
                // like the primary action. The label comes from the same
                // `EXECUTION_META` the badge reads, so the vocabulary is still
                // one vocabulary; only the chrome is a table's.
                cell: (c) => (
                    <span className="whitespace-nowrap text-muted-foreground">
                        {EXECUTION_META[executionOwner(c)].label}
                    </span>
                ),
            },
            {
                key: "filled",
                mobile: "meta",
                header: "Filled",
                sortable: true,
                numeric: true,
                width: "w-24",
                // Sorted on how full it is, not on the raw count: "which brief
                // is closest to short" is the question, and 2/2 is finished
                // where 2/12 is a problem.
                value: (c) =>
                    c.creators_needed ? (c.filled_slots || 0) / c.creators_needed : null,
                cell: (c) => `${c.filled_slots}/${c.creators_needed}`,
            },
            {
                key: "budget_per_creator",
                mobile: "trailing",
                header: "Per creator",
                sortable: true,
                numeric: true,
                width: "w-32",
                value: (c) => (isBarter(c) ? null : c.budget_per_creator ?? null),
                cell: (c) => (
                    <span title={compensationLabel(c)}>{money(c)}</span>
                ),
            },
            {
                key: "created_at",
                header: "Age",
                sortable: true,
                numeric: true,
                width: "w-28",
                hideBelow: true,
                // In review, the number that matters is how long they have been
                // waiting on us, not how long ago they wrote it.
                value: (c) =>
                    new Date(
                        (c.status === "pending_review" && c.submitted_for_review_at) ||
                            c.created_at ||
                            0,
                    ).getTime() || null,
                cell: (c) => (
                    <TimeAgo
                        iso={
                            (c.status === "pending_review" && c.submitted_for_review_at) ||
                            c.created_at
                        }
                    />
                ),
            },
            {
                key: "decision",
                mobile: "action",
                header: "",
                // Wide enough for the widest pair, measured: "Send back" and
                // "Approve" side by side clipped to "end back" at w-36.
                width: "w-52",
                cell: (c) => (
                    <span className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                        {c.status === "pending_review" ? (
                            <>
                                <RowButton
                                    tone="bad"
                                    disabled={busyId === c.id}
                                    onClick={() => actions.reject(c)}
                                    testid={IDS.reject(c.id)}
                                >
                                    Send back
                                </RowButton>
                                <RowButton
                                    tone="primary"
                                    disabled={busyId === c.id}
                                    onClick={() => actions.approve(c)}
                                    testid={IDS.approve(c.id)}
                                >
                                    Approve
                                </RowButton>
                            </>
                        ) : c.status === "paused" ? (
                            <RowButton
                                tone="primary"
                                disabled={busyId === c.id}
                                onClick={() => actions.resume(c)}
                                testid={IDS.resume(c.id)}
                            >
                                Resume
                            </RowButton>
                        ) : LIVE_STATUSES.includes(c.status) ? (
                            <RowButton
                                disabled={busyId === c.id}
                                onClick={() => actions.pause(c)}
                                testid={IDS.pause(c.id)}
                            >
                                Pause
                            </RowButton>
                        ) : null}
                    </span>
                ),
            },
        ],
        [actions, busyId],
    );

    const raw = useMemo(() => data?.campaigns || [], [data]);
    const rows = useMemo(() => sortRows(raw, columns, sort), [raw, columns, sort]);
    const peek = useMemo(() => rows.find((c) => c.id === peekId) || null, [rows, peekId]);

    const openPeek = useCallback(
        (i) => {
            setFocused(i);
            setPeekId(rows[i]?.id ?? null);
        },
        [rows],
    );

    useTableKeys({
        count: rows.length,
        focused,
        setFocused,
        onOpen: openPeek,
        onApprove: (i) => {
            const c = rows[i];
            if (!c) return;
            if (c.status === "pending_review") actions.approve(c);
            else if (c.status === "paused") actions.resume(c);
        },
        onReject: (i) => {
            const c = rows[i];
            if (c?.status === "pending_review") actions.reject(c);
        },
        onEscape: () => (peekId ? setPeekId(null) : setFocused(-1)),
        enabled: !confirm && !editFor && !inviteFor,
    });

    const filtered = Boolean(q || status || showcase || execution || brandFilter || from || to);
    const pages = data?.pages || 0;

    const brandName = useMemo(
        () => rows.find((c) => c.brand_id === brandFilter)?.brand_name,
        [rows, brandFilter],
    );

    const clearFilters = () => {
        setTyped("");
        reset();
        onClearBrand?.();
    };

    const chips = [
        { key: "search", label: "Title", value: q, onRemove: () => { setTyped(""); patch({ q: "", page: 1 }); } },
        {
            key: "brand",
            label: "Brand",
            value: brandFilter ? brandName || "Selected brand" : "",
            onRemove: () => onClearBrand?.(),
        },
        { key: "showcase", label: "Showcase", value: showcase ? "Showcase only" : "", onRemove: () => patch({ showcase: "" }) },
        {
            key: "execution",
            label: "Run by",
            value: EXECUTION_FILTERS.find((o) => o.value === execution)?.label || "",
            onRemove: () => patch({ execution: "", page: 1 }),
        },
        { key: "status", label: "Status", value: status, onRemove: () => patch({ status: "", page: 1 }) },
        { key: "from", label: "From", value: from ? formatDate(from) : "", onRemove: () => patch({ from: null, page: 1 }) },
        { key: "to", label: "To", value: to ? formatDate(to) : "", onRemove: () => patch({ to: null, page: 1 }) },
    ];

    const canInvite = peek && INVITABLE_STATUSES.includes(peek.status);
    const peekLive = peek && LIVE_STATUSES.includes(peek.status);

    return (
        <section data-testid={IDS.section}>
            <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className={TEXT.heading}>Campaigns</h1>
                    <p data-testid={IDS.count} className={`${TEXT.meta} text-muted-foreground`}>
                        {data
                            ? data.total
                                ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, data.total)} of ${data.total}`
                                : "No campaigns"
                            : "Loading…"}
                    </p>
                </div>
                <SaveFilter onSave={save} disabled={!filtered} savedNames={saved.map((s) => s.name)} />
            </header>

            <div
                data-testid={TABLE_IDS.toolbar}
                className={`mb-3 flex flex-wrap items-center gap-2 ${PANEL} ${DENSITY.row}`}
            >
                <div className="relative min-w-[9rem] flex-1">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={typed}
                        onChange={(e) => setTyped(e.target.value)}
                        data-testid={IDS.search}
                        placeholder="Campaign title"
                        aria-label="Search campaigns"
                        className={`h-8 border-white/10 bg-transparent pl-8 ${TEXT.body}`}
                    />
                </div>
                <FilterSelect
                    dense
                    label="Any status"
                    value={status}
                    onChange={(v) => patch({ status: v, page: 1 })}
                    options={STATUS_OPTIONS}
                    testid={IDS.filterStatus}
                />
                <FilterSelect
                    dense
                    label="Run by anyone"
                    value={execution}
                    onChange={(v) => patch({ execution: v, page: 1 })}
                    options={EXECUTION_FILTERS.filter((o) => o.value !== "all")}
                    testid={EXECUTION.filter}
                />
                {/* A toggle, not a select: "showcase" has two states, and the
                    third one a select would imply ("not showcase") is not
                    something anybody goes looking for. */}
                <button
                    type="button"
                    aria-pressed={Boolean(showcase)}
                    onClick={() => patch({ showcase: showcase ? "" : "1", page: 1 })}
                    data-testid={PERF_IDS.showcaseFilter}
                    className={
                        `inline-flex h-8 flex-none items-center gap-1.5 rounded border px-2 ${TEXT.body} ${CALM} ${FOCUS} ` +
                        (showcase
                            ? "border-ember-500 bg-ember-500/10 text-ember-500"
                            : "border-white/10 text-muted-foreground hover:border-white/25")
                    }
                >
                    <Star className={"h-3.5 w-3.5 " + (showcase ? "fill-current" : "")} />
                    Showcase
                </button>
                <DateFilter
                    dense
                    label="From"
                    value={asDate(from)}
                    onChange={(d) => patch({ from: d ? d.toISOString() : null, page: 1 })}
                    testid={IDS.filterDateFrom}
                />
                <DateFilter
                    dense
                    label="To"
                    value={asDate(to)}
                    onChange={(d) => patch({ to: d ? d.toISOString() : null, page: 1 })}
                    testid={IDS.filterDateTo}
                />
                {filtered && (
                    <button
                        type="button"
                        onClick={clearFilters}
                        data-testid={IDS.filterClear}
                        className={`inline-flex items-center gap-1.5 ${TEXT.meta} ${CALM} text-muted-foreground hover:text-ember-500 ${FOCUS}`}
                    >
                        <X className="h-3.5 w-3.5" />
                        Clear
                    </button>
                )}
            </div>

            {filtered && (
                <div className="mb-3">
                    <FilterChips chips={chips} onClearAll={clearFilters} />
                </div>
            )}

            <DataTable
                columns={columns}
                rows={rows}
                rowKey={(c) => c.id}
                rowTestId={(c) => IDS.row(c.id)}
                sort={sort}
                onSortChange={(s) => patch({ sort: s })}
                focused={focused}
                onFocus={setFocused}
                onOpen={openPeek}
                loading={!data}
                scrollRef={scrollRef}
                testid={IDS.list}
                empty={
                    <ListEmptyState
                        Icon={Sparkles}
                        testid={IDS.empty}
                        filtered={filtered}
                        onClearFilters={clearFilters}
                        emptyTitle="No campaign has been posted yet."
                        emptyBody="Briefs appear here the moment a brand drafts one, in every state from draft to closed."
                        filteredTitle="No campaign matches those filters."
                        filteredBody="Widen the date range, or clear the status and brand filters."
                    />
                }
            />

            {pages > 1 && (
                <div
                    data-testid={IDS.pagination}
                    className={`mt-3 flex items-center justify-between ${TEXT.meta} text-muted-foreground`}
                >
                    <span data-testid={IDS.pageLabel}>
                        Page {page} of {pages}
                    </span>
                    <div className="flex gap-1">
                        <RowButton
                            disabled={page <= 1}
                            onClick={() => patch({ page: Math.max(1, page - 1) })}
                            testid={IDS.pagePrev}
                        >
                            Previous
                        </RowButton>
                        <RowButton
                            disabled={page >= pages}
                            onClick={() => patch({ page: Math.min(pages, page + 1) })}
                            testid={IDS.pageNext}
                        >
                            Next
                        </RowButton>
                    </div>
                </div>
            )}

            {/* The panel is where the rest of the decisions live, and where the
                applicants are — the question "who is actually on this?" is the
                one the chevron was always answering. */}
            <PeekPanel
                open={Boolean(peek)}
                onOpenChange={(o) => !o && setPeekId(null)}
                title={peek?.title || "Campaign"}
                subtitle={peek?.brand_name}
                href={peek ? `/admin/campaigns/${peek.id}` : undefined}
                actions={
                    peek ? (
                        <>
                            {(peekLive || peek.status === "paused") && (
                                <>
                                    <PeekButton
                                        onClick={() => actions.edit(peek)}
                                        testid={IDS.edit(peek.id)}
                                    >
                                        <Pencil className="h-3.5 w-3.5" />
                                        Edit
                                    </PeekButton>
                                    {peek.status === "paused" ? (
                                        <PeekButton
                                            tone="primary"
                                            onClick={() => actions.resume(peek)}
                                            testid={ADMIN_PEEK.action("resume")}
                                        >
                                            <Play className="h-3.5 w-3.5" />
                                            Resume
                                        </PeekButton>
                                    ) : (
                                        <PeekButton
                                            onClick={() => actions.pause(peek)}
                                            testid={ADMIN_PEEK.action("pause")}
                                        >
                                            <Pause className="h-3.5 w-3.5" />
                                            Pause
                                        </PeekButton>
                                    )}
                                    <PeekButton
                                        tone="bad"
                                        onClick={() => actions.close(peek)}
                                        testid={IDS.close(peek.id)}
                                    >
                                        <XCircle className="h-3.5 w-3.5" />
                                        Close
                                    </PeekButton>
                                </>
                            )}
                            {peek.status === "pending_review" && (
                                <>
                                    <PeekButton
                                        tone="bad"
                                        onClick={() => actions.reject(peek)}
                                        testid={ADMIN_PEEK.action("send-back")}
                                    >
                                        <XCircle className="h-3.5 w-3.5" />
                                        Send back
                                    </PeekButton>
                                    <PeekButton
                                        tone="primary"
                                        onClick={() => actions.approve(peek)}
                                        testid={ADMIN_PEEK.action("approve")}
                                    >
                                        <BadgeCheck className="h-3.5 w-3.5" />
                                        Approve
                                    </PeekButton>
                                </>
                            )}
                            {canInvite && (
                                <PeekButton
                                    onClick={() => actions.invite(peek)}
                                    testid={IDS.inviteOpen(peek.id)}
                                >
                                    <Send className="h-3.5 w-3.5" />
                                    Invite
                                </PeekButton>
                            )}
                        </>
                    ) : null
                }
            >
                {peek && (
                    <div>
                        <PeekField label="Status">
                            <StatusTag
                                state={peek.status}
                                label={CAMPAIGN_STATUS_META[peek.status]?.label}
                                chip
                            />
                        </PeekField>
                        <PeekField label="Run by">
                            <ExecutionBadge campaign={peek} />
                        </PeekField>
                        <PeekField label="Per creator">
                            {money(peek)} · {compensationLabel(peek)}
                        </PeekField>
                        <PeekField label="Filled">
                            {peek.filled_slots}/{peek.creators_needed}
                        </PeekField>
                        <PeekField label="Where">{peek.area}</PeekField>
                        <PeekField label="Created">
                            <TimeAgo iso={peek.created_at} />
                        </PeekField>

                        {peek.review_reason && peek.status === "draft" && (
                            <p
                                data-testid={IDS.reviewReason(peek.id)}
                                className={`mt-3 rounded border border-amber-500/25 bg-amber-500/5 p-3 ${TEXT.body} text-amber-300`}
                            >
                                Sent back: {peek.review_reason}
                            </p>
                        )}

                        <h3 className={`mb-1 mt-5 ${TEXT.meta} uppercase tracking-[0.12em] text-muted-foreground`}>
                            On this brief
                        </h3>
                        {peek.creators.length === 0 ? (
                            <p
                                data-testid={IDS.creatorsEmpty(peek.id)}
                                className={`${TEXT.body} text-muted-foreground`}
                            >
                                Nobody has applied to this brief yet.
                            </p>
                        ) : (
                            <ul data-testid={IDS.creators(peek.id)}>
                                {peek.creators.map((c) => (
                                    <li
                                        key={c.collaboration_id}
                                        data-testid={IDS.creatorRow(c.collaboration_id)}
                                        className="flex items-center justify-between gap-3 border-b border-white/5 py-2"
                                    >
                                        <span className="min-w-0">
                                            <span className={`block truncate ${TEXT.body}`}>
                                                {c.name || "Unnamed"}
                                            </span>
                                            <StatusTag state={c.state} className={TEXT.meta} />
                                        </span>
                                        <span className="flex flex-none items-center gap-2">
                                            <span className={`${TEXT.meta} tabular-nums text-muted-foreground`}>
                                                {c.agreed_amount != null
                                                    ? rupees(c.agreed_amount)
                                                    : "Not agreed"}
                                            </span>
                                            {c.payment_state === "paid" && (
                                                <RowButton
                                                    tone="bad"
                                                    onClick={() => actions.refund(c, peek)}
                                                    testid={`admin-collab-refund-${c.collaboration_id}`}
                                                >
                                                    Refund
                                                </RowButton>
                                            )}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                )}
            </PeekPanel>

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                kicker={confirm?.kicker}
                title={confirm?.title || ""}
                description={confirm?.description}
                placeholder="What should the record say?"
                confirmLabel={confirm?.confirmLabel}
                extra={confirm?.extra}
                destructive
                onSubmit={(body) =>
                    run(confirm.campaign.id, () => confirm.request(body), confirm.success)
                }
            />

            <CampaignEditDialog
                campaign={editFor}
                open={Boolean(editFor)}
                onOpenChange={(v) => !v && setEditFor(null)}
                submitting={submitting}
                onSubmit={(changes) =>
                    run(
                        editFor.id,
                        () => api.patch(`/admin/campaigns/${editFor.id}`, changes),
                        "Campaign updated",
                    )
                }
            />

            <InviteCreatorsDialog
                campaign={inviteFor}
                open={Boolean(inviteFor)}
                onOpenChange={(v) => !v && setInviteFor(null)}
                onSent={load}
            />
        </section>
    );
}
