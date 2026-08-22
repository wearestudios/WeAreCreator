// Asking for a live post to come down, and the creator's answer.
//
// Content that is factually wrong, off-brand or legally problematic had no
// path at all: the brand messaged whoever they had a number for, the creator
// either did it or did not, and nothing recorded which. This is that
// conversation with a deadline on it and a record behind it.
//
// **Deliberately not the review flow.** A draft that needs changing is a
// change request; this is work that is already published, which is a different
// urgency and a different ask. The server refuses a takedown on anything not
// delivered, so the button is absent rather than present and 409ing.
//
// **Both answers are recorded, and neither is assumed.** A takedown that
// silently never happened and one the creator explained they could not do are
// very different facts about somebody, and the second is what stops a creator
// being marked down unfairly.
import React, { useState } from "react";
import { Clock, Loader2, ShieldAlert } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { TAKEDOWN as IDS } from "@/constants/testIds";
import { formatDateTime } from "@/lib/time";

/** Mirrors `TAKEDOWN_REASONS` in server.py. */
const REASONS = [
    { code: "factual_error", label: "Something in it is factually wrong" },
    { code: "off_brand", label: "It misrepresents the brand" },
    { code: "legal", label: "There's a legal or compliance problem" },
    { code: "rights", label: "It uses something we don't have the rights to" },
    { code: "other", label: "Something else" },
];

const OUTCOME = {
    requested: "Waiting on the creator",
    actioned: "Taken down",
    declined: "The creator says it's staying up",
    withdrawn: "Withdrawn",
};

/**
 * @param {boolean} [props.canRequest]  Server-decided. Absent on a draft.
 * @param {boolean} [props.canRespond]  The creator's side, and only theirs.
 */
export default function TakedownPanel({
    collaborationId,
    takedown,
    canRequest = false,
    canRespond = false,
    onChanged,
}) {
    const [asking, setAsking] = useState(false);
    const [code, setCode] = useState("factual_error");
    const [detail, setDetail] = useState("");
    const [note, setNote] = useState("");
    const [busy, setBusy] = useState(false);

    if (!takedown && !canRequest) return null;

    const pending = takedown?.state === "requested";
    const answering = canRespond && pending;

    const call = async (fn, success) => {
        setBusy(true);
        try {
            await fn();
            notifySuccess(success);
            setAsking(false);
            setDetail("");
            setNote("");
            onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be recorded." });
        } finally {
            setBusy(false);
        }
    };

    const request = () =>
        call(
            () =>
                api.post(`/disputes/${collaborationId}/takedown`, {
                    reason_code: code,
                    detail: detail.trim(),
                }),
            "Asked — the creator has been told."
        );

    const respond = (actioned) =>
        call(
            () =>
                api.post(`/disputes/${collaborationId}/takedown/respond`, {
                    actioned,
                    note: note.trim() || null,
                }),
            actioned ? "Thanks — recorded." : "Recorded, and they've been told why."
        );

    return (
        <section
            data-testid={IDS.panel}
            className={`rounded-md border p-4 ${
                pending
                    ? "border-amber-400/40 bg-amber-400/10"
                    : "border-white/10 bg-card"
            }`}
        >
            <div className="flex flex-wrap items-center gap-2">
                <ShieldAlert
                    aria-hidden="true"
                    className={`h-4 w-4 ${pending ? "text-amber-300" : "text-muted-foreground"}`}
                />
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    Takedown
                </p>
                {takedown && (
                    <span className="text-xs text-muted-foreground">
                        {OUTCOME[takedown.state] || takedown.state}
                    </span>
                )}
                {/* Derived server-side, like every other deadline here — a
                    stored flag would need a sweep, and a rule that depends on
                    cron is true on Tuesdays. */}
                {takedown?.overdue && (
                    <span className="inline-flex items-center gap-1 rounded bg-destructive/20 px-2 py-0.5 text-xs text-destructive-foreground">
                        <Clock aria-hidden="true" className="h-3 w-3" />
                        Past the window
                    </span>
                )}
            </div>

            {takedown && (
                <div className="mt-3 space-y-2 text-sm">
                    <p className="text-muted-foreground">
                        {takedown.requested_by_name || "Somebody"} asked
                        {takedown.requested_at
                            ? ` on ${formatDateTime(takedown.requested_at)}`
                            : ""}
                        : {takedown.reason_label || takedown.reason_code}
                    </p>
                    <p className="whitespace-pre-wrap">{takedown.detail}</p>
                    {pending && takedown.respond_by && (
                        <p className="text-xs text-muted-foreground">
                            An answer is due by {formatDateTime(takedown.respond_by)}.
                        </p>
                    )}
                    {takedown.response_note && (
                        <p className="rounded border border-white/10 bg-background/40 p-3 whitespace-pre-wrap">
                            {takedown.response_note}
                        </p>
                    )}
                </div>
            )}

            {canRequest && !asking && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setAsking(true)}
                    data-testid={IDS.open}
                    className="mt-4 min-h-[2.75rem] border-amber-400/30 bg-transparent text-amber-200 hover:bg-amber-400/10 sm:min-h-0"
                >
                    Ask for it to come down
                </Button>
            )}

            {asking && (
                <div className="mt-3 space-y-3">
                    <div className="flex flex-wrap gap-2">
                        {REASONS.map((r) => (
                            <button
                                key={r.code}
                                type="button"
                                onClick={() => setCode(r.code)}
                                data-testid={IDS.reason(r.code)}
                                className={`rounded border px-3 py-2 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 ${
                                    code === r.code
                                        ? "border-ember-500 bg-ember-500/10 text-foreground"
                                        : "border-white/10 text-muted-foreground hover:border-white/20"
                                }`}
                            >
                                {r.label}
                            </button>
                        ))}
                    </div>
                    <Textarea
                        rows={3}
                        maxLength={2000}
                        value={detail}
                        onChange={(e) => setDetail(e.target.value)}
                        placeholder="What exactly is wrong with it. The creator reads this."
                        data-testid={IDS.detail}
                        className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            onClick={request}
                            disabled={busy || detail.trim().length < 10}
                            data-testid={IDS.submit}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            Ask for it to come down
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setAsking(false)}
                            data-testid={IDS.cancel}
                        >
                            Cancel
                        </Button>
                    </div>
                </div>
            )}

            {answering && (
                <div data-testid={IDS.respond} className="mt-4 space-y-3">
                    {/* **The refusal needs a reason and the compliance does
                        not.** "I took it down" is complete on its own; "it is
                        staying up" with nothing beside it is an answer nobody
                        can act on, and the server refuses it. */}
                    <Textarea
                        rows={2}
                        maxLength={1000}
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Anything you want to say about it — required if it's staying up."
                        data-testid={IDS.note}
                        className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            onClick={() => respond(true)}
                            disabled={busy}
                            data-testid={IDS.actioned}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            I've taken it down
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => respond(false)}
                            disabled={busy || !note.trim()}
                            data-testid={IDS.declined}
                            className="min-h-[2.75rem] border-white/20 bg-transparent sm:min-h-0"
                        >
                            It's staying up
                        </Button>
                    </div>
                </div>
            )}
        </section>
    );
}
