// One creator's question thread, read from the answering side.
//
// Mounted where the staff already are: the application page, the admin
// campaign page, the brand's applicant board. Whether the caller may see it
// at all is the server's decision — the routes 404 for a brand on a
// weare-run campaign — so this component renders what it is given and never
// asks what role is looking.
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, Send } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { QUESTIONS } from "@/constants/testIds";

const formatWhen = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
};

function Row({ q }) {
    const theirs = q.author_side === "creator";
    return (
        <li
            data-testid={QUESTIONS.message(q.id)}
            className={`flex ${theirs ? "justify-start" : "justify-end"}`}
        >
            <div
                className={
                    "max-w-[85%] rounded-lg border px-4 py-3 " +
                    (theirs
                        ? "border-white/10 bg-white/5"
                        : "border-ember-500/25 bg-ember-500/10")
                }
            >
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    {q.author_name || (theirs ? "Creator" : "Team")}
                    {" · "}
                    {formatWhen(q.created_at)}
                </p>
                <p className="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-foreground/90">
                    {q.body}
                </p>
            </div>
        </li>
    );
}

/**
 * Fetches its own thread when given `campaignId` + `creatorId`; renders a
 * pre-fetched one when given `questions` (the threads panel already has them).
 * `onReplied` lets a parent refresh its unanswered badges.
 */
export default function QuestionThread({
    campaignId,
    creatorId,
    questions,
    onReplied,
    emptyText = "No questions from this creator.",
}) {
    const [fetched, setFetched] = useState(null);
    const [hidden, setHidden] = useState(false);
    const [draft, setDraft] = useState("");
    const [sending, setSending] = useState(false);
    const preloaded = Array.isArray(questions);

    const load = useCallback(async () => {
        if (preloaded) return;
        try {
            const { data } = await api.get(
                `/questions/campaign/${campaignId}/thread/${creatorId}`,
            );
            setFetched(data.questions);
        } catch {
            // 404 = not this caller's to read (weare-run campaign, brand
            // caller). The section disappears rather than erroring — the
            // parent asked optimistically.
            setHidden(true);
        }
    }, [campaignId, creatorId, preloaded]);

    useEffect(() => {
        setFetched(null);
        setHidden(false);
        load();
    }, [load]);

    const rows = preloaded ? questions : fetched;
    const [extra, setExtra] = useState([]);

    const reply = async () => {
        const body = draft.trim();
        if (!body) return;
        setSending(true);
        try {
            const { data } = await api.post(
                `/questions/campaign/${campaignId}/thread/${creatorId}/reply`,
                { body },
            );
            if (preloaded) setExtra((xs) => [...xs, data]);
            else setFetched((qs) => [...(qs || []), data]);
            setDraft("");
            notifySuccess("Answer sent — the creator is notified");
            onReplied?.();
        } catch (err) {
            notifyError(formatApiError(err));
        } finally {
            setSending(false);
        }
    };

    if (hidden) return null;
    if (rows === null) {
        return (
            <div className="space-y-3" aria-hidden="true">
                <Skeleton className="h-12 w-2/3 rounded-lg" />
                <Skeleton className="ml-auto h-12 w-1/2 rounded-lg" />
            </div>
        );
    }

    const all = [...rows, ...extra];

    return (
        <div data-testid={QUESTIONS.thread(creatorId)}>
            {all.length === 0 ? (
                <p className="text-sm text-muted-foreground">{emptyText}</p>
            ) : (
                <ul className="space-y-3">
                    {all.map((q) => (
                        <Row key={q.id} q={q} />
                    ))}
                </ul>
            )}
            {all.length > 0 && (
                <div className="mt-4">
                    <Textarea
                        data-testid={QUESTIONS.replyInput}
                        rows={2}
                        maxLength={2000}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        placeholder="Answer the creator — they'll see it here and on WhatsApp"
                        className="min-h-[64px] border-white/10 bg-card/60 focus-visible:ring-ember-500"
                    />
                    <div className="mt-3 flex justify-end">
                        <Button
                            type="button"
                            onClick={reply}
                            disabled={sending || !draft.trim()}
                            data-testid={QUESTIONS.replySend}
                            className="h-11 rounded-full bg-ember-500 px-5 text-black hover:bg-ember-400"
                        >
                            {sending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <>
                                    <Send className="mr-2 h-4 w-4" />
                                    Answer
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
