// Asking to be forgotten.
//
// **A right, not a feature.** The DPDP Act 2023 gives a person the right to
// erasure of their personal data, and until this existed the only way to
// exercise it was to email somebody and hope. A product that collects a
// WhatsApp number, a home address, a map pin, a PAN and a bank account and has
// no way to give any of it back is not one that can honestly claim to handle
// them carefully.
//
// **The screen has to say what "deleted" actually means**, because it does not
// mean everything vanishes: the transactions stay, without the person in them.
// Somebody agreeing to this without being told that has not agreed to what
// happens — and finding out afterwards is exactly the surprise the right
// exists to prevent.
//
// Blocked while work is in flight, and the block **names the work**. "You have
// three collaborations open" is not something anybody can act on; "the Toit
// tasting, waiting on your draft" is.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Loader2, Trash2 } from "lucide-react";

import { api, apiErrorCode, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ACCOUNT as IDS } from "@/constants/testIds";
import { formatDateTime } from "@/lib/time";

/** What is kept and what goes, said before anybody agrees to it. */
const WHAT_HAPPENS = [
    "Your name, number, email, address and photo are erased.",
    "Your payout details and PAN are erased.",
    "Your Instagram connection is removed and its token deleted.",
    "Records of completed work stay, without your name on them — a brand's proof of what it paid for, and ours for accounting.",
];

export default function DeleteAccount() {
    const [state, setState] = useState(null);
    const [open, setOpen] = useState(false);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const [blocked, setBlocked] = useState(null);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/account/deletion-request");
            setState(data);
        } catch {
            // A panel, not the page. Failing to read it must not cost somebody
            // the profile screen it sits at the bottom of.
            setState({ eligible: false, request: null, blocking: [] });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    if (!state?.eligible) return null;

    const request = state.request;

    const submit = async () => {
        setBusy(true);
        setBlocked(null);
        try {
            await api.post("/account/deletion-request", {
                reason: reason.trim() || null,
            });
            notifySuccess("Asked — we'll come back to you");
            setOpen(false);
            await load();
        } catch (err) {
            // The server's structured refusal carries the list. Rendering it
            // here rather than as a toast, because it is a set of things to go
            // and do, not a message to dismiss.
            //
            // **And the dialog closes, or the list is behind it.** The refusal
            // renders in the panel, so leaving the dialog up shows the person
            // an unchanged form and a button that did nothing — the one reading
            // of a refusal worse than the refusal itself.
            if (apiErrorCode(err) === "work_in_flight") {
                setBlocked(err?.response?.data?.detail || null);
                setOpen(false);
            } else {
                notifyError(err, { fallback: formatApiError(err) });
            }
        } finally {
            setBusy(false);
        }
    };

    const cancelRequest = async () => {
        setBusy(true);
        try {
            await api.delete("/account/deletion-request");
            notifySuccess("Request withdrawn — your account stays");
            await load();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be withdrawn." });
        } finally {
            setBusy(false);
        }
    };

    // Already asked: the panel becomes the status of the request rather than
    // the button that made it.
    if (request) {
        return (
            <section
                data-testid={IDS.deletionPending}
                className="rounded-md border border-amber-500/30 bg-amber-500/10 p-5"
            >
                <p className="text-xs uppercase tracking-[0.2em] text-amber-200">
                    Deletion requested
                </p>
                <p className="mt-3 text-sm leading-relaxed text-amber-100/90">
                    You asked on {formatDateTime(request.requested_at)}. We'll come back
                    to you once somebody has been through your account. You can change
                    your mind until then.
                </p>
                <Button
                    variant="outline"
                    onClick={cancelRequest}
                    disabled={busy}
                    data-testid={IDS.deletionWithdraw}
                    className="mt-4 min-h-[2.75rem] border-white/20 bg-transparent"
                >
                    Keep my account
                </Button>
            </section>
        );
    }

    return (
        <section
            data-testid={IDS.deletionSection}
            className="rounded-md border border-white/10 bg-card p-5 grain-surface"
        >
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Delete your account
            </p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                You can ask us to erase your personal details at any time. Somebody
                reads every request — it isn't automatic — and we'll tell you when it's
                done.
            </p>

            {/* The blocking list, when the server has just refused. Above the
                button rather than replacing it: the work clears and then this
                becomes possible, so the button is not gone, it is not yet. */}
            {blocked?.blocking?.length > 0 && (
                <div
                    data-testid={IDS.deletionBlocked}
                    className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 p-4"
                >
                    <p className="flex items-center gap-2 text-sm text-amber-200">
                        <AlertTriangle aria-hidden="true" className="h-4 w-4 flex-none" />
                        {blocked.message}
                    </p>
                    <ul className="mt-3 space-y-1.5 text-sm text-amber-100/90">
                        {blocked.blocking.map((b) => (
                            <li key={b.collaboration_id}>
                                <Link
                                    to="/dashboard"
                                    className="underline decoration-white/20 underline-offset-4"
                                >
                                    {b.campaign_title || "A campaign"}
                                </Link>{" "}
                                — {b.state?.replace(/_/g, " ")}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <Button
                variant="outline"
                onClick={() => setOpen(true)}
                data-testid={IDS.deletionOpen}
                className="mt-4 min-h-[2.75rem] border-destructive/40 bg-transparent text-destructive hover:bg-destructive/10"
            >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete my account
            </Button>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent data-testid={IDS.deletionDialog} className="sm:max-w-lg">
                    <DialogHeader className="text-left">
                        <DialogTitle>Delete your account?</DialogTitle>
                        <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                            Here's exactly what happens.
                        </DialogDescription>
                    </DialogHeader>

                    <ul className="space-y-2 text-sm leading-relaxed text-muted-foreground">
                        {WHAT_HAPPENS.map((line) => (
                            <li key={line} className="flex gap-2">
                                <span aria-hidden="true" className="text-ember-500">
                                    ·
                                </span>
                                {line}
                            </li>
                        ))}
                    </ul>

                    <label className="block">
                        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                            Anything you'd like to tell us{" "}
                            <span className="opacity-60">(optional)</span>
                        </span>
                        {/* Optional, deliberately. Nobody has to justify
                            leaving, and a required box here would be a toll on
                            a right. */}
                        <Textarea
                            rows={2}
                            maxLength={1000}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            data-testid={IDS.deletionReason}
                            className="mt-2 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                        />
                    </label>

                    <DialogFooter className="gap-2">
                        <Button
                            variant="ghost"
                            onClick={() => setOpen(false)}
                            data-testid={IDS.deletionCancel}
                        >
                            Keep my account
                        </Button>
                        <Button
                            onClick={submit}
                            disabled={busy}
                            data-testid={IDS.deletionSubmit}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Ask to be deleted
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </section>
    );
}
