// The three review queues: creators, campaigns, brands.
//
// Same shape each time — a table of things waiting, each opening a panel with
// whatever you need to make the call, with approve and reject on the row and in
// the panel, and on the A and R keys. They are separate
// tabs rather than one list because the three decisions need different things
// in front of you: a creator's Instagram, a campaign's brief, a brand's
// paperwork.
//
// Approving is one tap. Rejecting always opens a dialog and always requires a
// reason, because the person on the other end is told what it said — and that
// stays true of the A and R keys, which reach these same two handlers.
//
// **The expanding card became a row and a panel.** A queue is worked one item
// at a time: read, decide, next. Expanding in place pushed everything below it
// down, so the next row was never where it had just been; the panel opens
// beside the list and leaves the queue exactly where it was.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { notifyError } from "@/lib/feedback";
import {
    Building2,
    CheckCircle2,
    ExternalLink,
    Instagram,
    Sparkles,
    XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { ADMIN_PEEK, ADMIN_REVIEWS as IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";
import { ConfirmDialog } from "./dialogs";
import { useOptimisticList } from "./useOptimistic";
import DataTable, { sortRows } from "./console/DataTable";
import PeekPanel from "./console/PeekPanel";
import { PeekButton, RowButton } from "./console/RowActions";
import StatusTag from "./console/StatusTag";
import { TimeAgo } from "./console/format";
import { TEXT } from "./console/tokens";
import useListState from "./console/useListState";
import useTableKeys from "./console/useTableKeys";
import {
    CAMPAIGN_STATUS_META,
    CreatorAvatar,
    formatCompact,
    formatDate,
    formatRupees,
} from "./shared";

const DEFAULTS = { sort: { key: "since", dir: "asc" } };

/**
 * One review queue. The three tabs differ only in what they fetch, what each
 * row says, and what the two buttons call — so that is all `config` carries.
 */
function ReviewQueue({ config, onChanged }) {
    const { rows: raw, setRows, removeOptimistically, isBusy } = useOptimisticList(null);
    const [confirm, setConfirm] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [focused, setFocused] = useState(-1);
    const [peekId, setPeekId] = useState(null);
    // The queues carry no filters, but sort and scroll are worth keeping
    // across a trip to somebody's page and back.
    const { state, patch, scrollRef } = useListState(`reviews:${config.kind}`, DEFAULTS);
    const { sort } = state;

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get(config.endpoint);
            setRows(config.filter ? data.filter(config.filter) : data);
        } catch (e) {
            notifyError(e);
            setRows([]);
        }
    }, [config, setRows]);

    useEffect(() => {
        load();
    }, [load]);

    const approve = useCallback(
        (row) => {
            if (!row) return;
            setPeekId(null);
            removeOptimistically(config.idOf(row), () => api.post(config.approvePath(row)), {
                successMessage: config.approvedMessage(row),
                onDone: () => onChanged?.(),
            });
        },
        [config, onChanged, removeOptimistically],
    );

    const reject = useCallback(
        (row) => {
            if (!row) return;
            const id = config.idOf(row);
            setConfirm({
                row,
                onSubmit: async (body) => {
                    setSubmitting(true);
                    const ok = await removeOptimistically(
                        id,
                        () => api.post(config.rejectPath(row), body),
                        { successMessage: config.rejectedMessage(row), onDone: () => onChanged?.() },
                    );
                    setSubmitting(false);
                    if (ok) {
                        setConfirm(null);
                        setPeekId(null);
                    }
                },
            });
        },
        [config, onChanged, removeOptimistically],
    );

    const columns = useMemo(
        () => [
            {
                key: "primary",
                header: config.rowHeader || "Waiting",
                sortable: true,
                value: (r) => String(config.primary(r) || ""),
                cell: (r) => (
                    <span className="flex min-w-0 items-center gap-2">
                        {config.renderAvatar?.(r)}
                        <span className="truncate">{config.primary(r)}</span>
                    </span>
                ),
            },
            {
                key: "secondary",
                header: "Detail",
                hideBelow: true,
                cell: (r) => (
                    <span className="block truncate text-muted-foreground">{config.secondary(r)}</span>
                ),
            },
            {
                key: "since",
                header: "Waiting",
                sortable: true,
                numeric: true,
                width: "w-28",
                // Ascending is longest-waiting first, which is the order a
                // queue is meant to be worked in.
                value: (r) => new Date(config.since(r) || 0).getTime() || null,
                cell: (r) => <TimeAgo iso={config.since(r)} />,
            },
            {
                key: "decision",
                header: "",
                width: "w-40",
                cell: (r) => {
                    const id = config.idOf(r);
                    return (
                        <span className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                            <RowButton
                                tone="bad"
                                disabled={isBusy(id)}
                                onClick={() => reject(r)}
                                testid={IDS.reject(id)}
                            >
                                {config.rejectLabel}
                            </RowButton>
                            <RowButton
                                tone="primary"
                                disabled={isBusy(id)}
                                onClick={() => approve(r)}
                                testid={IDS.approve(id)}
                            >
                                {config.approveLabel}
                            </RowButton>
                        </span>
                    );
                },
            },
        ],
        [config, approve, reject, isBusy],
    );

    const rows = useMemo(() => sortRows(raw || [], columns, sort), [raw, columns, sort]);
    const peek = useMemo(
        () => rows.find((r) => config.idOf(r) === peekId) || null,
        [rows, peekId, config],
    );

    const openPeek = useCallback(
        (i) => {
            setFocused(i);
            setPeekId(rows[i] ? config.idOf(rows[i]) : null);
        },
        [rows, config],
    );

    useTableKeys({
        count: rows.length,
        focused,
        setFocused,
        onOpen: openPeek,
        onApprove: (i) => approve(rows[i]),
        onReject: (i) => reject(rows[i]),
        onEscape: () => (peekId ? setPeekId(null) : setFocused(-1)),
        enabled: !confirm,
    });

    const count = raw?.length ?? 0;

    return (
        <section data-testid={IDS.section(config.kind)}>
            <header className="mb-3">
                <h1 className={TEXT.heading}>
                    {count === 0 && raw ? config.clearTitle : config.title}
                </h1>
                <p data-testid={IDS.count(config.kind)} className={`${TEXT.meta} text-muted-foreground`}>
                    {raw ? `${count} waiting · longest first` : "Loading…"}
                </p>
            </header>

            {config.note && raw && count > 0 && (
                <p
                    data-testid={IDS.blockedNote}
                    className={`mb-3 rounded border border-ember-500/30 bg-ember-500/10 px-3 py-2 ${TEXT.body} text-ember-500`}
                >
                    {config.note}
                </p>
            )}

            <DataTable
                columns={columns}
                rows={rows}
                rowKey={(r) => config.idOf(r)}
                rowTestId={(r) => IDS.row(config.idOf(r))}
                sort={sort}
                onSortChange={(s) => patch({ sort: s })}
                focused={focused}
                onFocus={setFocused}
                onOpen={openPeek}
                loading={!raw}
                scrollRef={scrollRef}
                testid={IDS.list(config.kind)}
                empty={
                    <ListEmptyState
                        Icon={CheckCircle2}
                        testid={IDS.empty(config.kind)}
                        filtered={false}
                        emptyTitle={config.clearTitle}
                        emptyBody={config.emptyText}
                    />
                }
            />

            {/* Everything you need to make the call, beside the queue rather
                than inside it. `IDS.detail` is here because this is where the
                detail went, not a new thing. */}
            <PeekPanel
                open={Boolean(peek)}
                onOpenChange={(o) => !o && setPeekId(null)}
                title={peek ? String(config.primary(peek)) : "Review"}
                subtitle={peek ? String(config.secondary(peek) || "") : undefined}
                actions={
                    peek ? (
                        <>
                            <PeekButton
                                tone="bad"
                                disabled={isBusy(config.idOf(peek))}
                                onClick={() => reject(peek)}
                                testid={ADMIN_PEEK.action("reject")}
                            >
                                <XCircle className="h-3.5 w-3.5" />
                                {config.rejectLabel}
                            </PeekButton>
                            <PeekButton
                                tone="primary"
                                disabled={isBusy(config.idOf(peek))}
                                onClick={() => approve(peek)}
                                testid={ADMIN_PEEK.action("approve")}
                            >
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                {config.approveLabel}
                            </PeekButton>
                        </>
                    ) : null
                }
            >
                {peek && (
                    <div data-testid={IDS.detail(config.idOf(peek))}>
                        <div className="mb-3 flex items-center gap-3">
                            {config.renderBadge?.(peek)}
                            <span className={`${TEXT.meta} text-muted-foreground`}>
                                waiting <TimeAgo iso={config.since(peek)} />
                            </span>
                        </div>
                        {config.renderDetail(peek)}
                    </div>
                )}
            </PeekPanel>

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                destructive
                kicker={config.rejectKicker}
                title={confirm ? config.rejectTitle(confirm.row) : ""}
                description={config.rejectDescription}
                placeholder="What should they know?"
                confirmLabel={config.rejectLabel}
                onSubmit={(body) => confirm?.onSubmit(body)}
            />
        </section>
    );
}

// --- Creators ---------------------------------------------------------------

export function CreatorReviews({ onChanged }) {
    return (
        <ReviewQueue
            onChanged={onChanged}
            config={{
                kind: "creators",
                endpoint: "/admin/creators/pending",
                kicker: "Creator reviews",
                title: "Pending creator approvals",
                clearTitle: "No creators waiting.",
                blurb:
                    "Nobody can pitch on a brief until we've approved them, so this queue is the thing standing between a creator and their first job.",
                emptyText: "Inbox zero — every creator who finished signing up has an answer.",
                idOf: (r) => r.user_id,
                since: (r) => r.created_at,
                primary: (r) => r.name || "Unnamed creator",
                secondary: (r) =>
                    [
                        r.instagram_handle ? `@${r.instagram_handle}` : null,
                        r.city,
                        typeof r.follower_count === "number"
                            ? `${formatCompact(r.follower_count)} followers`
                            : null,
                    ]
                        .filter(Boolean)
                        .join(" · "),
                renderAvatar: (r) => <CreatorAvatar creator={r} size="h-6 w-6" />,
                renderDetail: (r) => (
                    <div className="space-y-4 text-sm">
                        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                            {[
                                ["Email", r.email],
                                ["Phone", r.phone],
                                ["City", r.city],
                                ["Area", r.address],
                                [
                                    "Base rate",
                                    r.base_rate != null ? `₹${formatRupees(r.base_rate)}` : null,
                                ],
                                [
                                    "Followers",
                                    typeof r.follower_count === "number"
                                        ? r.follower_count.toLocaleString("en-IN")
                                        : null,
                                ],
                                ["Joined", formatDate(r.created_at)],
                            ]
                                .filter(([, v]) => v)
                                .map(([label, value]) => (
                                    <div key={label}>
                                        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            {label}
                                        </dt>
                                        <dd className="mt-1 break-words">{value}</dd>
                                    </div>
                                ))}
                        </dl>

                        {r.niches?.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                                {r.niches.map((n) => (
                                    <span
                                        key={n}
                                        className="rounded-full bg-ember-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-ember-500"
                                    >
                                        {n}
                                    </span>
                                ))}
                            </div>
                        )}

                        {/* The single most useful thing on this screen: you
                            cannot vet a creator without looking at their feed. */}
                        {r.instagram_handle && (
                            <a
                                href={
                                    r.instagram_profile_url ||
                                    `https://instagram.com/${r.instagram_handle}`
                                }
                                target="_blank"
                                rel="noreferrer"
                                data-testid={IDS.instagram(r.user_id)}
                                className="inline-flex h-11 items-center gap-2 rounded-md border border-white/15 px-4 text-sm transition-colors duration-150 hover:border-ember-500/40 hover:text-ember-500"
                            >
                                <Instagram className="h-4 w-4" />
                                Open @{r.instagram_handle}
                                <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                        )}
                    </div>
                ),
                approveLabel: "Approve",
                rejectLabel: "Reject",
                approvePath: (r) => `/admin/creators/${r.user_id}/approve`,
                rejectPath: (r) => `/admin/creators/${r.user_id}/reject`,
                approvedMessage: (r) => `${r.name || "Creator"} verified`,
                rejectedMessage: (r) => `${r.name || "Creator"} rejected`,
                rejectKicker: "Reject creator",
                rejectTitle: (r) => `Reject ${r.name || "this creator"}?`,
                rejectDescription:
                    "They're told why, and briefs stay closed to them until we approve. They can fix their profile and come back.",
            }}
        />
    );
}

// --- Campaigns --------------------------------------------------------------

export function CampaignReviews({ onChanged }) {
    return (
        <ReviewQueue
            onChanged={onChanged}
            config={{
                kind: "campaigns",
                endpoint: "/admin/campaigns/pending",
                kicker: "Campaign reviews",
                title: "Briefs waiting to go live",
                clearTitle: "No briefs waiting.",
                blurb:
                    "A campaign reaches creators when it's approved here, and not before. Read the brief; it's what a creator will act on.",
                emptyText: "Nothing submitted for review.",
                idOf: (r) => r.id,
                since: (r) => r.submitted_for_review_at || r.created_at,
                primary: (r) => r.title,
                secondary: (r) =>
                    [
                        r.brand_name || "Unknown brand",
                        r.budget_per_creator != null
                            ? `₹${formatRupees(r.budget_per_creator)} per creator`
                            : null,
                        r.area,
                    ]
                        .filter(Boolean)
                        .join(" · "),
                renderBadge: () => (
                    <StatusTag
                        state="pending_review"
                        label={CAMPAIGN_STATUS_META.pending_review?.label}
                        chip
                    />
                ),
                renderDetail: (r) => (
                    <div className="space-y-5 text-sm">
                        {/* A brand that lost its verification while the brief
                            sat here can't have it approved — say so up front. */}
                        {!r.brand_verified && (
                            <p className="rounded-md border border-ember-500/30 bg-ember-500/10 px-4 py-3 text-sm leading-relaxed text-ember-500">
                                {r.brand_name || "This brand"} isn't verified. Approve them
                                in Brand reviews first — this brief can't go live until
                                they are.
                            </p>
                        )}

                        {r.previous_review_reason && (
                            <p className="rounded-md border border-white/10 bg-background/60 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
                                Last time we sent this back: “{r.previous_review_reason}”
                            </p>
                        )}

                        <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                The brief
                            </p>
                            <p className="mt-2 whitespace-pre-wrap leading-relaxed">
                                {r.brief}
                            </p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                Deliverables
                            </p>
                            <p className="mt-2 whitespace-pre-wrap leading-relaxed">
                                {r.deliverables}
                            </p>
                        </div>

                        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                            {[
                                ["Brand", r.brand_name],
                                ["Type", (r.campaign_type || "").replace(/_/g, " ")],
                                [
                                    "Budget",
                                    r.budget_per_creator != null
                                        ? `₹${formatRupees(r.budget_per_creator)} per creator`
                                        : null,
                                ],
                                ["Creators needed", r.creators_needed],
                                ["Area", r.area],
                                ["Category", r.category],
                                // Whichever dates this type actually carries.
                                ["Event day", r.event_date ? formatDate(r.event_date) : null],
                                [
                                    "Booking window",
                                    r.start_date
                                        ? `${formatDate(r.start_date)} – ${formatDate(r.end_date)}`
                                        : null,
                                ],
                                ["Submitted", formatDate(r.submitted_for_review_at)],
                            ]
                                .filter(([, v]) => v)
                                .map(([label, value]) => (
                                    <div key={label}>
                                        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            {label}
                                        </dt>
                                        <dd className="mt-1 capitalize">{value}</dd>
                                    </div>
                                ))}
                        </dl>
                    </div>
                ),
                approveLabel: "Approve & publish",
                rejectLabel: "Send back",
                approvePath: (r) => `/admin/campaigns/${r.id}/approve`,
                rejectPath: (r) => `/admin/campaigns/${r.id}/reject`,
                approvedMessage: (r) => `“${r.title}” is live`,
                rejectedMessage: (r) => `“${r.title}” sent back to the brand`,
                rejectKicker: "Send back",
                rejectTitle: (r) => `Send “${r.title}” back?`,
                rejectDescription:
                    "It returns to the brand as a draft with your reason attached, so they can fix it and submit again.",
            }}
        />
    );
}

// --- Brands -----------------------------------------------------------------

export function BrandReviews({ onChanged }) {
    return (
        <ReviewQueue
            onChanged={onChanged}
            config={{
                kind: "brands",
                endpoint: "/admin/brands/pending",
                // Somebody we already refused is not waiting on us.
                filter: (r) => r.verification_state !== "rejected",
                kicker: "Brand reviews",
                title: "Pending brand approvals",
                clearTitle: "No brands waiting.",
                blurb:
                    "An unverified brand can draft campaigns but cannot submit one, so nothing they write reaches a creator until this is done.",
                note:
                    "These brands cannot post campaigns. They can write drafts, but submitting one is blocked until you verify them.",
                emptyText: "Every brand that signed up has an answer.",
                idOf: (r) => r.user_id,
                since: (r) => r.signed_up_at || r.created_at,
                primary: (r) => r.business_name || r.name || "Unnamed brand",
                secondary: (r) =>
                    [r.category, r.email || r.phone, (r.areas || []).join(", ")]
                        .filter(Boolean)
                        .join(" · "),
                renderAvatar: () => (
                    <span className="grid h-6 w-6 flex-none place-items-center rounded border border-white/10 bg-ember-500/10 text-ember-500">
                        <Building2 className="h-3.5 w-3.5" />
                    </span>
                ),
                renderDetail: (r) => (
                    <div className="space-y-4 text-sm">
                        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                            {[
                                ["Business name", r.business_name],
                                ["Contact name", r.name],
                                ["Email", r.email],
                                ["Phone", r.phone],
                                ["Category", r.category],
                                ["Areas", (r.areas || []).join(", ")],
                                ["Signed up", formatDate(r.signed_up_at || r.created_at)],
                                [
                                    "Terms accepted",
                                    r.terms_accepted_at ? formatDate(r.terms_accepted_at) : null,
                                ],
                            ]
                                .filter(([, v]) => v)
                                .map(([label, value]) => (
                                    <div key={label}>
                                        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            {label}
                                        </dt>
                                        <dd className="mt-1 break-words capitalize">{value}</dd>
                                    </div>
                                ))}
                        </dl>

                        {/* Briefs stacked up behind this decision make it urgent
                            in a way the signup date alone doesn't show. */}
                        {r.campaigns_awaiting_review > 0 && (
                            <p className="inline-flex items-center gap-2 rounded-md border border-ember-500/30 bg-ember-500/10 px-4 py-2.5 text-sm text-ember-500">
                                <Sparkles className="h-3.5 w-3.5" />
                                {r.campaigns_awaiting_review} brief
                                {r.campaigns_awaiting_review === 1 ? "" : "s"} queued behind
                                this decision
                            </p>
                        )}

                        {r.campaign_count > 0 && (
                            <p className="text-sm text-muted-foreground">
                                {r.campaign_count} campaign
                                {r.campaign_count === 1 ? "" : "s"} written so far.
                            </p>
                        )}
                    </div>
                ),
                approveLabel: "Verify",
                rejectLabel: "Reject",
                approvePath: (r) => `/admin/brands/${r.user_id}/verify`,
                rejectPath: (r) => `/admin/brands/${r.user_id}/reject`,
                approvedMessage: (r) => `${r.business_name || "Brand"} verified`,
                rejectedMessage: (r) => `${r.business_name || "Brand"} rejected`,
                rejectKicker: "Reject brand",
                rejectTitle: (r) => `Reject ${r.business_name || "this brand"}?`,
                rejectDescription:
                    "They're told why, and any briefs of theirs waiting for review go back to draft. They can fix it and reapply.",
            }}
        />
    );
}
