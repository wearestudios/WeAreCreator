// Whether this brand's logo goes on the public home page.
//
// **Two halves of one decision, shown together on purpose.** The brand's
// consent says we may use its mark; the approval here says we are willing to
// make the claim. A panel offering the approval without showing the consent
// invites somebody to publish a trademark nobody agreed to let us use — so the
// button is disabled, with the reason on screen, until the brand has ticked
// its own box.
//
// **There is deliberately no control here that grants consent.** An admin
// cannot tick the brand's box for it, the same reason there is no endpoint
// that mints a second brand manager. If a brand has agreed over email, the
// place that gets recorded is the brand's own profile, by the brand.
//
// Revoking costs a reason in a way approving does not: "we put them on the
// wall" is complete on its own, and "we took them off" is the one somebody
// asks about later, because nothing visible happens as a result of it.
import React, { useState } from "react";
import { Loader2, Check, X } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ADMIN_BRAND_LOGO as IDS } from "@/constants/testIds";
import { TEXT } from "./console/tokens";

export default function BrandHomepageLogo({ userId, block, onChanged }) {
    const [asking, setAsking] = useState(false);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);

    if (!block) return null;

    const {
        opted_in: optedIn,
        consented_at: consentedAt,
        withdrawn_at: withdrawnAt,
        consent_terms: consentTerms,
        approved,
        approved_at: approvedAt,
        revoked_at: revokedAt,
        revoked_reason: revokedReason,
        campaigns_run: campaignsRun,
        has_logo: hasLogo,
    } = block;

    const act = async (action) => {
        setBusy(true);
        try {
            await api.post(`/admin/brands/${userId}/homepage-logo/${action}`,
                action === "revoke" ? { reason: reason.trim() } : {});
            notifySuccess(
                action === "approve"
                    ? "Their logo can go on the home page"
                    : "Taken off the home page",
            );
            setAsking(false);
            setReason("");
            onChanged?.();
        } catch (err) {
            notifyError(err);
        } finally {
            setBusy(false);
        }
    };

    // Why it is not live, in the order somebody can act on. Consent first,
    // because it is the one thing that is not ours to fix.
    const blockers = [];
    if (!optedIn) blockers.push("they have not given permission yet");
    if (!hasLogo) blockers.push("no logo uploaded");
    if (!campaignsRun) blockers.push("no finished campaign yet");

    const live = optedIn && approved && hasLogo && campaignsRun > 0;

    return (
        <div data-testid={IDS.panel} className="space-y-4">
            <div className="space-y-1">
                <p data-testid={IDS.state} className="text-sm">
                    {live
                        ? "On the home page."
                        : "Not on the home page."}
                </p>
                {!live && blockers.length > 0 && (
                    <p data-testid={IDS.blockers} className={TEXT.meta}>
                        {blockers.join(" · ")}
                    </p>
                )}
            </div>

            {/* **The permission as they actually agreed to it**, not today's
                wording. On a trademark this is the record: what the constant
                says now is irrelevant to what was consented to then. */}
            {consentedAt && (
                <div className="rounded-lg border border-tint/10 bg-card p-4">
                    <p className={TEXT.meta}>
                        Permission given {new Date(consentedAt).toLocaleDateString()}
                        {withdrawnAt
                            ? ` · withdrawn ${new Date(withdrawnAt).toLocaleDateString()}`
                            : ""}
                    </p>
                    {consentTerms && (
                        <p
                            data-testid={IDS.terms}
                            className={`mt-2 leading-relaxed ${TEXT.meta}`}
                        >
                            {consentTerms}
                        </p>
                    )}
                </div>
            )}

            {approvedAt && (
                <p className={TEXT.meta}>
                    Approved here {new Date(approvedAt).toLocaleDateString()}
                </p>
            )}
            {revokedAt && (
                <p data-testid={IDS.revoked} className={TEXT.meta}>
                    Taken off {new Date(revokedAt).toLocaleDateString()}
                    {revokedReason ? ` — ${revokedReason}` : ""}
                </p>
            )}

            {asking ? (
                <div className="space-y-3">
                    <Textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        data-testid={IDS.reason}
                        placeholder="Why are they coming off the wall?"
                        rows={3}
                    />
                    <div className="flex gap-2">
                        <Button
                            size="sm"
                            variant="destructive"
                            disabled={busy || !reason.trim()}
                            data-testid={IDS.confirmRevoke}
                            onClick={() => act("revoke")}
                        >
                            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Take off the home page
                        </Button>
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => {
                                setAsking(false);
                                setReason("");
                            }}
                        >
                            Cancel
                        </Button>
                    </div>
                </div>
            ) : (
                <div className="flex flex-wrap gap-2">
                    {!approved && (
                        <Button
                            size="sm"
                            disabled={busy || !optedIn}
                            data-testid={IDS.approve}
                            onClick={() => act("approve")}
                            title={
                                optedIn
                                    ? undefined
                                    : "The brand has to give permission first"
                            }
                        >
                            {busy ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <Check className="mr-2 h-4 w-4" />
                            )}
                            Approve for the home page
                        </Button>
                    )}
                    {approved && (
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            data-testid={IDS.revoke}
                            onClick={() => setAsking(true)}
                        >
                            <X className="mr-2 h-4 w-4" />
                            Take off the home page
                        </Button>
                    )}
                </div>
            )}
        </div>
    );
}
