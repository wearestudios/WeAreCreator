// Flagging a collaboration as having gone off-platform.
//
// **It raises a question and penalises nobody**, and the copy says so, because
// the people with a reason to press this are also people who might be annoyed
// about something else entirely. A flag that read like a punishment button
// would be pressed like one.
//
// On the shared application screen, which is mounted at `/admin`, `/brand` and
// `/manager` and at no creator route — but that is not what keeps the creator
// away from it. `can_report_circumvention` is decided server-side like every
// other action here, and this component **never asks what role is looking**.
import React, { useState } from "react";
import { Loader2, ShieldAlert } from "lucide-react";

import { CIRCUMVENTION as IDS } from "@/constants/testIds";
import { CIRCUMVENTION_REASONS } from "@/lib/platformTerms";
import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";

// The server's floor, mirrored so the button explains itself rather than
// producing a 422 somebody has to read as a toast.
const MIN_EVIDENCE = 10;

export default function CircumventionReport({ collabId, actions = {}, open, onReported }) {
    const [reason, setReason] = useState(CIRCUMVENTION_REASONS[0].value);
    const [evidence, setEvidence] = useState("");
    const [busy, setBusy] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);

    // Already with an admin. Said rather than hidden — somebody who flagged it
    // yesterday wants to know it landed, and a button that quietly vanished
    // reads as the report having been lost.
    if (open) {
        return (
            <p
                data-testid={IDS.reportPending}
                className="flex items-start gap-2 text-xs text-amber-300/90"
            >
                <ShieldAlert aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                    This collaboration is flagged as having gone off-platform and is
                    waiting on a review. Nothing has happened to the creator.
                </span>
            </p>
        );
    }

    if (!actions.can_report_circumvention) return null;

    const tooShort = evidence.trim().length < MIN_EVIDENCE;

    const submit = async () => {
        setBusy(true);
        try {
            await api.post(`/collaborations/${collabId}/circumvention-report`, {
                reason,
                evidence: evidence.trim(),
            });
            notifySuccess("Flagged. Somebody here will look at it.");
            setDialogOpen(false);
            setEvidence("");
            onReported?.();
        } catch (err) {
            notifyError(formatApiError(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.report}>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogTrigger asChild>
                    <Button
                        variant="outline"
                        data-testid={IDS.reportOpen}
                        className="min-h-[2.75rem] w-full sm:w-auto"
                    >
                        <ShieldAlert className="mr-2 h-4 w-4" />
                        Flag as off-platform
                    </Button>
                </DialogTrigger>
                {/* The shared dialog primitive's own grain is kept. The
                    console turns it off at its own call sites, but this one
                    component is mounted on the brand's screens too, and a
                    dialog that looked different depending on which console
                    opened it would be the variant this screen exists not to
                    have. */}
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Flag this as off-platform</DialogTitle>
                        <DialogDescription>
                            This raises a review item and nothing else. Nobody is
                            suspended, nothing is cancelled, and the creator is not told
                            — an admin reads it and decides.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="circumvention-reason">What happened</Label>
                            <select
                                id="circumvention-reason"
                                data-testid={IDS.reportReason}
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                className="min-h-[2.75rem] w-full rounded-lg border border-white/10 bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                            >
                                {CIRCUMVENTION_REASONS.map((r) => (
                                    <option key={r.value} value={r.value}>
                                        {r.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="circumvention-evidence">
                                What you saw, and where
                            </Label>
                            <Textarea
                                id="circumvention-evidence"
                                data-testid={IDS.reportEvidence}
                                rows={4}
                                value={evidence}
                                onChange={(e) => setEvidence(e.target.value)}
                                placeholder="The date, the conversation, who said what. Somebody has to decide whether a creator keeps their account on this."
                            />
                            {/* **Required, and not a formality.** A reason code
                                on its own is not something anybody can weigh. */}
                            <p className="text-xs text-muted-foreground">
                                A reason code alone is not enough to decide on. Say what
                                actually happened.
                            </p>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="ghost"
                            onClick={() => setDialogOpen(false)}
                            disabled={busy}
                            className="min-h-[2.75rem]"
                        >
                            Cancel
                        </Button>
                        <Button
                            data-testid={IDS.reportSubmit}
                            onClick={submit}
                            disabled={busy || tooShort}
                            className="min-h-[2.75rem]"
                        >
                            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Send for review
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
