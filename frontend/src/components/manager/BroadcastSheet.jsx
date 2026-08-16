// Messaging everyone on a campaign.
//
// Three steps on purpose: write it, read it back with the headcount, then send.
// A broadcast is the one action here that cannot be undone — it lands on
// strangers' phones — so the middle step exists to make a mis-tap impossible.
import React, { useEffect, useState } from "react";
import { AlertCircle, Check, Send, Users } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { MANAGER_BROADCAST as IDS } from "@/constants/testIds";
import { BigButton } from "./shared";

export default function BroadcastSheet({ open, onClose, recipients, onSend, busy, report }) {
    const [message, setMessage] = useState("");
    const [reviewing, setReviewing] = useState(false);
    const [err, setErr] = useState("");

    useEffect(() => {
        if (open) {
            setMessage("");
            setReviewing(false);
            setErr("");
        }
    }, [open]);

    const toReview = () => {
        if (message.trim().length < 3) {
            setErr("Write something first.");
            return;
        }
        setErr("");
        setReviewing(true);
    };

    const count = recipients?.length ?? 0;

    return (
        <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
            <SheetContent
                side="bottom"
                data-testid={IDS.sheet}
                className="max-h-[90vh] overflow-y-auto rounded-t-md border-t border-white/10 bg-card grain-surface"
            >
                {report ? (
                    <>
                        <SheetTitle className="font-serif text-2xl leading-tight">
                            Sent
                        </SheetTitle>
                        <SheetDescription className="mt-2 text-sm text-muted-foreground">
                            {report.delivered} delivered · {report.failed} didn't go through.
                            Everyone got it in the app either way.
                        </SheetDescription>

                        <ul data-testid={IDS.report} className="mt-5 divide-y divide-white/10">
                            {report.results.map((r) => (
                                <li
                                    key={r.creator_id}
                                    data-testid={IDS.reportRow(r.creator_id)}
                                    className="flex items-start gap-3 py-3"
                                >
                                    {r.delivered ? (
                                        <Check className="mt-0.5 h-4 w-4 flex-none text-emerald-300" />
                                    ) : (
                                        <AlertCircle className="mt-0.5 h-4 w-4 flex-none text-amber-300" />
                                    )}
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm">{r.name}</p>
                                        {r.error && (
                                            <p className="mt-0.5 text-xs text-muted-foreground">
                                                {r.error}
                                            </p>
                                        )}
                                    </div>
                                </li>
                            ))}
                        </ul>

                        <BigButton
                            type="button"
                            onClick={onClose}
                            data-testid={IDS.done}
                            className="mt-6 bg-ember-500 text-black hover:bg-ember-400"
                        >
                            Done
                        </BigButton>
                    </>
                ) : reviewing ? (
                    <>
                        <SheetTitle className="font-serif text-2xl leading-tight">
                            Send to {count} {count === 1 ? "creator" : "creators"}?
                        </SheetTitle>
                        <SheetDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                            This goes out on WhatsApp and can't be taken back. Read it once
                            more.
                        </SheetDescription>

                        <blockquote
                            data-testid={IDS.review}
                            className="mt-5 whitespace-pre-wrap rounded-md border border-white/10 bg-background/60 p-5 text-sm leading-relaxed"
                        >
                            {message.trim()}
                        </blockquote>

                        <p
                            data-testid={IDS.count}
                            className="mt-4 inline-flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground"
                        >
                            <Users className="h-3.5 w-3.5" />
                            {count} confirmed {count === 1 ? "creator" : "creators"}
                        </p>

                        <div className="mt-6 flex flex-col gap-3">
                            <BigButton
                                type="button"
                                busy={busy}
                                onClick={() => onSend(message.trim())}
                                data-testid={IDS.confirm}
                                className="bg-ember-500 text-black hover:bg-ember-400"
                            >
                                <Send className="mr-2 h-4 w-4" />
                                Send it
                            </BigButton>
                            <BigButton
                                type="button"
                                variant="outline"
                                onClick={() => setReviewing(false)}
                                data-testid={IDS.back}
                                className="border-white/15 bg-transparent"
                            >
                                Edit
                            </BigButton>
                        </div>
                    </>
                ) : (
                    <>
                        <SheetTitle className="font-serif text-2xl leading-tight">
                            Message everyone
                        </SheetTitle>
                        <SheetDescription className="mt-2 text-sm text-muted-foreground">
                            Goes to the {count} {count === 1 ? "creator" : "creators"} still
                            expected on this campaign.
                        </SheetDescription>

                        <Textarea
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            rows={5}
                            maxLength={1000}
                            data-testid={IDS.message}
                            placeholder="e.g. Parking is round the back today — ask for Riya at the events desk."
                            className="mt-5 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                        />
                        <p className="mt-2 text-right text-xs text-muted-foreground">
                            {message.length}/1000
                        </p>
                        {err && (
                            <p data-testid={IDS.error} className="mt-2 text-sm text-destructive">
                                {err}
                            </p>
                        )}

                        <div className="mt-6 flex flex-col gap-3">
                            <BigButton
                                type="button"
                                disabled={count === 0}
                                onClick={toReview}
                                data-testid={IDS.review + "-next"}
                                className="bg-ember-500 text-black hover:bg-ember-400"
                            >
                                Review
                            </BigButton>
                            <BigButton
                                type="button"
                                variant="outline"
                                onClick={onClose}
                                data-testid={IDS.cancel}
                                className="border-white/15 bg-transparent"
                            >
                                Cancel
                            </BigButton>
                        </div>
                    </>
                )}
            </SheetContent>
        </Sheet>
    );
}
