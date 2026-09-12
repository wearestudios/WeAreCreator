// What we charge, and what comes back when a brief underfills.
//
// Three controls that used to be an environment variable and two things
// nobody recorded: the commission rate, the flat campaign fee, and the refund
// decision. All three are read-only to a brand — it sees the rate on its
// invoices and hears the refund outcome from us, and neither is a field it
// can reach.
//
// **Nothing here computes a verdict.** `_refund_reckoning` decides on the
// server and ships the sentence; this draws it. A browser working out for
// itself whether a campaign underfilled would be a second definition of
// "filled", which is the mistake `isStale` made in this console once already.
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, Percent, Receipt, Undo2 } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { COMMERCIAL as IDS } from "@/constants/testIds";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { TEXT } from "./console/tokens";

const money = (v) =>
    v === null || v === undefined
        ? "—"
        : `₹${Math.round(Number(v)).toLocaleString("en-IN")}`;

/** Where a rate came from, in words. "15%" and "15%, because nobody has
 *  agreed anything else" are different facts, and only one is worth a call. */
const SOURCE = {
    campaign: "set on this campaign",
    brand: "agreed with this brand",
    default: "the standard rate — nothing negotiated",
};

/**
 * One rate, with who last moved it.
 *
 * `value` is the record's *own* rate and may be null; `effective` is what
 * actually applies once the levels above have been walked. Both are shown,
 * because "no rate set" and "paying nothing" are opposite answers that a
 * single number cannot tell apart.
 */
export function CommissionControl({
    label,
    endpoint,
    value,
    effective,
    setAt,
    setBy,
    setReason,
    onSaved,
}) {
    const [rate, setRate] = useState(value === null || value === undefined ? "" : String(value));
    const [reason, setReason_] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        setRate(value === null || value === undefined ? "" : String(value));
    }, [value]);

    const save = async () => {
        setBusy(true);
        try {
            const { data } = await api.put(endpoint, {
                // **Empty clears it and falls back to the level above**, which
                // is a different answer from zero and has to stay sendable.
                commission_percent: rate.trim() === "" ? null : Number(rate),
                reason: reason.trim(),
            });
            notifySuccess("Rate saved.");
            setReason_("");
            onSaved?.(data);
        } catch (err) {
            notifyError(err, { fallback: "That rate didn't save." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.commission} className="space-y-3">
            <p className={`${TEXT.meta} flex items-center gap-1.5 text-muted-foreground`}>
                <Percent aria-hidden="true" className="h-3 w-3" />
                {label}
            </p>
            <p data-testid={IDS.commissionEffective} className="text-sm">
                <span className="text-base font-medium tabular-nums">
                    {effective?.percent ?? "—"}%
                </span>{" "}
                <span className="text-muted-foreground">
                    — {SOURCE[effective?.source] || "unknown"}
                </span>
            </p>
            {setAt && (
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    Last changed by {setBy || "somebody"} — {setReason || "no reason given"}
                </p>
            )}
            <div className="flex flex-wrap items-end gap-2">
                <div className="w-28">
                    <Label htmlFor={`rate-${endpoint}`} className={TEXT.meta}>
                        Rate %
                    </Label>
                    <Input
                        id={`rate-${endpoint}`}
                        data-testid={IDS.commissionInput}
                        type="number"
                        min="0"
                        max="100"
                        step="0.5"
                        value={rate}
                        placeholder="Standard"
                        onChange={(e) => setRate(e.target.value)}
                        className="mt-1 h-10"
                    />
                </div>
                <div className="min-w-[14rem] flex-1">
                    <Label htmlFor={`why-${endpoint}`} className={TEXT.meta}>
                        Why
                    </Label>
                    <Input
                        id={`why-${endpoint}`}
                        data-testid={IDS.commissionReason}
                        value={reason}
                        placeholder="Agreed at the renewal call"
                        onChange={(e) => setReason_(e.target.value)}
                        className="mt-1 h-10"
                    />
                </div>
                <Button
                    data-testid={IDS.commissionSave}
                    onClick={save}
                    // **The reason is required in both directions**, clearing
                    // included: "why is this brand on 8%" and "why did it stop
                    // being 8%" are both questions somebody asks later.
                    disabled={busy || reason.trim().length < 3}
                    className="h-10"
                >
                    {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save
                </Button>
            </div>
        </div>
    );
}

/**
 * The flat fee for running a campaign, and the refund position.
 *
 * The reckoning arrives as a sentence — "underfilled by 3; brand rejected 0
 * of 5 shortlisted — refund eligible" — because an admin about to move money
 * needs to be able to read it out on a call, not reconstruct it from four
 * numbers.
 */
export function CampaignFeePanel({ campaignId, campaignFee, refund, onSaved }) {
    const [fee, setFee] = useState(
        campaignFee === null || campaignFee === undefined ? "" : String(campaignFee)
    );
    const [reason, setReason] = useState("");
    const [decision, setDecision] = useState("");
    const [busy, setBusy] = useState(false);

    const saveFee = async () => {
        setBusy(true);
        try {
            const { data } = await api.put(`/admin/campaigns/${campaignId}/fee`, {
                campaign_fee: fee.trim() === "" ? null : Number(fee),
                reason: reason.trim(),
            });
            notifySuccess("Campaign fee saved.");
            setReason("");
            onSaved?.(data);
        } catch (err) {
            notifyError(err, { fallback: "That fee didn't save." });
        } finally {
            setBusy(false);
        }
    };

    const decide = async (state) => {
        setBusy(true);
        try {
            await api.post(`/admin/campaigns/${campaignId}/refund`, {
                state,
                reason: decision.trim(),
            });
            notifySuccess(
                state === "refunded" ? "Refund recorded." : "Recorded — the fee stands."
            );
            setDecision("");
            onSaved?.();
        } catch (err) {
            notifyError(err, { fallback: "That didn't go through." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.fee} className="space-y-4">
            <div className="flex flex-wrap items-end gap-2">
                <div className="w-36">
                    <Label htmlFor="campaign-fee" className={TEXT.meta}>
                        Campaign fee
                    </Label>
                    <Input
                        id="campaign-fee"
                        data-testid={IDS.feeInput}
                        type="number"
                        min="0"
                        step="1000"
                        value={fee}
                        placeholder="None"
                        onChange={(e) => setFee(e.target.value)}
                        className="mt-1 h-10"
                    />
                </div>
                <div className="min-w-[14rem] flex-1">
                    <Label htmlFor="fee-why" className={TEXT.meta}>
                        Why
                    </Label>
                    <Input
                        id="fee-why"
                        data-testid={IDS.feeReason}
                        value={reason}
                        placeholder="Agreed in the brief call"
                        onChange={(e) => setReason(e.target.value)}
                        className="mt-1 h-10"
                    />
                </div>
                <Button
                    data-testid={IDS.feeSave}
                    onClick={saveFee}
                    disabled={busy || reason.trim().length < 3}
                    className="h-10"
                >
                    {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save
                </Button>
            </div>

            {/* **Absent on a brief with no fee**, which is most of them — a
                refund panel on a campaign that was never charged for would
                invent a question nobody has. */}
            {refund && refund.state !== "none" && (
                <div
                    data-testid={IDS.refund}
                    className="rounded-lg border border-white/10 bg-card p-4"
                >
                    <p className={`${TEXT.meta} flex items-center gap-1.5 text-muted-foreground`}>
                        <Receipt aria-hidden="true" className="h-3 w-3" />
                        Campaign fee — {money(refund.campaign_fee)}
                    </p>
                    {/* The server's sentence, drawn rather than rebuilt. */}
                    <p data-testid={IDS.refundReason} className="mt-2 text-sm">
                        {refund.reason}
                    </p>

                    {refund.decided ? (
                        <p
                            data-testid={IDS.refundDecided}
                            className={`mt-3 flex items-start gap-1.5 ${TEXT.meta} text-muted-foreground`}
                        >
                            <Undo2 aria-hidden="true" className="mt-0.5 h-3 w-3 shrink-0" />
                            <span>
                                {refund.decided_state === "refunded"
                                    ? "Refunded"
                                    : "Fee stands"}{" "}
                                by {refund.decided_by_name || "somebody"} —{" "}
                                {refund.decided_reason}
                                {/* An admin deciding against the rule is a
                                    judgement worth being able to find. */}
                                {refund.overridden && (
                                    <span
                                        data-testid={IDS.refundOverridden}
                                        className="ml-1 text-amber-300"
                                    >
                                        (against the reckoning)
                                    </span>
                                )}
                            </span>
                        </p>
                    ) : (
                        <div className="mt-3 space-y-2">
                            <Textarea
                                data-testid={IDS.refundReasonInput}
                                rows={2}
                                value={decision}
                                placeholder="What you decided, and on what. This is quoted to the brand."
                                onChange={(e) => setDecision(e.target.value)}
                            />
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    data-testid={IDS.refundConfirm}
                                    onClick={() => decide("refunded")}
                                    disabled={busy || decision.trim().length < 3}
                                    className="h-10"
                                >
                                    Refund {money(refund.campaign_fee)}
                                </Button>
                                <Button
                                    variant="outline"
                                    data-testid={IDS.refundDecline}
                                    onClick={() => decide("declined")}
                                    disabled={busy || decision.trim().length < 3}
                                    className="h-10"
                                >
                                    The fee stands
                                </Button>
                            </div>
                            {/* Neither button is the default and neither is
                                pre-selected: the reckoning is an input to the
                                decision, not the decision. */}
                            <p className={`${TEXT.meta} text-muted-foreground`}>
                                A reason either way — it goes in the audit log and to the
                                brand.
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default function CommercialTerms({ campaign, refund, commission, onSaved }) {
    const reload = useCallback(() => onSaved?.(), [onSaved]);
    if (!campaign?.id) return null;
    return (
        <div className="space-y-6">
            <CommissionControl
                label="Commission on this campaign"
                endpoint={`/admin/campaigns/${campaign.id}/commission`}
                value={campaign.commission_percent}
                effective={commission}
                setAt={campaign.commission_set_at}
                setBy={campaign.commission_set_by_name}
                setReason={campaign.commission_reason}
                onSaved={reload}
            />
            <CampaignFeePanel
                campaignId={campaign.id}
                campaignFee={campaign.campaign_fee}
                refund={refund}
                onSaved={reload}
            />
        </div>
    );
}
