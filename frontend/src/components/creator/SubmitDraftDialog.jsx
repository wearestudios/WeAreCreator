// Sending a cut up for review, before any of it is public.
//
// Two ways in, because one of them fails on the phone this is being used on:
// a finished reel is often 200–400MB, and a creator on mobile data will
// simply publish it rather than watch a bar crawl. So an unlisted link — a
// private YouTube upload, a Drive file — is a first-class option rather than
// a fallback, and the server accepts either.
//
// The file goes to private storage. That is the whole point of the stage: an
// unpublished draft is the one thing on this platform that must not be a
// guessed URL away from the internet.
import React, { useEffect, useState } from "react";
import { FileVideo, Link as LinkIcon, Loader2, Send } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { api, formatApiError } from "@/lib/api";
import { notifySuccess } from "@/lib/feedback";
import { CREATOR_DRAFT as IDS } from "@/constants/testIds";

const MODES = [
    { key: "file", label: "Upload the file", Icon: FileVideo, testid: IDS.modeFile },
    { key: "link", label: "Share an unlisted link", Icon: LinkIcon, testid: IDS.modeLink },
];

export default function SubmitDraftDialog({ open, onOpenChange, collab, onSubmitted }) {
    const [mode, setMode] = useState("file");
    const [file, setFile] = useState(null);
    const [url, setUrl] = useState("");
    const [note, setNote] = useState("");
    const [err, setErr] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        if (!open) return;
        setMode("file");
        setFile(null);
        setUrl("");
        setNote("");
        setErr("");
    }, [open, collab]);

    const submit = async (e) => {
        e.preventDefault();
        setErr("");

        if (mode === "link" && !/^https?:\/\/.+\..+/i.test(url.trim())) {
            setErr("The link must start with http:// or https:// and look like a real link.");
            return;
        }
        if (mode === "file" && !file) {
            setErr("Pick the video or image you want reviewed.");
            return;
        }

        setBusy(true);
        try {
            if (mode === "file") {
                const body = new FormData();
                body.append("file", file);
                if (note.trim()) body.append("note", note.trim());
                await api.post(`/drafts/${collab.id}/file`, body, {
                    // Let the browser set the multipart boundary; the client's
                    // JSON default would make this unparseable.
                    headers: { "Content-Type": undefined },
                });
            } else {
                await api.post(`/drafts/${collab.id}/link`, {
                    draft_url: url.trim(),
                    note: note.trim() || null,
                });
            }
            notifySuccess("Draft sent for review — we'll let you know the moment it's looked at");
            onOpenChange(false);
            onSubmitted?.();
        } catch (e2) {
            setErr(formatApiError(e2));
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
                        Draft for review
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {collab?.campaign_title}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        Nothing goes out until this is approved. Send the cut
                        itself, or an unlisted link if it's a big file.
                    </DialogDescription>
                </DialogHeader>

                {/* The note from the last round, where there was one. It is the
                    reason this dialog is open a second time, so it goes above
                    the fields rather than below them. */}
                {collab?.draft?.revision_note && (
                    <p className="mt-4 rounded-md border border-ember-500/30 bg-ember-500/10 px-4 py-3 text-sm leading-relaxed text-ember-500">
                        Changes asked for: {collab.draft.revision_note}
                    </p>
                )}

                <form onSubmit={submit} noValidate className="mt-4 space-y-4">
                    <div className="flex flex-col gap-2 sm:flex-row">
                        {MODES.map(({ key, label, Icon, testid }) => (
                            <button
                                key={key}
                                type="button"
                                data-testid={testid}
                                aria-pressed={mode === key}
                                onClick={() => {
                                    setMode(key);
                                    setErr("");
                                }}
                                className={
                                    "inline-flex min-h-[3rem] flex-1 items-center justify-center gap-2 rounded-full border px-4 text-sm transition-colors duration-200 " +
                                    (mode === key
                                        ? "border-ember-500/40 bg-ember-500/15 text-ember-500"
                                        : "border-white/10 bg-transparent text-muted-foreground hover:border-white/20")
                                }
                            >
                                <Icon className="h-4 w-4" />
                                {label}
                            </button>
                        ))}
                    </div>

                    {mode === "file" ? (
                        <div className="space-y-1">
                            <Label
                                htmlFor="draft-file"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                Video or image
                            </Label>
                            <Input
                                id="draft-file"
                                data-testid={IDS.file}
                                type="file"
                                accept="video/mp4,video/quicktime,video/webm,image/jpeg,image/png,image/webp"
                                onChange={(e) => setFile(e.target.files?.[0] || null)}
                                className="h-12 border-white/10 bg-background/60 file:mr-3 file:rounded-full file:border-0 file:bg-white/10 file:px-3 file:py-1.5 file:text-xs file:text-foreground focus-visible:ring-ember-500"
                            />
                            <p className="text-xs text-muted-foreground">
                                MP4, MOV, WebM or a still. Only the reviewer sees it.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            <Label
                                htmlFor="draft-url"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                Unlisted link
                            </Label>
                            <div className="relative">
                                <LinkIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    id="draft-url"
                                    data-testid={IDS.url}
                                    type="url"
                                    inputMode="url"
                                    value={url}
                                    onChange={(e) => setUrl(e.target.value)}
                                    placeholder="https://youtu.be/…"
                                    className="h-12 border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                                />
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Keep it unlisted or private — this shouldn't be public yet.
                            </p>
                        </div>
                    )}

                    <div className="space-y-1">
                        <Label
                            htmlFor="draft-note"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            Anything to flag (optional)
                        </Label>
                        <Textarea
                            id="draft-note"
                            data-testid={IDS.note}
                            rows={2}
                            maxLength={1000}
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            placeholder="Music is a placeholder, happy to swap it…"
                            className="min-h-[72px] border-white/10 bg-background/60 focus-visible:ring-ember-500"
                        />
                    </div>

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
                                    Sending…
                                </>
                            ) : (
                                <>
                                    <Send className="mr-2 h-4 w-4" />
                                    Send for review
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
