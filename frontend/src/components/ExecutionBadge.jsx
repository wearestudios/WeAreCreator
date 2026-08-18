// Who runs this campaign, as a chip.
//
// One component rather than a pill per console, because the whole point of
// `execution_owner` is that the admin, the brand and the creator agree about
// it — and three separately-written badges is how they stop agreeing.
import React from "react";

import { executionMeta, executionOwner } from "@/lib/execution";
import { EXECUTION } from "@/constants/testIds";

/**
 * @param {object|string} campaign  a campaign, or the owner string itself
 * @param {"default"|"creator"} audience  which wording to use — a creator is
 *   told who they will be dealing with, everyone else reads the short label
 */
export default function ExecutionBadge({ campaign, audience = "default", className = "" }) {
    const owner = executionOwner(campaign);
    const meta = executionMeta(campaign);
    return (
        <span
            data-testid={EXECUTION.badge(owner)}
            title={audience === "creator" ? meta.creatorNote : undefined}
            className={
                "inline-flex flex-none items-center rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                meta.tone +
                (className ? ` ${className}` : "")
            }
        >
            {audience === "creator" ? meta.creatorLabel : meta.label}
        </span>
    );
}

/**
 * The same fact as a sentence, for the one place per screen that has room to
 * say what it means rather than just naming it.
 */
export function ExecutionNote({ campaign, audience = "default", className = "" }) {
    const owner = executionOwner(campaign);
    const meta = executionMeta(campaign);
    const note =
        audience === "creator"
            ? meta.creatorNote
            : audience === "brand"
              ? meta.brandNote
              : meta.adminNote;
    return (
        <p
            data-testid={EXECUTION.note(owner)}
            className={"text-sm text-muted-foreground " + className}
        >
            {note}
        </p>
    );
}
