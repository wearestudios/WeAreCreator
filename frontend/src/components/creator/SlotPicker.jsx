// Booking a slot.
//
// Two shapes behind one dialog, because they are one decision to the creator:
// on a launch or a group event the manager has already set the times and the
// creator is choosing between them; on a personal table they are choosing a
// time inside a window the manager opened. Either way there is a review step
// before anything is written — a booked slot is a real seat at a real venue
// on a real evening, and a mis-tap on a phone shouldn't be able to take one.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
    AlertCircle,
    ArrowLeft,
    CalendarClock,
    Check,
    Loader2,
    Users,
} from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Skeleton } from "@/components/ui/skeleton";
import { api, formatApiError } from "@/lib/api";
import { CREATOR_SLOT_PICKER as IDS } from "@/constants/testIds";
import { formatDay, formatTime } from "./shared";

const HOUR_MS = 60 * 60 * 1000;

const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const sameDay = (a, b) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

/** Every local day a window touches, so a multi-day window gets a calendar. */
function daysWithin(startIso, endIso) {
    const start = new Date(startIso);
    const end = new Date(endIso || startIso);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return [];
    const days = [];
    let cursor = startOfDay(start);
    // A window longer than a season is a data problem, not a picker problem —
    // stop rather than render a thousand days.
    while (cursor <= end && days.length < 120) {
        days.push(cursor);
        cursor = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + 1);
    }
    return days;
}

/**
 * Bookable times on one day of a window, on the hour.
 *
 * Anything inside the next hour is dropped: a creator cannot be at a venue in
 * ten minutes, and offering it only produces a booking somebody has to undo.
 */
function timesOn(day, startIso, endIso) {
    const windowStart = new Date(startIso);
    const windowEnd = new Date(endIso || startIso);
    const soonest = new Date(Date.now() + HOUR_MS);

    let from = new Date(Math.max(windowStart.getTime(), startOfDay(day).getTime(), soonest.getTime()));
    const dayEnd = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 23, 59, 59);
    const to = new Date(Math.min(windowEnd.getTime(), dayEnd.getTime()));

    // Round up to the next whole hour.
    if (from.getMinutes() || from.getSeconds() || from.getMilliseconds()) {
        from = new Date(from.getFullYear(), from.getMonth(), from.getDate(), from.getHours() + 1);
    }

    const out = [];
    for (let t = from; t <= to && out.length < 24; t = new Date(t.getTime() + HOUR_MS)) {
        out.push(new Date(t));
    }
    return out;
}

const Chip = ({ on, children, testid, ...rest }) => (
    <button
        type="button"
        data-testid={testid}
        aria-pressed={on}
        className={
            "min-h-[3rem] rounded-md border px-4 text-sm transition-colors duration-200 " +
            (on
                ? "border-ember-500 bg-ember-500/10 text-ember-500"
                : "border-white/10 bg-background/60 text-foreground hover:border-white/25")
        }
        {...rest}
    >
        {children}
    </button>
);

export default function SlotPicker({ open, onOpenChange, collab, onBooked }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [slotId, setSlotId] = useState(null);
    const [day, setDay] = useState(null);
    const [time, setTime] = useState(null);
    const [reviewing, setReviewing] = useState(false);

    const campaignId = collab?.campaign_id;

    const load = useCallback(async () => {
        setError("");
        setData(null);
        try {
            const res = await api.get(`/creator/campaigns/${campaignId}/slots`);
            setData(res.data);
        } catch (e) {
            setError(formatApiError(e));
        }
    }, [campaignId]);

    useEffect(() => {
        if (!open || !campaignId) return;
        setSlotId(null);
        setDay(null);
        setTime(null);
        setReviewing(false);
        load();
    }, [open, campaignId, load]);

    const picksOwnTime = Boolean(data?.picks_own_time);
    const slots = useMemo(
        () => (data?.slots || []).filter((s) => !s.is_full),
        [data],
    );
    const chosen = useMemo(
        () => slots.find((s) => s.id === slotId) || null,
        [slots, slotId],
    );

    const days = useMemo(
        () => (chosen && picksOwnTime ? daysWithin(chosen.starts_at, chosen.ends_at) : []),
        [chosen, picksOwnTime],
    );
    const times = useMemo(
        () => (chosen && picksOwnTime && day ? timesOn(day, chosen.starts_at, chosen.ends_at) : []),
        [chosen, picksOwnTime, day],
    );

    // A single-day window has nothing to choose on a calendar, so skip it.
    useEffect(() => {
        if (picksOwnTime && days.length === 1 && !day) setDay(days[0]);
    }, [picksOwnTime, days, day]);

    const ready = picksOwnTime ? Boolean(chosen && time) : Boolean(chosen);
    const when = picksOwnTime ? time : chosen ? new Date(chosen.starts_at) : null;

    const confirm = async () => {
        if (!ready) return;
        setBusy(true);
        setError("");
        try {
            const body = { slot_id: chosen.id };
            if (picksOwnTime) body.preferred_time = time.toISOString();
            await api.post(`/creator/collaborations/${collab.id}/book-slot`, body);
            toast.success("Slot booked — it's on your dashboard");
            onOpenChange(false);
            onBooked?.();
        } catch (e) {
            // A lost race lands here. Re-reading the list is the only useful
            // next move, so do it for them rather than leaving a dead dialog.
            setError(formatApiError(e));
            setReviewing(false);
            load();
        } finally {
            setBusy(false);
        }
    };

    const pickSlot = (s) => {
        setSlotId(s.id);
        setTime(null);
        setDay(null);
        if (!picksOwnTime) setReviewing(true);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={IDS.dialog}
                className="max-h-[90vh] max-w-lg overflow-y-auto rounded-md border border-white/10 bg-card grain-surface"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        {reviewing ? "Check and confirm" : "Pick your slot"}
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {collab?.campaign_title || data?.campaign_title || "Your slot"}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        {reviewing
                            ? "One look before we take the seat."
                            : data?.how_it_works || "Choose a time that works for you."}
                    </DialogDescription>
                </DialogHeader>

                {!data && !error && (
                    <div data-testid={IDS.skeleton} className="mt-5 space-y-3">
                        {[0, 1, 2].map((i) => (
                            <Skeleton key={i} className="h-16 w-full rounded-md" />
                        ))}
                    </div>
                )}

                {error && (
                    <p
                        data-testid={IDS.error}
                        className="mt-5 flex items-start gap-2 rounded-md border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-200"
                    >
                        <AlertCircle className="mt-0.5 h-4 w-4 flex-none" />
                        {error}
                    </p>
                )}

                {data && !reviewing && (
                    <div className="mt-5 space-y-6">
                        {picksOwnTime && (
                            <p
                                data-testid={IDS.window}
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                Windows open on this campaign
                            </p>
                        )}

                        {slots.length === 0 ? (
                            <p
                                data-testid={IDS.empty}
                                className="rounded-md border border-white/10 bg-background/60 px-4 py-6 text-sm leading-relaxed text-muted-foreground"
                            >
                                Every slot is taken right now. The campaign manager
                                usually opens more — check back, or message them if
                                you're stuck.
                            </p>
                        ) : (
                            <ul data-testid={IDS.list} className="space-y-3">
                                {slots.map((s) => {
                                    const on = s.id === slotId;
                                    return (
                                        <li key={s.id}>
                                            <button
                                                type="button"
                                                data-testid={IDS.option(s.id)}
                                                aria-pressed={on}
                                                onClick={() => pickSlot(s)}
                                                className={
                                                    "flex min-h-[3.5rem] w-full items-center justify-between gap-4 rounded-md border px-4 py-3 text-left transition-colors duration-200 " +
                                                    (on
                                                        ? "border-ember-500 bg-ember-500/10"
                                                        : "border-white/10 bg-background/60 hover:border-white/25")
                                                }
                                            >
                                                <span className="min-w-0">
                                                    <span className="block text-sm">
                                                        {formatDay(s.starts_at)}
                                                    </span>
                                                    <span className="mt-1 block text-xs text-muted-foreground">
                                                        {formatTime(s.starts_at)}
                                                        {s.ends_at ? ` – ${formatTime(s.ends_at)}` : ""}
                                                    </span>
                                                </span>
                                                <span
                                                    data-testid={IDS.spots(s.id)}
                                                    className="inline-flex flex-none items-center gap-1.5 text-xs text-muted-foreground"
                                                >
                                                    <Users className="h-3.5 w-3.5" />
                                                    {s.spots_left} left
                                                </span>
                                            </button>
                                        </li>
                                    );
                                })}
                            </ul>
                        )}

                        {picksOwnTime && chosen && days.length > 1 && (
                            <div>
                                <p className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Which day?
                                </p>
                                <div
                                    data-testid={IDS.calendar}
                                    className="mt-3 rounded-md border border-white/10 bg-background/60"
                                >
                                    <Calendar
                                        mode="single"
                                        selected={day || undefined}
                                        onSelect={(d) => {
                                            setDay(d || null);
                                            setTime(null);
                                        }}
                                        fromDate={days[0]}
                                        toDate={days[days.length - 1]}
                                        disabled={(d) => !days.some((x) => sameDay(x, d))}
                                    />
                                </div>
                            </div>
                        )}

                        {picksOwnTime && chosen && day && (
                            <div>
                                <p className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    What time on {formatDay(day.toISOString())}?
                                </p>
                                {times.length === 0 ? (
                                    <p className="mt-3 text-sm text-muted-foreground">
                                        No times left on that day. Try another one.
                                    </p>
                                ) : (
                                    <div
                                        data-testid={IDS.timeList}
                                        className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4"
                                    >
                                        {times.map((t) => (
                                            <Chip
                                                key={t.toISOString()}
                                                testid={IDS.time(t.getTime())}
                                                on={Boolean(time) && time.getTime() === t.getTime()}
                                                onClick={() => setTime(t)}
                                            >
                                                {formatTime(t.toISOString())}
                                            </Chip>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {picksOwnTime && (
                            <Button
                                data-testid={IDS.review}
                                disabled={!ready}
                                onClick={() => setReviewing(true)}
                                className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400 disabled:opacity-40"
                            >
                                Review your booking
                            </Button>
                        )}
                    </div>
                )}

                {data && reviewing && chosen && (
                    <div className="mt-5 space-y-5">
                        <dl
                            data-testid={IDS.summary}
                            className="space-y-4 rounded-md border border-white/10 bg-background/60 p-5"
                        >
                            <div>
                                <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                    When
                                </dt>
                                <dd className="mt-2 inline-flex items-center gap-2 font-serif text-xl leading-tight">
                                    <CalendarClock className="h-4 w-4 text-ember-500" />
                                    {formatDay(when?.toISOString())} ·{" "}
                                    {formatTime(when?.toISOString())}
                                </dd>
                            </div>
                            {collab?.venue?.address && (
                                <div>
                                    <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                        Where
                                    </dt>
                                    <dd className="mt-2 text-sm leading-relaxed">
                                        {collab.venue.address}
                                    </dd>
                                </div>
                            )}
                            <div>
                                <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                    Places left on this slot
                                </dt>
                                <dd className="mt-2 text-sm text-muted-foreground">
                                    {chosen.spots_left}
                                </dd>
                            </div>
                        </dl>

                        <p className="text-xs leading-relaxed text-muted-foreground">
                            You can hand the slot back up to{" "}
                            {data.cancel_cutoff_hours ?? 24} hours before it. After
                            that the venue is already set up for you, so it's a call
                            to the campaign manager.
                        </p>

                        {/* Confirm sits lowest on a phone, where a thumb actually reaches,
                            and rightmost on a desktop. */}
                        <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
                            <Button
                                type="button"
                                variant="outline"
                                data-testid={IDS.back}
                                onClick={() => setReviewing(false)}
                                className="h-12 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Change it
                            </Button>
                            <Button
                                type="button"
                                data-testid={IDS.confirm}
                                disabled={busy}
                                onClick={confirm}
                                className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                {busy ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Booking…
                                    </>
                                ) : (
                                    <>
                                        <Check className="mr-2 h-4 w-4" />
                                        Book this slot
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
