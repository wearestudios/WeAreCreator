// What arrived against what was asked for.
//
// Two of three stories delivered was neither complete nor failed, so it was
// settled over WhatsApp with a number nobody wrote down. This is the number,
// on the record, on every screen that shows the collaboration — **including
// the creator's**, because they are the party a shortfall is a judgement about
// and finding out from a smaller payment than expected is the version of this
// that costs somebody.
//
// It renders nothing when there is nothing to say: a brief with no counted
// deliverables has no shortfall to compute, and a collaboration nobody counted
// against is unknown rather than complete. The server sends `null` for both.
import React from "react";
import { CheckCircle2, PackageOpen } from "lucide-react";

import { DELIVERABLE_PLURALS, DELIVERABLE_SINGULARS } from "@/lib/deliverables";

export default function Shortfall({ shortfall, testid, className = "" }) {
    if (!shortfall) return null;

    if (shortfall.complete) {
        return (
            <p
                data-testid={testid}
                className={`inline-flex items-center gap-1.5 text-sm text-muted-foreground ${className}`}
            >
                <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5 text-emerald-400" />
                Everything asked for
            </p>
        );
    }

    return (
        <div
            data-testid={testid}
            className={`rounded-md border border-amber-400/30 bg-amber-400/10 p-3 ${className}`}
        >
            <p className="flex items-center gap-2 text-sm text-amber-200">
                <PackageOpen aria-hidden="true" className="h-3.5 w-3.5 flex-none" />
                {/* The counted version, not "partially delivered" — a brand
                    reading a vague phrase has to open the campaign to find out
                    what is actually missing. */}
                {shortfall.delivered_total} of {shortfall.asked_total} delivered
            </p>
            <ul className="mt-2 space-y-1 text-sm text-amber-100/90">
                {shortfall.missing.map((row) => (
                    <li key={row.type}>
                        {/* **The spelled-out plurals, not a bolted-on "s".**
                            "storys" is what naive pluralisation gives, and
                            lowercasing "YouTube Short" gives "youtube short" —
                            a proper noun is not a word a formatter gets to
                            recase. Same table the brief itself is rendered
                            from, so the ask and the shortfall read alike. */}
                        {row.delivered} of {row.asked}{" "}
                        {row.asked === 1
                            ? DELIVERABLE_SINGULARS[row.type] || row.label
                            : DELIVERABLE_PLURALS[row.type] || row.label}{" "}
                        — {row.short} short
                    </li>
                ))}
            </ul>
        </div>
    );
}
