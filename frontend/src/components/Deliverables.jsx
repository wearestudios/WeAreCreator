// What a brief asks for, drawn.
//
// One component wherever the ask is shown, for the reason the structure exists
// at all: a campaign that asks for a reel and three stories should say so in
// the same words on the creator's feed, the brand's own console, the admin's
// review queue and the campaign page. Before this every surface printed the
// brand's free text, which meant the words changed with whoever typed them.
//
// **A campaign posted before the structured field existed renders its
// sentence.** That is not a degraded path — the sentence is what those briefs
// have, and it is also what the server derives from the structure, so the two
// forms of the same ask read alike.
import React from "react";

import {
    DELIVERABLE_PLURALS,
    DELIVERABLE_SINGULARS,
    deliverableItems,
    deliverableLabel,
} from "@/lib/deliverables";

/**
 * The ask as counted chips, falling back to the brief's sentence.
 *
 * `testid` lands on the wrapper either way, so a test asking "what does this
 * campaign want" finds one element whichever shape the campaign is in.
 */
export function DeliverableList({ campaign, testid, className = "" }) {
    const items = deliverableItems(campaign);
    const text = (campaign?.deliverables || "").trim();

    if (items.length === 0) {
        if (!text) return null;
        return (
            <p
                data-testid={testid}
                className={"text-sm leading-relaxed text-muted-foreground " + className}
            >
                {text}
            </p>
        );
    }

    return (
        <ul
            data-testid={testid}
            className={"flex flex-wrap gap-2 " + className}
        >
            {items.map((item) => (
                <li
                    key={item.type}
                    data-testid={`deliverable-${item.type}`}
                    className="inline-flex items-baseline gap-1.5 rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm"
                >
                    {/* The number leads and is the heavier of the two: the
                        format is the category, the count is the commitment.
                        The word comes from the vocabulary's own plural — "3
                        Storys" is what appending an s gets you. */}
                    <span className="font-medium tabular-nums">{item.quantity}</span>
                    <span className="text-muted-foreground">
                        {item.quantity === 1
                            ? DELIVERABLE_SINGULARS[item.type]
                            : DELIVERABLE_PLURALS[item.type]}
                    </span>
                </li>
            ))}
        </ul>
    );
}

/**
 * The same ask on one line, for a card that has room for a sentence and not a
 * row of chips.
 */
export function DeliverableSummary({ campaign, testid, className = "" }) {
    const items = deliverableItems(campaign);
    const text =
        items.length > 0
            ? items.map(deliverableLabel).join(" · ")
            : (campaign?.deliverables || "").trim();
    if (!text) return null;
    return (
        <span data-testid={testid} className={className}>
            {text}
        </span>
    );
}

export default DeliverableList;
