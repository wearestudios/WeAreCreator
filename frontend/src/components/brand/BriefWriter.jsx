// "Describe your campaign in two lines" — the top of Post a brief.
//
// The draft fills the form below and **posts nothing**: the brand reads it,
// changes what is wrong, and posts through the ordinary button. Whether it is
// shown at all is the server's answer (`brief_writer.available` on the brand
// profile), so with AI off there is no textarea and no button, not a broken
// one. Twenty seconds, then the brand fills the brief in themselves.
import React, { useState } from "react";
import { Sparkles } from "lucide-react";

import { api, apiErrorCode, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const FAILED = "Couldn't draft this — fill it in below.";
// A little over the server's own twenty, so its answer arrives first.
const CLIENT_TIMEOUT_MS = 22000;

export default function BriefWriter({ status, hasDraft, onDraft }) {
    const [text, setText] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [notices, setNotices] = useState([]);
    const [remaining, setRemaining] = useState(status?.remaining);

    if (!status?.available) return null;
    const left = remaining ?? status.remaining;
    const spent = left === 0;

    const draft = async () => {
        setBusy(true);
        setError("");
        try {
            const { data } = await api.post(
                "/brand/campaigns/brief-writer",
                { text: text.trim() },
                { timeout: CLIENT_TIMEOUT_MS },
            );
            setRemaining(data.remaining);
            setNotices(data.notices || []);
            onDraft(data.fields || {});
        } catch (e) {
            const code = apiErrorCode(e);
            if (code === "draft_limit") {
                setRemaining(0);
                setError(formatApiError(e));
            } else {
                setError(FAILED);
            }
        } finally {
            setBusy(false);
        }
    };

    return (
        <section
            data-testid="brief-writer"
            className="rounded-lg border border-border bg-card p-card-sm md:p-card"
        >
            <Label htmlFor="brief-writer-input" className="flex items-center gap-2 font-serif text-h3">
                <Sparkles className="h-4 w-4 text-muted-foreground" aria-hidden />
                Describe your campaign in two lines
            </Label>
            <p className="mt-1 max-w-measure text-meta text-muted-foreground">
                In English, Kannada or Hinglish. We draft the brief below in English for you to
                edit — nothing is posted until you post it.
            </p>
            <Textarea
                id="brief-writer-input"
                data-testid="brief-writer-input"
                rows={3}
                maxLength={1200}
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={busy}
                placeholder="What you want made, for whom, and roughly when."
                className="mt-4 border-border bg-card/60 focus-visible:ring-primary"
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
                <Button
                    type="button"
                    onClick={draft}
                    disabled={busy || spent || text.trim().length < 8}
                    data-testid="brief-writer-submit"
                >
                    {busy ? "Drafting…" : hasDraft ? "Regenerate" : "Draft my brief"}
                </Button>
                <span data-testid="brief-writer-remaining" className="text-meta text-muted-foreground">
                    {spent ? "No drafts left today" : `${left} of ${status.limit} drafts left today`}
                </span>
            </div>
            {busy ? (
                <div data-testid="brief-writer-skeleton" aria-hidden className="mt-5 space-y-3">
                    <Skeleton className="h-5 w-2/3" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                </div>
            ) : null}
            {busy ? (
                <p role="status" className="sr-only">
                    Drafting your brief
                </p>
            ) : null}
            {error ? (
                <p data-testid="brief-writer-error" role="alert" className="mt-4 text-meta text-state-danger">
                    {error}
                </p>
            ) : null}
            {notices.length && !busy ? (
                <ul data-testid="brief-writer-notices" className="mt-4 space-y-1.5">
                    {notices.map((n) => (
                        <li key={n} className="rounded-md bg-state-warn-wash px-3 py-2 text-meta text-state-warn">
                            {n}
                        </li>
                    ))}
                </ul>
            ) : null}
        </section>
    );
}

/** The marker beside a field the draft filled and nobody has changed yet. */
export function AiMark({ on, testid }) {
    if (!on) return null;
    return (
        <span
            data-testid={testid}
            className="ml-2 inline-flex items-center gap-1 rounded-pill border border-dashed border-border px-2 py-0.5 align-middle text-meta normal-case tracking-normal text-muted-foreground"
        >
            <Sparkles className="h-3 w-3" aria-hidden />
            AI draft
        </span>
    );
}
