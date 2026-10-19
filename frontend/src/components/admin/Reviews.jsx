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
import { Link } from "react-router-dom";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    Building2,
    CheckCircle2,
    ExternalLink,
    Instagram,
    Sparkles,
    XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { ADMIN_PEEK, ADMIN_REVIEWS as IDS, BULK, TRUST } from "@/constants/testIds";
import { Button } from "@/components/ui/button";
import { ListEmptyState } from "@/components/data/DenseView";
import { ConfirmDialog } from "./dialogs";
import { useOptimisticList } from "./useOptimistic";
import DataTable, { sortRows } from "./console/DataTable";
import PeekPanel from "./console/PeekPanel";
import { PeekButton, RowButton } from "./console/RowActions";
import { DeliverableList } from "@/components/Deliverables";
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
    // Ids ticked for a bulk decision. A Set because the only two
    // questions asked of it are "is this one in" and "how many".
    const [selected, setSelected] = useState(new Set());
    const [bulk, setBulk] = useState(null);
    const [bulkBusy, setBulkBusy] = useState(false);
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

    /**
     * The primary action for one row, which is not always "approve".
     *
     * **A queue can hold rows whose approve cannot succeed.** The campaign
     * queue returns two kinds: a brief awaiting a decision, and a trusted
     * brand's brief that is *already live* and awaiting a look. Approve
     * writes with `status == pending_review` as its precondition, so on the
     * second kind it answered 409 "This just moved — reload and try again" —
     * a refusal that describes a race that did not happen and sends somebody
     * to reload a list that was never stale.
     *
     * `config.altPrimary(row)` returns the action that *can* succeed, or null
     * for an ordinary row. Offering approve and letting the server refuse is
     * the thing this replaces, so there is no row where both are drawn.
     */
    const primaryFor = useCallback(
        (row) => (row ? config.altPrimary?.(row) || null : null),
        [config],
    );

    const approve = useCallback(
        (row) => {
            if (!row) return;
            const alt = primaryFor(row);
            setPeekId(null);
            removeOptimistically(
                config.idOf(row),
                () => api.post(alt ? alt.path : config.approvePath(row)),
                {
                    successMessage: alt ? alt.message : config.approvedMessage(row),
                    onDone: () => onChanged?.(),
                },
            );
        },
        [config, onChanged, removeOptimistically, primaryFor],
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
            // **Selection is a column, not a mode.** A separate "select" state
            // that has to be turned on is a step between somebody and the
            // fifty decisions they came here to enter.
            ...(config.bulkKind
                ? [{
                      key: "select",
                      header: "",
                      width: "w-10",
                      cell: (r) => {
                          const id = config.idOf(r);
                          return (
                              <input
                                  type="checkbox"
                                  checked={selected.has(id)}
                                  aria-label={`Select ${config.primary(r)}`}
                                  data-testid={BULK.select(id)}
                                  onClick={(e) => e.stopPropagation()}
                                  onChange={(e) => {
                                      const next = new Set(selected);
                                      if (e.target.checked) next.add(id);
                                      else next.delete(id);
                                      setSelected(next);
                                  }}
                                  className="h-4 w-4 accent-primary"
                              />
                          );
                      },
                  }]
                : []),
            {
                key: "primary",
                mobile: "primary",
                header: config.rowHeader || "Waiting",
                sortable: true,
                value: (r) => String(config.primary(r) || ""),
                cell: (r) => (
                    <span className="flex min-w-0 items-center gap-2">
                        {config.renderAvatar?.(r)}
                        {/* **The name is a link to the whole record.** A row
                            opens the peek, which is a preview; the name goes
                            to the page, which is everything. Before this the
                            queue was preview-only, so a brand's GST number
                            and its documents were unreachable from the one
                            screen where they decide it. `stopPropagation` so
                            the peek does not also open behind the navigation. */}
                        <Link
                            to={config.href(r)}
                            onClick={(e) => e.stopPropagation()}
                            data-testid={IDS.open(config.idOf(r))}
                            className="truncate transition-colors duration-150 hover:text-primary-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                            {config.primary(r)}
                        </Link>
                        {r.reference && (
                            <span className="flex-none font-mono text-[10px] tracking-wider text-muted-foreground/70">
                                {r.reference}
                            </span>
                        )}
                        {/* **The exception, on the row rather than only in the
                            peek.** `renderBadge` draws the state inside the
                            peek, where both kinds want naming; here a chip on
                            every row would print "Pending review" down a queue
                            that is entirely pending review. So this marks only
                            the row that is *not* what the queue implies — the
                            one an admin would otherwise approve by reflex. */}
                        {config.rowBadge?.(r)}
                    </span>
                ),
            },
            {
                key: "secondary",
                mobile: "meta",
                header: "Detail",
                hideBelow: true,
                cell: (r) => (
                    <span className="block truncate text-muted-foreground">{config.secondary(r)}</span>
                ),
            },
            {
                key: "since",
                mobile: "meta",
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
                mobile: "action",
                header: "",
                width: "w-40",
                cell: (r) => {
                    const id = config.idOf(r);
                    const alt = primaryFor(r);
                    return (
                        <span className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                            <RowButton
                                tone="bad"
                                disabled={isBusy(id)}
                                onClick={() => reject(r)}
                                testid={IDS.reject(id)}
                            >
                                {alt?.rejectLabel || config.rejectLabel}
                            </RowButton>
                            <RowButton
                                tone="primary"
                                disabled={isBusy(id)}
                                onClick={() => approve(r)}
                                testid={alt ? alt.testid(id) : IDS.approve(id)}
                            >
                                {alt ? alt.label : config.approveLabel}
                            </RowButton>
                        </span>
                    );
                },
            },
        ],
        [config, approve, reject, isBusy, selected, primaryFor],
    );

    const rows = useMemo(() => sortRows(raw || [], columns, sort), [raw, columns, sort]);

    // **Cleared whenever the list changes.** A selection that survives a
    // reload is a set of ids that may no longer be on screen, and acting on
    // one of those is the bulk version of pressing a button you cannot see.
    useEffect(() => {
        setSelected(new Set());
    }, [raw]);
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

    /**
     * Send the batch, then reload rather than patching the list.
     *
     * **Partial success is the normal case, not an error.** A row that moved
     * since the list was drawn comes back in `failed` and the rest still went
     * through; reporting "it failed" over one stale row would be a lie about
     * forty-nine real decisions.
     */
    /**
     * Which of the ticked rows this batch may actually be sent for.
     *
     * **A row whose approve cannot succeed is excluded from approving, not
     * from selecting.** `POST /admin/bulk/campaigns` loops the real handler,
     * so an auto-published brief in an approve batch comes back in `failed`
     * with the same 409 the single row gave — forty-nine real decisions
     * reported beside a refusal that was predictable before it was sent.
     * Rejecting them in bulk is a different matter and stays allowed: pulling
     * live briefs off the feed together is a real thing to want.
     */
    const approvableIds = useMemo(
        () =>
            [...selected].filter((id) => {
                const row = (raw || []).find((r) => config.idOf(r) === id);
                return !(row && primaryFor(row));
            }),
        [selected, raw, config, primaryFor],
    );

    const bulkIds = bulk === "approve" ? approvableIds : [...selected];
    const bulkSkipped = selected.size - approvableIds.length;

    const runBulk = async (body) => {
        setBulkBusy(true);
        try {
            const { data } = await api.post(`/admin/bulk/${config.bulkKind}`, {
                ids: bulkIds,
                action: bulk,
                reason: (body?.reason || "").trim() || null,
            });
            const done = data.done?.length || 0;
            const failed = data.failed?.length || 0;
            notifySuccess(
                failed
                    ? `${done} done, ${failed} couldn't be — ${data.failed[0].error}`
                    : `${done} ${bulk === "approve" ? "approved" : "rejected"}`
            );
            setSelected(new Set());
            setBulk(null);
            await load();
            onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That batch couldn't be sent." });
        } finally {
            setBulkBusy(false);
        }
    };

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
                    className={`mb-3 rounded border border-primary/30 bg-primary/10 px-3 py-2 ${TEXT.body} text-primary-ink`}
                >
                    {config.note}
                </p>
            )}

            {/* **Only when something is picked.** A permanently visible bulk
                bar is chrome above every queue for the one visit in ten where
                it is used, and it pushes the rows down on a phone. */}
            {config.bulkKind && selected.size > 0 && (
                <div
                    data-testid={BULK.bar}
                    className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 py-2"
                >
                    <span className={`${TEXT.body} text-primary-ink`}>
                        {selected.size} selected
                    </span>
                    {/* **Disabled rather than absent, with the reason in the
                        title.** The bar itself is absent until something is
                        picked, which is the rule for chrome; this button has
                        been picked *for* and cannot run, so vanishing it would
                        read as the bar being broken. */}
                    <Button
                        size="sm"
                        onClick={() => setBulk("approve")}
                        disabled={approvableIds.length === 0}
                        title={
                            approvableIds.length === 0
                                ? "Everything selected is already live and awaiting a spot check — clear those one at a time."
                                : undefined
                        }
                        data-testid={BULK.approve}
                        className="min-h-[2.75rem] bg-primary text-primary-foreground hover:bg-primary-hover disabled:opacity-40 sm:min-h-0"
                    >
                        {config.approveLabel}
                        {approvableIds.length === selected.size
                            ? " all"
                            : ` ${approvableIds.length}`}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setBulk("reject")}
                        data-testid={BULK.reject}
                        className="min-h-[2.75rem] border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10 sm:min-h-0"
                    >
                        {config.rejectLabel} all
                    </Button>
                    <button
                        type="button"
                        onClick={() => setSelected(new Set())}
                        className={`${TEXT.meta} text-muted-foreground underline-offset-4 hover:underline`}
                    >
                        Clear
                    </button>
                    <button
                        type="button"
                        data-testid={BULK.selectAll}
                        onClick={() => setSelected(new Set(rows.map(config.idOf)))}
                        className={`${TEXT.meta} text-muted-foreground underline-offset-4 hover:underline`}
                    >
                        Select all {rows.length}
                    </button>
                </div>
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
                href={peek ? config.href(peek) : undefined}
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
                                {primaryFor(peek)?.rejectLabel || config.rejectLabel}
                            </PeekButton>
                            <PeekButton
                                tone="primary"
                                disabled={isBusy(config.idOf(peek))}
                                onClick={() => approve(peek)}
                                testid={ADMIN_PEEK.action("approve")}
                            >
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                {primaryFor(peek)?.label || config.approveLabel}
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

            {/* **The summary is the point of the confirmation.** "Are you
                sure?" over fifty records is a question nobody can answer;
                naming the number and the outcome is. The reason is required
                on a rejection, exactly as it is one at a time, and everybody
                in the batch is told the same one. */}
            <ConfirmDialog
                open={Boolean(bulk)}
                onOpenChange={(v) => !v && setBulk(null)}
                submitting={bulkBusy}
                destructive={bulk === "reject"}
                kicker={bulk === "reject" ? config.rejectKicker : "Confirm"}
                title={
                    bulk === "reject"
                        ? `${config.rejectLabel} ${selected.size}?`
                        : `${config.approveLabel} ${bulkIds.length}?`
                }
                description={
                    bulk === "reject"
                        ? `All ${selected.size} are told the same reason, and each decision is recorded separately.`
                        : // **The skipped ones are named, not silently dropped.**
                          // Ticking six and being told six went through when
                          // four did is the shape of this that costs somebody
                          // an afternoon of believing the queue is clear.
                          [
                              `All ${bulkIds.length} go through one at a time, each one recorded and each person told.`,
                              bulkSkipped
                                  ? `${bulkSkipped} of the ${selected.size} selected ${
                                        bulkSkipped === 1 ? "is" : "are"
                                    } already live and awaiting a spot check — ${
                                        bulkSkipped === 1 ? "it is" : "they are"
                                    } left out, because approving ${
                                        bulkSkipped === 1 ? "it" : "them"
                                    } is not a thing that can happen. Clear ${
                                        bulkSkipped === 1 ? "it" : "them"
                                    } one at a time.`
                                  : null,
                          ]
                              .filter(Boolean)
                              .join(" ")
                }
                requireReason={bulk === "reject"}
                placeholder="What should they all know?"
                confirmLabel={bulk === "reject" ? config.rejectLabel : config.approveLabel}
                onSubmit={runBulk}
            />

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                destructive
                kicker={config.rejectKicker}
                title={confirm ? config.rejectTitle(confirm.row) : ""}
                // **A string on two queues and a function on the third.** What
                // rejecting *does* depends on the row where one queue holds
                // two kinds: sending a draft back to its brand and pulling a
                // brief creators can currently see are not the same warning.
                description={
                    typeof config.rejectDescription === "function"
                        ? config.rejectDescription(confirm?.row)
                        : config.rejectDescription
                }
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
                // Which bulk queue this is. Absent would mean no
                // selection column at all — see the columns above.
                bulkKind: "creators",
                endpoint: "/admin/creators/pending",
                kicker: "Creator reviews",
                title: "Pending creator approvals",
                clearTitle: "No creators waiting.",
                blurb:
                    "Nobody can pitch on a brief until we've approved them, so this queue is the thing standing between a creator and their first job.",
                emptyText: "Inbox zero — every creator who finished signing up has an answer.",
                idOf: (r) => r.user_id,
                // **Where the whole record is.** A queue row is a summary and
                // a peek is a preview; neither carries everything a decision
                // needs, and an admin who could only see the preview was
                // approving on a fraction of what we hold.
                href: (r) => `/admin/creators/${r.user_id}`,
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
                                        className="rounded-full bg-primary/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-primary-ink"
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
                                className="inline-flex h-11 items-center gap-2 rounded-md border border-tint/15 px-4 text-sm transition-colors duration-150 hover:border-primary/40 hover:text-primary-ink"
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
                // Which bulk queue this is. Absent would mean no
                // selection column at all — see the columns above.
                bulkKind: "campaigns",
                endpoint: "/admin/campaigns/pending",
                kicker: "Campaign reviews",
                title: "Briefs waiting to go live",
                clearTitle: "No briefs waiting.",
                blurb:
                    "Most briefs reach creators when they're approved here. A trusted brand's goes live on submission and lands here already live, for a spot check — read the brief either way; it's what a creator will act on.",
                emptyText: "Nothing submitted for review.",
                idOf: (r) => r.id,
                href: (r) => `/admin/campaigns/${r.id}`,
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
                // **Two kinds of row, so the badge has to read the row.** It
                // was hardcoded to `pending_review`, which labelled a brief
                // that creators could already see "Pending review" — the one
                // word for it that is false.
                renderBadge: (r) =>
                    r?.auto_published ? (
                        <StatusTag
                            state="open"
                            label="Live — needs a spot check"
                            chip
                        />
                    ) : (
                        <StatusTag
                            state="pending_review"
                            label={CAMPAIGN_STATUS_META.pending_review?.label}
                            chip
                        />
                    ),
                rowBadge: (r) =>
                    r.auto_published ? (
                        <span
                            data-testid={TRUST.autoBadge(r.id)}
                            className="flex-none"
                            title="This brand publishes on submission. The brief is live; this is the read after the fact."
                        >
                            <StatusTag state="open" label="Live" chip />
                        </span>
                    ) : null,
                // **The action that can succeed on an auto-published row.**
                // Approve's write precondition is `status == pending_review`,
                // which these do not have and never will: they are live. So
                // approve is not offered on them at all — see `primaryFor` in
                // `ReviewQueue` for why offering it and letting the server
                // refuse is the thing this replaces.
                altPrimary: (r) =>
                    r.auto_published
                        ? {
                              label: "Looks fine",
                              path: `/admin/campaigns/${r.id}/spot-check`,
                              message: `“${r.title}” spot-checked`,
                              testid: TRUST.spotCheck,
                              // Reject still works and is the right door, but
                              // on this row it does something different from
                              // what "Send back" means on the others: it takes
                              // a brief off the feed that creators can see now.
                              rejectLabel: "Pull it down",
                          }
                        : null,
                renderDetail: (r) => (
                    <div className="space-y-5 text-sm">
                        {/* **What kind of row this is, before the brief.** The
                            reader's next action differs, so the fact that
                            changes it goes above the thing they are reading. */}
                        {r.auto_published && (
                            <p className="rounded-md border border-state-progress/30 bg-state-progress/10 px-4 py-3 text-sm leading-relaxed text-state-progress">
                                This brand has earned publishing on submission, so this
                                brief went live on its own
                                {r.auto_published_at
                                    ? ` ${formatDate(r.auto_published_at)}`
                                    : ""}{" "}
                                and nobody has read it yet. Clearing it records the read;
                                rejecting it takes it off the feed.
                            </p>
                        )}

                        {/* A brand that lost its verification while the brief
                            sat here can't have it approved — say so up front. */}
                        {!r.brand_verified && (
                            <p className="rounded-md border border-primary/30 bg-primary/10 px-4 py-3 text-sm leading-relaxed text-primary-ink">
                                {r.brand_name || "This brand"} isn't verified. Approve them
                                in Brand reviews first — this brief can't go live until
                                they are.
                            </p>
                        )}

                        {r.previous_review_reason && (
                            <p className="rounded-md border border-tint/10 bg-background/60 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
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
                            <DeliverableList campaign={r} className="mt-2" />
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
                rejectTitle: (r) =>
                    r?.auto_published
                        ? `Pull “${r.title}” off the feed?`
                        : `Send “${r.title}” back?`,
                rejectDescription: (r) =>
                    r?.auto_published
                        ? // Said plainly, because this is the one row where
                          // the button's ordinary meaning understates it:
                          // creators can see this brief right now, and some
                          // may already have pitched on it.
                          "This brief is live. Rejecting it takes it off the feed and returns it to the brand as a draft with your reason attached — anyone already looking at it will stop seeing it."
                        : "It returns to the brand as a draft with your reason attached, so they can fix it and submit again.",
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
                // Which bulk queue this is. Absent would mean no
                // selection column at all — see the columns above.
                bulkKind: "brands",
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
                // The GST number, the registered address and the documents
                // themselves all live on the brand's page. Deciding without
                // them is deciding on the business name alone, which is what
                // this queue used to make an admin do.
                href: (r) => `/admin/brands/${r.user_id}`,
                since: (r) => r.signed_up_at || r.created_at,
                primary: (r) => r.business_name || r.name || "Unnamed brand",
                secondary: (r) =>
                    [r.category, r.email || r.phone, (r.areas || []).join(", ")]
                        .filter(Boolean)
                        .join(" · "),
                renderAvatar: () => (
                    <span className="grid h-6 w-6 flex-none place-items-center rounded border border-tint/10 bg-primary/10 text-primary-ink">
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
                            <p className="inline-flex items-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm text-primary-ink">
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
