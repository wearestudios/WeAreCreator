// Day-of mode: the checklist you work through while people are arriving.
//
// One column, one row per creator, three targets each — call, check in, or open
// the rest. Everything is thumb-sized and nothing is behind a hover, because
// this is used one-handed while holding a clipboard or a phone to your ear.
// Actions that cost something (no-show, reschedule) open a sheet from the
// bottom rather than firing on the tap that reached them.
import React, { useMemo, useState } from "react";
import { toast } from "sonner";
import {
    CalendarClock,
    Check,
    ChevronDown,
    PartyPopper,
    Phone,
    UserX,
} from "lucide-react";
import { api, formatApiError } from "@/lib/api";
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
    const [filter, setFilter] = useState("expected");
    const [openId, setOpenId] = useState(null);
    const [busyId, setBusyId] = useState(null);
    const [noShowFor, setNoShowFor] = useState(null);
    const [rescheduleFor, setRescheduleFor] = useState(null);

    const rows = useMemo(() => {
        const list = roster || [];
        if (filter === "all") return list;
        return list.filter((r) => r.attendance === filter);
    }, [roster, filter]);

    const done = (roster || []).filter((r) => r.attendance !== "expected").length;
    const total = (roster || []).length;

    const run = async (row, fn, message) => {
        setBusyId(row.collaboration_id);
        try {
            await fn();
            toast.success(message);
            setNoShowFor(null);
            setRescheduleFor(null);
            setOpenId(null);
            await onChanged?.();
        } catch (e) {
            toast.error(formatApiError(e));
        } finally {
            setBusyId(null);
        }
    };

    const checkIn = (row) =>
        run(
            row,
            () => api.post(`/manager/collaborations/${row.collaboration_id}/check-in`),
            `${row.name || "Creator"} checked in`,
        );

    if (loading) {
        return <RowListSkeleton rows={5} testid={IDS.skeleton} />;
    }

    return (
        <section data-testid={IDS.section} className="space-y-5">
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
                        () =>
                            api.post(
                                `/manager/collaborations/${noShowFor.collaboration_id}/no-show`,
                                { note },
                            ),
                        "Reported — the WeAre team will pick it up",
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
                        () =>
                            api.post(
                                `/manager/collaborations/${rescheduleFor.collaboration_id}/reschedule`,
                                body,
                            ),
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
