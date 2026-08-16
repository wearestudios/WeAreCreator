// The work notes thread on one application.
//
// Negotiation happens offline — on WhatsApp, on the phone, at the venue. This
// is where what was said gets written down, so the reasoning behind a fee
// outlives whoever had the call. Creators never see it; the API refuses them
// outright, and this component is only ever rendered on brand and staff pages.
//
// Collapsed by default. A thread is something you open when you are deciding
// about a person, not a wall of text on every row of a list.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { notifyError } from "@/lib/feedback";
import { IndianRupee, Loader2, MessageSquare, Send } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { WORK_NOTES } from "@/constants/testIds";

const ROLE_LABEL = {
    brand: "Brand",
    brand_manager: "Brand",
    admin: "WeAre",
    campaign_manager: "WeAre manager",
};

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : "—";

function formatWhen(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
    });
}

export function WorkNotes({ collaborationId, agreedAmount, quotedRate, defaultOpen = false }) {
    const [open, setOpen] = useState(defaultOpen);
    const [loading, setLoading] = useState(false);
    const [thread, setThread] = useState(null);
    const [draft, setDraft] = useState("");
    const [sending, setSending] = useState(false);
    // Notes are append-only and the thread is short, so the newest one is what
    // you came to read. Scrolling to it beats making the reader hunt.
    const endRef = useRef(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const { data } = await api.get(`/collaborations/${collaborationId}/notes`);
            setThread(data);
        } catch (err) {
            notifyError(err, { onRetry: () => load() });
        } finally {
            setLoading(false);
        }
    }, [collaborationId]);

    useEffect(() => {
        if (open && thread === null) load();
    }, [open, thread, load]);

    useEffect(() => {
        if (open && thread?.notes?.length) {
            endRef.current?.scrollIntoView({ block: "nearest" });
        }
    }, [open, thread]);

    const submit = async (e) => {
        e.preventDefault();
        const body = draft.trim();
        if (!body || sending) return;
        setSending(true);
        try {
            const { data } = await api.post(`/collaborations/${collaborationId}/notes`, {
                body,
            });
            // Append locally rather than refetching: the thread is ordered and
            // the server just told us exactly what was written.
            setThread((t) => ({ ...(t || {}), notes: [...(t?.notes || []), data] }));
            setDraft("");
        } catch (err) {
            notifyError(err);
        } finally {
            setSending(false);
        }
    };

    const notes = thread?.notes || [];
    // The freshly-loaded thread is authoritative about the number; until then
    // use what the row already knew, so the figure never blinks.
    const agreed = thread ? thread.agreed_amount : agreedAmount;
    const quoted = thread ? thread.quoted_rate : quotedRate;

    return (
        <div
            data-testid={WORK_NOTES.section(collaborationId)}
            className="rounded-md border border-white/10 bg-background/40"
        >
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                data-testid={WORK_NOTES.toggle(collaborationId)}
                aria-expanded={open}
                className="flex min-h-[2.75rem] w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors duration-200 hover:bg-white/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ember-500"
            >
                <span className="inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    <MessageSquare className="h-3.5 w-3.5" />
                    Work notes
                    {notes.length > 0 && (
                        <span className="text-ember-500">{notes.length}</span>
                    )}
                </span>
                <span className="text-xs text-muted-foreground">
                    {open ? "Hide" : "Open"}
                </span>
            </button>

            {open && (
                <div className="border-t border-white/10 px-4 py-4">
                    {/* The number sits above the conversation that produced it. */}
                    <div
                        data-testid={WORK_NOTES.agreed(collaborationId)}
                        className="mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-1"
                    >
                        <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            {agreed != null ? "Agreed" : "They quoted"}
                        </span>
                        <span className="inline-flex items-baseline font-serif text-2xl">
                            <IndianRupee className="h-4 w-4 text-ember-500" />
                            {formatRupees(agreed ?? quoted)}
                        </span>
                        {agreed != null && quoted != null && agreed !== quoted && (
                            <span className="text-xs text-muted-foreground">
                                from ₹{formatRupees(quoted)} quoted
                            </span>
                        )}
                    </div>

                    {loading && thread === null ? (
                        <div
                            data-testid={WORK_NOTES.loading(collaborationId)}
                            className="flex items-center gap-2 py-4 text-sm text-muted-foreground"
                        >
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading the thread…
                        </div>
                    ) : notes.length === 0 ? (
                        <p
                            data-testid={WORK_NOTES.empty(collaborationId)}
                            className="py-2 text-sm leading-relaxed text-muted-foreground"
                        >
                            Nothing recorded yet. What was asked for, what was offered, what
                            was agreed and why — the next person to look at this will only
                            know what's written here.
                        </p>
                    ) : (
                        <ol
                            data-testid={WORK_NOTES.thread(collaborationId)}
                            className="flex max-h-80 flex-col gap-4 overflow-y-auto pr-1"
                        >
                            {notes.map((n) => (
                                <li key={n.id} data-testid={WORK_NOTES.note(n.id)}>
                                    <div
                                        data-testid={WORK_NOTES.noteAuthor(n.id)}
                                        className="flex flex-wrap items-baseline gap-x-2 text-xs"
                                    >
                                        <span className="font-medium text-foreground/90">
                                            {n.author_name || "Someone"}
                                        </span>
                                        <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                                            {ROLE_LABEL[n.author_role] || n.author_role}
                                        </span>
                                        <span className="text-muted-foreground/70">
                                            {formatWhen(n.created_at)}
                                        </span>
                                    </div>
                                    <p
                                        data-testid={WORK_NOTES.noteBody(n.id)}
                                        className="mt-1 whitespace-pre-wrap border-l-2 border-white/10 pl-3 text-sm leading-relaxed text-foreground/85"
                                    >
                                        {n.body}
                                    </p>
                                </li>
                            ))}
                            <li ref={endRef} aria-hidden="true" />
                        </ol>
                    )}

                    <form onSubmit={submit} className="mt-4 flex flex-col gap-2">
                        <Textarea
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            rows={2}
                            maxLength={4000}
                            placeholder="Asked for ₹12k on the call, offered ₹8k…"
                            data-testid={WORK_NOTES.input(collaborationId)}
                            aria-label="Add a work note"
                        />
                        <div className="flex items-center justify-between gap-3">
                            {/* Said once, plainly, rather than as a warning banner. */}
                            <span className="text-[11px] text-muted-foreground">
                                Only you and the WeAre team can see these.
                            </span>
                            <Button
                                type="submit"
                                size="sm"
                                disabled={!draft.trim() || sending}
                                data-testid={WORK_NOTES.submit(collaborationId)}
                            >
                                {sending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Send className="h-4 w-4" />
                                )}
                                Add note
                            </Button>
                        </div>
                    </form>
                </div>
            )}
        </div>
    );
}

export default WorkNotes;
