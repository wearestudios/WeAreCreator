// What the published work did, typed in by whoever was at the shoot.
//
// `POST /manager/collaborations/{id}/performance` shipped with no caller.
// `ManagerHome` keeps finished campaigns folded-but-present with a comment
// saying it is "because performance still gets recorded days later" — and
// there was no control to record it with, so the manager opened a past
// campaign and found the roster of a shoot that had already happened.
//
// **An unknown metric is left blank, never zeroed.** A post with no saves and
// a post whose saves nobody could read are different, and averaging the second
// as a zero makes a campaign look worse than it was. Blank fields are omitted
// from the payload entirely, which is what the server reads as "not known".
//
// `engagement_rate` is deliberately not asked for: it is derived from these
// numbers on read, so it can never contradict them.
import React, { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { MANAGER_PERFORMANCE as IDS } from "@/constants/testIds";

import { BigButton } from "./shared";

// Mirrors PERFORMANCE_METRICS in server.py, in the order somebody reads them
// off an Instagram insights screen.
const METRICS = [
    { key: "reach", label: "Reach" },
    { key: "impressions", label: "Impressions" },
    { key: "views", label: "Views" },
    { key: "likes", label: "Likes" },
    { key: "comments", label: "Comments" },
    { key: "saves", label: "Saves" },
];

const BLANK = { note: "", ...Object.fromEntries(METRICS.map((m) => [m.key, ""])) };

export default function PerformanceSheet({ row, onClose, onSaved }) {
    const [form, setForm] = useState(BLANK);
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState("");

    useEffect(() => {
        if (row) {
            setForm(BLANK);
            setErr("");
        }
    }, [row]);

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async () => {
        // Only the numbers actually typed. An empty box is a reading nobody
        // took, and sending it as 0 would be a lie the rollup then averages.
        const body = {};
        for (const m of METRICS) {
            const raw = String(form[m.key]).trim();
            if (raw !== "") body[m.key] = Number(raw);
        }
        if (Object.keys(body).length === 0) {
            setErr("Put in at least one number — a record of nothing is not a record.");
            return;
        }
        if (form.note.trim()) body.note = form.note.trim();

        setBusy(true);
        setErr("");
        try {
            await api.post(
                `/manager/collaborations/${row.collaboration_id}/performance`,
                body,
            );
            notifySuccess(`Recorded for ${row.name || "the creator"}`);
            onClose();
            await onSaved?.();
        } catch (e) {
            notifyError(e, { fallback: "That couldn't be saved." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <Sheet open={Boolean(row)} onOpenChange={(v) => !v && onClose()}>
            <SheetContent
                side="bottom"
                data-testid={IDS.sheet}
                className="max-h-[90dvh] overflow-y-auto rounded-t-md border-t border-white/10 bg-card grain-surface"
            >
                <SheetTitle className="font-serif text-2xl leading-tight">
                    How did {row?.name || "it"} do?
                </SheetTitle>
                <SheetDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    Read off the post's own insights. Leave anything you cannot see
                    blank — a blank is "not known", which is different from zero, and
                    the report treats it that way.
                </SheetDescription>

                <div className="mt-5 grid grid-cols-2 gap-3">
                    {METRICS.map((m) => (
                        <label key={m.key} className="block min-w-0">
                            <span className="block text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                                {m.label}
                            </span>
                            <Input
                                type="number"
                                min="0"
                                inputMode="numeric"
                                value={form[m.key]}
                                onChange={set(m.key)}
                                data-testid={IDS.field(m.key)}
                                className="mt-1 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                            />
                        </label>
                    ))}
                </div>

                <label className="mt-4 block">
                    <span className="block text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Note <span className="opacity-60">(optional)</span>
                    </span>
                    <Textarea
                        rows={2}
                        maxLength={500}
                        value={form.note}
                        onChange={set("note")}
                        data-testid={IDS.note}
                        placeholder="e.g. Read 4 days after posting"
                        className="mt-1 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />
                </label>

                {err && (
                    <p data-testid={IDS.error} className="mt-3 text-sm text-destructive">
                        {err}
                    </p>
                )}

                <div className="mt-6 flex flex-col gap-3">
                    <BigButton
                        type="button"
                        busy={busy}
                        onClick={submit}
                        data-testid={IDS.submit}
                        className="bg-ember-500 text-black hover:bg-ember-400"
                    >
                        Save the numbers
                    </BigButton>
                    <BigButton
                        type="button"
                        variant="outline"
                        onClick={onClose}
                        data-testid={IDS.cancel}
                        className="border-white/15 bg-transparent"
                    >
                        Back
                    </BigButton>
                </div>
            </SheetContent>
        </Sheet>
    );
}
