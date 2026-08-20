// Day-of mode: the checklist you work through while people are arriving.
//
// One column, one row per creator, three targets each — call, check in, or open
// the rest. Everything is thumb-sized and nothing is behind a hover, because
// this is used one-handed while holding a clipboard or a phone to your ear.
// Actions that cost something (no-show, reschedule) open a sheet from the
// bottom rather than firing on the tap that reached them.
import React, { useEffect, useMemo, useState } from "react";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    CalendarClock,
    Check,
    ChevronDown,
    PartyPopper,
    Phone,
    UploadCloud,
    UserX,
} from "lucide-react";
import { api } from "@/lib/api";
import { enqueue, shouldRetry } from "@/lib/offlineQueue";
import QueueBanner from "@/components/manager/QueueBanner";
import CheckInQr from "@/components/manager/CheckInQr";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import {
    MANAGER_DAY_OF as IDS,
    MANAGER_NO_SHOW as NO_SHOW_IDS,
    MANAGER_RESCHEDULE as RESCHEDULE_IDS,
} from "@/constants/testIds";
import {
    ATTENDANCE_META,
    BigButton,
    EmptyState,
    Pill,
    RowListSkeleton,
    TOUCH,
    formatTime,
} from "./shared";

const FILTERS = [
    { key: "expected", label: "To check in" },
    { key: "attended", label: "Checked in" },
    { key: "all", label: "Everyone" },
];

export default function DayOfMode({ roster, slots, loading, onChanged }) {
    // Which slot's code to show. The busiest one today, because that is the
    // queue actually forming at the door; a single-slot shoot has exactly one
    // answer and this picks it without asking.
    const qrSlotId = useMemo(() => {
        const counts = new Map();
        for (const r of roster || []) {
            if (!r.slot_id) continue;
            counts.set(r.slot_id, (counts.get(r.slot_id) || 0) + 1);
        }
        let best = null;
        for (const [id, n] of counts) {
            if (!best || n > best[1]) best = [id, n];
        }
        return best ? best[0] : null;
    }, [roster]);

    const [filter, setFilter] = useState("expected");
    const [openId, setOpenId] = useState(null);
    const [busyId, setBusyId] = useState(null);
    const [noShowFor, setNoShowFor] = useState(null);
    const [rescheduleFor, setRescheduleFor] = useState(null);
    // Rows the screen is showing as done before the server has confirmed it.
    const [optimistic, setOptimistic] = useState({});
    // Rows whose check-in is on the offline queue. Kept apart from `optimistic`
    // because these get a visible "waiting to sync" marker: the manager should
    // be able to tell the difference between done and going-to-be-done without
    // reading the banner at the top of a long list.
    const [queued, setQueued] = useState({});

    // The roster as the screen shows it: the server's answer, with any
    // not-yet-confirmed check-ins applied on top. Everything below — the
    // filters, the count, the progress figure — reads from this, so an
    // optimistic tap moves all of them together rather than just the row.
    const shown = useMemo(
        () =>
            (roster || []).map((r) => {
                const pending = queued[r.collaboration_id];
                const override = optimistic[r.collaboration_id];
                if (!pending && !override) return r;
                return {
                    ...r,
                    attendance: override || "attended",
                    _queued: Boolean(pending),
                };
            }),
        [roster, optimistic, queued],
    );

    // Once the server's own roster says attended, the local marker has done its
    // job. Without this a synced row would keep saying "waiting" until the page
    // was reloaded.
    useEffect(() => {
        if (!roster) return;
        setQueued((s) => {
            const next = { ...s };
            let changed = false;
            for (const r of roster) {
                if (next[r.collaboration_id] && r.attendance !== "expected") {
                    delete next[r.collaboration_id];
                    changed = true;
                }
            }
            return changed ? next : s;
        });
    }, [roster]);

    const rows = useMemo(() => {
        if (filter === "all") return shown;
        return shown.filter((r) => r.attendance === filter);
    }, [shown, filter]);

    const done = shown.filter((r) => r.attendance !== "expected").length;
    const total = shown.length;

    // No-show and reschedule, **queued on a network failure exactly like a
    // check-in**.
    //
    // They used to raise a Retry toast instead. That was the wrong half of a
    // rule the check-in already got right: it is the same manager, in the same
    // basement, on the same phone, in the same minute — and asking somebody
    // mid-queue to notice a toast and tap it is asking them to do the
    // network's job. A reschedule that silently failed is worse than a lost
    // check-in, because the creator has been told a new time nobody recorded.
    //
    // A 4xx still drops through and says why: a refusal is the server telling
    // us the truth about state, and replaying it can never succeed.
    const run = async (row, { url, body = null }, message) => {
        const id = row.collaboration_id;
        setBusyId(id);
        try {
            await api.post(url, body);
            notifySuccess(message);
            setNoShowFor(null);
            setRescheduleFor(null);
            setOpenId(null);
            await onChanged?.();
        } catch (e) {
            if (shouldRetry(e)) {
                // Keyed on the action, so a second tap replaces rather than
                // stacks — the same rule the check-in queue holds.
                enqueue({ key: `${url}`, url, body, label: `${message} for ${row.name || "a creator"}` });
                notifySuccess(`${message} — will sync`);
                setNoShowFor(null);
                setRescheduleFor(null);
                setOpenId(null);
            } else {
                notifyError(e);
            }
        } finally {
            setBusyId(null);
        }
    };

    // Check-in is optimistic: the row flips the moment you tap it, because you
    // are looking at the person you just checked in, not at the phone.
    //
    // **A network failure does not roll it back — it queues it.** Reverting was
    // the old behaviour and it is wrong here: the manager has somebody in front
    // of them, the check-in did happen in the room, and asking them to notice a
    // toast and tap Retry while a queue forms is asking them to do the network's
    // job. So the request goes on disk and replays itself, the row stays
    // checked in, and the banner says how many are waiting.
    //
    // A refusal is different. A 409 ("already checked in", "this just moved")
    // is the server telling us the truth about state, so that one does revert
    // and say why — queueing it would replay a request that can never succeed.
    const checkIn = async (row) => {
        const id = row.collaboration_id;
        const drop = () =>
            setOptimistic((m) => {
                const next = { ...m };
                delete next[id];
                return next;
            });

        setOptimistic((m) => ({ ...m, [id]: "attended" }));
        setBusyId(id);
        try {
            await api.post(`/manager/collaborations/${id}/check-in`);
            notifySuccess(`${row.name || "Creator"} checked in`);
            setOpenId(null);
            await onChanged?.();
            // Only drop the local override once the refreshed roster carries
            // the new state, or the row would flicker back for a frame.
            drop();
        } catch (e) {
            if (shouldRetry(e)) {
                enqueue({
                    key: `check-in:${id}`,
                    url: `/manager/collaborations/${id}/check-in`,
                    label: `Check-in for ${row.name || "a creator"}`,
                });
                // The override stays until a refreshed roster shows `attended`,
                // so the row reads as done for as long as the queue holds it.
                setQueued((s) => ({ ...s, [id]: true }));
                notifySuccess(`${row.name || "Creator"} checked in — will sync`);
                setOpenId(null);
            } else {
                drop();
                notifyError(e);
            }
        } finally {
            setBusyId(null);
        }
    };

    if (loading) {
        return <RowListSkeleton rows={5} testid={IDS.skeleton} />;
    }

    return (
        <section data-testid={IDS.section} className="space-y-5">
            {/* Above the progress figure, because a queued check-in is counted
                in that figure and the manager should know why. */}
            <QueueBanner />

            {/* Progress first: the only number that matters mid-shift. */}
            <div
                data-testid={IDS.progress}
                className="rounded-md border border-white/10 bg-card p-5 grain-surface"
            >
                <div className="flex items-baseline justify-between">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Checked in
                    </p>
                    <p className="font-serif text-2xl leading-none">
                        {done}
                        <span className="text-muted-foreground">/{total}</span>
                    </p>
                </div>
                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div
                        className="h-full rounded-full bg-ember-500 transition-[width] duration-300"
                        style={{ width: total ? `${(done / total) * 100}%` : "0%" }}
                    />
                </div>
            </div>

            {/* The code, once, above the list — not per row. It names the
                slot, so one screen serves everybody booked on it, which is
                the whole reason it beats twenty taps. Shown for the slot
                most people are on today; a shoot with several slots keeps a
                code per slot, so the manager picks. */}
            {qrSlotId && <CheckInQr slotId={qrSlotId} />}

            <div className="flex gap-2">
                {FILTERS.map((f) => {
                    const on = filter === f.key;
                    const count =
                        f.key === "all"
                            ? total
                            : (roster || []).filter((r) => r.attendance === f.key).length;
                    return (
                        <button
                            key={f.key}
                            type="button"
                            aria-pressed={on}
                            onClick={() => setFilter(f.key)}
                            data-testid={IDS.filter(f.key)}
                            className={
                                "flex-1 rounded-md border px-3 py-3 text-xs uppercase tracking-[0.15em] transition-colors duration-200 " +
                                (on
                                    ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                    : "border-white/10 text-muted-foreground")
                            }
                        >
                            {f.label}
                            <span className="ml-1.5 opacity-70">{count}</span>
                        </button>
                    );
                })}
            </div>

            {rows.length === 0 ? (
                <EmptyState
                    testid={IDS.empty}
                    Icon={filter === "expected" ? PartyPopper : CalendarClock}
                >
                    {filter === "expected"
                        ? total === 0
                            ? "Nobody is booked on this campaign yet."
                            : "Everyone has been dealt with. That's the room done."
                        : "Nobody in this list yet."}
                </EmptyState>
            ) : (
                <ul className="space-y-3">
                    {rows.map((row) => {
                        const open = openId === row.collaboration_id;
                        const busy = busyId === row.collaboration_id;
                        const settled = row.attendance !== "expected";
                        return (
                            <li
                                key={row.collaboration_id}
                                data-testid={IDS.row(row.collaboration_id)}
                                className="overflow-hidden rounded-md border border-white/10 bg-card grain-surface"
                            >
                                <div className="flex items-stretch gap-3 p-4">
                                    <div className="flex min-w-0 flex-1 flex-col justify-center">
                                        <div className="flex items-center gap-2">
                                            <span className="font-serif text-lg leading-none">
                                                {formatTime(row.slot_time)}
                                            </span>
                                            {settled && (
                                                <Pill
                                                    meta={ATTENDANCE_META}
                                                    value={row.attendance}
                                                    testid={IDS.done(row.collaboration_id)}
                                                />
                                            )}
                                            {row._queued && (
                                                <span
                                                    data-testid={IDS.queued(row.collaboration_id)}
                                                    className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] text-amber-200"
                                                >
                                                    <UploadCloud className="h-3 w-3" />
                                                    Waiting
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-1.5 truncate text-sm">{row.name}</p>
                                        {row.instagram_handle && (
                                            <p className="truncate text-xs text-muted-foreground">
                                                @{row.instagram_handle}
                                            </p>
                                        )}
                                    </div>

                                    {row.phone && (
                                        <a
                                            href={`tel:${row.phone.replace(/\s+/g, "")}`}
                                            aria-label={`Call ${row.name}`}
                                            data-testid={IDS.call(row.collaboration_id)}
                                            className={`grid w-14 flex-none place-items-center rounded-md border border-white/15 text-muted-foreground transition-colors duration-200 hover:text-ember-500 ${TOUCH}`}
                                        >
                                            <Phone className="h-5 w-5" />
                                        </a>
                                    )}

                                    {row.attendance === "expected" ? (
                                        <button
                                            type="button"
                                            disabled={busy}
                                            onClick={() => checkIn(row)}
                                            aria-label={`Check in ${row.name}`}
                                            data-testid={IDS.checkIn(row.collaboration_id)}
                                            className={`grid w-16 flex-none place-items-center rounded-md bg-ember-500 text-black transition-colors duration-200 hover:bg-ember-400 disabled:opacity-50 ${TOUCH}`}
                                        >
                                            <Check className="h-6 w-6" />
                                        </button>
                                    ) : (
                                        <div className="grid w-16 flex-none place-items-center rounded-md border border-white/10 text-emerald-300">
                                            <Check className="h-5 w-5" />
                                        </div>
                                    )}
                                </div>

                                {/* The costly actions live one tap deeper, so the
                                    fast path stays a single thumb press. */}
                                {!settled && (
                                    <>
                                        <button
                                            type="button"
                                            aria-expanded={open}
                                            onClick={() => setOpenId(open ? null : row.collaboration_id)}
                                            className="flex w-full items-center justify-center gap-1.5 border-t border-white/10 py-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-foreground"
                                        >
                                            More
                                            <ChevronDown
                                                className={
                                                    "h-3.5 w-3.5 transition-transform duration-200 " +
                                                    (open ? "rotate-180" : "")
                                                }
                                            />
                                        </button>
                                        {open && (
                                            <div className="grid gap-2 border-t border-white/10 p-4 sm:grid-cols-2">
                                                <Button
                                                    type="button"
                                                    variant="outline"
                                                    disabled={busy}
                                                    onClick={() => setRescheduleFor(row)}
                                                    data-testid={IDS.reschedule(row.collaboration_id)}
                                                    className={`rounded-md border-white/15 bg-transparent ${TOUCH}`}
                                                >
                                                    <CalendarClock className="mr-2 h-4 w-4" />
                                                    Move slot
                                                </Button>
                                                <Button
                                                    type="button"
                                                    variant="outline"
                                                    disabled={busy}
                                                    onClick={() => setNoShowFor(row)}
                                                    data-testid={IDS.noShow(row.collaboration_id)}
                                                    className={`rounded-md border-red-500/30 bg-transparent text-red-300 hover:bg-red-500/10 ${TOUCH}`}
                                                >
                                                    <UserX className="mr-2 h-4 w-4" />
                                                    No-show
                                                </Button>
                                            </div>
                                        )}
                                    </>
                                )}
                            </li>
                        );
                    })}
                </ul>
            )}

            <NoShowSheet
                row={noShowFor}
                busy={busyId === noShowFor?.collaboration_id}
                onClose={() => setNoShowFor(null)}
                onSubmit={(note) =>
                    run(
                        noShowFor,
                        {
                            url: `/manager/collaborations/${noShowFor.collaboration_id}/no-show`,
                            body: { note },
                        },
                        "Reported",
                    )
                }
            />

            <RescheduleSheet
                row={rescheduleFor}
                slots={slots}
                busy={busyId === rescheduleFor?.collaboration_id}
                onClose={() => setRescheduleFor(null)}
                onSubmit={(body) =>
                    run(
                        rescheduleFor,
                        {
                            url: `/manager/collaborations/${rescheduleFor.collaboration_id}/reschedule`,
                            body,
                        },
                        "Moved",
                    )
                }
            />
        </section>
    );
}

/**
 * A no-show needs a note, and the sheet says plainly what it does — the manager
 * is reporting, not cancelling. Somebody else decides what the creator is owed.
 */
function NoShowSheet({ row, busy, onClose, onSubmit }) {
    const [note, setNote] = useState("");
    const [err, setErr] = useState("");

    React.useEffect(() => {
        if (row) {
            setNote("");
            setErr("");
        }
    }, [row]);

    const submit = () => {
        if (note.trim().length < 3) {
            setErr("Say what happened — the team reads this before deciding anything.");
            return;
        }
        onSubmit(note.trim());
    };

    return (
        <Sheet open={Boolean(row)} onOpenChange={(v) => !v && onClose()}>
            <SheetContent
                side="bottom"
                data-testid={NO_SHOW_IDS.sheet}
                className="rounded-t-md border-t border-white/10 bg-card grain-surface"
            >
                <SheetTitle className="font-serif text-2xl leading-tight">
                    {row?.name} didn't turn up?
                </SheetTitle>
                <SheetDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    This flags it for the WeAre team. It doesn't cancel anything — they
                    decide what happens to the booking and the fee.
                </SheetDescription>

                <Textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={3}
                    maxLength={500}
                    data-testid={NO_SHOW_IDS.note}
                    placeholder="e.g. Waited an hour, no answer on the phone"
                    className="mt-5 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                />
                {err && (
                    <p data-testid={NO_SHOW_IDS.error} className="mt-3 text-sm text-destructive">
                        {err}
                    </p>
                )}

                <div className="mt-6 flex flex-col gap-3">
                    <BigButton
                        type="button"
                        busy={busy}
                        onClick={submit}
                        data-testid={NO_SHOW_IDS.submit}
                        className="border border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10"
                    >
                        Report no-show
                    </BigButton>
                    <BigButton
                        type="button"
                        variant="outline"
                        onClick={onClose}
                        data-testid={NO_SHOW_IDS.cancel}
                        className="border-white/15 bg-transparent"
                    >
                        Back
                    </BigButton>
                </div>
            </SheetContent>
        </Sheet>
    );
}

/** Moving somebody: pick the new slot, with what's left on each one shown. */
function RescheduleSheet({ row, slots, busy, onClose, onSubmit }) {
    const [picked, setPicked] = useState(null);
    const [reason, setReason] = useState("");

    React.useEffect(() => {
        if (row) {
            setPicked(null);
            setReason("");
        }
    }, [row]);

    const options = (slots || []).filter(
        (s) => s.id !== row?.slot_id && s.spots_left > 0,
    );

    return (
        <Sheet open={Boolean(row)} onOpenChange={(v) => !v && onClose()}>
            <SheetContent
                side="bottom"
                data-testid={RESCHEDULE_IDS.sheet}
                className="max-h-[85vh] overflow-y-auto rounded-t-md border-t border-white/10 bg-card grain-surface"
            >
                <SheetTitle className="font-serif text-2xl leading-tight">
                    Move {row?.name}
                </SheetTitle>
                <SheetDescription className="mt-2 text-sm text-muted-foreground">
                    Currently at {formatTime(row?.slot_time)}. Only slots with room are
                    listed.
                </SheetDescription>

                {options.length === 0 ? (
                    <p
                        data-testid={RESCHEDULE_IDS.empty}
                        className="mt-6 rounded-md border border-white/10 bg-background/40 px-5 py-8 text-center text-sm text-muted-foreground"
                    >
                        Every other slot is full. Add one, or free a place first.
                    </p>
                ) : (
                    <ul className="mt-5 space-y-2">
                        {options.map((s) => {
                            const on = picked === s.id;
                            return (
                                <li key={s.id}>
                                    <button
                                        type="button"
                                        aria-pressed={on}
                                        onClick={() => setPicked(s.id)}
                                        data-testid={RESCHEDULE_IDS.option(s.id)}
                                        className={
                                            "flex w-full items-center justify-between rounded-md border px-5 text-left transition-colors duration-200 " +
                                            TOUCH +
                                            " " +
                                            (on
                                                ? "border-ember-500 bg-ember-500/10"
                                                : "border-white/10 hover:border-white/25")
                                        }
                                    >
                                        <span className="font-serif text-lg">
                                            {formatTime(s.starts_at)}
                                        </span>
                                        <span className="text-xs text-muted-foreground">
                                            {s.spots_left} left
                                        </span>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}

                <Textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    rows={2}
                    maxLength={500}
                    data-testid={RESCHEDULE_IDS.reason}
                    placeholder="Why (optional) — e.g. stuck in traffic"
                    className="mt-5 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                />

                <div className="mt-6 flex flex-col gap-3">
                    <BigButton
                        type="button"
                        busy={busy}
                        disabled={!picked}
                        onClick={() => onSubmit({ slot_id: picked, reason: reason.trim() || null })}
                        data-testid={RESCHEDULE_IDS.submit}
                        className="bg-ember-500 text-black hover:bg-ember-400"
                    >
                        Move them
                    </BigButton>
                    <BigButton
                        type="button"
                        variant="outline"
                        onClick={onClose}
                        data-testid={RESCHEDULE_IDS.cancel}
                        className="border-white/15 bg-transparent"
                    >
                        Back
                    </BigButton>
                </div>
            </SheetContent>
        </Sheet>
    );
}
