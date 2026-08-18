// When a shoot may happen — the frontend half of the campaign's scheduling
// preferences.
//
// Mirrors `SHOOT_WINDOW_PRESETS`, `WEEKDAY_NAMES` and `SHOOT_TZ` in
// `backend/server.py`; a unit test fails if the two drift. Everything here is
// pure so the picker, the campaign page and the slot form all describe the
// same rule in the same words.
//
// **Weekday indexes match Python's `datetime.weekday()`: Monday is 0.** They
// deliberately do not match JavaScript's `Date.getDay()`, where Sunday is 0 —
// one convention has to win, and it is the one the stored data uses. `dayIndex`
// is the only place that conversion happens.

export const WEEKDAYS = [
    { value: 0, label: "Monday", short: "Mon" },
    { value: 1, label: "Tuesday", short: "Tue" },
    { value: 2, label: "Wednesday", short: "Wed" },
    { value: 3, label: "Thursday", short: "Thu" },
    { value: 4, label: "Friday", short: "Fri" },
    { value: 5, label: "Saturday", short: "Sat" },
    { value: 6, label: "Sunday", short: "Sun" },
];

export const SHOOT_WINDOW_PRESETS = [
    { key: "breakfast", label: "Breakfast", start: "07:00", end: "11:00" },
    { key: "lunch", label: "Lunch", start: "12:00", end: "15:00" },
    { key: "afternoon", label: "Afternoon", start: "15:00", end: "18:00" },
    { key: "evening", label: "Evening", start: "18:00", end: "21:00" },
    { key: "late", label: "Late night", start: "21:00", end: "23:30" },
];

export const WINDOW_LABELS = {
    ...Object.fromEntries(SHOOT_WINDOW_PRESETS.map((p) => [p.key, p.label])),
    custom: "Custom",
};

export const MAX_SHOOT_WINDOWS = 6;

// Bengaluru. The server compares weekdays and hours in IST because a 19:00
// sitting is the next day in UTC; the browser has to agree or the picker
// greys out a different set of times than the API refuses.
const IST_OFFSET_MINUTES = 5 * 60 + 30;

/** A Date's weekday in the server's convention (Monday 0), read in IST. */
export function dayIndex(date) {
    const d = date instanceof Date ? date : new Date(date);
    if (Number.isNaN(d.getTime())) return null;
    const ist = new Date(d.getTime() + (IST_OFFSET_MINUTES + d.getTimezoneOffset()) * 60000);
    return (ist.getDay() + 6) % 7; // JS Sunday-0 → Python Monday-0
}

/** Minutes past IST midnight. */
export function minutesOfDay(date) {
    const d = date instanceof Date ? date : new Date(date);
    if (Number.isNaN(d.getTime())) return null;
    const ist = new Date(d.getTime() + (IST_OFFSET_MINUTES + d.getTimezoneOffset()) * 60000);
    return ist.getHours() * 60 + ist.getMinutes();
}

export function parseHHMM(value) {
    if (typeof value !== "string") return null;
    const [h, m] = value.split(":");
    const hours = Number(h);
    const minutes = Number(m);
    if (!Number.isInteger(hours) || !Number.isInteger(minutes)) return null;
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;
    return hours * 60 + minutes;
}

/** "18:00" → "6:00 pm", because a brief is read by a person. */
export function readableTime(hhmm) {
    const total = parseHHMM(hhmm);
    if (total === null) return hhmm || "";
    const hours = Math.floor(total / 60);
    const minutes = total % 60;
    const suffix = hours < 12 ? "am" : "pm";
    const twelve = hours % 12 === 0 ? 12 : hours % 12;
    return `${twelve}:${String(minutes).padStart(2, "0")} ${suffix}`;
}

export function windowLabel(w) {
    if (!w) return "";
    const hours = `${readableTime(w.start)}–${readableTime(w.end)}`;
    // A custom window has no name worth printing: "Custom 6:30–8:30" tells a
    // creator nothing that "6:30–8:30" doesn't. Presets keep theirs, because
    // "Lunch" is the thing a venue actually says.
    if (w.key === "custom") return hours;
    return `${WINDOW_LABELS[w.key] || w.key} ${hours}`;
}

/**
 * The days this campaign is open, as labels. Says what a creator can do
 * rather than what they can't — "Saturdays and Sundays" is the answer to the
 * question they actually have.
 */
export function openDayLabels(restrictedDays) {
    const shut = new Set((restrictedDays || []).map(Number));
    return WEEKDAYS.filter((d) => !shut.has(d.value)).map((d) => d.label);
}

export function hasSchedulingPreferences(campaign) {
    return (
        ((campaign || {}).restricted_days || []).length > 0 ||
        ((campaign || {}).shoot_windows || []).length > 0
    );
}

/**
 * Why this moment isn't allowed on this campaign, or null.
 *
 * The mirror of `_shoot_time_refusal`. The server decides — this exists so a
 * picker can disable a time rather than offer it and then refuse it, which is
 * the difference between a rule and a trap.
 */
export function shootTimeRefusal(campaign, when) {
    if (!when) return null;
    const day = dayIndex(when);
    if (day === null) return null;

    const shut = new Set(((campaign || {}).restricted_days || []).map(Number));
    if (shut.has(day)) {
        const open = openDayLabels(campaign?.restricted_days);
        return (
            `${WEEKDAYS[day].label}s don't work for this venue.` +
            (open.length ? ` Open: ${open.join(", ")}.` : "")
        );
    }

    const windows = (campaign || {}).shoot_windows || [];
    if (windows.length === 0) return null;

    const minutes = minutesOfDay(when);
    for (const w of windows) {
        const start = parseHHMM(w.start);
        const end = parseHHMM(w.end);
        if (start === null || end === null) continue;
        if (minutes >= start && minutes <= end) return null;
    }
    return `This campaign shoots in set windows: ${windows.map(windowLabel).join(", ")}.`;
}
