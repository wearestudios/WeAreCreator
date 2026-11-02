// How many rounds of changes were agreed, and how many are used.
//
// The brief says how many rounds it includes, the number is frozen into the
// terms when a creator is taken on, and a send-back past it is refused. This
// draws the server's `revisions` block — "1 of 2 used" in the same words on
// both sides — and the two decisions that come after it: the reviewer asking
// for one extra round, and the creator answering. It works out nothing for
// itself; whether either button is offered arrives as a flag decided on the
// server, like every other action on these screens.
//
// Renders nothing on a collaboration with no agreed number — every one taken
// on before the cap existed, which is unlimited by design.
import React, { useState } from "react";
import { Loader2, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { REVISIONS } from "@/constants/testIds";

export const NO_REVISIONS_LEFT = "No revisions left — approve, or ask for an extra round.";

export default function RevisionAllowance({
    collabId,
    revisions,
    canRequestExtra = false,
    canAnswer = false,
    onChanged,
    className = "",
}) {
    const [busy, setBusy] = useState(null);
    if (!revisions || revisions.unlimited) return null;

    const act = async (key, request, done) => {
        setBusy(key);
        try {
            await request();
            notifySuccess(done);
            onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That didn't go through." });
        } finally {
            setBusy(null);
        }
    };

    const pending = revisions.extra_pending;
    return (
        <div
            data-testid={REVISIONS.block(collabId)}
            className={`rounded-md border border-border bg-muted/40 px-3 py-2.5 text-meta ${className}`}
        >
            <p className="flex items-center gap-2 text-foreground">
                <RotateCcw className="h-3.5 w-3.5 flex-none text-muted-foreground" aria-hidden="true" />
                <span>
                    Rounds of changes:{" "}
                    <span data-testid={REVISIONS.used(collabId)} className="font-medium">
                        {revisions.label}
                    </span>
                    {revisions.extra > 0 && (
                        <span className="text-muted-foreground">
                            {" "}
                            (includes {revisions.extra} extra agreed)
                        </span>
                    )}
                </span>
            </p>

            {revisions.exhausted && !pending && !canAnswer && (
                <p data-testid={REVISIONS.none(collabId)} className="mt-1.5 text-muted-foreground">
                    {NO_REVISIONS_LEFT}
                </p>
            )}

            {pending && !canAnswer && (
                <p data-testid={REVISIONS.pending(collabId)} className="mt-1.5 text-muted-foreground">
                    An extra round was asked for — waiting on the creator's answer.
                </p>
            )}

            {canRequestExtra && (
                <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    data-testid={REVISIONS.askExtra(collabId)}
                    disabled={busy !== null}
                    onClick={() =>
                        act(
                            "ask",
                            () => api.post(`/collaborations/${collabId}/revisions/extra`, {}),
                            "Asked — the creator decides",
                        )
                    }
                    className="mt-2 rounded-full"
                >
                    {busy === "ask" && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
                    Ask for an extra round
                </Button>
            )}

            {canAnswer && (
                <div className="mt-2">
                    <p className="text-foreground">
                        You've been asked for one more round of changes than your brief included.
                        It's your call.
                    </p>
                    {revisions.extra_request?.note && (
                        <p className="mt-1 text-muted-foreground">“{revisions.extra_request.note}”</p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-2">
                        <Button
                            type="button"
                            size="sm"
                            data-testid={REVISIONS.accept(collabId)}
                            disabled={busy !== null}
                            onClick={() =>
                                act(
                                    "accept",
                                    () => api.post(`/creator/collaborations/${collabId}/revisions/extra/accept`, {}),
                                    "One more round added",
                                )
                            }
                            className="rounded-full bg-primary text-primary-foreground hover:bg-primary-hover"
                        >
                            Accept one more round
                        </Button>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            data-testid={REVISIONS.decline(collabId)}
                            disabled={busy !== null}
                            onClick={() =>
                                act(
                                    "decline",
                                    () => api.post(`/creator/collaborations/${collabId}/revisions/extra/decline`, {}),
                                    "Declined",
                                )
                            }
                            className="rounded-full"
                        >
                            Decline
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
