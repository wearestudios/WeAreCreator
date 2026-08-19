// Every booked shoot, a month at a time.
//
// The campaign lists already say who is booked on *this* brief; nothing said
// what next Tuesday looks like across all of them, which is the question
// somebody asks before agreeing to a date.
//
// **The agenda is the view, and the grid is the extra.** A month grid on a
// 390px screen gives each day a box about a centimetre square, which can hold
// a number and nothing else — so on a phone this is a list of days with the
// shoots under them, and the grid appears at md: where there is room for it.
// That is the opposite of the usual "hide the sidebar" responsive move: the
// small screen gets the more useful thing, not the leftovers.
//
// The component never asks what role is looking. One endpoint scopes itself —
// a brand sees its own campaigns, a WeAre manager the ones assigned to them,
// an admin everything — and all three get the same shape, carrying no contact
// detail for anybody.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, ChevronLeft, ChevronRight, MapPin } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { ListEmptyState } from "@/components/data/DenseView";
import { CALENDAR as IDS } from "@/constants/testIds";
import { STATE_META } from "@/components/admin/shared";

const ALL = "__all__";
const WEEKDAY_HEADS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** yyyy-mm-dd in local time. `toISOString` would bucket an evening shoot into
 *  the next day for everybody in IST, which is the bug this whole product
 *  keeps having to answer. */
const dayKey = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
        d.getDate(),
    ).padStart(2, "0")}`;

const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
const endOfMonth = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59);

/** The six-week block a month grid draws, Monday-first. */
function gridDays(month) {
    const first = startOfMonth(month);
    const offset = (first.getDay() + 6) % 7; // JS Sunday-0 → Monday-0
    const start = new Date(first.getFullYear(), first.getMonth(), 1 - offset);
    return Array.from({ length: 42 }, (_, i) =>
        new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
    );
}

const timeOf = (iso) => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
};

const longDay = (d) =>
    d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

function EntryRow({ entry }) {
    const meta = STATE_META[entry.state] || {};
    return (
        <li data-testid={IDS.entry(entry.id)}>
            <Link
                to={entry.href}
                className="flex items-start gap-3 rounded-md border border-white/10 bg-card/60 p-4 transition-colors duration-200 hover:border-ember-500/40"
            >
                <span className="w-16 flex-none font-serif text-sm leading-tight text-ember-500">
                    {timeOf(entry.starts_at)}
                </span>
                <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{entry.creator_name}</span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">
                        {entry.campaign_title}
                        {entry.brand_name ? ` · ${entry.brand_name}` : ""}
                    </span>
                    {entry.area && (
                        <span className="mt-1.5 inline-flex items-center gap-1 text-xs text-muted-foreground/80">
                            <MapPin className="h-3 w-3" />
                            {entry.area}
                        </span>
                    )}
                </span>
                {meta.label && (
                    <span
                        className={
                            "flex-none rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] " +
                            (meta.tone || "border-white/15 text-muted-foreground")
                        }
                    >
                        {meta.label}
                    </span>
                )}
            </Link>
        </li>
    );
}

export default function ShootCalendar() {
    const { user } = useAuth();
    const [month, setMonth] = useState(() => startOfMonth(new Date()));
    const [campaign, setCampaign] = useState(ALL);
    const [data, setData] = useState(null);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        setData(null);
        setError("");
        try {
            const { data: res } = await api.get("/calendar", {
                params: {
                    start: startOfMonth(month).toISOString(),
                    end: endOfMonth(month).toISOString(),
                    ...(campaign !== ALL ? { campaign } : {}),
                },
            });
            setData(res);
        } catch (e) {
            setError(formatApiError(e));
        }
    }, [month, campaign]);

    useEffect(() => {
        load();
    }, [load]);

    // One pass, keyed on the local day — every view below reads this rather
    // than filtering the list again per cell.
    const byDay = useMemo(() => {
        const map = new Map();
        for (const e of data?.entries || []) {
            const d = new Date(e.starts_at);
            if (Number.isNaN(d.getTime())) continue;
            const key = dayKey(d);
            if (!map.has(key)) map.set(key, []);
            map.get(key).push(e);
        }
        return map;
    }, [data]);

    const agendaDays = useMemo(
        () => [...byDay.keys()].sort(),
        [byDay],
    );

    const todayKey = dayKey(new Date());
    const monthLabel = month.toLocaleDateString("en-IN", {
        month: "long",
        year: "numeric",
    });

    if (!user) return null;

    return (
        <div
            data-testid={IDS.page}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <Navbar />
            <main className="mx-auto max-w-6xl px-6 py-12 md:py-16">
                <header className="flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            Calendar
                        </p>
                        <h1 className="mt-3 font-serif text-fluid-4xl leading-none tracking-tight">
                            Every shoot on the books.
                        </h1>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            aria-label="Previous month"
                            data-testid={IDS.prev}
                            onClick={() =>
                                setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))
                            }
                            className="grid h-11 w-11 place-items-center rounded-full border border-white/15 text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </button>
                        <span
                            data-testid={IDS.monthLabel}
                            className="min-w-[9rem] text-center font-serif text-lg"
                        >
                            {monthLabel}
                        </span>
                        <button
                            type="button"
                            aria-label="Next month"
                            data-testid={IDS.next}
                            onClick={() =>
                                setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))
                            }
                            className="grid h-11 w-11 place-items-center rounded-full border border-white/15 text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                        >
                            <ChevronRight className="h-4 w-4" />
                        </button>
                        <Button
                            type="button"
                            variant="outline"
                            data-testid={IDS.today}
                            onClick={() => setMonth(startOfMonth(new Date()))}
                            className="h-11 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                        >
                            Today
                        </Button>
                    </div>
                </header>

                {(data?.campaigns || []).length > 1 && (
                    <div className="mt-8 max-w-sm">
                        <Select value={campaign} onValueChange={setCampaign}>
                            <SelectTrigger
                                data-testid={IDS.campaignFilter}
                                className="h-11 border-white/10 bg-card/60 focus:ring-ember-500"
                            >
                                <SelectValue placeholder="All campaigns" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={ALL}>All campaigns</SelectItem>
                                {data.campaigns.map((c) => (
                                    <SelectItem key={c.id} value={c.id}>
                                        {c.title}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}

                {error && (
                    <p data-testid={IDS.error} className="mt-8 text-sm text-destructive">
                        {error}
                    </p>
                )}

                {!data && !error && (
                    <div data-testid={IDS.skeleton} aria-hidden="true" className="mt-10 space-y-3">
                        {Array.from({ length: 5 }).map((_, i) => (
                            <Skeleton key={i} className="h-20 w-full rounded-md" />
                        ))}
                    </div>
                )}

                {data && (
                    <>
                        {/* The grid: desktop only, because a month of
                            centimetre-square cells on a phone can hold a
                            number and nothing else. */}
                        <div
                            data-testid={IDS.grid}
                            className="mt-10 hidden md:block"
                        >
                            <div className="grid grid-cols-7 gap-px rounded-md border border-white/10 bg-white/10 overflow-hidden">
                                {WEEKDAY_HEADS.map((d) => (
                                    <div
                                        key={d}
                                        className="bg-background px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground"
                                    >
                                        {d}
                                    </div>
                                ))}
                                {gridDays(month).map((d) => {
                                    const key = dayKey(d);
                                    const rows = byDay.get(key) || [];
                                    const otherMonth = d.getMonth() !== month.getMonth();
                                    return (
                                        <div
                                            key={key}
                                            data-testid={IDS.day(key)}
                                            className={
                                                "min-h-[7rem] bg-card/60 p-2 " +
                                                (otherMonth ? "opacity-40" : "") +
                                                (key === todayKey
                                                    ? " ring-1 ring-inset ring-ember-500/50"
                                                    : "")
                                            }
                                        >
                                            <div className="flex items-baseline justify-between">
                                                <span className="text-xs text-muted-foreground">
                                                    {d.getDate()}
                                                </span>
                                                {rows.length > 0 && (
                                                    <span
                                                        data-testid={IDS.dayCount(key)}
                                                        className="rounded-full bg-ember-500/15 px-1.5 text-[10px] text-ember-500"
                                                    >
                                                        {rows.length}
                                                    </span>
                                                )}
                                            </div>
                                            <ul className="mt-1.5 space-y-1">
                                                {rows.slice(0, 3).map((e) => (
                                                    <li key={e.id}>
                                                        <Link
                                                            to={e.href}
                                                            className="block truncate rounded-sm bg-white/5 px-1.5 py-1 text-[11px] leading-tight transition-colors duration-200 hover:bg-ember-500/15 hover:text-ember-500"
                                                        >
                                                            {timeOf(e.starts_at)}{" "}
                                                            {e.creator_name}
                                                        </Link>
                                                    </li>
                                                ))}
                                                {rows.length > 3 && (
                                                    <li className="px-1.5 text-[11px] text-muted-foreground">
                                                        +{rows.length - 3} more
                                                    </li>
                                                )}
                                            </ul>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* The agenda: the whole view on a phone, and a
                            readable index under the grid on a laptop. */}
                        <div data-testid={IDS.agenda} className="mt-10 space-y-8">
                            {agendaDays.length === 0 ? (
                                <ListEmptyState
                                    testid={IDS.empty}
                                    Icon={CalendarDays}
                                    filtered={campaign !== ALL}
                                    onClearFilters={() => setCampaign(ALL)}
                                    filteredTitle="Nothing booked on that campaign this month."
                                    filteredBody="Try another month, or clear the filter."
                                    clearLabel="All campaigns"
                                    emptyTitle="Nothing booked this month."
                                    emptyBody="Slots show up here the moment a creator books one."
                                />
                            ) : (
                                agendaDays.map((key) => (
                                    <section key={key} data-testid={IDS.agendaDay(key)}>
                                        <p
                                            className={
                                                "text-xs uppercase tracking-[0.2em] " +
                                                (key === todayKey
                                                    ? "text-ember-500"
                                                    : "text-muted-foreground")
                                            }
                                        >
                                            {key === todayKey ? "Today · " : ""}
                                            {longDay(new Date(`${key}T00:00:00`))}
                                        </p>
                                        <ul className="mt-4 space-y-2">
                                            {byDay.get(key).map((e) => (
                                                <EntryRow key={e.id} entry={e} />
                                            ))}
                                        </ul>
                                    </section>
                                ))
                            )}
                        </div>
                    </>
                )}
            </main>
        </div>
    );
}
