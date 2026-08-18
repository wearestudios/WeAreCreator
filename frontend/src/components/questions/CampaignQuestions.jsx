// The creator's question thread on one campaign.
//
// This is the channel a creator uses to ask "is parking possible" without
// applying and hoping. It is scoped to them: the API reads the thread off the
// session, so there is no creator id here to get wrong, and no other
// creator's thread is reachable from this component at all.
//
// Deliberately not the work notes. Those are the internal paper trail this
// creator must never see; this thread is the opposite shape — the creator is
// a party to it, and the answer comes labelled with who they are dealing
// with ("brand" or "weare"), the same two words execution_owner prints
// everywhere else.
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, MessageCircleQuestion, Send } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { QUESTIONS } from "@/constants/testIds";

const sideLabel = (side) => (side === "brand" ? "The brand" : "WeAre team");
// Mid-sentence version, because "Ask The brand" reads like a typo.
const sideInline = (side) => (side === "brand" ? "the brand" : "the WeAre team");

const formatWhen = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
};

export function QuestionBubble({ q }) {
    const mine = q.author_side === "creator";
    return (
        <li
            data-testid={QUESTIONS.message(q.id)}
            className={`flex ${mine ? "justify-end" : "justify-start"}`}
        >
            <div
                className={
                    "max-w-[85%] rounded-lg border px-4 py-3 " +
                    (mine
                        ? "border-ember-500/25 bg-ember-500/10"
                        : "border-white/10 bg-white/5")
                }
            >
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    {mine ? "You" : sideLabel(q.author_side)}
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

export default function CampaignQuestions({ campaignId }) {
    const [thread, setThread] = useState(null);
    const [failed, setFailed] = useState(false);
    const [draft, setDraft] = useState("");
    const [sending, setSending] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/questions/campaign/${campaignId}`);
            setThread(data);
        } catch {
            // A 404 here is a campaign this creator can't discuss (or a
            // signed-out state mid-expiry). Either way the section simply
            // isn't for them — an error box would make a non-feature a fault.
            setFailed(true);
        }
    }, [campaignId]);

    useEffect(() => {
        setThread(null);
        setFailed(false);
        load();
    }, [load]);

    const send = async () => {
        const body = draft.trim();
        if (!body) return;
        setSending(true);
        try {
            const { data } = await api.post(`/questions/campaign/${campaignId}`, { body });
            setThread((t) => ({ ...t, questions: [...(t?.questions || []), data] }));
            setDraft("");
        } catch (err) {
            notifyError(formatApiError(err));
        } finally {
            setSending(false);
        }
    };

    if (failed) return null;

    return (
        <section
            data-testid={QUESTIONS.section}
            className="mt-12 rounded-md border border-white/10 bg-card p-6 md:p-8 grain-surface"
        >
            <p className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-ember-500">
                <MessageCircleQuestion className="h-4 w-4" />
                Questions
            </p>

            {thread === null ? (
                <div className="mt-5 space-y-3" aria-hidden="true">
                    <Skeleton className="h-14 w-3/4 rounded-lg" />
                    <Skeleton className="ml-auto h-14 w-2/3 rounded-lg" />
                </div>
            ) : (
                <>
                    {thread.questions.length === 0 ? (
                        <p
                            data-testid={QUESTIONS.empty}
                            className="mt-4 text-sm leading-relaxed text-muted-foreground"
                        >
                            Wondering about timings, parking, a plus-one? Ask here —
                            only you and {sideInline(thread.answered_by)} can see
                            this thread.
                        </p>
                    ) : (
                        <ul data-testid={QUESTIONS.list} className="mt-5 space-y-3">
                            {thread.questions.map((q) => (
                                <QuestionBubble key={q.id} q={q} />
                            ))}
                        </ul>
                    )}

                    {thread.can_ask ? (
                        <div className="mt-5">
                            <Textarea
                                data-testid={QUESTIONS.input}
                                rows={2}
                                maxLength={2000}
                                value={draft}
                                onChange={(e) => setDraft(e.target.value)}
                                placeholder={`Ask ${sideInline(thread.answered_by)} anything about this brief…`}
                                className="min-h-[72px] border-white/10 bg-card/60 focus-visible:ring-ember-500"
                            />
                            <div className="mt-3 flex items-center justify-between gap-3">
                                <p className="text-xs text-muted-foreground">
                                    Answers land here and on WhatsApp.
                                </p>
                                <Button
                                    type="button"
                                    onClick={send}
                                    disabled={sending || !draft.trim()}
                                    data-testid={QUESTIONS.send}
                                    className="h-11 rounded-full bg-ember-500 px-5 text-black hover:bg-ember-400"
                                >
                                    {sending ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <>
                                            <Send className="mr-2 h-4 w-4" />
                                            Ask
                                        </>
                                    )}
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <p className="mt-5 text-xs text-muted-foreground">
                            This campaign has wrapped up, so the thread is closed.
                        </p>
                    )}
                </>
            )}
        </section>
    );
}
