// One application, at /admin/collaborations/:id.
//
// The lifecycle is the point of this page. A collaboration is a sequence of
// states somebody moved it through, and the question asked about it later is
// almost always "who agreed that, and when" — so the timeline is drawn from the
// audit log, which is the record that already answers it.
//
// The steps still ahead are drawn as well as the ones behind. A page that shows
// only what has happened makes you remember what comes next; showing the whole
// run makes the next move obvious.
import React, { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Check, ExternalLink, Circle, IndianRupee } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { WorkNotes } from "@/components/brand/WorkNotes";
import {
    ADMIN_COLLAB_PAGE as IDS,
    ADMIN_DETAIL as DIDS,
} from "@/constants/testIds";
import {
    DetailShell,
    Field,
    Panel,
    Section,
    Stat,
} from "@/components/admin/DetailPage";
import {
    STATE_META,
    StatePill,
    formatDateTime,
    formatRupees,
} from "@/components/admin/shared";
import { AdvanceDialog, ConfirmDialog } from "@/components/admin/dialogs";
import { CampaignLink, CreatorLink } from "@/components/admin/links";
import { PerformancePanel } from "@/components/admin/Performance";
import DisputePanel from "@/components/DisputePanel";
import { INVOICE } from "@/constants/testIds";
import { TEXT } from "./console/tokens";
import { useAdminConsole } from "@/pages/AdminConsole";

// The transitions that need something typed before they can happen. Everything
// else is a straight advance.
const NEEDS_INPUT = ["commercial_agreed", "slot_booked", "in_payment"];

// What the brand owes us, in the three words a person would use. The stored
// values are `pending` / `sent` / `settled`; `void` exists too and is written
// only by the refund path, so it is readable here and not settable.
const INVOICE_WORDS = {
    pending: "Not invoiced",
    sent: "Issued",
    settled: "Paid",
    void: "Written off",
};

const INVOICE_STATES = [
    { value: "sent", label: "Mark issued", done: "Invoice issued" },
    { value: "settled", label: "Mark paid", done: "Invoice settled" },
    { value: "pending", label: "Withdraw it", done: "Invoice withdrawn" },
];

export default function CollaborationDetailPage() {
    const { id } = useParams();
    const { reloadCounts, feePercent, allAccess } = useAdminConsole();

    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [notFound, setNotFound] = useState(false);
    const [busy, setBusy] = useState(null);
    const [dialog, setDialog] = useState({ kind: null });

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/admin/collaborations/${id}`);
            setData(data);
            setError("");
        } catch (err) {
            if (err?.response?.status === 404) setNotFound(true);
            else setError(formatApiError(err));
        }
    }, [id]);

    useEffect(() => {
        setData(null);
        setNotFound(false);
        load();
    }, [id, load]);

    const act = async (key, request, message) => {
        setBusy(key);
        try {
            await request();
            notifySuccess(message);
            setDialog({ kind: null });
            await load();
            reloadCounts?.();
        } catch (err) {
            notifyError(err, { onRetry: () => act(key, request, message) });
        } finally {
            setBusy(null);
        }
    };

    /** Where the invoice has got to. Marking it issued starts the clock the
     *  health panel and the publish block both read. */
    const setInvoice = (paymentId, row) =>
        act(
            `invoice-${row.value}`,
            () => api.post(`/admin/payments/${paymentId}/invoice_state`, {
                state: row.value,
            }),
            row.done
        );

    const collab = data?.collaboration;
    const payment = data?.payment;

    // Where this application sits in the run, so the steps can be drawn as
    // done / here / still ahead. A terminal state has no position — it left the
    // sequence rather than finishing it.
    const order = data?.state_order || [];
    const terminal = (data?.terminal_states || []).includes(collab?.state);
    const currentIndex = terminal ? -1 : order.indexOf(collab?.state);

    const advance = () => {
        const next = collab.next_state;
        if (NEEDS_INPUT.includes(next)) {
            setDialog({ kind: "advance", mode: next });
            return;
        }
        act(
            "advance",
            () => api.post(`/admin/collaborations/${id}/advance`, { to_state: next }),
            `Moved to ${STATE_META[next]?.label || next}`,
        );
    };

    return (
        <DetailShell
            testid={IDS.page}
            backTo="/admin/queue"
            backLabel="Back to the queue"
            crumbs={[
                { key: "console", label: "Console", to: "/admin" },
                { key: "campaigns", label: "Campaigns", to: "/admin/campaigns" },
                collab?.campaign?.id && {
                    key: "campaign",
                    label: collab.campaign.title || "Campaign",
                    to: `/admin/campaigns/${collab.campaign.id}`,
                },
                { key: "collab", label: collab?.creator?.name || "Application" },
            ]}
            kicker={
                [collab?.reference, collab?.brand_name || "Collaboration"]
                    .filter(Boolean)
                    .join(" · ")
            }
            title={collab?.creator?.name || "Collaboration"}
            loading={!data && !error && !notFound}
            error={error}
            notFound={notFound}
            notFoundMessage="This application doesn't exist, or it was removed."
            subtitle={
                collab && (
                    <>
                        <StatePill state={collab.state} />
                        <CampaignLink
                            id={collab.campaign?.id}
                            title={collab.campaign?.title}
                            testid={IDS.campaignLink}
                        />
                        <CreatorLink
                            id={collab.creator?.id}
                            name="Creator profile"
                            testid={IDS.creatorLink}
                        />
                    </>
                )
            }
            aside={
                collab && (
                    <>
                        {collab.can_advance && (
                            <Button
                                data-testid={DIDS.action("advance")}
                                disabled={busy === "advance"}
                                onClick={advance}
                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                {STATE_META[collab.next_state]?.label || "Advance"}
                            </Button>
                        )}
                        {collab.next_owner === "brand" && collab.next_state && (
                            // Saying why the button is missing beats leaving a
                            // gap where somebody expects one.
                            <span className="text-sm leading-relaxed text-muted-foreground">
                                {STATE_META[collab.next_state]?.label} is the brand's to do.
                            </span>
                        )}
                        {collab.state !== "closed" && !collab.can_advance && collab.can_cancel && (
                            <span className="text-sm text-muted-foreground">
                                Waiting on the creator.
                            </span>
                        )}
                        {collab.can_cancel && (
                            <>
                                <Button
                                    variant="outline"
                                    data-testid={DIDS.action("revert")}
                                    onClick={() => setDialog({ kind: "revert" })}
                                    className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                >
                                    Step back
                                </Button>
                                <Button
                                    variant="outline"
                                    data-testid={DIDS.action("cancel")}
                                    onClick={() => setDialog({ kind: "cancel" })}
                                    className="rounded-full border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10"
                                >
                                    Cancel
                                </Button>
                            </>
                        )}
                    </>
                )
            }
        >
            {data && (
                <>
                    {/* **Where the mediation is actually done.** The queue's
                        job is to get you here; deciding it needs the pitch,
                        the notes, the delivery and the amount in front of you,
                        which is exactly what this page has. The panel is the
                        same one both parties read — what differs is that this
                        caller is an admin, so the server sends them
                        `can_resolve_dispute` and neither of the other two. */}
                    <div className="mb-6">
                        <DisputePanel
                            collaborationId={id}
                            dispute={collab.dispute}
                            actions={{
                                can_resolve_dispute:
                                    allAccess && collab.dispute?.state === "open",
                            }}
                            onChanged={load}
                        />
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <Stat
                            testid={DIDS.stat("quoted")}
                            label="They quoted"
                            value={`₹${formatRupees(collab.quoted_rate)}`}
                        />
                        <Stat
                            testid={DIDS.stat("agreed")}
                            label="Agreed"
                            value={
                                collab.agreed_amount != null
                                    ? `₹${formatRupees(collab.agreed_amount)}`
                                    : "—"
                            }
                            highlight={collab.agreed_amount != null}
                        />
                        <Stat
                            testid={DIDS.stat("payout")}
                            label="Payout"
                            value={
                                payment
                                    ? `₹${formatRupees(payment.creator_payout)}`
                                    : "—"
                            }
                        />
                        <Stat
                            testid={DIDS.stat("payment-state")}
                            label="Payment"
                            value={payment?.state || "Not raised"}
                        />
                    </div>

                    <Section id="timeline" title="Lifecycle">
                        <Panel className="p-0">
                            <ol className="divide-y divide-white/10">
                                {order.map((state, i) => {
                                    const done = currentIndex >= 0 && i < currentIndex;
                                    const here = state === collab.state;
                                    // The audit entry that produced this state,
                                    // if there is one — the log records the
                                    // action, so the timeline can name who.
                                    const event = (data.timeline || []).find((e) =>
                                        (e.after || {}).state === state,
                                    );
                                    return (
                                        <li
                                            key={state}
                                            data-testid={IDS.step(state)}
                                            className={
                                                "flex flex-col gap-2 px-5 py-4 md:flex-row md:items-center md:gap-6 " +
                                                (here ? "bg-ember-500/[0.07]" : "")
                                            }
                                        >
                                            <span className="flex w-56 flex-none items-center gap-3">
                                                {done ? (
                                                    <Check className="h-4 w-4 flex-none text-emerald-400" />
                                                ) : here ? (
                                                    <span className="h-2 w-2 flex-none rounded-full bg-ember-500" />
                                                ) : (
                                                    <Circle className="h-3 w-3 flex-none text-muted-foreground/40" />
                                                )}
                                                <span
                                                    className={
                                                        "text-sm " +
                                                        (done || here
                                                            ? "text-foreground"
                                                            : "text-muted-foreground/60")
                                                    }
                                                >
                                                    {STATE_META[state]?.label || state}
                                                </span>
                                            </span>
                                            <span className="min-w-0 flex-1 text-sm text-muted-foreground">
                                                {event?.note || ""}
                                            </span>
                                            <span className="flex-none text-sm text-muted-foreground">
                                                {event
                                                    ? `${event.actor_name || "—"} · ${formatDateTime(event.created_at)}`
                                                    : ""}
                                            </span>
                                        </li>
                                    );
                                })}
                                {terminal && (
                                    <li
                                        data-testid={IDS.step(collab.state)}
                                        className="flex items-center gap-3 bg-red-500/[0.06] px-5 py-4"
                                    >
                                        <span className="h-2 w-2 flex-none rounded-full bg-red-400" />
                                        <span className="text-sm">
                                            {STATE_META[collab.state]?.label || collab.state}
                                        </span>
                                        {collab.exit_reason && (
                                            <span className="min-w-0 text-sm text-muted-foreground">
                                                {collab.exit_reason}
                                            </span>
                                        )}
                                    </li>
                                )}
                            </ol>
                        </Panel>
                    </Section>

                    <div className="grid gap-8 lg:grid-cols-2">
                        <Section id="slot" title="Slot">
                            <Panel data-testid={IDS.slot}>
                                {data.slot ? (
                                    <dl className="space-y-4">
                                        <Field label="When">
                                            {formatDateTime(data.slot.starts_at)}
                                            {data.slot.ends_at
                                                ? ` – ${formatDateTime(data.slot.ends_at)}`
                                                : ""}
                                        </Field>
                                        <Field label="Capacity">
                                            {data.slot.booked_count}/{data.slot.capacity}
                                        </Field>
                                        <Field label="Where">{collab.location_note}</Field>
                                    </dl>
                                ) : (
                                    <p className="text-sm leading-relaxed text-muted-foreground">
                                        No slot booked. The creator picks one once the fee is
                                        agreed.
                                    </p>
                                )}
                            </Panel>
                        </Section>

                        <Section id="content" title="Content">
                            <Panel data-testid={IDS.content}>
                                {collab.content_urls?.length ? (
                                    <ul className="space-y-3">
                                        {collab.content_urls.map((url) => (
                                            <li key={url}>
                                                <a
                                                    href={url}
                                                    target="_blank"
                                                    rel="noreferrer noopener"
                                                    className="inline-flex items-center gap-2 break-all text-sm text-ember-500 transition-colors duration-150 hover:text-ember-400"
                                                >
                                                    <ExternalLink className="h-3.5 w-3.5 flex-none" />
                                                    {url}
                                                </a>
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <p className="text-sm leading-relaxed text-muted-foreground">
                                        Nothing submitted yet.
                                    </p>
                                )}
                                {collab.revision_note && (
                                    <p className="mt-5 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-relaxed text-amber-200">
                                        Changes asked for: {collab.revision_note}
                                    </p>
                                )}
                            </Panel>
                        </Section>
                    </div>

                    {payment && (
                        <Section id="payment" title="Payment">
                            <Panel data-testid={IDS.payment}>
                                <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                                    <Field label="State">{payment.state}</Field>
                                    <Field label="Creator payout">
                                        ₹{formatRupees(payment.creator_payout)}
                                    </Field>
                                    <Field label="Platform fee">
                                        ₹{formatRupees(payment.platform_fee)}
                                    </Field>
                                    <Field label="Brand invoice">
                                        ₹{formatRupees(payment.brand_invoice_amount)}
                                    </Field>
                                    <Field label="Reference">{payment.reference}</Field>
                                    <Field label="Paid">
                                        {payment.paid_at ? formatDateTime(payment.paid_at) : "—"}
                                    </Field>
                                    <Field label="Invoice">
                                        <span data-testid={INVOICE.state}>
                                            {INVOICE_WORDS[payment.invoice_state] ||
                                                "Not invoiced"}
                                        </span>
                                        {/* Derived server-side and never
                                            recomputed here — the due date
                                            depends on the terms in force when
                                            the invoice went out, not on the
                                            terms today. */}
                                        {payment.invoice?.overdue && (
                                            <span
                                                data-testid={INVOICE.overdue}
                                                className={`ml-2 rounded bg-destructive/20 px-2 py-0.5 ${TEXT.meta} text-destructive-foreground`}
                                            >
                                                {payment.invoice.days_overdue}d overdue
                                            </span>
                                        )}
                                    </Field>
                                </dl>

                                {/* **Where the money owed to *us* is
                                    recorded.** The payout row above is what we
                                    pay the creator; this is what the brand
                                    pays us, and they are two different debts
                                    on one collaboration. Marking an invoice
                                    sent starts the clock the health panel and
                                    the publish block both read. */}
                                <div className="mt-4 flex flex-wrap gap-2">
                                    {INVOICE_STATES.map((row) => (
                                        <Button
                                            key={row.value}
                                            variant="outline"
                                            size="sm"
                                            disabled={
                                                busy === `invoice-${row.value}` ||
                                                payment.invoice_state === row.value
                                            }
                                            data-testid={INVOICE.set(row.value)}
                                            onClick={() => setInvoice(payment.id, row)}
                                            className="min-h-[2.75rem] border-white/20 bg-transparent sm:min-h-0"
                                        >
                                            {row.label}
                                        </Button>
                                    ))}
                                </div>
                                {payment.state !== "paid" && (
                                    <Button
                                        data-testid={DIDS.action("mark-paid")}
                                        onClick={() => setDialog({ kind: "mark-paid" })}
                                        className="mt-6 rounded-full bg-ember-500 text-black hover:bg-ember-400"
                                    >
                                        <IndianRupee className="mr-2 h-4 w-4" />
                                        Mark paid
                                    </Button>
                                )}
                            </Panel>
                        </Section>
                    )}

                    <Section id="performance" title="What the post did">
                        <PerformancePanel
                            collaborationId={id}
                            performance={data.performance}
                            delivered={(data.delivered_states || []).includes(collab.state)}
                            onSaved={load}
                        />
                    </Section>

                    <Section id="pitch" title="What they wrote">
                        <Panel>
                            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                                {collab.pitch || "No pitch."}
                            </p>
                        </Panel>
                    </Section>

                    <Section id="notes" title="Work notes">
                        {/* The same thread the brand and the assigned manager
                            see. Creators never do — the API refuses the role. */}
                        <WorkNotes
                            collaborationId={id}
                            agreedAmount={collab.agreed_amount}
                            quotedRate={collab.quoted_rate}
                            defaultOpen
                        />
                    </Section>
                </>
            )}

            <AdvanceDialog
                open={dialog.kind === "advance"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                mode={dialog.mode}
                collab={collab}
                feePercent={feePercent}
                submitting={busy === "advance"}
                onSubmit={(body) =>
                    act(
                        "advance",
                        () =>
                            api.post(`/admin/collaborations/${id}/advance`, {
                                to_state: dialog.mode,
                                ...body,
                            }),
                        `Moved to ${STATE_META[dialog.mode]?.label || dialog.mode}`,
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "revert"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Step back"
                title={collab?.creator?.name}
                description="Moves this application back one state. Say why — it goes in the audit log."
                confirmLabel="Step back"
                submitting={busy === "revert"}
                onSubmit={(body) =>
                    act(
                        "revert",
                        () => api.post(`/admin/collaborations/${id}/revert`, body),
                        "Stepped back",
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "cancel"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Cancel"
                title={collab?.creator?.name}
                description="Ends this collaboration. The creator is told, their slot is released, and this cannot be undone. How much notice this gives is recorded automatically — count back from the shoot before deciding on a fee."
                confirmLabel="Cancel it"
                destructive
                submitting={busy === "cancel"}
                extras={[
                    {
                        name: "kill_fee",
                        label: "Cancellation fee",
                        type: "number",
                        // **What we owe them, as decided, not calculated.**
                        // There is no schedule of notice periods in this
                        // product; inventing one would apply it to
                        // arrangements nobody agreed it against.
                        hint: "Leave blank if none is owed. Raises a payable row and tells the creator the amount.",
                        placeholder: "e.g. 2000",
                    },
                ]}
                onSubmit={(body) =>
                    act(
                        "cancel",
                        () => api.post(`/admin/collaborations/${id}/cancel`, body),
                        "Cancelled",
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "mark-paid"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Mark paid"
                title={`₹${formatRupees(payment?.creator_payout)} to ${collab?.creator?.name || "the creator"}`}
                description="Records that the money has left. The creator is notified."
                reasonLabel="Note"
                confirmLabel="Mark paid"
                submitting={busy === "mark-paid"}
                extras={[
                    {
                        // **`payment_reference`, which is what the server
                        // reads.** This said `reference`, so every mark-paid
                        // from this page answered 422 on a required field the
                        // form was filling in under another name.
                        name: "payment_reference",
                        label: "Payment reference",
                        required: true,
                        placeholder: "UTR or transaction id",
                    },
                    {
                        name: "tds_amount",
                        label: "TDS withheld",
                        type: "number",
                        // **Recorded, never computed.** Which section applies
                        // and whether this creator is under the threshold this
                        // year change by finance act and by creator; a rate in
                        // code would be quietly wrong for somebody.
                        hint: "Leave blank if none applies. The platform records what you enter — it doesn't work the rate out.",
                        placeholder: "e.g. 800",
                    },
                ]}
                onSubmit={(body) =>
                    act(
                        "mark-paid",
                        () =>
                            api.post(`/admin/payments/${payment.id}/mark_paid`, {
                                payment_reference: body.payment_reference,
                                // Three states, and the form can only express
                                // two: a figure means it applies, blank means
                                // none does. "Nobody has looked yet" is the
                                // state a payment is in *before* this dialog.
                                tds_applicable: body.tds_amount != null,
                                tds_amount: body.tds_amount,
                            }),
                        "Marked paid",
                    )
                }
            />
        </DetailShell>
    );
}
