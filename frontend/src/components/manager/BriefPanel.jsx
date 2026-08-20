// What the shoot is actually for.
//
// **No manager surface carried this at all.** The person running the day could
// see who was coming, when, and where — and not one word of what the creators
// had been asked to produce. "How many stories was it again?" was a question
// with no answer on the screen, standing in a venue, so it became a phone call
// to whoever posted the brief.
//
// It sits in its own tab rather than on the roster, because it is the same for
// everybody on the campaign: repeating it per row would be the same paragraph
// eight times on a phone.
import React from "react";
import { FileText } from "lucide-react";

import { DeliverableList } from "@/components/Deliverables";
import { formatCompensation } from "@/lib/compensation";
import { MANAGER_BRIEF as IDS } from "@/constants/testIds";

import { EmptyState } from "./shared";

export default function BriefPanel({ campaign }) {
    const brief = (campaign?.brief || "").trim();
    const items = campaign?.deliverable_items || [];
    const sentence = campaign?.deliverables;

    if (!brief && items.length === 0 && !sentence) {
        return (
            <EmptyState testid={IDS.empty} Icon={FileText}>
                This campaign has no brief on it yet. The brand writes one when they
                post it — ask the WeAre team if you need the detail today.
            </EmptyState>
        );
    }

    return (
        <section data-testid={IDS.section} className="space-y-4">
            {/* The ask first, because it is the thing being checked against on
                the day. The paragraph is context; the counts are the job. */}
            <div className="rounded-md border border-white/10 bg-card p-5 grain-surface">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    Each creator delivers
                </p>
                <div className="mt-3" data-testid={IDS.deliverables}>
                    {/* The one renderer, so this reads the same here as it does
                        on the creator's card and the brand's board — falling
                        back to the stored sentence for a brief written before
                        the counts existed. */}
                    <DeliverableList campaign={campaign} />
                </div>

                <p
                    data-testid={IDS.fee}
                    className="mt-4 border-t border-white/10 pt-4 text-sm text-muted-foreground"
                >
                    {/* Through `formatCompensation`, so a barter shoot says so
                        rather than printing the vestigial budget as money the
                        creator is owed. */}
                    <span className="text-foreground">
                        {formatCompensation(campaign).text}
                    </span>{" "}
                    per creator
                </p>
            </div>

            {brief && (
                <div className="rounded-md border border-white/10 bg-card p-5 grain-surface">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        The brief
                    </p>
                    {/* `whitespace-pre-wrap`: a brand writes these with line
                        breaks and losing them turns a list into a paragraph. */}
                    <p
                        data-testid={IDS.text}
                        className="mt-3 whitespace-pre-wrap text-sm leading-relaxed"
                    >
                        {brief}
                    </p>
                </div>
            )}
        </section>
    );
}
