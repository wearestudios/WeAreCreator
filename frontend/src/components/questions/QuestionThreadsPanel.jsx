// Every question thread on one campaign, for whoever answers them.
//
// Sits on the admin campaign page and the brand's applicant board. The server
// decides whether this caller gets threads at all (a brand on a weare-run
// campaign gets a 404, and the panel vanishes) — so the same component serves
// both without asking who is mounting it.
import React, { useCallback, useEffect, useState } from "react";
import { MessageCircleQuestion } from "lucide-react";

import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { QUESTIONS } from "@/constants/testIds";
import QuestionThread from "./QuestionThread";

export default function QuestionThreadsPanel({ campaignId, className = "" }) {
    const [threads, setThreads] = useState(null);
    const [hidden, setHidden] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/questions/campaign/${campaignId}/threads`);
            // `|| []` because the catch below only covers a failed request:
            // a 200 with an unexpected shape would reach `.map` and take the
            // section down, which is a louder failure than the empty panel
            // this component is already designed to render.
            setThreads(data.threads || []);
        } catch {
            setHidden(true);
        }
    }, [campaignId]);

    useEffect(() => {
        setThreads(null);
        setHidden(false);
        load();
    }, [load]);

    if (hidden) return null;
    // Nothing asked yet: say nothing at all. An empty "questions" panel on
    // every campaign page is furniture; the panel earns its place by having
    // something in it.
    if (Array.isArray(threads) && threads.length === 0) return null;

    return (
        <section
            data-testid={QUESTIONS.threadsPanel}
            className={`rounded-md border border-white/10 bg-card p-6 grain-surface ${className}`}
        >
            <p className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                <MessageCircleQuestion className="h-4 w-4 text-ember-500" />
                Creator questions
                {Array.isArray(threads) && (
                    <span className="text-muted-foreground">
                        · {threads.filter((t) => t.unanswered).length} waiting
                    </span>
                )}
            </p>

            {threads === null ? (
                <div className="mt-5 space-y-3" aria-hidden="true">
                    <Skeleton className="h-12 w-2/3 rounded-lg" />
                    <Skeleton className="h-12 w-1/2 rounded-lg" />
                </div>
            ) : (
                <div className="mt-5 space-y-8">
                    {threads.map((t) => (
                        <div key={t.creator_id}>
                            <p className="mb-3 text-sm">
                                <span className="font-serif text-base">
                                    {t.creator?.name || "A creator"}
                                </span>
                                {t.unanswered && (
                                    <span className="ml-2 rounded-full bg-ember-500/15 px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] text-ember-500">
                                        Waiting on you
                                    </span>
                                )}
                            </p>
                            <QuestionThread
                                campaignId={campaignId}
                                creatorId={t.creator_id}
                                questions={t.questions}
                                onReplied={load}
                            />
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}
