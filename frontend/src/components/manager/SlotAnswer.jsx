// The second half of the booking handshake, on the screen the manager is on.
//
// A creator picks a time and the seat is held — but nothing is arranged until
// whoever holds the venue's diary says yes. On a weare-run campaign that is
// this manager, and until now there was no way for them to say it: the two
// routes existed, `manager_slot_pending` notified them, and the notification
// deep-linked to a page that showed neither the request nor a button. Every
// booking sat pending until an admin answered it from the console.
//
// **A band above everything, not a tab.** Somebody is holding a seat waiting
// on an answer; that is not a section you go and look in. It renders nothing
// when there is nothing waiting, for the same reason `QueueBanner` does — a
// permanent empty box trains you to stop reading that part of the screen.
//
// The refusal takes a **required reason**, because without one the creator
// picks the same impossible time again. Confirming does not.
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Check, X } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { MANAGER_SLOT_ANSWER as IDS } from "@/constants/testIds";

import { BigButton, TOUCH, formatDay, formatTime } from "./shared";

/** Everyone on this roster whose booking nobody has answered. */
export const pendingRows = (rows) => (rows || []).filter((r) => r.slot_pending);

export default function SlotAnswer({ rows, onChanged }) {
    const waiting = pendingRows(rows);
    const [busyId, setBusyId] = useState(null);
    const [decliningFor, setDecliningFor] = useState(null);

    if (waiting.length === 0) return null;

    const confirm = async (row) => {
        setBusyId(row.collaboration_id);
        try {
            await api.post(
                `/manager/collaborations/${row.collaboration_id}/slot/confirm`,
            );
            notifySuccess(`${row.name || "They"} are confirmed — they've been told`);
            await onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be confirmed." });
        } finally {
            setBusyId(null);
        }
    };

    const decline = async (reason) => {
        const row = decliningFor;
        setBusyId(row.collaboration_id);
        try {
            await api.post(
                `/manager/collaborations/${row.collaboration_id}/slot/decline`,
                { reason },
            );
            notifySuccess("Turned down — they can pick another time");
            setDecliningFor(null);
            await onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be turned down." });
        } finally {
            setBusyId(null);
        }
    };

    return (
        <section
            data-testid={IDS.band}
            className="mt-6 rounded-md border border-ember-500/40 bg-ember-500/10 p-4"
        >
            <p className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-ember-500">
                <CalendarClock aria-hidden="true" className="h-3.5 w-3.5" />
                {waiting.length === 1
                    ? "A booking is waiting on you"
                    : `${waiting.length} bookings are waiting on you`}
            </p>

            <ul className="mt-4 space-y-3">
                {waiting.map((r) => (
                    <li
                        key={r.collaboration_id}
                        data-testid={IDS.row(r.collaboration_id)}
                        className="rounded-md border border-white/10 bg-card p-4"
                    >
                        <p className="text-sm">
                            {/* The name opens the whole application — the fast
                                answer is here, the reason to hesitate is
                                there. */}
                            <Link
                                to={`/manager/applications/${r.collaboration_id}`}
                                className="underline decoration-white/20 underline-offset-4 hover:text-ember-500"
                            >
                                {r.name || "A creator"}
                            </Link>{" "}
                            asked for{" "}
                            <span className="text-ember-500">
                                {r.slot_time
                                    ? `${formatDay(r.slot_time)}, ${formatTime(r.slot_time)}`
                                    : "a time"}
                            </span>
                        </p>
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                            <BigButton
                                type="button"
                                busy={busyId === r.collaboration_id}
                                onClick={() => confirm(r)}
                                data-testid={IDS.confirm(r.collaboration_id)}
                                className="bg-ember-500 text-black hover:bg-ember-400 sm:flex-1"
                            >
                                <Check className="mr-2 h-4 w-4" />
                                Confirm
                            </BigButton>
                            <BigButton
                                type="button"
                                variant="outline"
                                disabled={busyId === r.collaboration_id}
                                onClick={() => setDecliningFor(r)}
                                data-testid={IDS.decline(r.collaboration_id)}
                                className="border-white/15 bg-transparent sm:flex-1"
                            >
                                <X className="mr-2 h-4 w-4" />
                                Doesn't work
                            </BigButton>
                        </div>
                    </li>
                ))}
            </ul>

            <DeclineSheet
                row={decliningFor}
                busy={busyId === decliningFor?.collaboration_id}
                onClose={() => setDecliningFor(null)}
                onSubmit={decline}
            />
        </section>
    );
}

/**
 * Turning a time down, with the reason that stops it happening again.
 *
 * The creator is told either way; this is the half where what we say matters,
 * because "no" with nothing after it sends them back to the picker to choose
 * the same evening.
 */
function DeclineSheet({ row, busy, onClose, onSubmit }) {
    const [reason, setReason] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (row) {
            setReason("");
            setErr("");
        }
    }, [row]);

    const submit = () => {
        if (reason.trim().length < 3) {
            setErr("Say why — otherwise they pick the same time again.");
            return;
        }
        onSubmit(reason.trim());
    };

    return (
        <Sheet open={Boolean(row)} onOpenChange={(v) => !v && onClose()}>
            <SheetContent
                side="bottom"
                data-testid={IDS.sheet}
                className="rounded-t-md border-t border-white/10 bg-card grain-surface"
            >
                <SheetTitle className="font-serif text-2xl leading-tight">
                    That time doesn't work?
                </SheetTitle>
                <SheetDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {row?.name || "They"} keep their place on the campaign and can pick
                    another slot. They see what you write here.
                </SheetDescription>

                <Textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    rows={3}
                    maxLength={500}
                    data-testid={IDS.reason}
                    placeholder="e.g. Kitchen is closed Monday evenings — any lunchtime works"
                    className="mt-5 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                />
                {err && (
                    <p data-testid={IDS.error} className={`mt-3 text-sm text-destructive`}>
                        {err}
                    </p>
                )}

                <div className="mt-6 flex flex-col gap-3">
                    <BigButton
                        type="button"
                        busy={busy}
                        onClick={submit}
                        data-testid={IDS.submit}
                        className={`border border-white/15 bg-transparent ${TOUCH}`}
                    >
                        Send it back
                    </BigButton>
                    <BigButton
                        type="button"
                        variant="outline"
                        onClick={onClose}
                        data-testid={IDS.cancel}
                        className="border-white/15 bg-transparent"
                    >
                        Back
                    </BigButton>
                </div>
            </SheetContent>
        </Sheet>
    );
}
