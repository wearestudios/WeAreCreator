// Submitting published links.
//
// Several URLs rather than one, because a deliverable is usually a reel plus
// a story set plus a carousel, and making a creator pick which one "counts"
// only produces a follow-up message.
import React, { useEffect, useState } from "react";
import { notifySuccess } from "@/lib/feedback";
import { Link as LinkIcon, Loader2, Plus as PlusIcon, Send, X as XIcon } from "lucide-react";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, formatApiError } from "@/lib/api";
import { CREATOR_SUBMIT_CONTENT as IDS } from "@/constants/testIds";

export default function SubmitContentDialog({ open, onOpenChange, collab, onSubmitted }) {
    const [urls, setUrls] = useState([""]);
    const [err, setErr] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        if (!open) return;
        const initial =
            collab?.content_urls && collab.content_urls.length > 0
                ? [...collab.content_urls]
                : collab?.content_url
                ? [collab.content_url]
                : [""];
        setUrls(initial.length ? initial : [""]);
        setErr("");
    }, [open, collab]);

    const setAt = (i, v) => setUrls((prev) => prev.map((u, j) => (j === i ? v : u)));
    const addRow = () => setUrls((prev) => [...prev, ""]);
    const removeAt = (i) =>
        setUrls((prev) => (prev.length <= 1 ? [""] : prev.filter((_, j) => j !== i)));

    const submit = async (e) => {
        e.preventDefault();
        setErr("");
        const clean = [];
        for (const raw of urls) {
            const u = (raw || "").trim();
            if (!u) continue;
            if (!/^https?:\/\/.+\..+/i.test(u)) {
                setErr("Every URL must start with http:// or https:// and look like a real link.");
                return;
            }
            if (!clean.includes(u)) clean.push(u);
        }
        if (clean.length === 0) {
            setErr("Paste at least one link to your published post or reel.");
            return;
        }
        if (clean.length > 25) {
            setErr("You can submit up to 25 URLs at a time.");
            return;
        }
        setBusy(true);
        try {
            await api.post(`/creator/collaborations/${collab.id}/submit_content`, {
                content_urls: clean,
            });
            notifySuccess(
                clean.length === 1
                    ? "Content submitted — the WeAre team will review it"
                    : `${clean.length} links submitted — the WeAre team will review them`,
            );
            onOpenChange(false);
            onSubmitted?.();
        } catch (e) {
            setErr(formatApiError(e));
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={IDS.dialog}
                className="max-h-[90vh] max-w-lg overflow-y-auto rounded-md border border-white/10 bg-card grain-surface"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Submit content
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {collab?.campaign_title}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        Paste every published link — reel, carousel, stories archive.
                        Add as many as your deliverable calls for.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-4">
                    <div className="space-y-3">
                        {urls.map((u, i) => (
                            <div key={i} className="space-y-1">
                                <Label
                                    htmlFor={`sc-url-${i}`}
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    URL {i + 1}
                                </Label>
                                <div className="relative">
                                    <LinkIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id={`sc-url-${i}`}
                                        data-testid={i === 0 ? IDS.url : IDS.urlAt(i)}
                                        type="url"
                                        inputMode="url"
                                        value={u}
                                        onChange={(e) => setAt(i, e.target.value)}
                                        className="h-12 border-white/10 bg-background/60 pl-9 pr-10 focus-visible:ring-ember-500"
                                        placeholder="https://instagram.com/p/..."
                                    />
                                    {urls.length > 1 && (
                                        <button
                                            type="button"
                                            aria-label={`Remove URL ${i + 1}`}
                                            data-testid={IDS.remove(i)}
                                            onClick={() => removeAt(i)}
                                            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-muted-foreground transition-colors duration-200 hover:bg-white/5 hover:text-red-300"
                                        >
                                            <XIcon className="h-3.5 w-3.5" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    <button
                        type="button"
                        data-testid={IDS.add}
                        onClick={addRow}
                        disabled={urls.length >= 25}
                        className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-transparent px-3 py-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 disabled:opacity-40"
                    >
                        <PlusIcon className="h-3.5 w-3.5" />
                        Add another URL
                    </button>

                    {err && (
                        <p data-testid={IDS.error} className="text-sm text-destructive">
                            {err}
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                data-testid={IDS.cancel}
                                className="h-12 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            data-testid={IDS.submit}
                            disabled={busy}
                            className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {busy ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Submitting…
                                </>
                            ) : (
                                <>
                                    <Send className="mr-2 h-4 w-4" />
                                    Submit content
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
