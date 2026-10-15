// What this brief pays, when, and whether getting there is covered.
//
// **The survey is the whole reason this component exists.** Late payment is
// what creators name most often as the thing that goes wrong, and the
// striking half of the finding is that creators who *were* paid inside a week
// still name it — because no brief had ever said when payment comes, so an
// unstated wait is assumed to be a long one and remembered as one. Saying it
// up front costs nothing and is the single cheapest thing on this list.
//
// One component for the creator deciding whether to apply, the manager
// standing in the room and the brand previewing its own brief, because all
// three are reading the same promise and three of them wording it differently
// is how a promise stops being one. Same arrangement `ShootWindowNote` uses,
// and the same rule underneath it: **it never asks what role is looking.**
//
// Everything here is decided server-side. `payout` (`{days, promise}`),
// `travel` (`{stated, covered, amount, text}`) and `barter_description` are
// built by `_payout_block`, `_travel_block` and `_resolve_barter` in
// server.py; this file renders them and computes no threshold of its own —
// the lesson `isStale` taught the console.
import React from "react";
import { BadgeIndianRupee, Bus, Gift } from "lucide-react";

import { PAYOUT as IDS } from "@/constants/testIds";
import { isBarter } from "@/lib/compensation";
import { payoutPromise, travelText } from "@/lib/payoutWindow";
import { formatDate } from "@/lib/time";

/**
 * The date, on its own.
 *
 * **Exported because the creator's own card needs this half and not the
 * other.** Their row carries `payout_due_at` and no campaign block — the
 * promise was read on the brief, and what is useful once they have delivered
 * is the date. Two mounts, one wording: a card that phrased it for itself
 * would be a second definition of a sentence we are being held to.
 */
export function PayoutDue({ dueAt, className = "" }) {
    if (!dueAt) return null;
    return (
        <p
            data-testid={IDS.due}
            className={"text-sm font-medium text-foreground " + className}
        >
            Payment due by {formatDate(dueAt)}
        </p>
    );
}

/**
 * @param campaign  the campaign, carrying `payout`, `travel` and
 *                  `barter_description`
 * @param dueAt     an ISO instant, present only on a creator's own row once
 *                  their delivery has been approved. A date rather than a
 *                  duration: "within 7 days" is the policy, "by 3 Nov" is the
 *                  thing somebody can act on.
 */
export default function PayoutNote({ campaign, dueAt = null, className = "" }) {
    if (!campaign) return null;

    const barter = isBarter(campaign);
    const offer = (campaign.barter_description || "").trim();
    const travel = travelText(campaign.travel);
    // On a barter brief there is no payout window to promise, because there
    // is no payment. Saying "paid within 7 days" beside "a free meal" is the
    // kind of sentence that makes a whole page read as boilerplate.
    const promise = barter ? null : payoutPromise(campaign.payout);

    if (!promise && !travel && !offer) return null;

    return (
        <div
            data-testid={IDS.note}
            className={
                "rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm leading-relaxed " +
                className
            }
        >
            <p className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-primary">
                <BadgeIndianRupee className="h-3.5 w-3.5" />
                {barter ? "What you get" : "When you are paid"}
            </p>

            {offer && (
                <p data-testid={IDS.barter} className="mt-2 flex gap-2 text-muted-foreground">
                    <Gift className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>{offer}</span>
                </p>
            )}

            {promise && (
                <p data-testid={IDS.promise} className="mt-2 text-muted-foreground">
                    {promise}
                </p>
            )}

            {/* Only once there is an approval to count from — before that
                there is no date, and inventing one would be a promise with
                nothing behind it. */}
            <PayoutDue dueAt={dueAt} className="mt-1" />

            {/* Absent on every brief that was never asked, which is most of
                them. "Travel: not covered" on a brief nobody answered tells a
                creator something we did not say — the tri-state is in
                `_travel_block` precisely so this line can be missing. */}
            {travel && (
                <p data-testid={IDS.travel} className="mt-1 flex gap-2 text-muted-foreground">
                    <Bus className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>{travel}</span>
                </p>
            )}
        </div>
    );
}
