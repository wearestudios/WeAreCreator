// What a campaign manager sees when they open the app: the campaigns they are
// running, and nothing else. Sorted with the soonest first, because the one
// happening today is the only one they care about while standing in a venue.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { CalendarClock, ChevronRight, MapPin, Users } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";
import { MANAGER_HOME as IDS } from "@/constants/testIds";
import {
    CAMPAIGN_TYPE_META,
    CardListSkeleton,
    EmptyState,
    ManagerHeader,
    Pill,
    whenText,
} from "@/components/manager/shared";

// A campaign that has been and gone is not what you opened the app for.
const sortForToday = (rows) =>
    [...rows].sort((a, b) => {
        const when = (c) => c.event_date || c.start_date || c.created_at || "";
        return String(when(a)).localeCompare(String(when(b)));
    });

export default function ManagerHome() {
    const [rows, setRows] = useState(null);

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get("/manager/campaigns");
            setRows(sortForToday(data));
        } catch (e) {
            toast.error(formatApiError(e));
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background">
            <Navbar />
            <main className="mx-auto max-w-3xl px-5 py-10 md:px-6 md:py-14">
                <ManagerHeader
                    kicker="Campaign manager"
                    title="Your campaigns"
                    sub="Everything you're running. Tap one to see the roster and check people in."
                    onRefresh={load}
                    refreshTestId={IDS.refresh}
                />

                <div className="mt-8">
                    {!rows ? (
                        <CardListSkeleton cards={3} testid={IDS.skeleton} />
                    ) : rows.length === 0 ? (
                        <EmptyState testid={IDS.empty} Icon={CalendarClock}>
                            Nothing assigned to you yet. The WeAre team assigns campaigns —
                            they'll show up here as soon as one is yours.
                        </EmptyState>
                    ) : (
                        <ul data-testid={IDS.list} className="space-y-4">
                            {rows.map((c) => (
                                <li key={c.id}>
                                    <Link
                                        to={`/manager/campaigns/${c.id}`}
                                        data-testid={IDS.card(c.id)}
                                        className="flex items-center gap-4 rounded-md border border-white/10 bg-card p-6 transition-colors duration-200 hover:border-ember-500/40"
                                    >
                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <Pill
                                                    meta={CAMPAIGN_TYPE_META}
                                                    value={c.campaign_type}
                                                    testid={IDS.cardType(c.id)}
                                                />
                                                <span
                                                    data-testid={IDS.cardWhen(c.id)}
                                                    className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground"
                                                >
                                                    {whenText(c)}
                                                </span>
                                            </div>

                                            <p className="mt-3 truncate font-serif text-xl leading-tight">
                                                {c.title}
                                            </p>
                                            <p className="mt-1 truncate text-xs text-muted-foreground">
                                                {c.brand_name || "Unknown brand"}
                                                {c.area ? ` · ${c.area}` : ""}
                                            </p>

                                            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
                                                <span
                                                    data-testid={IDS.cardSlots(c.id)}
                                                    className="inline-flex items-center gap-1.5"
                                                >
                                                    <CalendarClock className="h-3.5 w-3.5" />
                                                    {c.slot_count === 0
                                                        ? "No slots yet"
                                                        : `${c.slot_booked}/${c.slot_capacity} places taken`}
                                                </span>
                                                <span
                                                    data-testid={IDS.cardCreators(c.id)}
                                                    className="inline-flex items-center gap-1.5"
                                                >
                                                    <Users className="h-3.5 w-3.5" />
                                                    {c.filled_slots} of {c.creators_needed} confirmed
                                                </span>
                                                {c.venue_address && (
                                                    <span className="inline-flex min-w-0 items-center gap-1.5">
                                                        <MapPin className="h-3.5 w-3.5 flex-none" />
                                                        <span className="truncate">
                                                            {c.venue_address}
                                                        </span>
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <ChevronRight className="h-5 w-5 flex-none text-muted-foreground" />
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </main>
        </div>
    );
}
