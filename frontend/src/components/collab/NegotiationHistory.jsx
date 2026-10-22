// How a collaboration got to its fee, newest first.
//
// The record of a negotiation that used to live in three memories: who offered
// what, who came back with what, what was finally agreed and what it was
// corrected to later. The server writes every entry through one helper and
// never rewrites one, so this list is the history rather than a summary of it.
//
// **It never asks what role is looking.** The creator, the brand and a
// campaign manager receive entries with no author id and no source, and with
// contact details already taken out of the notes; the admin receives both.
// What renders is what arrived — a `source` line appears because the server
// sent one, not because this component worked out who it is talking to.
//
// On barter the brief's terms stand where a number would, and no entry
// carries an amount: "Agreed" with nothing beside it, under a line saying what
// the creator gets, is the honest reading of a deal with no money in it.
import React, { useState } from "react";

import { formatMoney } from "@/lib/budget";
import { formatDateTime } from "@/lib/time";
import { NEGOTIATION as IDS } from "@/constants/testIds";

const KIND = {
    offer: "Offered",
    counter: "Countered",
    accept: "Agreed",
    decline: "Declined",
    adjust: "Adjusted",
};

const WHO = {
    brand: "Brand",
    creator: "Creator",
    admin: "WeAre",
    system: "WeAre",
};

const SOURCE = {
    in_app: "In the app",
    recorded_offline: "Agreed offline, recorded here",
    admin_adjustment: "Admin adjustment",
    backfill: "Backfilled",
};

// The card on a creator's dashboard has room for the latest few; the full
// thread is one tap away rather than pushing the next card off the screen.
const COMPACT_ROWS = 3;

export default function NegotiationHistory({ negotiation, compact = false, className = "" }) {
    const [all, setAll] = useState(false);
    const entries = negotiation?.entries || [];
    if (!entries.length) return null;

    const barter = negotiation.compensation_type === "barter";
    const shown = compact && !all ? entries.slice(0, COMPACT_ROWS) : entries;

    return (
        <div data-testid={IDS.panel} className={className}>
            {barter && negotiation.barter_terms && (
                <p
                    data-testid={IDS.barterTerms}
                    className="mb-3 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-muted-foreground"
                >
                    Barter: {negotiation.barter_terms}
                </p>
            )}
            <ol className="space-y-3">
                {shown.map((e, i) => (
                    <li
                        key={`${e.at}-${i}`}
                        data-testid={IDS.entry(i)}
                        className="rounded-md border border-white/10 bg-background/60 px-4 py-3"
                    >
                        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                            <p className="text-sm">
                                <span className="text-foreground">{KIND[e.kind] || e.kind}</span>
                                {!barter && e.amount != null && (
                                    <span className="text-foreground"> · {formatMoney(e.amount)}</span>
                                )}
                                {!e.recorded_before_tracking && (
                                    <span className="text-muted-foreground">
                                        {" "}
                                        · {WHO[e.by_role] || "WeAre"}
                                    </span>
                                )}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                {e.recorded_before_tracking ? (
                                    <span data-testid={IDS.backfilled(i)}>
                                        Recorded before history tracking
                                    </span>
                                ) : (
                                    formatDateTime(e.at)
                                )}
                            </p>
                        </div>
                        {e.note && (
                            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
                                “{e.note}”
                            </p>
                        )}
                        {/* The admin's half: how it was recorded and by whom.
                            Present only when the server sent it. */}
                        {e.source !== undefined && (
                            <p className="mt-2 text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                {SOURCE[e.source] || e.source || "Unknown source"}
                                {e.by_user_id ? ` · user ${e.by_user_id}` : ""}
                            </p>
                        )}
                    </li>
                ))}
            </ol>
            {compact && entries.length > COMPACT_ROWS && (
                <button
                    type="button"
                    onClick={() => setAll((v) => !v)}
                    className="mt-3 inline-flex min-h-[2.75rem] items-center text-sm text-muted-foreground underline underline-offset-4 transition-colors duration-200 hover:text-primary"
                >
                    {all ? "Show the latest only" : `Show all ${entries.length}`}
                </button>
            )}
        </div>
    );
}
