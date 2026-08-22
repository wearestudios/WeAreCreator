// "It's been a while since we checked."
//
// Verification never expired, so a business verified two years ago still read
// `verified` because nothing had ever run out — and the record said we had
// checked, which by then we had not. A validity period fixes that; this is how
// somebody hears about it.
//
// **Told before it happens, and the ask is a confirmation rather than a
// resubmission.** A lapse is not a rejection: `verified` stays true and the
// history is intact, and what runs out is our confidence that it is still
// current. Somebody who finds out on the day they try to apply has been locked
// out; somebody told a month early has a job to do.
//
// One component for the creator and the brand, because the block the server
// sends is the same shape on both — `_verification_ageing` is one reader for
// exactly that reason.
import React, { useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { REVALIDATE as IDS } from "@/constants/testIds";
import { formatDate } from "@/lib/time";

/**
 * @param {object}   props.verification  The server's block: `days_left`,
 *   `lapsed`, `expiring_soon`, `expires_at`. `null` on a record that never
 *   expires, which is every unverified one.
 * @param {"creator"|"brand"} props.kind  Which confirm route to post to, and
 *   which noun to use. Nothing else differs.
 */
export default function VerificationExpiry({ verification, kind, onConfirmed }) {
    const [busy, setBusy] = useState(false);

    // Nothing to say. The overwhelming majority of the time this is the case,
    // and a green "your verification is fine" band on every profile load is
    // chrome nobody reads and everybody scrolls past.
    if (!verification || (!verification.lapsed && !verification.expiring_soon)) {
        return null;
    }

    const lapsed = verification.lapsed;
    const noun = kind === "brand" ? "business details" : "details";

    const confirm = async () => {
        setBusy(true);
        try {
            await api.post(
                kind === "brand"
                    ? "/brand/verification/confirm"
                    : "/creator/verification/confirm"
            );
            notifySuccess("Thanks — you're good for another year.");
            onConfirmed?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be confirmed." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <section
            data-testid={IDS.prompt}
            className={`rounded-md border p-4 ${
                lapsed
                    ? "border-destructive/40 bg-destructive/10"
                    : "border-amber-400/30 bg-amber-400/10"
            }`}
        >
            <div className="flex flex-wrap items-center gap-2">
                <ShieldCheck
                    aria-hidden="true"
                    className={`h-4 w-4 ${lapsed ? "text-destructive" : "text-amber-300"}`}
                />
                <p className="text-sm font-medium">
                    {lapsed
                        ? `Confirm your ${noun} to carry on`
                        : `Your ${noun} need a check soon`}
                </p>
            </div>

            <p className="mt-2 text-sm text-muted-foreground">
                {/* **What is lost and what is not**, both said. The single
                    most likely reading of "your verification expired" is that
                    the account is gone, and it is the wrong one. */}
                {lapsed
                    ? kind === "brand"
                      ? "You can't publish new campaigns until you tell us these are still right. Campaigns already running are not affected, and nothing about your account has changed."
                      : "You can't apply to new campaigns until you tell us these are still right. Work you're already on carries on exactly as it was."
                    : `We check every year. Yours runs out on ${formatDate(
                          verification.expires_at
                      )} — confirming now takes a moment and nothing is interrupted.`}
            </p>

            {!lapsed && typeof verification.days_left === "number" && (
                <p data-testid={IDS.expiry} className="mt-1 text-xs text-muted-foreground">
                    {verification.days_left}{" "}
                    {verification.days_left === 1 ? "day" : "days"} left
                </p>
            )}

            <Button
                size="sm"
                onClick={confirm}
                disabled={busy}
                data-testid={IDS.confirm}
                className="mt-3 min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
            >
                {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                Yes, this is all still right
            </Button>
        </section>
    );
}
