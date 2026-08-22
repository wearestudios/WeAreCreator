// When the two sides disagree about whether the work was done.
//
// A brand rejecting delivered content, or refusing to pay for it, used to
// leave the creator with nothing: the collaboration hung at
// `content_submitted` forever, the payment sat unmade, and the only recourse
// was a WhatsApp message to whoever answered. This is the recourse.
//
// **One component, three audiences, and it never asks what role is looking.**
// The server decides who may raise, who may withdraw and who may resolve, and
// sends the answer in `actions` — the same rule the shared application screen
// holds. What every party sees is identical: a mediation where the two sides
// read different accounts of what is being mediated is not one.
import React, { useState } from "react";
import { AlertOctagon, Loader2, Scale, Snowflake } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DISPUTE as IDS } from "@/constants/testIds";
import { formatDateTime } from "@/lib/time";

/**
 * What an admin can decide. Mirrors `DISPUTE_RESOLUTIONS` in server.py — and
 * `cancelled` is deliberately one of the four: sometimes the honest answer is
 * that the arrangement should not have happened, and forcing a mediator to
 * pick "release" or "refund" when neither is right records the decision as
 * something it was not.
 */
const RESOLUTIONS = [
    { key: "release", label: "Pay the creator in full" },
    { key: "partial_release", label: "Pay the creator part of it" },
    { key: "refund", label: "Refund the brand" },
    { key: "cancelled", label: "Call the whole thing off" },
];

const WHO = { creator: "the creator", runner: "the campaign runner" };

/**
 * @param {object}   props.collaborationId
 * @param {object}   [props.dispute]   The server's block, or null.
 * @param {object}   [props.actions]   `can_raise_dispute`, `can_withdraw_dispute`,
 *   `can_resolve_dispute` — all decided server-side.
 * @param {function} props.onChanged   Refetch; the freeze changes what else the
 *   screen may offer, so the parent reloads rather than patching one field.
 */
export default function DisputePanel({
    collaborationId,
    dispute,
    actions = {},
    onChanged,
}) {
    const [raising, setRaising] = useState(false);
    const [reason, setReason] = useState("");
    const [resolving, setResolving] = useState(false);
    const [resolution, setResolution] = useState("release");
    const [amount, setAmount] = useState("");
    const [note, setNote] = useState("");
    const [busy, setBusy] = useState(false);

    const open = dispute?.state === "open";

    // Nothing to say and nothing to offer: render nothing rather than an empty
    // box headed "Dispute", which reads as a fact about the collaboration.
    if (!dispute && !actions.can_raise_dispute) return null;

    const call = async (fn, success) => {
        setBusy(true);
        try {
            await fn();
            notifySuccess(success);
            setRaising(false);
            setResolving(false);
            setReason("");
            setNote("");
            setAmount("");
            onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be recorded." });
        } finally {
            setBusy(false);
        }
    };

    const raise = () =>
        call(
            () => api.post(`/disputes/${collaborationId}`, { reason: reason.trim() }),
            "Raised — WeAre will look at it."
        );

    const withdraw = () =>
        call(
            () => api.post(`/disputes/${collaborationId}/withdraw`),
            "Taken back — this carries on."
        );

    const resolve = () =>
        call(
            () =>
                api.post(`/admin/disputes/${collaborationId}/resolve`, {
                    resolution,
                    note: note.trim(),
                    amount:
                        resolution === "partial_release" && amount !== ""
                            ? Number(amount)
                            : null,
                }),
            "Decided, and both sides told."
        );

    return (
        <section
            data-testid={IDS.panel}
            className={`rounded-md border p-4 ${
                open
                    ? "border-destructive/40 bg-destructive/10"
                    : "border-white/10 bg-card"
            }`}
        >
            <div className="flex flex-wrap items-center gap-2">
                <Scale
                    aria-hidden="true"
                    className={`h-4 w-4 ${open ? "text-destructive" : "text-muted-foreground"}`}
                />
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    {open ? "Under dispute" : "Dispute"}
                </p>
                {/* **The freeze is said, not implied.** Somebody wondering why
                    their payment has not moved is owed the reason on the same
                    screen, not in a support thread. */}
                {open && dispute?.frozen && (
                    <span className="inline-flex items-center gap-1 rounded bg-destructive/20 px-2 py-0.5 text-xs text-destructive-foreground">
                        <Snowflake aria-hidden="true" className="h-3 w-3" />
                        Payment held
                    </span>
                )}
            </div>

            {dispute && (
                <div className="mt-3 space-y-2 text-sm">
                    <p className="text-muted-foreground">
                        Raised by {WHO[dispute.raised_by_role] || "somebody"}
                        {dispute.raised_at ? ` on ${formatDateTime(dispute.raised_at)}` : ""}.
                    </p>
                    <p className="whitespace-pre-wrap">{dispute.reason}</p>

                    {dispute.state === "resolved" && (
                        <div className="rounded border border-white/10 bg-background/40 p-3">
                            <p className="text-sm">
                                {dispute.resolution_label || dispute.resolution}
                                {typeof dispute.resolution_amount === "number"
                                    ? ` — ₹${dispute.resolution_amount.toLocaleString("en-IN")}`
                                    : ""}
                            </p>
                            {/* The reasoning, always. "Released" with nothing
                                beside it is a decision nobody can defend six
                                months later, and the party it went against is
                                the one who will ask. */}
                            <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                                {dispute.resolution_note}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                Decided by {dispute.resolved_by_name || "WeAre"}
                                {dispute.resolved_at
                                    ? ` on ${formatDateTime(dispute.resolved_at)}`
                                    : ""}
                            </p>
                        </div>
                    )}
                    {dispute.state === "withdrawn" && (
                        <p className="text-sm text-muted-foreground">
                            Taken back. Nothing is held.
                        </p>
                    )}
                </div>
            )}

            {open && !dispute?.resolution && (
                <p className="mt-3 text-sm text-muted-foreground">
                    WeAre is mediating. Nothing moves on either side until it is
                    decided, and you will both be told the outcome and the reasoning.
                </p>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
                {actions.can_raise_dispute && !raising && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRaising(true)}
                        data-testid={IDS.open}
                        className="min-h-[2.75rem] border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10 sm:min-h-0"
                    >
                        <AlertOctagon className="mr-1.5 h-3.5 w-3.5" />
                        Raise a dispute
                    </Button>
                )}
                {actions.can_withdraw_dispute && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={withdraw}
                        disabled={busy}
                        data-testid={IDS.withdraw}
                        className="min-h-[2.75rem] border-white/20 bg-transparent sm:min-h-0"
                    >
                        {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                        Take it back
                    </Button>
                )}
                {actions.can_resolve_dispute && !resolving && (
                    <Button
                        size="sm"
                        onClick={() => setResolving(true)}
                        data-testid={IDS.resolve}
                        className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                    >
                        Decide it
                    </Button>
                )}
            </div>

            {raising && (
                <div className="mt-3 space-y-2">
                    <Textarea
                        rows={3}
                        maxLength={2000}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="What happened, and what you think should happen about it."
                        data-testid={IDS.reason}
                        className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />
                    <p className="text-xs text-muted-foreground">
                        This freezes the collaboration and any payment on it until
                        WeAre decides. The other side is told straight away.
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            onClick={raise}
                            disabled={busy || reason.trim().length < 10}
                            data-testid={IDS.submit}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            Raise it
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setRaising(false)}
                            data-testid={IDS.cancel}
                        >
                            Cancel
                        </Button>
                    </div>
                </div>
            )}

            {resolving && (
                <div className="mt-3 space-y-3">
                    <div className="flex flex-wrap gap-2">
                        {RESOLUTIONS.map((r) => (
                            <button
                                key={r.key}
                                type="button"
                                onClick={() => setResolution(r.key)}
                                data-testid={IDS.resolution(r.key)}
                                className={`rounded border px-3 py-2 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 ${
                                    resolution === r.key
                                        ? "border-ember-500 bg-ember-500/10 text-foreground"
                                        : "border-white/10 text-muted-foreground hover:border-white/20"
                                }`}
                            >
                                {r.label}
                            </button>
                        ))}
                    </div>

                    {/* Only where the decision has a figure in it. A number
                        box on "refund the brand" is a question with no answer. */}
                    {resolution === "partial_release" && (
                        <Input
                            type="number"
                            inputMode="numeric"
                            min={0}
                            value={amount}
                            onChange={(e) => setAmount(e.target.value)}
                            placeholder="How much goes to the creator"
                            data-testid={IDS.resolveAmount}
                            className="h-11 border-white/10 bg-background/60 text-base tabular-nums"
                        />
                    )}

                    <Textarea
                        rows={3}
                        maxLength={2000}
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Why this is the right outcome. Both sides read it."
                        data-testid={IDS.resolveNote}
                        className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />

                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            onClick={resolve}
                            disabled={
                                busy ||
                                !note.trim() ||
                                (resolution === "partial_release" && amount === "")
                            }
                            data-testid={IDS.resolveSubmit}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            Record the decision
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setResolving(false)}>
                            Cancel
                        </Button>
                    </div>
                </div>
            )}
        </section>
    );
}
