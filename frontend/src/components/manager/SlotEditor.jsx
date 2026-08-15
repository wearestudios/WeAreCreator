// Creating and editing slots.
//
// The form follows the campaign's type rather than offering every field and
// hoping: an event campaign's slots are fixed times on a day already decided,
// so only the time is asked for. A personal table is a window, so it needs
// both ends. The server enforces the same rule; this just doesn't ask for
// something it would then refuse.
import React, { useEffect, useState } from "react";
import { Minus, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { MANAGER_SLOT_EDITOR as IDS } from "@/constants/testIds";
import { BigButton, TOUCH, formatDay } from "./shared";

// An ISO timestamp split into the two values the inputs want.
const toParts = (iso) => {
    if (!iso) return { date: "", time: "" };
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return { date: "", time: "" };
    const pad = (n) => String(n).padStart(2, "0");
    return {
        date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
        time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
    };
};

const toIso = (date, time) => {
    if (!date || !time) return null;
    const d = new Date(`${date}T${time}`);
    return Number.isNaN(d.getTime()) ? null : d.toISOString();
};

export default function SlotEditor({ open, slot, campaign, onClose, onSubmit, busy }) {
    const isEvent = campaign?.campaign_type !== "personal_table";
    const editing = Boolean(slot);

    const [date, setDate] = useState("");
    const [startTime, setStartTime] = useState("");
    const [endTime, setEndTime] = useState("");
    const [capacity, setCapacity] = useState(4);
    const [err, setErr] = useState("");

    useEffect(() => {
        if (!open) return;
        setErr("");
        if (slot) {
            const s = toParts(slot.starts_at);
            const e = toParts(slot.ends_at);
            setDate(s.date);
            setStartTime(s.time);
            setEndTime(e.time);
            setCapacity(slot.capacity ?? 4);
        } else {
            // An event's slots can only be on the event day, so it is filled in
            // and left alone rather than offered as a choice.
            setDate(isEvent ? toParts(campaign?.event_date).date : toParts(campaign?.start_date).date);
            setStartTime("");
            setEndTime("");
            setCapacity(4);
        }
    }, [open, slot, campaign, isEvent]);

    const submit = () => {
        const starts = toIso(date, startTime);
        if (!starts) {
            setErr(isEvent ? "Pick a time." : "Pick a date and a start time.");
            return;
        }
        if (!isEvent && !endTime) {
            setErr("A window needs an end time too.");
            return;
        }
        const ends = isEvent ? null : toIso(date, endTime);
        if (ends && new Date(ends) <= new Date(starts)) {
            setErr("The window has to end after it starts.");
            return;
        }
        const n = Number(capacity);
        if (!Number.isInteger(n) || n < 1) {
            setErr("At least one place.");
            return;
        }
        setErr("");
        onSubmit({ starts_at: starts, ends_at: ends, capacity: n });
    };

    const booked = slot?.booked_count ?? 0;

    return (
        <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
            <SheetContent
                side="bottom"
                data-testid={IDS.dialog}
                className="max-h-[90vh] overflow-y-auto rounded-t-md border-t border-white/10 bg-card"
            >
                <SheetTitle className="font-serif text-2xl leading-tight">
                    {editing ? "Edit slot" : "Add a slot"}
                </SheetTitle>
                <SheetDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {isEvent
                        ? `Fixed time on ${formatDay(campaign?.event_date) || "the event day"}.`
                        : "An availability window creators can book into."}
                </SheetDescription>

                <div className="mt-6 space-y-5">
                    {/* An event's day is decided by the brief; only a table
                        window gets to choose which day it sits on. */}
                    {!isEvent && (
                        <div>
                            <Label
                                htmlFor="slot-date"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                Date
                            </Label>
                            <Input
                                id="slot-date"
                                type="date"
                                value={date}
                                onChange={(e) => setDate(e.target.value)}
                                data-testid={IDS.date}
                                className={`mt-2 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500 ${TOUCH}`}
                            />
                        </div>
                    )}

                    <div className={isEvent ? "" : "grid grid-cols-2 gap-4"}>
                        <div>
                            <Label
                                htmlFor="slot-start"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                {isEvent ? "Time" : "From"}
                            </Label>
                            <Input
                                id="slot-start"
                                type="time"
                                value={startTime}
                                onChange={(e) => setStartTime(e.target.value)}
                                data-testid={IDS.startTime}
                                className={`mt-2 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500 ${TOUCH}`}
                            />
                        </div>
                        {!isEvent && (
                            <div>
                                <Label
                                    htmlFor="slot-end"
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    To
                                </Label>
                                <Input
                                    id="slot-end"
                                    type="time"
                                    value={endTime}
                                    onChange={(e) => setEndTime(e.target.value)}
                                    data-testid={IDS.endTime}
                                    className={`mt-2 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500 ${TOUCH}`}
                                />
                            </div>
                        )}
                    </div>

                    <div>
                        <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            Places
                        </Label>
                        {/* Steppers rather than a keyboard: this gets changed
                            standing up, and the numbers are small. */}
                        <div className="mt-2 flex items-center gap-3">
                            <button
                                type="button"
                                aria-label="One fewer place"
                                data-testid={IDS.capacityMinus}
                                onClick={() => setCapacity((c) => Math.max(booked || 1, Number(c) - 1))}
                                className={`grid w-16 flex-none place-items-center rounded-md border border-white/15 transition-colors duration-200 hover:border-white/30 ${TOUCH}`}
                            >
                                <Minus className="h-5 w-5" />
                            </button>
                            <Input
                                type="number"
                                min={Math.max(1, booked)}
                                value={capacity}
                                onChange={(e) => setCapacity(e.target.value)}
                                data-testid={IDS.capacity}
                                className={`rounded-md border-white/10 bg-background/60 text-center font-serif text-xl focus-visible:ring-ember-500 ${TOUCH}`}
                            />
                            <button
                                type="button"
                                aria-label="One more place"
                                data-testid={IDS.capacityPlus}
                                onClick={() => setCapacity((c) => Number(c) + 1)}
                                className={`grid w-16 flex-none place-items-center rounded-md border border-white/15 transition-colors duration-200 hover:border-white/30 ${TOUCH}`}
                            >
                                <Plus className="h-5 w-5" />
                            </button>
                        </div>
                        {booked > 0 && (
                            <p className="mt-2 text-xs text-muted-foreground">
                                {booked} already booked — it can't go below that.
                            </p>
                        )}
                    </div>

                    {err && (
                        <p data-testid={IDS.error} className="text-sm text-destructive">
                            {err}
                        </p>
                    )}
                </div>

                <div className="mt-6 flex flex-col gap-3">
                    <BigButton
                        type="button"
                        busy={busy}
                        onClick={submit}
                        data-testid={IDS.submit}
                        className="bg-ember-500 text-black hover:bg-ember-400"
                    >
                        {editing ? "Save slot" : "Add slot"}
                    </BigButton>
                    <BigButton
                        type="button"
                        variant="outline"
                        onClick={onClose}
                        data-testid={IDS.cancel}
                        className="border-white/15 bg-transparent"
                    >
                        Cancel
                    </BigButton>
                </div>
            </SheetContent>
        </Sheet>
    );
}
