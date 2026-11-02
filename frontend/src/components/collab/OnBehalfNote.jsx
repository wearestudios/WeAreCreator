// A step WeAre took for the creator, said wherever that step is shown.
//
// `advance_collaboration` refuses the creator-owned transitions and keeps
// refusing them; what exists instead is an audited override, and the rule the
// override is held to is that a row it touched **renders differently
// everywhere it appears** — "booked by WeAre on their behalf", never a bare
// "booked". If the only visible difference were in the audit log, the
// override would have failed. This is the one renderer for that difference,
// on the creator's own card, the shared application screen, the admin's
// collaboration page and the manager's roster.
//
// It never asks what role is looking. The caller says whose voice to use:
// `voice="you"` on the creator's own surfaces, `voice="they"` everywhere
// else — the one word that changes, and the one the server cannot decide
// because it does not know which screen the block is on.
import React from "react";
import { UserCog } from "lucide-react";

import { formatDateTime } from "@/lib/time";

// What each overridden step is called, in both voices. Keyed by the step the
// server names, so a step this file has no sentence for renders nothing
// rather than a wrong one.
const SAID = {
    slot_booked: {
        you: "WeAre booked this slot on your behalf",
        they: "Booked by WeAre on the creator's behalf",
    },
    address_confirmed: {
        you: "WeAre confirmed your delivery address on your behalf",
        they: "Address confirmed by WeAre on the creator's behalf",
    },
};

/**
 * One line per overridden step: what was done, by whom, when, and why.
 *
 * `onBehalf` is the server's `on_behalf` block — `null` on every row the
 * creator moved themselves, which is what makes this render nothing most of
 * the time. `steps` narrows it to the steps a surface is actually showing
 * (the manager's roster is about the slot and nothing else).
 */
export default function OnBehalfNote({
    onBehalf,
    voice = "they",
    steps = null,
    testid,
    className = "",
}) {
    const entries = Object.entries(onBehalf || {}).filter(
        ([step, record]) => record && SAID[step] && (!steps || steps.includes(step)),
    );
    if (entries.length === 0) return null;
    return (
        <div data-testid={testid} className={`space-y-2 ${className}`}>
            {entries.map(([step, record]) => (
                <p
                    key={step}
                    data-testid={testid ? `${testid}-${step}` : undefined}
                    data-on-behalf-step={step}
                    className="flex items-start gap-2 rounded-md border border-state-pending/30 bg-state-pending/10 px-3 py-2 text-sm leading-relaxed text-state-pending"
                >
                    <UserCog className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
                    <span className="min-w-0">
                        <span className="font-medium">{SAID[step][voice] || SAID[step].they}</span>
                        {(record.by_name || record.at) && (
                            <span className="text-state-pending/80">
                                {" "}
                                — {record.by_name || "WeAre"}
                                {record.at ? `, ${formatDateTime(record.at)}` : ""}
                            </span>
                        )}
                        {record.reason && (
                            <span className="mt-0.5 block text-foreground/80">
                                “{record.reason}”
                            </span>
                        )}
                    </span>
                </p>
            ))}
        </div>
    );
}
