// Every time this product shows, in the time zone it operates in.
//
// **The portal is IST.** A campaign runs in Bengaluru, a slot is a real hour
// at a real venue, and "6h ago" is a claim about when something happened
// here — none of that is a fact about the reader's laptop clock. So every
// formatter below passes `timeZone: IST` rather than letting the browser
// decide, and a manager opening the daysheet from a hotel in Dubai reads the
// same times as the person standing at the door.
//
// **Storage stays UTC.** The database holds UTC, the API emits UTC with an
// offset, and the conversion happens exactly here, once, on the way to a
// screen. The backend's `_iso` is the other half of that bargain: BSON has no
// time zone, so a value read back from Mongo is naive, and `isoformat()` on a
// naive value emits no offset at all — `new Date()` then reads it as *local*,
// which was 5½ hours out for everybody here and is why the notification panel
// said "6h ago" about something twenty minutes old.
//
// `SHOOT_TZ` in `server.py` is the same zone for the same reason, on the
// server's side of the line: a 19:00 Bengaluru sitting is the next day in UTC,
// so weekday and hour rules have to be evaluated in IST too.

/** The one zone. Bengaluru-first is an operating fact, not a preference. */
export const IST = "Asia/Kolkata";

/** The locale that goes with it — Indian digit grouping and date order. */
export const LOCALE = "en-IN";

const parse = (value) => {
    if (!value) return null;
    const d = value instanceof Date ? value : new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
};

/** 20 Aug 2026 */
export function formatDate(value, opts = {}) {
    const d = parse(value);
    if (!d) return "—";
    return d.toLocaleDateString(LOCALE, {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: IST,
        ...opts,
    });
}

/** 20 Aug, 7:30 pm */
export function formatDateTime(value, opts = {}) {
    const d = parse(value);
    if (!d) return "—";
    return d.toLocaleString(LOCALE, {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: IST,
        ...opts,
    });
}

/** 7:30 pm */
export function formatTime(value, opts = {}) {
    const d = parse(value);
    if (!d) return "—";
    return d.toLocaleTimeString(LOCALE, {
        hour: "numeric",
        minute: "2-digit",
        timeZone: IST,
        ...opts,
    });
}

/** Thursday, 20 August — for a day heading. */
export function formatDayLong(value) {
    return formatDate(value, {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: undefined,
    });
}

/**
 * How long ago, in the shortest true form.
 *
 * Time zone does not enter into an elapsed duration — the instant is the
 * instant — but it is here because everything else that reads a timestamp is,
 * and because the bug this file exists for looked like a relative-time bug.
 * What actually matters: `new Date()` on a string with no offset is read as
 * local, so the arithmetic was right and its input was wrong.
 */
export function timeAgo(value) {
    const d = parse(value);
    if (!d) return "—";
    const mins = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000));
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours}h`;
    const days = Math.round(hours / 24);
    if (days < 14) return `${days}d`;
    if (days < 60) return `${Math.round(days / 7)}w`;
    return `${Math.round(days / 30)}mo`;
}

/**
 * The IST calendar day a timestamp falls on, as `YYYY-MM-DD`.
 *
 * **This is what "today" has to be bucketed on.** `toISOString().slice(0, 10)`
 * is the UTC day, which moves every evening shoot in India to the next date —
 * a 19:00 Friday sitting is Saturday in UTC. `en-CA` because it is the locale
 * that formats as ISO.
 */
export function dayKey(value) {
    const d = parse(value);
    if (!d) return "";
    return d.toLocaleDateString("en-CA", { timeZone: IST });
}

/** Today, in IST, as `YYYY-MM-DD`. */
export const todayKey = () => dayKey(new Date());

/** Whether a timestamp falls on today's IST date. */
export const isToday = (value) => Boolean(value) && dayKey(value) === todayKey();

/** Midnight IST at the start of the day a timestamp falls on, as a Date. */
export function startOfDay(value) {
    const key = dayKey(value);
    if (!key) return null;
    // Built from the IST date parts, then read back as an instant. The offset
    // is fixed (+05:30, no daylight saving), so writing it is exact.
    return new Date(`${key}T00:00:00+05:30`);
}

/**
 * The IST calendar date, as a plain local `Date` at midnight.
 *
 * For building a month grid: the cells are pure arithmetic on year/month/day,
 * so they have to start from the *IST* date rather than the browser's, or a
 * manager opening the calendar at 01:00 IST from another zone is shown last
 * month. The Date returned is local — it carries the IST calendar date, not
 * the IST instant — which is exactly what `getDate()` arithmetic wants.
 */
export function istCalendarDate(value = new Date()) {
    const key = dayKey(value);
    if (!key) return null;
    const [y, m, d] = key.split("-").map(Number);
    return new Date(y, m - 1, d);
}

/** The same key for a grid cell, which was built from local parts already. */
export const cellKey = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
        d.getDate(),
    ).padStart(2, "0")}`;

/** How many whole IST days from now — negative for the past. */
export function daysFromToday(value) {
    const start = startOfDay(value);
    if (!start) return null;
    const today = startOfDay(new Date());
    return Math.round((start.getTime() - today.getTime()) / 86400000);
}
