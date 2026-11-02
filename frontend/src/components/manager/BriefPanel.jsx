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
import BriefChecklist from "@/components/campaign/BriefChecklist";
import PayoutNote from "@/components/campaign/PayoutNote";
import { hasBriefDetails } from "@/lib/briefDetails";
import { formatCompensation } from "@/lib/compensation";
import BudgetMeter from "@/components/campaign/BudgetMeter";
import { budgetApplies } from "@/lib/budget";
import { MANAGER_BRIEF as IDS } from "@/constants/testIds";

import { EmptyState } from "./shared";

export default function BriefPanel({ campaign }) {
    const brief = (campaign?.brief || "").trim();
    const items = campaign?.deliverable_items || [];
    const sentence = campaign?.deliverables;

    // The structured half counts as a brief too: a campaign with three don'ts
    // and no paragraph has plenty for the manager to check against, and the
    // empty state would say otherwise.
    if (!brief && items.length === 0 && !sentence && !hasBriefDetails(campaign?.brief_details)) {
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
            <div className="rounded-md border border-border bg-card p-5 grain-surface">
                <p className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground">
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
                    className="mt-4 border-t border-border pt-4 text-meta text-muted-foreground"
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

            {/* What the brief promised about *when* that money lands, and
                about getting there — because the person in the room is the
                one a creator asks, and answering "I'll check" to the
                question the brief already answers is how the promise stops
                being read as one. One renderer with the brief and the share
                page, so the three cannot word it differently. */}
            <PayoutNote campaign={campaign} />

            {/* The cap, because on a weare-run brief the manager is the runner
                and therefore the one agreeing fees against it. Same component
                and same figures the brand and the admin read. */}
            {budgetApplies(campaign) && <BudgetMeter budget={campaign.budget} />}

            {/* The do's, don'ts and tags, on the screen of the person
                standing in the room while it is being shot — the last moment
                any of it can still be got right for free. Above the narrative
                because it is the checkable half. */}
            <BriefChecklist details={campaign.brief_details} />

            {brief && (
                <div className="rounded-md border border-border bg-card p-5 grain-surface">
                    <p className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground">
                        The brief
                    </p>
                    {/* `whitespace-pre-wrap`: a brand writes these with line
                        breaks and losing them turns a list into a paragraph. */}
                    <p
                        data-testid={IDS.text}
                        className="mt-3 whitespace-pre-wrap text-body leading-relaxed"
                    >
                        {brief}
                    </p>
                </div>
            )}
        </section>
    );
}
