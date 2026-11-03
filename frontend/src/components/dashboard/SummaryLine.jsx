// The AI summary, as one line with the rest behind "Read more".
//
// **It hides itself whenever there is nothing honest to show**: AI switched
// off (`available: false`), too few measured posts, or no summary yet. The
// numbers on the dashboard are the record; this is a reading of them, and a
// reading with no data under it is not one to print.
//
// Stale is said, not hidden: "The numbers changed since this summary" beside a
// Regenerate button. The server decides staleness, the remaining
// regenerations and whether one may be asked for — this draws what it is
// given.
import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { DASHBOARD as IDS } from "@/constants/testIds";

function Points({ title, items }) {
    if (!items?.length) return null;
    return (
        <div>
            <h3 className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground">{title}</h3>
            <ul className="mt-1.5 space-y-1.5">
                {items.map((p, i) => (
                    <li key={i} className="text-body leading-relaxed">{p.text}</li>
                ))}
            </ul>
        </div>
    );
}

export default function SummaryLine({ campaignId, refreshKey, className = "" }) {
    const [state, setState] = useState(null);
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/brand/campaigns/${campaignId}/summary`);
            setState(data);
        } catch {
            // A summary is an extra. Its failure is silence, never an error
            // banner over the numbers the brand came for.
            setState(null);
        }
    }, [campaignId]);

    useEffect(() => {
        load();
    }, [load, refreshKey]);

    const regenerate = async () => {
        setBusy(true);
        try {
            const { data } = await api.post(`/brand/campaigns/${campaignId}/summary/regenerate`, {});
            setState(data);
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    const summary = state?.available ? state.summary : null;
    if (!summary) return null;

    return (
        <section
            data-testid={IDS.summary}
            className={`rounded-lg border border-border bg-card px-card-sm py-4 md:px-card ${className}`}
        >
            <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
                <Sparkles className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                <p className="min-w-0 flex-1 text-body-lg leading-snug">
                    {summary.headline}{" "}
                    <button
                        type="button"
                        onClick={() => setOpen((v) => !v)}
                        aria-expanded={open}
                        data-testid={IDS.summaryMore}
                        className="whitespace-nowrap text-meta font-medium text-foreground underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    >
                        {open ? "Show less" : "Read more"}
                    </button>
                </p>
            </div>
            {state.stale ? (
                <div
                    data-testid={IDS.summaryStale}
                    className="mt-3 flex flex-wrap items-center gap-3 text-meta text-muted-foreground"
                >
                    <span>The numbers changed since this summary.</span>
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={regenerate}
                        disabled={busy || state.regenerations_left <= 0}
                        data-testid={IDS.summaryRegenerate}
                        title={state.regenerations_left <= 0 ? "You can regenerate again tomorrow." : undefined}
                    >
                        <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
                        {busy ? "Regenerating…" : "Regenerate"}
                    </Button>
                </div>
            ) : null}
            {open ? (
                <div data-testid={IDS.summaryDetail}>
                    <div className="mt-4 grid gap-4 md:grid-cols-3">
                        <Points title="What worked" items={summary.worked} />
                        <Points title="What didn't" items={summary.didnt} />
                        <Points title="Next time" items={summary.next} />
                    </div>
                    <p className="mt-4 text-meta text-muted-foreground">
                        Written by AI from this campaign's numbers. Every figure in it is checked
                        against them before it is shown.
                    </p>
                </div>
            ) : null}
        </section>
    );
}
