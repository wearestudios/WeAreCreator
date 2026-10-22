// The draft review window on the application screen: the countdown
// (`ReviewWindowNote`, re-exported from components/collab) and the admin's
// controls.
//
// `ReviewWindowControls` is the admin's half. Whether it renders is the
// server's call (`actions.can_manage_review_window`), and every control costs
// a reason, because each one moves a deadline somebody else is waiting on and
// the audit line is read later by somebody who was not there.
import React, { useState } from "react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/admin/dialogs";
import { REVIEW_WINDOW as IDS } from "@/constants/testIds";
import ReviewWindowNote from "@/components/collab/ReviewWindowNote";

export { ReviewWindowNote };

const CONTROLS = {
    extend: {
        path: "extend",
        kicker: "Review window",
        title: "Give the reviewer more time",
        description:
            "Moves the auto-approval deadline later. The reviewer and the creator see the new date.",
        confirmLabel: "Extend",
        placeholder: "e.g. The brand's marketing lead is away until Monday.",
        extra: {
            name: "days",
            label: "Days to add",
            type: "number",
            required: true,
            placeholder: "1 to 14",
        },
        done: "Review window extended",
    },
    pause: {
        path: "pause",
        kicker: "Review window",
        title: "Pause auto-approval",
        description:
            "Stops the clock until you resume it. The time it spends paused is given back.",
        confirmLabel: "Pause",
        placeholder: "e.g. Waiting on legal sign-off for the claim in the caption.",
        done: "Auto-approval paused",
    },
    resume: {
        path: "resume",
        kicker: "Review window",
        title: "Resume auto-approval",
        description: "Starts the clock again, with the paused time added to the deadline.",
        confirmLabel: "Resume",
        placeholder: "e.g. Legal signed off.",
        done: "Auto-approval resumed",
    },
    approve: {
        path: "approve-now",
        kicker: "Review window",
        title: "Approve the draft now",
        description:
            "Ends the window and approves the draft as a WeAre decision. The creator can publish straight away. The disclosure is still checked when the live post comes in.",
        confirmLabel: "Approve now",
        placeholder: "e.g. The brand confirmed by phone that they're happy with it.",
        done: "Draft approved",
    },
};

export function ReviewWindowControls({ collaborationId, reviewWindow, onChanged }) {
    const [open, setOpen] = useState(null);
    const [busy, setBusy] = useState(false);
    if (!reviewWindow || reviewWindow.frozen_by_dispute) return null;
    const config = open ? CONTROLS[open] : null;

    const submit = async ({ reason, days }) => {
        setBusy(true);
        try {
            await api.post(
                `/admin/collaborations/${collaborationId}/draft-review/${config.path}`,
                days != null ? { reason, days } : { reason },
            );
            notifySuccess(config.done);
            setOpen(null);
            await onChanged?.();
        } catch (err) {
            notifyError(formatApiError(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.controls} className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Button
                variant="outline"
                data-testid={IDS.extend}
                className="min-h-[2.75rem]"
                onClick={() => setOpen("extend")}
            >
                Extend
            </Button>
            {reviewWindow.paused ? (
                <Button
                    variant="outline"
                    data-testid={IDS.resume}
                    className="min-h-[2.75rem]"
                    onClick={() => setOpen("resume")}
                >
                    Resume
                </Button>
            ) : (
                <Button
                    variant="outline"
                    data-testid={IDS.pause}
                    className="min-h-[2.75rem]"
                    onClick={() => setOpen("pause")}
                >
                    Pause
                </Button>
            )}
            <Button
                variant="outline"
                data-testid={IDS.approveNow}
                className="min-h-[2.75rem]"
                onClick={() => setOpen("approve")}
            >
                Approve now
            </Button>

            <ConfirmDialog
                open={Boolean(config)}
                onOpenChange={(v) => !v && setOpen(null)}
                kicker={config?.kicker}
                title={config?.title}
                description={config?.description}
                placeholder={config?.placeholder}
                confirmLabel={config?.confirmLabel}
                extra={config?.extra || null}
                submitting={busy}
                onSubmit={submit}
            />
        </div>
    );
}
