// Work that fell over, and on whose call.
//
// **On the creator's page and the brand's, from one component**, because the
// same event is two different questions: a brand's page asks "how often do we
// pull out on people", a creator's asks "how often does this get cancelled
// around them". Two panels would answer them differently the first time one
// was changed.
//
// It renders nothing when nothing has fallen over. An empty box headed
// "Cancellations" reads as a fact about the record rather than the absence of
// one, and this is a panel somebody glances at before agreeing to staff a
// shoot that costs money.
import React from "react";
import { CircleSlash } from "lucide-react";

import { formatDateTime } from "@/lib/time";
import { ADMIN_CANCELLATIONS as IDS } from "@/constants/testIds";

import { CampaignLink, CreatorLink } from "./links";
import { PANEL, TEXT } from "./console/tokens";

/**
 * How much warning there was, said the way a person would say it.
 *
 * **The fact, not a verdict.** Whether four days is enough notice is a
 * commercial judgement that differs by brand and by venue; the panel reports
 * the number and leaves the judgement to whoever is reading.
 */
const noticeText = (days) => {
    if (days == null) return null;
    if (days < 0) return `${Math.abs(days)} days after the shoot`;
    if (days === 0) return "on the day";
    return `${days} day${days === 1 ? "" : "s"} before`;
};

export default function CancellationHistory({ rows, showCreator = false }) {
    if (!rows || rows.length === 0) return null;

    return (
        <ul data-testid={IDS.list} className="space-y-3">
            {rows.map((r) => {
                const notice = noticeText(r.notice_days);
                return (
                    <li
                        key={r.collaboration_id}
                        data-testid={IDS.row(r.collaboration_id)}
                        className={`${PANEL} p-4`}
                    >
                        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                            <CircleSlash
                                aria-hidden="true"
                                className="h-3.5 w-3.5 shrink-0 self-center text-muted-foreground"
                            />
                            {/* Withdrawn and cancelled are different events and
                                the row says which. A withdrawal happens before
                                anybody is committed and is the creator's to
                                make — printing it as a cancellation would put
                                a black mark where there is none. */}
                            <span className="text-sm">
                                {r.state === "withdrawn" ? "Withdrawn" : "Cancelled"}
                            </span>
                            <span className={`${TEXT.meta} text-muted-foreground`}>
                                by {r.cancelled_by || "somebody"}
                                {notice ? ` · ${notice}` : ""}
                                {r.from_state ? ` · at ${r.from_state.replace(/_/g, " ")}` : ""}
                            </span>
                        </div>

                        <p className={`mt-2 ${TEXT.meta} text-muted-foreground`}>
                            <CampaignLink id={r.campaign_id} title={r.campaign_title} />
                            {showCreator && r.creator_id ? (
                                <>
                                    {" · "}
                                    <CreatorLink id={r.creator_id} name={r.creator_name} />
                                </>
                            ) : null}
                            {r.at ? ` · ${formatDateTime(r.at)}` : ""}
                        </p>

                        {r.reason && <p className="mt-2 text-sm">“{r.reason}”</p>}

                        {r.kill_fee != null && (
                            <p
                                data-testid={IDS.fee(r.collaboration_id)}
                                className={`mt-2 inline-flex rounded border border-ember-500/30 bg-ember-500/10 px-2 py-0.5 ${TEXT.meta} text-ember-500`}
                            >
                                ₹{Number(r.kill_fee).toLocaleString("en-IN")} cancellation fee
                            </p>
                        )}
                    </li>
                );
            })}
        </ul>
    );
}
