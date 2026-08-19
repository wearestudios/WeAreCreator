// When a shoot may happen, as the brand sets it.
//
// Two questions, and both are opt-in: most briefs have no restriction and a
// form that insists on an answer gets a made-up one. Days first, because "not
// Mondays" is the thing a venue says without being asked; windows second,
// because they only matter once you know which days.
//
// Presets carry their own times and the client never sends them — the server
// resolves "lunch" from its own table, so a preset whose hours we retune later
// cannot silently move a brief somebody already agreed to. Only a custom
// window carries times, which is why it is the only one with inputs.
import React, { useState } from "react";
import { Plus, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SCHEDULING as IDS } from "@/constants/testIds";
import {
    MAX_SHOOT_WINDOWS,
    SHOOT_WINDOW_PRESETS,
    WEEKDAYS,
    openDayLabels,
    parseHHMM,
    readableTime,
} from "@/lib/shootWindows";

const chip = (on) =>
    "min-h-[2.75rem] rounded-full border px-4 text-sm transition-colors duration-200 " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 " +
    "focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
    (on
        ? "border-ember-500 bg-ember-500/15 text-ember-500"
        : "border-white/10 bg-card/60 text-muted-foreground hover:border-white/25");

export default function ShootPreferences({ days, windows, onChange }) {
    const [customStart, setCustomStart] = useState("");
    const [customEnd, setCustomEnd] = useState("");
    const [customError, setCustomError] = useState("");

    const shut = new Set((days || []).map(Number));
    const picked = windows || [];
    const presetOn = (key) => picked.some((w) => w.key === key);
    const customs = picked.filter((w) => w.key === "custom");
    const full = picked.length >= MAX_SHOOT_WINDOWS;

    const toggleDay = (value) => {
        const next = new Set(shut);
        if (next.has(value)) next.delete(value);
        // Leaving no day open is a campaign nobody can book — the server 422s
        // on it, so the control refuses rather than letting somebody find out.
        else if (next.size < 6) next.add(value);
        onChange({ days: [...next].sort((a, b) => a - b), windows: picked });
    };

    const togglePreset = (key) => {
        const next = presetOn(key)
            ? picked.filter((w) => w.key !== key)
            : full
              ? picked
              : [...picked, { key }];
        onChange({ days: [...shut].sort((a, b) => a - b), windows: next });
    };

    const addCustom = () => {
        const start = parseHHMM(customStart);
        const end = parseHHMM(customEnd);
        if (start === null || end === null) {
            setCustomError("Give both a start and an end time.");
            return;
        }
        if (end <= start) {
            setCustomError("The window has to end after it starts.");
            return;
        }
        setCustomError("");
        setCustomStart("");
        setCustomEnd("");
        onChange({
            days: [...shut].sort((a, b) => a - b),
            windows: [...picked, { key: "custom", start: customStart, end: customEnd }],
        });
    };

    const removeCustom = (index) => {
        let seen = -1;
        onChange({
            days: [...shut].sort((a, b) => a - b),
            windows: picked.filter((w) => {
                if (w.key !== "custom") return true;
                seen += 1;
                return seen !== index;
            }),
        });
    };

    const open = openDayLabels([...shut]);

    return (
        <div data-testid={IDS.section} className="space-y-6">
            <div>
                <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                    Days that don't work
                </Label>
                <div className="mt-3 flex flex-wrap gap-2">
                    {WEEKDAYS.map((d) => (
                        <button
                            key={d.value}
                            type="button"
                            role="switch"
                            aria-checked={shut.has(d.value)}
                            data-testid={IDS.day(d.value)}
                            onClick={() => toggleDay(d.value)}
                            className={chip(shut.has(d.value))}
                        >
                            {d.short}
                        </button>
                    ))}
                </div>
                {/* Say the positive back, because "not Mon, not Tue, not Wed"
                    is four things to hold in your head and "Thu to Sun" is
                    one. */}
                <p
                    data-testid={IDS.openDays}
                    className="mt-2 text-xs leading-relaxed text-muted-foreground"
                >
                    {shut.size === 0
                        ? "Any day works. Tap the ones your venue is closed or too busy."
                        : `Creators can be booked on ${open.join(", ")}.`}
                </p>
            </div>

            <div>
                <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                    Hours that work
                </Label>
                <div className="mt-3 flex flex-wrap gap-2">
                    {SHOOT_WINDOW_PRESETS.map((p) => (
                        <button
                            key={p.key}
                            type="button"
                            role="switch"
                            aria-checked={presetOn(p.key)}
                            data-testid={IDS.window(p.key)}
                            disabled={full && !presetOn(p.key)}
                            onClick={() => togglePreset(p.key)}
                            className={chip(presetOn(p.key)) + " disabled:opacity-40"}
                        >
                            {p.label}
                            <span className="ml-2 text-xs opacity-70">
                                {readableTime(p.start)}–{readableTime(p.end)}
                            </span>
                        </button>
                    ))}
                </div>

                {customs.length > 0 && (
                    <ul className="mt-3 space-y-2">
                        {customs.map((w, i) => (
                            <li
                                key={`${w.start}-${w.end}-${i}`}
                                data-testid={IDS.customRow(i)}
                                className="flex items-center justify-between gap-3 rounded-md border border-ember-500/25 bg-ember-500/10 px-4 py-2.5 text-sm text-ember-500"
                            >
                                <span>
                                    {readableTime(w.start)} – {readableTime(w.end)}
                                </span>
                                <button
                                    type="button"
                                    aria-label="Remove this window"
                                    data-testid={IDS.customRemove(i)}
                                    onClick={() => removeCustom(i)}
                                    className="rounded-full p-1.5 transition-colors duration-200 hover:bg-white/10"
                                >
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            </li>
                        ))}
                    </ul>
                )}

                <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
                    <div className="flex-1">
                        <Label
                            htmlFor="pc-window-start"
                            className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            Or a custom window — from
                        </Label>
                        <Input
                            id="pc-window-start"
                            data-testid={IDS.customStart}
                            type="time"
                            value={customStart}
                            onChange={(e) => setCustomStart(e.target.value)}
                            className="mt-1 h-12 border-white/10 bg-background/60 focus-visible:ring-ember-500"
                        />
                    </div>
                    <div className="flex-1">
                        <Label
                            htmlFor="pc-window-end"
                            className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            to
                        </Label>
                        <Input
                            id="pc-window-end"
                            data-testid={IDS.customEnd}
                            type="time"
                            value={customEnd}
                            onChange={(e) => setCustomEnd(e.target.value)}
                            className="mt-1 h-12 border-white/10 bg-background/60 focus-visible:ring-ember-500"
                        />
                    </div>
                    <button
                        type="button"
                        data-testid={IDS.customAdd}
                        onClick={addCustom}
                        disabled={full}
                        className="inline-flex min-h-[3rem] items-center justify-center gap-1.5 rounded-full border border-white/10 px-4 text-sm text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 disabled:opacity-40"
                    >
                        <Plus className="h-4 w-4" />
                        Add
                    </button>
                </div>

                {customError && (
                    <p className="mt-2 text-sm text-destructive">{customError}</p>
                )}
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                    {picked.length === 0
                        ? "Any time of day works. Pick windows if the kitchen, the floor or the light only allow some."
                        : "Slots can only be created inside these windows, so a manager can't book a shoot over your busiest hour."}
                </p>
            </div>
        </div>
    );
}
