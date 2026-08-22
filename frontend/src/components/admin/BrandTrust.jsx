// Whether this brand's briefs still queue behind a person.
//
// Trust is arithmetic — `TRUSTED_BRAND_APPROVALS` campaigns approved with none
// sent back — so most of this panel is reporting a count. The part that is a
// decision is the revocation, and it deliberately outlives the count: a brand
// that has been revoked does not earn its way back by posting three more good
// briefs, because that would give somebody's judgement an expiry date they did
// not choose.
import React, { useState } from "react";
import { Loader2, ShieldCheck, ShieldOff } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { TRUST as IDS } from "@/constants/testIds";
import { TEXT } from "./console/tokens";

export default function BrandTrust({ userId, trust, onChanged }) {
    const [asking, setAsking] = useState(null);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);

    if (!trust) return null;

    const act = async (action) => {
        setBusy(true);
        try {
            await api.post(`/admin/brands/${userId}/trust/${action}`, {
                reason: reason.trim(),
            });
            notifySuccess(
                action === "revoke"
                    ? "Their campaigns go back through review"
                    : "Trust restored"
            );
            setAsking(null);
            setReason("");
            onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be saved." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.panel} className="space-y-3">
            <p className="flex flex-wrap items-center gap-2 text-sm">
                {trust.trusted ? (
                    <ShieldCheck aria-hidden="true" className="h-4 w-4 text-emerald-400" />
                ) : (
                    <ShieldOff aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
                )}
                {trust.trusted
                    ? "Their campaigns publish without waiting on us."
                    : "Their campaigns wait for a review."}
            </p>

            <p className={`${TEXT.meta} text-muted-foreground`}>
                {/* The count either way, because "not trusted" with no number
                    beside it gives somebody nothing to act on. */}
                {trust.approvals} approved
                {trust.rejections > 0 && `, ${trust.rejections} sent back`}
                {" · "}
                {trust.rejections > 0
                    ? "a single rejection ends it — we read every brief from a brand we have had to send one back to"
                    : trust.remaining
                    ? `${trust.remaining} more clean approval${
                          trust.remaining === 1 ? "" : "s"
                      } and they stop queueing`
                    : `${trust.threshold} clean approvals is the bar`}
            </p>

            {trust.revoked && (
                <p className="rounded-md border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-100/90">
                    Revoked by hand: {trust.revoked_reason}
                </p>
            )}

            {!asking && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setAsking(trust.revoked ? "restore" : "revoke")}
                    data-testid={trust.revoked ? IDS.restore : IDS.revoke}
                    className="min-h-[2.75rem] border-white/20 bg-transparent sm:min-h-0"
                >
                    {trust.revoked ? "Let them publish again" : "Send their briefs back to review"}
                </Button>
            )}

            {asking && (
                <div className="space-y-2">
                    <Textarea
                        rows={2}
                        maxLength={500}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder={
                            asking === "revoke"
                                ? "Why. e.g. Two briefs in a row needed edits after publication."
                                : "Why. e.g. Spoke to them; the briefing problem is sorted."
                        }
                        data-testid={IDS.reason}
                        className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            onClick={() => act(asking)}
                            disabled={busy || !reason.trim()}
                            data-testid={IDS.submit}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            {asking === "revoke" ? "Revoke" : "Restore"}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setAsking(null)}>
                            Cancel
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
