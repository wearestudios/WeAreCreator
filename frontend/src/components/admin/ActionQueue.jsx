// The landing screen: one list of everything waiting on us, whatever kind of
// thing it is. Five queues used to be five places to look, which is how a
// creator ends up waiting a week for a decision nobody knew was theirs.
//
// Ordered by what it costs to leave it: money owed first, then work already in
// flight that has stalled, then people who cannot start until we act. Age is
// the tie-break inside each band, and anything past two days is marked so it
// stops blending in.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    ArrowRight,
    BadgeCheck,
    Building2,
    CheckCircle2,
    IndianRupee,
    MessageCircleQuestion,
    Sparkles,
    Undo2,
    Users,
    Wallet,
    XCircle,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ADMIN_PEEK, ADMIN_QUEUE as IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";
import { AdvanceDialog, ConfirmDialog } from "./dialogs";
import DataTable, { sortRows } from "./console/DataTable";
import PeekPanel, { PeekField } from "./console/PeekPanel";
import { PeekButton, RowButton } from "./console/RowActions";
import StatusTag from "./console/StatusTag";
import { TimeAgo } from "./console/format";
import { CALM, DENSITY, FOCUS, PANEL, ROW_H, TEXT } from "./console/tokens";
import useListState from "./console/useListState";
import useTableKeys from "./console/useTableKeys";
import { formatRupees, isStale } from "./shared";

// Collaboration states where the next move is ours. Mirrors ADMIN_ACTION_STATES
// on the server; anything else is waiting on the brand or the creator.
const ADMIN_ACTION_STATES = [
    "applied",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "content_approved",
];

// What each step is actually called when you're the one doing it.
const NEXT_STEP_LABEL = {
    verified: "Verify creator",
    commercial_agreed: "Agree fee",
    slot_booked: "Book slot",
    attended: "Mark attended",
    in_payment: "Start payment",
};

const KIND_META = {
    payment: { label: "Payout", Icon: Wallet, band: 0 },
    // Above the pipeline work: a creator is literally waiting on a reply, and
    // a question aged three days answers itself — they went elsewhere.
    question: { label: "Question", Icon: MessageCircleQuestion, band: 0.5 },
    collaboration: { label: "Collaboration", Icon: Users, band: 1 },
    campaign: { label: "Campaign", Icon: Sparkles, band: 2 },
    brand: { label: "Brand", Icon: Building2, band: 3 },
    creator: { label: "Creator", Icon: BadgeCheck, band: 4 },
};

const KINDS = ["payment", "question", "collaboration", "campaign", "brand", "creator"];

// The queue's own order is the point of the screen, so "priority" is the
// default sort rather than a column somebody has to find.
const DEFAULTS = { sort: { key: "kind", dir: "asc" } };

export default function ActionQueue({ onChanged, feePercent }) {
    const [items, setItems] = useState(null);
    const [waiting, setWaiting] = useState([]);
    const [kind, setKind] = useState("");
    const [showWaiting, setShowWaiting] = useState(false);
    const [busyId, setBusyId] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [confirm, setConfirm] = useState(null);
    const [advance, setAdvance] = useState(null);
    const [focused, setFocused] = useState(-1);
    const [peekId, setPeekId] = useState(null);
    const { state, patch, scrollRef } = useListState("queue", DEFAULTS);
    const { sort } = state;
    const navigate = useNavigate();

    const load = useCallback(async () => {
        setItems(null);
        try {
            const [brands, campaigns, creators, changed, board, questions] = await Promise.all([
                api.get("/admin/brands/pending"),
                api.get("/admin/campaigns/pending"),
                api.get("/admin/creators/pending"),
                // Verified creators who edited something material — still live
                // to brands, still a decision waiting on us.
                api.get("/admin/creators/changed"),
                api.get("/admin/collaborations"),
                // Threads whose last word is a creator's.
                api.get("/questions/unanswered"),
            ]);

            const rows = [];

            for (const q of questions.data) {
                rows.push({
                    id: `question-${q.campaign_id}-${q.creator_id}`,
                    kind: "question",
                    since: q.asked_at,
                    primary: `“${q.body?.length > 120 ? q.body.slice(0, 120) + "…" : q.body}”`,
                    secondary: [q.creator_name, q.campaign_title, q.brand_name]
                        .filter(Boolean)
                        .join(" · "),
                    note: q.execution_owner === "weare" ? "Ours to answer" : "Brand-run — nudge or answer",
                    link: `/admin/campaigns/${q.campaign_id}`,
                    raw: q,
                });
            }

            for (const b of brands.data) {
                // A brand we already refused is not waiting on us.
                if (b.verification_state === "rejected") continue;
                rows.push({
                    id: `brand-${b.user_id}`,
                    kind: "brand",
                    since: b.signed_up_at || b.created_at,
                    primary: b.business_name || b.name || "Unnamed brand",
                    secondary: [b.category, b.email || b.phone].filter(Boolean).join(" · "),
                    note:
                        b.campaigns_awaiting_review > 0
                            ? `${b.campaigns_awaiting_review} brief(s) queued behind this`
                            : null,
                    raw: b,
                });
            }

            for (const c of campaigns.data) {
                rows.push({
                    id: `campaign-${c.id}`,
                    kind: "campaign",
                    since: c.submitted_for_review_at || c.created_at,
                    primary: c.title,
                    secondary: [
                        c.brand_name || "Unknown brand",
                        c.budget_per_creator != null ? `₹${formatRupees(c.budget_per_creator)}` : null,
                        c.area,
                    ]
                        .filter(Boolean)
                        .join(" · "),
                    note: c.brand_verified ? null : "Brand isn't verified — approve them first",
                    blocked: !c.brand_verified,
                    raw: c,
                });
            }

            for (const c of [...creators.data, ...changed.data]) {
                const edited = changed.data.includes(c);
                rows.push({
                    id: `creator-${c.user_id}`,
                    note: edited ? "Edited since approval — re-check what changed" : null,
                    kind: "creator",
                    since: c.created_at,
                    primary: c.name || "Unnamed creator",
                    secondary: [
                        c.instagram_handle ? `@${c.instagram_handle}` : null,
                        c.city,
                        typeof c.follower_count === "number"
                            ? `${c.follower_count.toLocaleString("en-IN")} followers`
                            : null,
                    ]
                        .filter(Boolean)
                        .join(" · "),
                    raw: c,
                });
            }

            const byState = board.data.by_state || {};
            const stillWaiting = [];
            for (const [state, list] of Object.entries(byState)) {
                for (const row of list) {
                    const isPayout = state === "in_payment" && row.payment?.state === "pending";
                    if (isPayout) {
                        rows.push({
                            id: `payment-${row.payment.id}`,
                            kind: "payment",
                            since: row.updated_at || row.created_at,
                            primary: `₹${formatRupees(row.payment.creator_payout)} to ${
                                row.creator?.name || "creator"
                            }`,
                            secondary: [row.campaign?.title, row.brand_name]
                                .filter(Boolean)
                                .join(" · "),
                            raw: row,
                        });
                        continue;
                    }
                    if (ADMIN_ACTION_STATES.includes(state) && row.can_advance) {
                        rows.push({
                            id: `collab-${row.id}`,
                            kind: "collaboration",
                            since: row.updated_at || row.created_at,
                            primary: row.creator?.name || "Creator",
                            secondary: [row.campaign?.title, row.brand_name]
                                .filter(Boolean)
                                .join(" · "),
                            state,
                            raw: row,
                        });
                        continue;
                    }
                    // Everything else in flight: not ours to move, but losing
                    // sight of it entirely is how a collaboration stalls.
                    if (!["closed", "declined", "cancelled"].includes(state)) {
                        stillWaiting.push({ ...row, state });
                    }
                }
            }

            rows.sort((a, b) => {
                const band = KIND_META[a.kind].band - KIND_META[b.kind].band;
                if (band !== 0) return band;
                return new Date(a.since || 0) - new Date(b.since || 0);
            });
            stillWaiting.sort(
                (a, b) => new Date(a.updated_at || 0) - new Date(b.updated_at || 0),
            );

            setItems(rows);
            setWaiting(stillWaiting);
        } catch (e) {
            notifyError(e);
            setItems([]);
            setWaiting([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const run = useCallback(
        async (item, fn, successMessage) => {
            setBusyId(item.id);
            setSubmitting(true);
            try {
                await fn();
                notifySuccess(successMessage);
                setConfirm(null);
                setAdvance(null);
                await load();
                onChanged?.();
            } catch (e) {
                notifyError(e);
                // A 409 means somebody else moved it — the list is stale either way.
                if (e?.response?.status === 409) await load();
            } finally {
                setBusyId(null);
                setSubmitting(false);
            }
        },
        [load, onChanged],
    );

    // --- the actions themselves -------------------------------------------

    const approve = useCallback((item) => {
        const { kind: k, raw } = item;
        if (k === "brand") {
            return run(item, () => api.post(`/admin/brands/${raw.user_id}/verify`), "Brand verified");
        }
        if (k === "creator") {
            return run(
                item,
                () => api.post(`/admin/creators/${raw.user_id}/approve`),
                "Creator verified",
            );
        }
        if (k === "campaign") {
            return run(
                item,
                () => api.post(`/admin/campaigns/${raw.id}/approve`),
                "Campaign approved — it's live",
            );
        }
        if (k === "collaboration") {
            const next = raw.next_state;
            // Three steps need a number or a date first; the rest are a click.
            if (["commercial_agreed", "in_payment", "slot_booked"].includes(next)) {
                setAdvance({ item, mode: next });
                return undefined;
            }
            return run(
                item,
                () =>
                    api.post(`/admin/collaborations/${raw.id}/advance`, {
                        from_state: raw.state,
                    }),
                "Moved forward",
            );
        }
        if (k === "payment") {
            setConfirm({
                item,
                kicker: "Release payout",
                title: `Record ₹${formatRupees(raw.payment.creator_payout)} as paid?`,
                description:
                    "This asserts the money already left the bank — it doesn't move it. The collaboration closes and the creator is told.",
                reasonLabel: "Note",
                placeholder: "e.g. Paid in the 4pm batch",
                confirmLabel: "Record payout",
                extra: {
                    name: "payment_reference",
                    label: "Payment reference",
                    placeholder: "UTR or transaction id",
                    required: true,
                },
                onSubmit: (body) =>
                    run(
                        item,
                        () =>
                            api.post(`/admin/payments/${raw.payment.id}/mark_paid`, {
                                payment_reference: body.payment_reference,
                            }),
                        "Payout recorded — collaboration closed",
                    ),
            });
        }
        return undefined;
    }, [run]);

    const reject = useCallback((item) => {
        const { kind: k, raw } = item;
        const config = {
            brand: {
                kicker: "Reject brand",
                title: `Reject ${raw.business_name || "this brand"}?`,
                description:
                    "They're told why, any briefs of theirs waiting for review go back to draft, and they can't submit until we verify them.",
                confirmLabel: "Reject brand",
                request: (body) => api.post(`/admin/brands/${raw.user_id}/reject`, body),
                success: "Brand rejected",
            },
            creator: {
                kicker: "Reject creator",
                title: `Reject ${raw.name || "this creator"}?`,
                description: "They're told why, and briefs stay closed to them until we approve.",
                confirmLabel: "Reject creator",
                request: (body) => api.post(`/admin/creators/${raw.user_id}/reject`, body),
                success: "Creator rejected",
            },
            campaign: {
                kicker: "Send back",
                title: `Send “${raw.title}” back?`,
                description:
                    "It returns to the brand as a draft with your reason attached, so they can fix it and resubmit.",
                confirmLabel: "Send back",
                request: (body) => api.post(`/admin/campaigns/${raw.id}/reject`, body),
                success: "Sent back to the brand",
            },
            collaboration: {
                kicker: "End collaboration",
                title: "Cancel this collaboration?",
                description:
                    "The creator is told, and any pending payout is voided. Use Revert instead if you only need to redo the last step.",
                confirmLabel: "Cancel collaboration",
                request: (body) => api.post(`/admin/collaborations/${raw.id}/cancel`, body),
                success: "Collaboration cancelled",
            },
        }[k];
        if (!config) return;
        setConfirm({
            item,
            destructive: true,
            placeholder: "What should they know?",
            ...config,
            onSubmit: (body) => run(item, () => config.request(body), config.success),
        });
    }, [run]);

    const revert = useCallback((item) => {
        const { raw } = item;
        setConfirm({
            item,
            kicker: "Step back",
            title: `Move back to ${(raw.state || "").replace(/_/g, " ")}'s previous step?`,
            description:
                "The collaboration goes back one state so the last step can be redone. A pending payout is voided and recreated when you move forward again.",
            confirmLabel: "Revert one step",
            placeholder: "e.g. Agreed the wrong fee",
            onSubmit: (body) =>
                run(item, () => api.post(`/admin/collaborations/${raw.id}/revert`, body), "Stepped back"),
        });
    }, [run]);

    // --- rendering ---------------------------------------------------------

    const counts = useMemo(() => {
        const out = {};
        for (const k of KINDS) out[k] = 0;
        for (const i of items || []) out[i.kind] += 1;
        return out;
    }, [items]);

    const visible = useMemo(
        () => (items || []).filter((i) => !kind || i.kind === kind),
        [items, kind],
    );

    /**
     * The columns.
     *
     * The queue is already ordered by what it costs to leave a thing — money,
     * then a creator waiting on a reply, then stalled work, then people who
     * cannot start. That order is the screen's argument, so it is the default
     * sort and the "Priority" column is what expresses it; sorting by age is
     * still one click away when the question is "what is oldest".
     */
    const columns = useMemo(
        () => [
            {
                key: "kind",
                header: "Kind",
                sortable: true,
                width: "w-40",
                value: (i) => KIND_META[i.kind].band,
                cell: (i) => {
                    const meta = KIND_META[i.kind];
                    return (
                        <span
                            data-testid={IDS.rowKind(i.id)}
                            className="inline-flex items-center gap-2 whitespace-nowrap text-muted-foreground"
                        >
                            <meta.Icon className="h-3.5 w-3.5 shrink-0" />
                            {meta.label}
                        </span>
                    );
                },
            },
            {
                key: "primary",
                header: "Waiting on you",
                sortable: true,
                value: (i) => String(i.primary || ""),
                cell: (i) => (
                    <span className="flex min-w-0 flex-col">
                        <span data-testid={IDS.rowPrimary(i.id)} className="truncate">
                            {i.primary}
                        </span>
                        {/* The note is why this row is not simply "approve" —
                            a blocked campaign, a re-check, briefs queued behind
                            a brand. It belongs on the row, not in a panel
                            somebody has to open to find out. */}
                        {i.note && (
                            <span className={`truncate ${TEXT.meta} text-ember-500`}>{i.note}</span>
                        )}
                    </span>
                ),
            },
            {
                key: "secondary",
                header: "Detail",
                hideBelow: true,
                cell: (i) => (
                    <span
                        data-testid={IDS.rowSecondary(i.id)}
                        className="block truncate text-muted-foreground"
                    >
                        {i.secondary}
                    </span>
                ),
            },
            {
                key: "state",
                header: "State",
                width: "w-36",
                hideBelow: true,
                cell: (i) => (i.state ? <StatusTag state={i.state} /> : null),
            },
            {
                key: "since",
                header: "Age",
                sortable: true,
                numeric: true,
                width: "w-28",
                value: (i) => new Date(i.since || 0).getTime() || null,
                cell: (i) => (
                    <span
                        data-testid={IDS.rowAge(i.id)}
                        // Overdue is the one place a row changes colour: it is
                        // a fact about this row, not a category of row.
                        className={`whitespace-nowrap ${isStale(i.since) ? "text-ember-500" : ""}`}
                        title={isStale(i.since) ? "Overdue" : undefined}
                    >
                        <TimeAgo iso={i.since} />
                        {isStale(i.since) ? " !" : ""}
                    </span>
                ),
            },
            {
                key: "decision",
                header: "",
                width: "w-44",
                cell: (i) => (
                    <span className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                        {i.kind === "question" ? (
                            // Not an approve/reject: the reply box lives on the
                            // campaign page's threads panel, one click away.
                            <Link
                                to={i.link}
                                data-testid={IDS.row(i.id) + "-answer"}
                                className={`inline-flex items-center gap-1 whitespace-nowrap rounded border border-ember-500/40 bg-ember-500/10 px-2 py-0.5 ${TEXT.meta} text-ember-500 ${CALM} hover:bg-ember-500/20 ${FOCUS}`}
                            >
                                Answer
                                <ArrowRight className="h-3 w-3" />
                            </Link>
                        ) : (
                            <>
                                {i.kind !== "payment" && (
                                    <RowButton
                                        tone="bad"
                                        disabled={busyId === i.id}
                                        onClick={() => reject(i)}
                                        testid={IDS.rowSecondaryAction(i.id)}
                                    >
                                        {i.kind === "collaboration" ? "Cancel" : "Reject"}
                                    </RowButton>
                                )}
                                <RowButton
                                    tone="primary"
                                    disabled={busyId === i.id || i.blocked}
                                    onClick={() => approve(i)}
                                    testid={IDS.rowPrimaryAction(i.id)}
                                    title={i.blocked ? "Verify the brand first" : undefined}
                                >
                                    {nextLabelFor(i)}
                                </RowButton>
                            </>
                        )}
                    </span>
                ),
            },
        ],
        [approve, reject, busyId],
    );

    const rows = useMemo(() => sortRows(visible, columns, sort), [visible, columns, sort]);
    const peek = useMemo(() => rows.find((i) => i.id === peekId) || null, [rows, peekId]);

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
        // A on a question would be an approval of something nobody approves;
        // the row's own action is a link, and the keyboard follows it.
        onApprove: (i) => {
            const item = rows[i];
            if (!item || item.blocked) return;
            if (item.kind === "question") navigate(item.link);
            else approve(item);
        },
        onReject: (i) => {
            const item = rows[i];
            if (item && item.kind !== "payment" && item.kind !== "question") reject(item);
        },
        onEscape: () => (peekId ? setPeekId(null) : setFocused(-1)),
        enabled: !confirm && !advance,
    });

    const total = items?.length ?? 0;

    return (
        <section data-testid={IDS.section}>
            <header className="mb-3">
                <h1 className={TEXT.heading}>
                    {total === 0 && items ? "Nothing waiting on you." : "Waiting on you"}
                </h1>
                <p data-testid={IDS.count} className={`${TEXT.meta} text-muted-foreground`}>
                    {items ? `${rows.length} of ${total} · most costly first` : "Loading…"}
                </p>
            </header>

            {items && total > 0 && (
                <div
                    data-testid={IDS.stats}
                    className={`mb-3 flex flex-wrap items-center gap-1.5 ${PANEL} ${DENSITY.row}`}
                >
                    <KindChip
                        on={!kind}
                        onClick={() => setKind("")}
                        testid={IDS.filter("all")}
                        label={`All ${total}`}
                    />
                    {KINDS.filter((k) => counts[k] > 0).map((k) => (
                        <KindChip
                            key={k}
                            on={kind === k}
                            onClick={() => setKind(kind === k ? "" : k)}
                            testid={IDS.filter(k)}
                            Icon={KIND_META[k].Icon}
                            label={`${KIND_META[k].label} ${counts[k]}`}
                        />
                    ))}
                </div>
            )}

            <DataTable
                columns={columns}
                rows={rows}
                rowKey={(i) => i.id}
                rowTestId={(i) => IDS.row(i.id)}
                sort={sort}
                onSortChange={(s) => patch({ sort: s })}
                focused={focused}
                onFocus={setFocused}
                onOpen={openPeek}
                loading={!items}
                scrollRef={scrollRef}
                testid={IDS.list}
                empty={
                    <ListEmptyState
                        Icon={CheckCircle2}
                        testid={IDS.empty}
                        filtered={Boolean(kind)}
                        onClearFilters={() => setKind("")}
                        emptyTitle="Inbox zero."
                        emptyBody="Nothing is waiting on a decision from you."
                        filteredTitle="Nothing of that kind is waiting."
                        filteredBody="Clear the filter to see the rest of the queue."
                        clearLabel="Show everything"
                    />
                }
            />

            {/* In flight, waiting on somebody else. Folded shut because it is
                not a to-do list — but kept, because losing sight of a stalled
                collaboration entirely is how one stalls for a fortnight. */}
            {waiting.length > 0 && (
                <div className="mt-6">
                    <button
                        type="button"
                        onClick={() => setShowWaiting((v) => !v)}
                        aria-expanded={showWaiting}
                        data-testid={IDS.showWaiting}
                        className={`${TEXT.meta} ${CALM} text-muted-foreground hover:text-ember-500 ${FOCUS}`}
                    >
                        {showWaiting ? "Hide" : "Show"} {waiting.length} in flight, waiting on
                        somebody else
                    </button>

                    {showWaiting && (
                        <ul
                            data-testid={IDS.waitingList}
                            className={`mt-2 divide-y divide-white/5 ${PANEL}`}
                        >
                            {waiting.map((row) => (
                                <li
                                    key={row.id}
                                    className={`flex items-center justify-between gap-4 ${DENSITY.row} ${ROW_H}`}
                                >
                                    <span className="min-w-0">
                                        <span className={`block truncate ${TEXT.body}`}>
                                            {row.creator?.name || "Creator"}
                                        </span>
                                        <span className={`block truncate ${TEXT.meta} text-muted-foreground`}>
                                            {row.campaign?.title || "—"}
                                            {row.brand_name ? ` · ${row.brand_name}` : ""}
                                        </span>
                                    </span>
                                    <span className="flex flex-none items-center gap-3">
                                        <span className={`${TEXT.meta} text-muted-foreground`}>
                                            <TimeAgo iso={row.updated_at} />
                                        </span>
                                        <StatusTag state={row.state} />
                                    </span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            <PeekPanel
                open={Boolean(peek)}
                onOpenChange={(o) => !o && setPeekId(null)}
                title={peek ? String(peek.primary) : "Waiting"}
                subtitle={peek?.secondary}
                href={peek?.link}
                actions={
                    peek && peek.kind !== "question" ? (
                        <>
                            {(peek.kind === "collaboration" || peek.kind === "payment") && (
                                <PeekButton
                                    disabled={busyId === peek.id}
                                    onClick={() => revert(peek)}
                                    testid={ADMIN_PEEK.action("revert")}
                                >
                                    <Undo2 className="h-3.5 w-3.5" />
                                    Revert
                                </PeekButton>
                            )}
                            {peek.kind !== "payment" && (
                                <PeekButton
                                    tone="bad"
                                    disabled={busyId === peek.id}
                                    onClick={() => reject(peek)}
                                    testid={ADMIN_PEEK.action("reject")}
                                >
                                    <XCircle className="h-3.5 w-3.5" />
                                    {peek.kind === "collaboration" ? "Cancel" : "Reject"}
                                </PeekButton>
                            )}
                            <PeekButton
                                tone="primary"
                                disabled={busyId === peek.id || peek.blocked}
                                onClick={() => approve(peek)}
                                testid={ADMIN_PEEK.action("approve")}
                            >
                                {peek.kind === "payment" ? (
                                    <IndianRupee className="h-3.5 w-3.5" />
                                ) : (
                                    <ArrowRight className="h-3.5 w-3.5" />
                                )}
                                {nextLabelFor(peek)}
                            </PeekButton>
                        </>
                    ) : null
                }
            >
                {peek && (
                    <div>
                        <PeekField label="Kind">{KIND_META[peek.kind].label}</PeekField>
                        {peek.state && (
                            <PeekField label="State">
                                <StatusTag state={peek.state} chip />
                            </PeekField>
                        )}
                        <PeekField label="Waiting">
                            <TimeAgo iso={peek.since} />
                            {isStale(peek.since) ? " · overdue" : ""}
                        </PeekField>
                        <PeekField label="Detail">{peek.secondary}</PeekField>
                        {peek.note && (
                            <p className={`mt-3 rounded border border-ember-500/25 bg-ember-500/5 p-3 ${TEXT.body} text-ember-500`}>
                                {peek.note}
                            </p>
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
                reasonLabel={confirm?.reasonLabel}
                placeholder={confirm?.placeholder}
                confirmLabel={confirm?.confirmLabel}
                destructive={confirm?.destructive}
                extra={confirm?.extra}
                onSubmit={(body) => confirm?.onSubmit(body)}
            />

            <AdvanceDialog
                open={Boolean(advance)}
                onOpenChange={(v) => !v && setAdvance(null)}
                mode={advance?.mode}
                collab={advance?.item?.raw}
                submitting={submitting}
                feePercent={feePercent}
                onSubmit={(body) =>
                    run(
                        advance.item,
                        () =>
                            api.post(`/admin/collaborations/${advance.item.raw.id}/advance`, {
                                ...body,
                                from_state: advance.item.raw.state,
                            }),
                        "Moved forward",
                    )
                }
            />
        </section>
    );
}

/** What the primary action on this row is actually called. */
function nextLabelFor(item) {
    if (item.kind === "collaboration") {
        return NEXT_STEP_LABEL[item.raw.next_state] || "Move forward";
    }
    return item.kind === "payment" ? "Record payout" : "Approve";
}

/** One kind of thing, and how many of them are waiting. */
function KindChip({ on, onClick, testid, Icon, label }) {
    return (
        <button
            type="button"
            aria-pressed={on}
            onClick={onClick}
            data-testid={testid}
            className={
                `inline-flex h-7 items-center gap-1.5 rounded border px-2 ${TEXT.meta} ${CALM} ${FOCUS} ` +
                (on
                    ? "border-ember-500 bg-ember-500/10 text-ember-500"
                    : "border-white/10 text-muted-foreground hover:border-white/25 hover:text-foreground")
            }
        >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {label}
        </button>
    );
}
