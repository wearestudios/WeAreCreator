// Pitches made before we had finished checking them.
//
// Verification used to gate pitching, so a creator browsed, found something
// they were right for, and hit a wall. They came back two days later to a
// brief that had filled. The wait was ours and the cost was theirs.
//
// Now the pitch is taken and held. The whole value of that is in what this
// panel says: **it is in, you do not have to come back, and here is the one
// thing still outstanding.** A held pitch the creator has to remember to
// re-send is the wall again with an extra step.
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Clock, Loader2, X } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { HELD as IDS } from "@/constants/testIds";
import { formatDate } from "@/lib/time";
import { SectionHead } from "./shared";

export default function HeldApplications({ held, outstanding, onChanged }) {
    const [busy, setBusy] = useState(null);

    // Renders nothing when there is nothing waiting — which is almost always,
    // because a verified creator's pitches go straight in.
    if (!held?.length) return null;

    const cancel = async (row) => {
        setBusy(row.id);
        try {
            await api.delete(`/creator/held-applications/${row.id}`);
            notifySuccess("Taken back");
            onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be taken back." });
        } finally {
            setBusy(null);
        }
    };

    return (
        <section data-testid={IDS.panel}>
            <SectionHead
                kicker="Waiting on your verification"
                title={`${held.length} pitch${held.length === 1 ? "" : "es"} ready to go in`}
            />

            {/* **The reassurance first, and it is the point.** Somebody looking
                at this is asking one question — do I need to do this again —
                and the answer is at the top rather than inferable from the
                rows. */}
            <p
                data-testid={IDS.outstanding}
                className="mt-4 rounded-md border border-ember-500/30 bg-ember-500/10 p-4 text-sm leading-relaxed text-ember-500/90"
            >
                {outstanding?.message}
                {outstanding?.waiting_on === "you" && outstanding?.missing?.length > 0 && (
                    <>
                        {" "}
                        Still needed:{" "}
                        <span className="text-foreground">
                            {outstanding.missing.map((m) => m.label).join(", ")}
                        </span>
                        .{" "}
                        <Link
                            to="/onboarding/creator"
                            className="underline underline-offset-4 hover:no-underline"
                        >
                            Finish your profile
                        </Link>
                    </>
                )}
            </p>

            <ul className="mt-4 divide-y divide-white/10 overflow-hidden rounded-md border border-white/10 bg-card grain-surface">
                {held.map((row) => (
                    <li
                        key={row.id}
                        data-testid={IDS.row(row.id)}
                        className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4 sm:px-6"
                    >
                        <span className="min-w-0 flex-1">
                            <Link
                                to={`/campaigns/${row.campaign_id}`}
                                className="block truncate text-sm transition-colors duration-200 hover:text-ember-500"
                            >
                                {row.campaign_title || "A campaign"}
                            </Link>
                            <span className="mt-0.5 block text-xs text-muted-foreground">
                                {row.brand_name}
                                {row.created_at ? ` · pitched ${formatDate(row.created_at)}` : ""}
                            </span>
                        </span>

                        <span className="inline-flex flex-none items-center gap-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            <Clock aria-hidden="true" className="h-3.5 w-3.5" />
                            Held
                        </span>

                        {/* Theirs to take back, for the same reason an
                            application is withdrawable up to acceptance:
                            nobody has committed to them, so changing their
                            mind costs nobody anything. */}
                        <button
                            type="button"
                            onClick={() => cancel(row)}
                            disabled={busy === row.id}
                            data-testid={IDS.cancel(row.id)}
                            className="inline-flex min-h-[2.75rem] flex-none items-center gap-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-foreground disabled:opacity-50 sm:min-h-0"
                        >
                            {busy === row.id ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                                <X className="h-3.5 w-3.5" />
                            )}
                            Take back
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
}
