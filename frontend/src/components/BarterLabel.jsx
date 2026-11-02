// "Barter" as a label, on every card and invitation for a brief that pays in
// kind rather than in money.
//
// A creator who opted into barter briefs sees them in the feed, and anyone a
// brand invites to one sees the invitation — in both places the first thing
// they should be able to tell is that this one is not paid. A word inside the
// fee line was there already; this is the version you cannot read past. It
// renders nothing on a paid brief, and decides that through `isBarter`, the
// one reader of the kind of money.
import React from "react";
import { Gift } from "lucide-react";

import { isBarter } from "@/lib/compensation";
import { BARTER } from "@/constants/testIds";

export default function BarterLabel({ campaign, id, className = "" }) {
    if (!isBarter(campaign)) return null;
    return (
        <span
            data-testid={BARTER.label(id ?? campaign?.id)}
            className={`inline-flex items-center gap-1.5 rounded-full border border-state-pending/40 bg-state-pending-wash px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-state-pending ${className}`}
        >
            <Gift className="h-3 w-3" aria-hidden="true" />
            Barter
        </span>
    );
}
