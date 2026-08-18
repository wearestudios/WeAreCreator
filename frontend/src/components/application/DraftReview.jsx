// The draft, and the decision about it.
//
// This is the panel that makes the stage worth having: the reviewer sees the
// work here, before the creator's audience does. Two outcomes, and only two —
// approve it, or send it back with a note saying what to change. A send-back
// with no note is a wasted round trip, so the note is required and the button
// says so rather than producing a 422.
//
// Like the rest of this screen, it never asks what role is looking. Whether
// there is anything to decide arrives as `canReview` from the server, which
// works it out from execution_owner: a brand on a weare-run campaign reads
// the draft's status and gets no buttons.
import React, { useState } from "react";
import { Download, ExternalLink, Loader2 } from "lucide-react";

import { API_BASE, api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { DRAFT_REVIEW as IDS } from "@/constants/testIds";

const STATUS = {
    draft_submitted: "Waiting for your review.",
    draft_approved: "Approved. The creator is publishing it now.",
};

const formatWhen = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
    });
};

const formatSize = (bytes) => {
    if (typeof bytes !== "number" || bytes <= 0) return null;
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? `${mb.toFixed(1)}MB` : `${Math.round(bytes / 1024)}KB`;
};

export default function DraftReview({ collaborationId, draft, canReview, onDecided }) {
    const [busy, setBusy] = useState(null);
    const [note, setNote] = useState("");
    const [asking, setAsking] = useState(false);

    if (!draft) return null;

    const submitted = Boolean(draft.submitted_at);
    const size = formatSize(draft.size);

    const run = async (key, request, message) => {
        setBusy(key);
        try {
            await request();
            notifySuccess(message);
            setAsking(false);
            setNote("");
            await onDecided?.();
        } catch (err) {
            notifyError(formatApiError(err));
        } finally {
            setBusy(null);
        }
    };

    return (
        <div data-testid={IDS.panel} className="space-y-4">
            <p data-testid={IDS.state} className="text-sm leading-relaxed text-muted-foreground">
                {submitted
                    ? STATUS[draft.state] ||
                      "The creator hasn't sent a new draft since the last round."
                    : "Nothing sent yet — the creator submits a draft after the shoot."}
            </p>

            {submitted && (
                <div className="rounded-md border border-white/10 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                        Sent {formatWhen(draft.submitted_at)}
                        {draft.revision_count > 0 && (
                            <>
                                {" · "}
                                <span data-testid={IDS.revisions}>
                                    round {draft.revision_count + 1}
                                </span>
                            </>
                        )}
                    </p>

                    {draft.kind === "link" && draft.draft_url && (
                        <a
                            href={draft.draft_url}
                            target="_blank"
                            rel="noreferrer"
                            data-testid={IDS.link}
                            className="mt-3 inline-flex items-center gap-2 text-sm text-ember-500 underline underline-offset-4"
                        >
                            <ExternalLink className="h-4 w-4" />
                            Open the unlisted link
                        </a>
                    )}

                    {draft.has_file && (
                        // A plain anchor rather than a fetch: the route streams
                        // the file with its own auth cookie and Content-
                        // Disposition, and buffering a 300MB video into memory
                        // to hand it back to the browser helps nobody.
                        <a
                            href={`${API_BASE}/drafts/${collaborationId}/file`}
                            target="_blank"
                            rel="noreferrer"
                            data-testid={IDS.file}
                            className="mt-3 inline-flex items-center gap-2 text-sm text-ember-500 underline underline-offset-4"
                        >
                            <Download className="h-4 w-4" />
                            {draft.original_name || "Open the draft"}
                            {size ? ` · ${size}` : ""}
                        </a>
                    )}

                    {draft.note && (
                        <p
                            data-testid={IDS.note}
                            className="mt-3 whitespace-pre-line text-sm leading-relaxed text-foreground/90"
                        >
                            “{draft.note}”
                        </p>
                    )}
                </div>
            )}

            {/* The outstanding request, kept on screen after the send-back so
                the thread reads as a conversation rather than a state flip. */}
            {draft.revision_note && draft.state !== "draft_submitted" && (
                <p
                    data-testid={IDS.revisionNote}
                    className="rounded-md border border-ember-500/25 bg-ember-500/10 px-4 py-3 text-sm leading-relaxed text-ember-500"
                >
                    You asked for: {draft.revision_note}
                </p>
            )}

            {canReview && (
                <div className="space-y-3">
                    <div className="flex flex-col gap-3 sm:flex-row">
                        <Button
                            data-testid={IDS.approve}
                            disabled={busy === "approve"}
                            className="min-h-[2.75rem]"
                            onClick={() =>
                                run(
                                    "approve",
                                    () => api.post(`/drafts/${collaborationId}/approve`),
                                    "Draft approved — the creator can publish",
                                )
                            }
                        >
                            {busy === "approve" && (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            )}
                            Approve the draft
                        </Button>
                        <Button
                            variant="outline"
                            data-testid={IDS.requestChanges}
                            onClick={() => setAsking((v) => !v)}
                            className="min-h-[2.75rem]"
                        >
                            Request changes
                        </Button>
                    </div>

                    {asking && (
                        <div className="space-y-3">
                            <Textarea
                                data-testid={IDS.changeNote}
                                rows={3}
                                maxLength={1000}
                                value={note}
                                onChange={(e) => setNote(e.target.value)}
                                placeholder="What needs to change? The creator sees this word for word."
                                className="min-h-[88px] border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            />
                            <Button
                                data-testid={IDS.changeSubmit}
                                disabled={busy === "changes" || !note.trim()}
                                className="min-h-[2.75rem]"
                                onClick={() =>
                                    run(
                                        "changes",
                                        () =>
                                            api.post(
                                                `/drafts/${collaborationId}/request-changes`,
                                                { note: note.trim() },
                                            ),
                                        "Sent back with your note",
                                    )
                                }
                            >
                                {busy === "changes" && (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                )}
                                Send it back
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
