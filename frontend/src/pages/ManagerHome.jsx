// What a campaign manager sees when they open the app.
//
// The shape of this page is one observation: a manager opens it either the
// night before a shoot or while standing in the venue on the day, and those two
// moments want opposite things. So the day's work comes first and at full size,
// with a straight route into day-of mode; everything else is smaller, below it,
// and the campaigns that have already happened are folded away entirely.
//
// Sorting alone was not enough. A soonest-first list puts today's campaign at
// the top and makes it look exactly like the one in three weeks — the manager
// has to read a date to find out which is which, standing up, one-handed.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
    AlertTriangle,
    CalendarClock,
    ChevronDown,
    ChevronRight,
    ClipboardCheck,
    MapPin,
    Phone,
    Users,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";
import { MANAGER_HOME as IDS } from "@/constants/testIds";
import QueueBanner from "@/components/manager/QueueBanner";
import { SafeSection } from "@/components/ErrorBoundary";
import {
    CAMPAIGN_TYPE_META,
    CardListSkeleton,
    EmptyState,
    ManagerHeader,
    Pill,
    SEVERITY_TONE,
    TOUCH,
    attentionFor,
    daysUntil,
    isToday,
    whenText,
} from "@/components/manager/shared";
import { startOfDay } from "@/lib/time";

const byWhen = (a, b) => {
    const when = (c) => c.event_date || c.start_date || c.created_at || "";
    return String(when(a)).localeCompare(String(when(b)));
};

/**
 * Three buckets, in the order a manager cares about them.
 *
 * "Past" is anything whose window closed before today. It is kept rather than
 * dropped — a manager still needs to get back into last week's campaign to
 * finish recording performance — but it is folded shut, because it is never
 * what they opened the app for.
 */
function bucket(rows, now = new Date()) {
    const today = [];
    const upcoming = [];
    const past = [];
    for (const c of rows) {
        if (isToday(c, now)) today.push(c);
        else {
            const d = daysUntil(c, now);
            // No date at all counts as upcoming: a draft brief with no day yet
            // is still work coming, and hiding it in "past" would lose it.
            // IST midnight, and not `now.setHours(0,0,0,0)`, which was wrong
            // twice over: it is midnight wherever the laptop is rather than in
            // Bengaluru, and it *mutates* `now` — so every campaign after the
            // first one with an end date had its "is it today" and "how many
            // days" answered against midnight instead of the current moment.
            const ended = c.end_date
                ? new Date(c.end_date).getTime() < startOfDay(now).getTime()
                : d !== null && d < 0;
            (ended ? past : upcoming).push(c);
        }
    }
    return {
        today: today.sort(byWhen),
        upcoming: upcoming.sort(byWhen),
        past: past.sort(byWhen).reverse(),
    };
}

/** One line of "this needs looking at", coloured by how much. */
function AttentionRow({ campaign, item }) {
    return (
        <li
            data-testid={IDS.attentionItem(campaign.id, item.key)}
            className={"rounded-md border px-4 py-3 text-sm " + SEVERITY_TONE[item.severity]}
        >
            <span className="block truncate text-[10px] uppercase tracking-[0.18em] opacity-80">
                {campaign.title}
            </span>
            <span className="mt-1 block leading-snug">{item.text}</span>
        </li>
    );
}

/**
 * A campaign card.
 *
 * `prominent` is today's treatment: ember hairline, bigger title, and the two
 * things a manager does on the day as full-width targets rather than a chevron
 * to hunt for. The compact version is the same information at reading size.
 */
function CampaignCard({ campaign: c, prominent }) {
    const attention = attentionFor(c);
    const worst = attention.some((a) => a.severity === "urgent") ? "urgent" : attention[0]?.severity;

    return (
        <div
            data-testid={IDS.card(c.id)}
            data-today={prominent ? "true" : "false"}
            className={
                "overflow-hidden rounded-md border grain-surface " +
                (prominent
                    ? "border-ember-500/40 bg-card"
                    : "border-white/10 bg-card")
            }
        >
            <Link
                to={`/manager/campaigns/${c.id}`}
                data-testid={IDS.cardOpen(c.id)}
                className={
                    "flex items-center gap-4 transition-colors duration-200 hover:bg-white/[0.03] " +
                    (prominent ? "p-5 md:p-6" : "p-5")
                }
            >
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        {prominent && (
                            <span
                                data-testid={IDS.cardToday(c.id)}
                                className="inline-flex items-center gap-1.5 rounded-full bg-ember-500 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-black"
                            >
                                Today
                            </span>
                        )}
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

                    <p
                        className={
                            "mt-3 truncate font-serif leading-tight " +
                            (prominent ? "text-fluid-2xl" : "text-xl")
                        }
                    >
                        {c.title}
                    </p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                        {c.brand_name || "Unknown brand"}
                        {c.area ? ` · ${c.area}` : ""}
                    </p>

                    <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
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
                                <span className="truncate">{c.venue_address}</span>
                            </span>
                        )}
                    </div>

                    {attention.length > 0 && (
                        <p
                            data-testid={IDS.cardAttention(c.id)}
                            className={
                                "mt-4 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.15em] " +
                                SEVERITY_TONE[worst]
                            }
                        >
                            <AlertTriangle className="h-3 w-3" />
                            {attention.length === 1
                                ? attention[0].text
                                : `${attention.length} things to look at`}
                        </p>
                    )}
                </div>
                <ChevronRight className="h-5 w-5 flex-none text-muted-foreground" />
            </Link>

            {/* On the day, the two things you actually do. Full-width and
                bottom-anchored within the card so both are in thumb reach on a
                phone, and separated so a mis-tap on "call" does not land on
                "check people in". */}
            {prominent && (
                <div className="flex flex-col gap-2 border-t border-white/10 p-3 sm:flex-row">
                    <Link
                        to={`/manager/campaigns/${c.id}?mode=day-of`}
                        data-testid={IDS.cardDayOf(c.id)}
                        className={`inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-ember-500 text-sm font-medium text-black transition-colors duration-200 hover:bg-ember-400 ${TOUCH}`}
                    >
                        <ClipboardCheck className="h-5 w-5" />
                        Check people in
                    </Link>
                    {c.on_site_contact && (
                        <a
                            href={`tel:${String(c.on_site_contact).replace(/[^\d+]/g, "")}`}
                            data-testid={IDS.cardCall(c.id)}
                            aria-label={`Call the venue contact for ${c.title}`}
                            className={`inline-flex items-center justify-center gap-2 rounded-md border border-white/15 px-5 text-sm text-muted-foreground transition-colors duration-200 hover:text-ember-500 sm:flex-none ${TOUCH}`}
                        >
                            <Phone className="h-5 w-5" />
                            <span className="sm:hidden">Call the venue</span>
                        </a>
                    )}
                </div>
            )}
        </div>
    );
}

export default function ManagerHome() {
    const [rows, setRows] = useState(null);
    const [error, setError] = useState("");
    const [showPast, setShowPast] = useState(false);

    const load = useCallback(async () => {
        setRows(null);
        setError("");
        try {
            const { data } = await api.get("/manager/campaigns");
            setRows(Array.isArray(data) ? data : []);
        } catch (e) {
            // Named on the page rather than only in a toast: a toast is gone by
            // the time somebody looks up from the room they are standing in.
            setError(formatApiError(e));
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const groups = useMemo(() => bucket(rows || []), [rows]);

    // Attention is drawn from today and the next two days only, and flattened
    // across campaigns — the question is "what needs me", not "what is wrong
    // with campaign four".
    const attention = useMemo(
        () =>
            [...groups.today, ...groups.upcoming].flatMap((c) =>
                attentionFor(c).map((item) => ({ campaign: c, item })),
            ),
        [groups],
    );

    const loading = rows === null;

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background grain-page">
            <Navbar />
            <main className="mx-auto max-w-3xl px-5 py-10 md:px-6 md:py-14">
                <ManagerHeader
                    kicker="Campaign manager"
                    title="Your campaigns"
                    sub="Today's work first. Tap one to see the roster and check people in."
                    onRefresh={load}
                    refreshTestId={IDS.refresh}
                />

                <div className="mt-6">
                    <QueueBanner />
                </div>

                {/* The calendar is the same work seen by date, and it is the
                    view somebody wants before agreeing to a Tuesday. It was in
                    the navbar and nowhere on the page the manager actually
                    lives on, which on a phone means behind the menu sheet. */}
                <Link
                    to="/calendar"
                    data-testid={IDS.calendar}
                    className={`mt-4 flex items-center justify-center gap-2 rounded-md border border-white/10 text-sm text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 ${TOUCH}`}
                >
                    <CalendarClock className="h-4 w-4" />
                    Everything by date
                </Link>

                {error && (
                    <p
                        data-testid={IDS.error}
                        className="mt-6 rounded-md border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-200"
                    >
                        {error}
                    </p>
                )}

                {loading ? (
                    <div className="mt-8">
                        <CardListSkeleton cards={3} testid={IDS.skeleton} />
                    </div>
                ) : rows.length === 0 ? (
                    <div className="mt-8">
                        <EmptyState testid={IDS.empty} Icon={CalendarClock}>
                            Nothing assigned to you yet. The WeAre team assigns
                            campaigns — they'll show up here as soon as one is
                            yours.
                        </EmptyState>
                    </div>
                ) : (
                    <>
                        {/* What needs you, before what you have. */}
                        {attention.length > 0 && (
                            <SafeSection name="manager-attention" className="mt-8">
                                <p className="text-xs uppercase tracking-[0.2em] text-amber-200">
                                    Needs a look
                                </p>
                                <ul
                                    data-testid={IDS.attention}
                                    className="mt-3 space-y-2"
                                >
                                    {attention.map(({ campaign, item }) => (
                                        <AttentionRow
                                            key={`${campaign.id}-${item.key}`}
                                            campaign={campaign}
                                            item={item}
                                        />
                                    ))}
                                </ul>
                            </SafeSection>
                        )}

                        <SafeSection name="manager-today" className="mt-10">
                            <div className="flex items-baseline justify-between gap-3">
                                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                    Today
                                </p>
                                <span
                                    data-testid={IDS.todayCount}
                                    className="text-xs text-muted-foreground"
                                >
                                    {groups.today.length === 0
                                        ? "nothing on"
                                        : `${groups.today.length} ${groups.today.length === 1 ? "campaign" : "campaigns"}`}
                                </span>
                            </div>
                            {groups.today.length === 0 ? (
                                // Said rather than left blank: "nothing today"
                                // is information, and an absent section reads
                                // as a page that failed to load its top half.
                                <p
                                    data-testid={IDS.todayEmpty}
                                    className="mt-3 rounded-md border border-white/10 bg-card/40 px-5 py-6 text-sm text-muted-foreground"
                                >
                                    Nothing on today. The next one is below.
                                </p>
                            ) : (
                                <ul
                                    data-testid={IDS.todaySection}
                                    className="mt-3 space-y-4"
                                >
                                    {groups.today.map((c) => (
                                        <li key={c.id}>
                                            <CampaignCard campaign={c} prominent />
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </SafeSection>

                        <SafeSection name="manager-upcoming" className="mt-10">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Coming up
                            </p>
                            {groups.upcoming.length === 0 ? (
                                <p
                                    data-testid={IDS.upcomingEmpty}
                                    className="mt-3 rounded-md border border-white/10 bg-card/40 px-5 py-6 text-sm text-muted-foreground"
                                >
                                    Nothing else scheduled yet.
                                </p>
                            ) : (
                                <ul
                                    data-testid={IDS.upcomingSection}
                                    className="mt-3 space-y-3"
                                >
                                    {groups.upcoming.map((c) => (
                                        <li key={c.id}>
                                            <CampaignCard campaign={c} />
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </SafeSection>

                        {/* Folded, not dropped: performance still gets recorded
                            against a campaign days after it happened. */}
                        {groups.past.length > 0 && (
                            <SafeSection name="manager-past" className="mt-10">
                                <button
                                    type="button"
                                    aria-expanded={showPast}
                                    onClick={() => setShowPast((v) => !v)}
                                    data-testid={IDS.pastToggle}
                                    className={`flex w-full items-center justify-between rounded-md border border-white/10 px-5 text-left text-xs uppercase tracking-[0.2em] text-muted-foreground transition-colors duration-200 hover:text-foreground ${TOUCH}`}
                                >
                                    Been and gone · {groups.past.length}
                                    <ChevronDown
                                        className={
                                            "h-4 w-4 transition-transform duration-200 " +
                                            (showPast ? "rotate-180" : "")
                                        }
                                    />
                                </button>
                                {showPast && (
                                    <ul
                                        data-testid={IDS.pastSection}
                                        className="mt-3 space-y-3"
                                    >
                                        {groups.past.map((c) => (
                                            <li key={c.id}>
                                                <CampaignCard campaign={c} />
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </SafeSection>
                        )}
                    </>
                )}
            </main>
        </div>
    );
}
