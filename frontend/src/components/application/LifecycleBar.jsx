// The lifecycle of one application, across the top of its screen.
//
// Every state from applied to closed, which one it is on, and — the part that
// matters operationally — who has to do the next thing. An application sitting
// still is the normal case in this product; the question is never "what
// happened" but "whose move is it, and have they been told".
//
// The steps come from the server (`lifecycle.steps`). Rebuilding the ladder
// here would be a second copy of the state machine, and the bug this screen
// exists to fix was two surfaces disagreeing about what one state meant.
import React from "react";
import { Check } from "lucide-react";

import { APPLICATION } from "@/constants/testIds";

// Who is being waited on. The creator gets the accent because those are the
// steps where nobody at WeAre can do anything except chase.
const OWNER = {
    admin: { label: "WeAre", tone: "text-sky-300 border-sky-500/30 bg-sky-500/10" },
    brand: { label: "The brand", tone: "text-violet-300 border-violet-500/30 bg-violet-500/10" },
    creator: { label: "The creator", tone: "text-ember-500 border-ember-500/40 bg-ember-500/15" },
};

const STEP_LABEL = {
    applied: "Applied",
    verified: "Approved",
    accepted: "Accepted",
    commercial_agreed: "Fee agreed",
    slot_booked: "Slot booked",
    attended: "Attended",
    content_submitted: "Content in",
    content_approved: "Content approved",
    in_payment: "In payment",
    closed: "Closed",
};

const EXIT_LABEL = {
    declined: "Declined — the brand passed on this one.",
    cancelled: "Cancelled.",
};

export default function LifecycleBar({ lifecycle }) {
    if (!lifecycle) return null;

    const { steps = [], next_action: next, exited, current } = lifecycle;
    const owner = next?.owner ? OWNER[next.owner] : null;

    return (
        <div data-testid={APPLICATION.lifecycle} className="min-w-0">
            {/* The bar itself. Horizontally scrollable rather than wrapped: ten
                steps wrapped onto three rows on a phone stops reading as a
                sequence, which is the only thing it is for. */}
            <ol
                className="flex gap-1 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                aria-label="Application lifecycle"
            >
                {steps.map((step) => {
                    const state = step.current
                        ? "current"
                        : step.done
                          ? "done"
                          : "todo";
                    return (
                        <li
                            key={step.state}
                            data-testid={APPLICATION.lifecycleStep(step.state)}
                            data-state={state}
                            aria-current={step.current ? "step" : undefined}
                            className={
                                "flex flex-none items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[10px] uppercase tracking-[0.16em] transition-colors duration-200 " +
                                (step.current
                                    ? "border-ember-500/40 bg-ember-500/15 text-ember-500"
                                    : step.done
                                      ? "border-white/10 bg-white/5 text-muted-foreground"
                                      : "border-white/10 bg-transparent text-muted-foreground/50")
                            }
                        >
                            {step.done && <Check className="h-3 w-3 flex-none" aria-hidden="true" />}
                            {STEP_LABEL[step.state] || step.state}
                        </li>
                    );
                })}
            </ol>

            {/* An exit is the bar stopping, not a step on it — so it is said in
                words rather than drawn as an eleventh box. */}
            {exited ? (
                <p
                    data-testid={APPLICATION.lifecycleExit}
                    className="mt-3 rounded-md border border-white/10 bg-card px-4 py-3 text-sm text-muted-foreground grain-surface"
                >
                    {EXIT_LABEL[current] || "This application has ended."}
                </p>
            ) : next ? (
                <div
                    data-testid={APPLICATION.nextAction}
                    className="mt-3 flex flex-col gap-2 rounded-md border border-white/10 bg-card px-4 py-3 grain-surface sm:flex-row sm:items-center sm:gap-3"
                >
                    <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Next
                    </span>
                    {owner && (
                        <span
                            data-testid={APPLICATION.nextOwner}
                            className={
                                "inline-flex w-fit flex-none items-center rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                                owner.tone
                            }
                        >
                            {owner.label}
                        </span>
                    )}
                    <span className="min-w-0 text-sm">
                        {next.label}
                        {next.detail ? (
                            <span className="block text-xs text-muted-foreground sm:inline sm:before:content-['_—_']">
                                {next.detail}
                            </span>
                        ) : null}
                    </span>
                </div>
            ) : null}
        </div>
    );
}
