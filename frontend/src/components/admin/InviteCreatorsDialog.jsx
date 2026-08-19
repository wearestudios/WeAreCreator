// Inviting creators to a campaign. Sourcing is a manual job — someone reads the
// brief and picks people — so this is a searchable multi-select over the roster,
// and it reports what actually happened per creator rather than one verdict for
// the batch. A WhatsApp send can fail for one number and land for the next.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { notifyError, notifySuccess, notifyWarning } from "@/lib/feedback";
import { AlertCircle, Check, Loader2, Search, Send, UserCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ADMIN_INVITE as IDS } from "@/constants/testIds";
import { CreatorAvatar, formatCompact, formatRupees } from "./shared";

// One page of candidates is enough to pick from by eye; past that, search.
const PAGE_SIZE = 50;

const RESULT_META = {
    invited: {
        label: "Invited",
        tone: "text-emerald-300",
        Icon: Check,
    },
    already_invited: {
        label: "Already invited",
        tone: "text-muted-foreground",
        Icon: UserCheck,
    },
    failed: {
        label: "Not sent",
        tone: "text-red-300",
        Icon: AlertCircle,
    },
};

export default function InviteCreatorsDialog({ campaign, open, onOpenChange, onSent }) {
    const [q, setQ] = useState("");
    const [search, setSearch] = useState("");
    const [rows, setRows] = useState(null);
    const [selected, setSelected] = useState([]);
    const [note, setNote] = useState("");
    const [sending, setSending] = useState(false);
    const [report, setReport] = useState(null);

    // A fresh dialog every time — a leftover selection from the last campaign
    // is how the wrong creator gets messaged.
    useEffect(() => {
        if (open) {
            setQ("");
            setSearch("");
            setSelected([]);
            setNote("");
            setReport(null);
        }
    }, [open, campaign?.id]);

    useEffect(() => {
        const t = setTimeout(() => setSearch(q.trim()), 300);
        return () => clearTimeout(t);
    }, [q]);

    const load = useCallback(async () => {
        if (!open) return;
        setRows(null);
        try {
            // Only verified creators can apply, so only they can usefully be
            // invited — the server refuses the rest anyway.
            const { data } = await api.get("/admin/creators", {
                params: {
                    verification_status: "verified",
                    page_size: PAGE_SIZE,
                    ...(search ? { q: search } : {}),
                },
            });
            setRows(data.creators || []);
        } catch (e) {
            notifyError(e);
            setRows([]);
        }
    }, [open, search]);

    useEffect(() => {
        load();
    }, [load]);

    // Someone selected on page one must stay selected after the list is
    // re-searched, so the chosen rows are tracked whole, not as ids into `rows`.
    const toggle = (creator) => {
        setSelected((prev) =>
            prev.some((c) => c.user_id === creator.user_id)
                ? prev.filter((c) => c.user_id !== creator.user_id)
                : [...prev, creator],
        );
    };

    const selectedIds = useMemo(
        () => new Set(selected.map((c) => c.user_id)),
        [selected],
    );

    const send = async () => {
        if (selected.length === 0) return;
        setSending(true);
        try {
            const { data } = await api.post(`/admin/campaigns/${campaign.id}/invite`, {
                creator_ids: selected.map((c) => c.user_id),
                note: note.trim() || null,
            });
            setReport(data);
            if (data.invited > 0 && data.failed === 0) {
                notifySuccess(
                    `Invited ${data.invited} creator${data.invited === 1 ? "" : "s"}`,
                );
            } else if (data.invited > 0) {
                // Partial sends are the reason this screen exists — say so
                // rather than showing a green tick over a half-failure.
                notifyWarning(`${data.invited} sent, ${data.failed} didn't go through`);
            } else {
                notifyError("Nothing was sent — see the detail below.");
            }
            onSent?.();
        } catch (e) {
            notifyError(e);
        } finally {
            setSending(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={IDS.dialog}
                className="flex max-h-[85vh] max-w-lg flex-col rounded-md border border-white/10 bg-card"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Invite creators
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {campaign?.title}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm text-muted-foreground">
                        {campaign?.brand_name || "Unknown brand"} · ₹
                        {formatRupees(campaign?.budget_per_creator)} per creator. They get a
                        WhatsApp message and a note in their dashboard.
                    </DialogDescription>
                </DialogHeader>

                {report ? (
                    <div data-testid={IDS.report} className="mt-2 min-h-0 flex-1 overflow-y-auto">
                        <p className="text-sm text-muted-foreground">
                            {report.invited} invited · {report.failed} failed ·{" "}
                            {report.already_invited} already had one.
                        </p>
                        <ul className="mt-4 divide-y divide-white/10">
                            {report.results.map((r) => {
                                const meta = RESULT_META[r.status] || RESULT_META.failed;
                                const { Icon } = meta;
                                return (
                                    <li
                                        key={r.creator_id}
                                        data-testid={IDS.reportRow(r.creator_id)}
                                        className="flex items-start gap-3 py-3"
                                    >
                                        <Icon className={`mt-0.5 h-4 w-4 flex-none ${meta.tone}`} />
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm">
                                                {r.name || r.creator_id}{" "}
                                                <span className={`text-sm ${meta.tone}`}>
                                                    · {meta.label}
                                                </span>
                                            </p>
                                            {r.reason && (
                                                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                                                    {r.reason}
                                                </p>
                                            )}
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                ) : (
                    <>
                        <div className="relative mt-2">
                            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                value={q}
                                onChange={(e) => setQ(e.target.value)}
                                data-testid={IDS.search}
                                placeholder="Search verified creators"
                                aria-label="Search verified creators"
                                className="h-11 md:h-10 rounded-md border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                            />
                        </div>

                        <div className="min-h-0 flex-1 overflow-y-auto rounded-md border border-white/10 bg-background/40">
                            {rows === null ? (
                                <div data-testid={IDS.skeleton} className="divide-y divide-white/10">
                                    {[0, 1, 2, 3].map((i) => (
                                        <div key={i} className="flex items-center gap-3 px-4 py-3">
                                            <Skeleton className="h-9 w-9 flex-none rounded-md" />
                                            <div className="flex-1 space-y-2">
                                                <Skeleton className="h-3 w-1/2" />
                                                <Skeleton className="h-3 w-1/3" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : rows.length === 0 ? (
                                <p
                                    data-testid={IDS.empty}
                                    className="px-4 py-8 text-center text-sm text-muted-foreground"
                                >
                                    {search
                                        ? "No verified creator matches that."
                                        : "No verified creators to invite yet."}
                                </p>
                            ) : (
                                <ul data-testid={IDS.list} className="divide-y divide-white/10">
                                    {rows.map((c) => {
                                        const isOn = selectedIds.has(c.user_id);
                                        return (
                                            <li key={c.user_id}>
                                                <button
                                                    type="button"
                                                    onClick={() => toggle(c)}
                                                    aria-pressed={isOn}
                                                    data-testid={IDS.option(c.user_id)}
                                                    className={
                                                        "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 " +
                                                        (isOn ? "bg-ember-500/10" : "hover:bg-white/5")
                                                    }
                                                >
                                                    <CreatorAvatar creator={c} size="h-9 w-9" />
                                                    <div className="min-w-0 flex-1">
                                                        <p className="truncate text-sm">{c.name}</p>
                                                        <p className="truncate text-sm text-muted-foreground">
                                                            {c.instagram_handle
                                                                ? `@${c.instagram_handle}`
                                                                : "No handle"}
                                                            {typeof c.follower_count === "number"
                                                                ? ` · ${formatCompact(c.follower_count)}`
                                                                : ""}
                                                            {c.city ? ` · ${c.city}` : ""}
                                                        </p>
                                                    </div>
                                                    <span
                                                        className={
                                                            "grid h-5 w-5 flex-none place-items-center rounded border transition-colors duration-150 " +
                                                            (isOn
                                                                ? "border-ember-500 bg-ember-500 text-black"
                                                                : "border-white/20")
                                                        }
                                                    >
                                                        {isOn && <Check className="h-3.5 w-3.5" />}
                                                    </span>
                                                </button>
                                            </li>
                                        );
                                    })}
                                </ul>
                            )}
                        </div>

                        {rows?.length === PAGE_SIZE && (
                            <p className="text-sm text-muted-foreground">
                                Showing the first {PAGE_SIZE}. Search to narrow it down.
                            </p>
                        )}

                        <div>
                            <Label
                                htmlFor="invite-note"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                Note (internal)
                            </Label>
                            <Input
                                id="invite-note"
                                value={note}
                                onChange={(e) => setNote(e.target.value)}
                                data-testid={IDS.note}
                                maxLength={500}
                                placeholder="Why these creators — kept on the record, not sent"
                                className="mt-2 h-11 md:h-10 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            />
                        </div>
                    </>
                )}

                <DialogFooter className="gap-2">
                    {report ? (
                        <DialogClose asChild>
                            <Button
                                type="button"
                                data-testid={IDS.reportDone}
                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                Done
                            </Button>
                        </DialogClose>
                    ) : (
                        <>
                            <span
                                data-testid={IDS.selectedCount}
                                className="mr-auto self-center text-xs uppercase tracking-[0.18em] text-muted-foreground"
                            >
                                {selected.length} selected
                            </span>
                            <DialogClose asChild>
                                <Button
                                    type="button"
                                    variant="outline"
                                    data-testid={IDS.cancel}
                                    className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                >
                                    Cancel
                                </Button>
                            </DialogClose>
                            <Button
                                type="button"
                                onClick={send}
                                disabled={sending || selected.length === 0}
                                data-testid={IDS.submit}
                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                {sending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Sending…
                                    </>
                                ) : (
                                    <>
                                        <Send className="mr-2 h-4 w-4" />
                                        Send invites
                                    </>
                                )}
                            </Button>
                        </>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
