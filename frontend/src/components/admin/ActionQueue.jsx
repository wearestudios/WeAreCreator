// The landing screen: one list of everything waiting on us, whatever kind of
// thing it is. Five queues used to be five places to look, which is how a
// creator ends up waiting a week for a decision nobody knew was theirs.
//
// Ordered by what it costs to leave it: money owed first, then work already in
// flight that has stalled, then people who cannot start until we act. Age is
// the tie-break inside each band, and anything past two days is marked so it
// stops blending in.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
    ArrowRight,
    BadgeCheck,
    Building2,
    CheckCircle2,
    IndianRupee,
    Sparkles,
    Undo2,
    Users,
    Wallet,
    XCircle,
} from "lucide-react";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ADMIN_QUEUE as IDS } from "@/constants/testIds";
import { AdvanceDialog, ConfirmDialog } from "./dialogs";
import {
    EmptyState,
    ListSkeleton,
    SectionHeader,
    StatePill,
    formatRupees,
    isStale,
    timeAgo,
} from "./shared";

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
    collaboration: { label: "Collaboration", Icon: Users, band: 1 },
    campaign: { label: "Campaign", Icon: Sparkles, band: 2 },
    brand: { label: "Brand", Icon: Building2, band: 3 },
    creator: { label: "Creator", Icon: BadgeCheck, band: 4 },
};

const KINDS = ["payment", "collaboration", "campaign", "brand", "creator"];

export default function ActionQueue({ onChanged, feePercent }) {
    const [items, setItems] = useState(null);
    const [waiting, setWaiting] = useState([]);
    const [kind, setKind] = useState("");
    const [showWaiting, setShowWaiting] = useState(false);
    const [busyId, setBusyId] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [confirm, setConfirm] = useState(null);
    const [advance, setAdvance] = useState(null);

    const load = useCallback(async () => {
        setItems(null);
        try {
            const [brands, campaigns, creators, changed, board] = await Promise.all([
                api.get("/admin/brands/pending"),
                api.get("/admin/campaigns/pending"),
                api.get("/admin/creators/pending"),
                // Verified creators who edited something material — still live
                // to brands, still a decision waiting on us.
                api.get("/admin/creators/changed"),
                api.get("/admin/collaborations"),
            ]);

            const rows = [];

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
            toast.error(formatApiError(e));
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
                toast.success(successMessage);
                setConfirm(null);
                setAdvance(null);
                await load();
                onChanged?.();
            } catch (e) {
                toast.error(formatApiError(e));
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

    const approve = (item) => {
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
    };

    const reject = (item) => {
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
    };

    const revert = (item) => {
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
    };

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

    const total = items?.length ?? 0;

    return (
        <section data-testid={IDS.section}>
            <SectionHeader
                kicker="Action queue"
                title={total === 0 && items ? "Nothing waiting on you." : "Waiting on you"}
                blurb="Everything that needs a decision, most costly first. Clear it here — you shouldn't need to go looking."
                onRefresh={load}
                refreshTestId={IDS.refresh}
            />

            {items && total > 0 && (
                <div
                    data-testid={IDS.stats}
                    className="mt-8 flex flex-wrap items-center gap-2"
                >
                    <button
                        type="button"
                        aria-pressed={!kind}
                        onClick={() => setKind("")}
                        data-testid={IDS.filter("all")}
                        className={
                            "rounded-full border px-3 py-1.5 text-xs uppercase tracking-[0.15em] transition-colors duration-200 " +
                            (!kind
                                ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                : "border-white/10 text-muted-foreground hover:border-white/25 hover:text-foreground")
                        }
                    >
                        All {total}
                    </button>
                    {KINDS.filter((k) => counts[k] > 0).map((k) => {
                        const meta = KIND_META[k];
                        const on = kind === k;
                        return (
                            <button
                                key={k}
                                type="button"
                                aria-pressed={on}
                                onClick={() => setKind(on ? "" : k)}
                                data-testid={IDS.filter(k)}
                                className={
                                    "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs uppercase tracking-[0.15em] transition-colors duration-200 " +
                                    (on
                                        ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                        : "border-white/10 text-muted-foreground hover:border-white/25 hover:text-foreground")
                                }
                            >
                                <meta.Icon className="h-3.5 w-3.5" />
                                {meta.label} {counts[k]}
                            </button>
                        );
                    })}
                </div>
            )}

            <div className="mt-6 rounded-md border border-white/10 bg-card grain-surface">
                {!items ? (
                    <ListSkeleton rows={6} testid={IDS.skeleton} />
                ) : visible.length === 0 ? (
                    <EmptyState testid={IDS.empty} Icon={CheckCircle2}>
                        {total === 0
                            ? "Inbox zero. Nothing is waiting on a decision from you."
                            : "Nothing of that kind is waiting."}
                    </EmptyState>
                ) : (
                    <ul data-testid={IDS.list} className="divide-y divide-white/10">
                        {visible.map((item) => (
                            <QueueRow
                                key={item.id}
                                item={item}
                                busy={busyId === item.id}
                                onApprove={approve}
                                onReject={reject}
                                onRevert={revert}
                            />
                        ))}
                    </ul>
                )}
            </div>

            {items && (
                <p
                    data-testid={IDS.count}
                    className="mt-4 text-xs uppercase tracking-[0.18em] text-muted-foreground"
                >
                    {visible.length} of {total} shown
                </p>
            )}

            {waiting.length > 0 && (
                <div className="mt-10">
                    <button
                        type="button"
                        onClick={() => setShowWaiting((v) => !v)}
                        aria-expanded={showWaiting}
                        data-testid={IDS.showWaiting}
                        className="text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                    >
                        {showWaiting ? "Hide" : "Show"} {waiting.length} in flight, waiting on
                        somebody else
                    </button>

                    {showWaiting && (
                        <ul
                            data-testid={IDS.waitingList}
                            className="mt-4 divide-y divide-white/10 rounded-md border border-white/10 bg-card grain-surface"
                        >
                            {waiting.map((row) => (
                                <li
                                    key={row.id}
                                    className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-6"
                                >
                                    <div className="min-w-0">
                                        <p className="truncate text-sm">
                                            {row.creator?.name || "Creator"}
                                        </p>
                                        <p className="truncate text-xs text-muted-foreground">
                                            {row.campaign?.title || "—"}
                                            {row.brand_name ? ` · ${row.brand_name}` : ""}
                                        </p>
                                    </div>
                                    <div className="flex flex-none items-center gap-3">
                                        <span className="text-xs text-muted-foreground">
                                            {timeAgo(row.updated_at)}
                                        </span>
                                        <StatePill state={row.state} />
                                    </div>
                                </li>
                            ))}
                        </ul>
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

function QueueRow({ item, busy, onApprove, onReject, onRevert }) {
    const meta = KIND_META[item.kind];
    const stale = isStale(item.since);
    const collab = item.kind === "collaboration";
    const nextLabel = collab
        ? NEXT_STEP_LABEL[item.raw.next_state] || "Move forward"
        : item.kind === "payment"
        ? "Record payout"
        : "Approve";

    return (
        <li
            data-testid={IDS.row(item.id)}
            className="flex flex-col gap-4 px-5 py-4 md:flex-row md:items-center md:gap-6"
        >
            <div className="flex min-w-0 flex-1 items-start gap-3">
                <meta.Icon className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
                <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span
                            data-testid={IDS.rowKind(item.id)}
                            className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground"
                        >
                            {meta.label}
                        </span>
                        {collab && <StatePill state={item.state} />}
                        <span
                            data-testid={IDS.rowAge(item.id)}
                            className={
                                "text-[10px] uppercase tracking-[0.18em] " +
                                (stale ? "text-ember-500" : "text-muted-foreground")
                            }
                        >
                            {timeAgo(item.since)}
                            {stale ? " · overdue" : ""}
                        </span>
                    </div>
                    <p
                        data-testid={IDS.rowPrimary(item.id)}
                        className="mt-1 truncate text-sm text-foreground"
                    >
                        {item.primary}
                    </p>
                    {item.secondary && (
                        <p
                            data-testid={IDS.rowSecondary(item.id)}
                            className="mt-0.5 truncate text-xs text-muted-foreground"
                        >
                            {item.secondary}
                        </p>
                    )}
                    {item.note && (
                        <p className="mt-1.5 text-xs text-ember-500">{item.note}</p>
                    )}
                </div>
            </div>

            <div className="flex flex-none flex-wrap items-center gap-2 md:justify-end">
                {(collab || item.kind === "payment") && (
                    <Button
                        type="button"
                        variant="outline"
                        disabled={busy}
                        onClick={() => onRevert(item)}
                        className="h-8 rounded-full border-white/15 bg-transparent px-3 text-xs hover:bg-white/5"
                    >
                        <Undo2 className="mr-1.5 h-3.5 w-3.5" />
                        Revert
                    </Button>
                )}
                {item.kind !== "payment" && (
                    <Button
                        type="button"
                        variant="outline"
                        disabled={busy}
                        onClick={() => onReject(item)}
                        className="h-8 rounded-full border-red-500/30 bg-transparent px-3 text-xs text-red-300 hover:bg-red-500/10 hover:text-red-200"
                    >
                        <XCircle className="mr-1.5 h-3.5 w-3.5" />
                        {collab ? "Cancel" : "Reject"}
                    </Button>
                )}
                <Button
                    type="button"
                    disabled={busy || item.blocked}
                    onClick={() => onApprove(item)}
                    title={item.blocked ? "Verify the brand first" : undefined}
                    className="h-8 rounded-full bg-ember-500 px-4 text-xs text-black hover:bg-ember-400 disabled:opacity-40"
                >
                    {item.kind === "payment" ? (
                        <IndianRupee className="mr-1.5 h-3.5 w-3.5" />
                    ) : (
                        <ArrowRight className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    {nextLabel}
                </Button>
            </div>
        </li>
    );
}
