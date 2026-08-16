// Every brief in every state, with the controls inline where the state allows
// them: approve/send-back while it's in review, pause/close/edit while it's
// live, resume while it's paused. The row is the workbench — there is no
// separate "manage" page to lose.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    BadgeCheck,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    IndianRupee,
    Pause,
    Pencil,
    Play,
    Search,
    Send,
    Sparkles,
    X,
    XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { compensationLabel, isBarter } from "@/lib/compensation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ADMIN_CAMPAIGNS as IDS, STICKY_BAR } from "@/constants/testIds";
import { FilterChips, StickyBar } from "@/components/data/DenseView";
import InviteCreatorsDialog from "./InviteCreatorsDialog";
import { CampaignEditDialog, ConfirmDialog } from "./dialogs";
import {
    CAMPAIGN_STATUS_META,
    DateFilter,
    EmptyState,
    FilterSelect,
    INVITABLE_STATUSES,
    ListSkeleton,
    Pill,
    SectionHeader,
    StatePill,
    endOfDay,
    formatDate,
    formatRupees,
    timeAgo,
} from "./shared";

const PAGE_SIZE = 10;

const STATUS_OPTIONS = Object.entries(CAMPAIGN_STATUS_META).map(([value, m]) => ({
    value,
    label: m.label,
}));

function CampaignRow({ campaign, expanded, onToggle, busy, actions }) {
    const status = campaign.status;
    const canInvite = INVITABLE_STATUSES.includes(status);
    const inReview = status === "pending_review";
    const live = ["upcoming", "open", "in_progress"].includes(status);
    const paused = status === "paused";

    return (
        <li data-testid={IDS.row(campaign.id)} className="px-5 py-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:gap-6">
                {/* Two affordances, deliberately separate: the chevron peeks
                    at the applicants inline, the title opens the campaign's
                    own page. Before this the whole row was the toggle, so
                    clicking a campaign expanded it and there was no way to get
                    to it at all. */}
                <div className="flex min-w-0 flex-1 items-start gap-3">
                    <button
                        type="button"
                        onClick={onToggle}
                        aria-expanded={expanded}
                        aria-label={expanded ? "Hide applicants" : "Show applicants"}
                        data-testid={IDS.expand(campaign.id)}
                        className="-m-2 grid h-11 w-11 flex-none place-items-center rounded-md text-muted-foreground transition-colors duration-200 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 md:h-8 md:w-8"
                    >
                        <ChevronDown
                            className={
                                "h-4 w-4 transition-transform duration-200 " +
                                (expanded ? "rotate-180" : "")
                            }
                        />
                    </button>
                    <div className="min-w-0">
                        <Link
                            to={`/admin/campaigns/${campaign.id}`}
                            data-testid={IDS.open(campaign.id)}
                            className="block truncate font-serif text-lg leading-tight transition-colors duration-200 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                        >
                            {campaign.title}
                        </Link>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                            {[
                                campaign.brand_name || "Unknown brand",
                                campaign.area,
                                // Barter shows as barter, not as the leftover
                                // figure the brief was posted with.
                                isBarter(campaign)
                                    ? "Barter"
                                    : `₹${formatRupees(campaign.budget_per_creator)} · ${compensationLabel(campaign)}`,
                                `${campaign.filled_slots}/${campaign.creators_needed} filled`,
                                inReview && campaign.submitted_for_review_at
                                    ? `waiting ${timeAgo(campaign.submitted_for_review_at)}`
                                    : `created ${formatDate(campaign.created_at)}`,
                            ]
                                .filter(Boolean)
                                .join(" · ")}
                        </p>
                    </div>
                </div>

                <div className="flex flex-none flex-wrap items-center gap-2 md:justify-end">
                    <Pill meta={CAMPAIGN_STATUS_META} value={status} />

                    {inReview && (
                        <>
                            <Button
                                type="button"
                                variant="outline"
                                disabled={busy}
                                onClick={() => actions.reject(campaign)}
                                data-testid={IDS.reject(campaign.id)}
                                className="h-8 rounded-full border-red-500/30 bg-transparent px-3 text-xs text-red-300 hover:bg-red-500/10 hover:text-red-200"
                            >
                                <XCircle className="mr-1.5 h-3.5 w-3.5" />
                                Send back
                            </Button>
                            <Button
                                type="button"
                                disabled={busy}
                                onClick={() => actions.approve(campaign)}
                                data-testid={IDS.approve(campaign.id)}
                                className="h-8 rounded-full bg-ember-500 px-4 text-xs text-black hover:bg-ember-400"
                            >
                                <BadgeCheck className="mr-1.5 h-3.5 w-3.5" />
                                Approve
                            </Button>
                        </>
                    )}

                    {(live || paused) && (
                        <>
                            <Button
                                type="button"
                                variant="outline"
                                disabled={busy}
                                onClick={() => actions.edit(campaign)}
                                data-testid={IDS.edit(campaign.id)}
                                className="h-8 rounded-full border-white/15 bg-transparent px-3 text-xs hover:bg-white/5"
                            >
                                <Pencil className="mr-1.5 h-3.5 w-3.5" />
                                Edit
                            </Button>
                            {paused ? (
                                <Button
                                    type="button"
                                    disabled={busy}
                                    onClick={() => actions.resume(campaign)}
                                    data-testid={IDS.resume(campaign.id)}
                                    className="h-8 rounded-full bg-ember-500 px-4 text-xs text-black hover:bg-ember-400"
                                >
                                    <Play className="mr-1.5 h-3.5 w-3.5" />
                                    Resume
                                </Button>
                            ) : (
                                <Button
                                    type="button"
                                    variant="outline"
                                    disabled={busy}
                                    onClick={() => actions.pause(campaign)}
                                    data-testid={IDS.pause(campaign.id)}
                                    className="h-8 rounded-full border-white/15 bg-transparent px-3 text-xs hover:bg-white/5"
                                >
                                    <Pause className="mr-1.5 h-3.5 w-3.5" />
                                    Pause
                                </Button>
                            )}
                            <Button
                                type="button"
                                variant="outline"
                                disabled={busy}
                                onClick={() => actions.close(campaign)}
                                data-testid={IDS.close(campaign.id)}
                                className="h-8 rounded-full border-red-500/30 bg-transparent px-3 text-xs text-red-300 hover:bg-red-500/10 hover:text-red-200"
                            >
                                <XCircle className="mr-1.5 h-3.5 w-3.5" />
                                Close
                            </Button>
                        </>
                    )}

                    {canInvite && (
                        <Button
                            type="button"
                            disabled={busy}
                            onClick={() => actions.invite(campaign)}
                            data-testid={IDS.inviteOpen(campaign.id)}
                            variant="outline"
                            className="h-8 rounded-full border-white/15 bg-transparent px-3 text-xs hover:bg-white/5"
                        >
                            <Send className="mr-1.5 h-3.5 w-3.5" />
                            Invite
                        </Button>
                    )}
                </div>
            </div>

            {/* Why we sent it back last time — visible while the brand fixes it. */}
            {campaign.review_reason && status === "draft" && (
                <p
                    data-testid={IDS.reviewReason(campaign.id)}
                    className="mt-3 pl-7 text-xs text-amber-300/80"
                >
                    Sent back: {campaign.review_reason}
                </p>
            )}

            {expanded && (
                <div
                    data-testid={IDS.creators(campaign.id)}
                    className="mt-4 rounded-md border border-white/10 bg-background/40 px-5 py-2"
                >
                    {campaign.creators.length === 0 ? (
                        <p
                            data-testid={IDS.creatorsEmpty(campaign.id)}
                            className="py-4 text-sm text-muted-foreground"
                        >
                            Nobody has applied to this brief yet.
                        </p>
                    ) : (
                        <ul className="divide-y divide-white/10">
                            {campaign.creators.map((c) => (
                                <li
                                    key={c.collaboration_id}
                                    data-testid={IDS.creatorRow(c.collaboration_id)}
                                    className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6"
                                >
                                    <div className="min-w-0">
                                        <p className="truncate text-sm">{c.name || "Unnamed"}</p>
                                        {c.instagram_handle && (
                                            <p className="truncate text-xs text-muted-foreground">
                                                @{c.instagram_handle}
                                            </p>
                                        )}
                                    </div>
                                    <div className="flex flex-none items-center gap-3">
                                        <span className="inline-flex items-baseline text-xs text-muted-foreground">
                                            {c.agreed_amount != null ? (
                                                <>
                                                    <IndianRupee className="h-3 w-3" />
                                                    {formatRupees(c.agreed_amount)}
                                                </>
                                            ) : (
                                                "Not agreed"
                                            )}
                                        </span>
                                        <StatePill state={c.state} />
                                        {c.payment_state === "paid" && (
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => actions.refund(c, campaign)}
                                                data-testid={`admin-collab-refund-${c.collaboration_id}`}
                                                className="h-7 rounded-full border-red-500/30 bg-transparent px-3 text-xs text-red-300 hover:bg-red-500/10 hover:text-red-200"
                                            >
                                                Refund
                                            </Button>
                                        )}
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </li>
    );
}

export default function AdminCampaigns({ brandFilter, onClearBrand, onChanged }) {
    const [data, setData] = useState(null);
    const [q, setQ] = useState("");
    const [search, setSearch] = useState("");
    const [status, setStatus] = useState("");
    const [from, setFrom] = useState(null);
    const [to, setTo] = useState(null);
    const [page, setPage] = useState(1);
    const [expanded, setExpanded] = useState({});
    const [busyId, setBusyId] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [confirm, setConfirm] = useState(null);
    const [editFor, setEditFor] = useState(null);
    const [inviteFor, setInviteFor] = useState(null);

    useEffect(() => {
        const t = setTimeout(() => {
            setSearch(q.trim());
            setPage(1);
        }, 300);
        return () => clearTimeout(t);
    }, [q]);

    // Arriving from the Brands section resets to their first page.
    useEffect(() => {
        setPage(1);
    }, [brandFilter]);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: d } = await api.get("/admin/campaigns", {
                params: {
                    page,
                    page_size: PAGE_SIZE,
                    ...(search ? { q: search } : {}),
                    ...(status ? { status } : {}),
                    ...(brandFilter ? { brand_id: brandFilter } : {}),
                    ...(from ? { date_from: from.toISOString() } : {}),
                    ...(to ? { date_to: endOfDay(to).toISOString() } : {}),
                },
            });
            setData(d);
        } catch (e) {
            notifyError(e);
            setData({ campaigns: [], total: 0, pages: 0 });
        }
    }, [page, search, status, brandFilter, from, to]);

    useEffect(() => {
        load();
    }, [load]);

    const run = async (id, fn, msg) => {
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
            if (e?.response?.status === 409) await load();
        } finally {
            setBusyId(null);
            setSubmitting(false);
        }
    };

    const actions = {
        approve: (c) =>
            run(c.id, () => api.post(`/admin/campaigns/${c.id}/approve`), "Campaign approved — it's live"),
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
    };

    const filtered = Boolean(search || status || brandFilter || from || to);
    const rows = useMemo(() => data?.campaigns || [], [data]);
    const pages = data?.pages || 0;

    const brandName = useMemo(
        () => rows.find((c) => c.brand_id === brandFilter)?.brand_name,
        [rows, brandFilter],
    );

    const clearFilters = () => {
        setQ("");
        setSearch("");
        setStatus("");
        setFrom(null);
        setTo(null);
        setPage(1);
        onClearBrand?.();
    };

    const chips = [
        { key: "search", label: "Title", value: search, onRemove: () => { setQ(""); setSearch(""); setPage(1); } },
        { key: "brand", label: "Brand", value: brandFilter ? brandName || "Selected brand" : "", onRemove: () => onClearBrand?.() },
        { key: "status", label: "Status", value: status, onRemove: () => { setStatus(""); setPage(1); } },
        { key: "from", label: "From", value: from ? formatDate(from.toISOString()) : "", onRemove: () => { setFrom(null); setPage(1); } },
        { key: "to", label: "To", value: to ? formatDate(to.toISOString()) : "", onRemove: () => { setTo(null); setPage(1); } },
    ];

    return (
        <section data-testid={IDS.section}>
            <SectionHeader
                kicker="Campaigns"
                title="Every brief"
                blurb="Drafts, briefs in review, live ones and closed ones. Approve or send back from the row; expand it to see who's on it."
                onRefresh={load}
                refreshTestId={IDS.refresh}
            />

            {brandFilter && (
                <button
                    type="button"
                    onClick={() => onClearBrand?.()}
                    className="mt-6 inline-flex items-center gap-2 rounded-full border border-ember-500/40 bg-ember-500/10 px-3 py-1.5 text-xs uppercase tracking-[0.15em] text-ember-500 transition-colors duration-200 hover:bg-ember-500/20"
                >
                    {brandName || "One brand"}
                    <X className="h-3.5 w-3.5" />
                </button>
            )}

            <StickyBar level="headerFromMd" testid={STICKY_BAR.adminSection} className="mt-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                <div className="relative min-w-0 flex-1 sm:min-w-[14rem]">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        data-testid={IDS.search}
                        placeholder="Campaign title"
                        aria-label="Search campaigns"
                        className="h-11 md:h-10 rounded-md border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                    />
                </div>
                <FilterSelect
                    label="Any status"
                    value={status}
                    onChange={(v) => {
                        setStatus(v);
                        setPage(1);
                    }}
                    options={STATUS_OPTIONS}
                    testid={IDS.filterStatus}
                />
                <DateFilter
                    label="From"
                    value={from}
                    onChange={(d) => {
                        setFrom(d);
                        setPage(1);
                    }}
                    testid={IDS.filterDateFrom}
                />
                <DateFilter
                    label="To"
                    value={to}
                    onChange={(d) => {
                        setTo(d);
                        setPage(1);
                    }}
                    testid={IDS.filterDateTo}
                />
                {filtered && (
                    <button
                        type="button"
                        onClick={clearFilters}
                        data-testid={IDS.filterClear}
                        className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                    >
                        <X className="h-3.5 w-3.5" />
                        Clear
                    </button>
                )}
            </div>

            <FilterChips chips={chips} onClearAll={clearFilters} className="mt-3" />
            </StickyBar>

            <div className="mt-6 rounded-md border border-white/10 bg-card grain-surface">
                {!data ? (
                    <ListSkeleton rows={5} testid={IDS.skeleton} />
                ) : rows.length === 0 ? (
                    <EmptyState testid={IDS.empty} Icon={Sparkles}>
                        {filtered
                            ? "No campaign matches those filters."
                            : "No campaign has been posted yet."}
                    </EmptyState>
                ) : (
                    <ul data-testid={IDS.list} className="divide-y divide-white/10">
                        {rows.map((c) => (
                            <CampaignRow
                                key={c.id}
                                campaign={c}
                                expanded={Boolean(expanded[c.id])}
                                onToggle={() => setExpanded((e) => ({ ...e, [c.id]: !e[c.id] }))}
                                busy={busyId === c.id}
                                actions={actions}
                            />
                        ))}
                    </ul>
                )}
            </div>

            {data && rows.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
                    <p
                        data-testid={IDS.count}
                        className="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                    >
                        {data.total
                            ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(
                                  page * PAGE_SIZE,
                                  data.total,
                              )} of ${data.total}`
                            : "No campaigns"}
                    </p>
                    {pages > 1 && (
                        <div data-testid={IDS.pagination} className="flex items-center gap-6">
                            <button
                                type="button"
                                disabled={page <= 1}
                                onClick={() => setPage((p) => Math.max(1, p - 1))}
                                data-testid={IDS.pagePrev}
                                className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 disabled:pointer-events-none disabled:opacity-40"
                            >
                                <ChevronLeft className="h-3.5 w-3.5" />
                                Previous
                            </button>
                            <span
                                data-testid={IDS.pageLabel}
                                className="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                            >
                                Page {page} of {pages}
                            </span>
                            <button
                                type="button"
                                disabled={page >= pages}
                                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                                data-testid={IDS.pageNext}
                                className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 disabled:pointer-events-none disabled:opacity-40"
                            >
                                Next
                                <ChevronRight className="h-3.5 w-3.5" />
                            </button>
                        </div>
                    )}
                </div>
            )}

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                kicker={confirm?.kicker}
                title={confirm?.title || ""}
                description={confirm?.description}
                placeholder="What should the record say?"
                confirmLabel={confirm?.confirmLabel}
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
