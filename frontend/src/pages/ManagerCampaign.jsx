// One campaign, as the manager running it needs it.
//
// Three tabs and a mode. Roster and slots are the planning views; day-of mode
// takes over the screen when people are actually arriving, because the job
// changes shape at that point — you stop reading and start tapping.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    ArrowLeft,
    CalendarClock,
    ChevronLeft,
    Download,
    MapPin,
    Pencil,
    Phone,
    Plus,
    Send,
    Trash2,
    Users,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
    MANAGER_CAMPAIGN as IDS,
    MANAGER_ROSTER as ROSTER_IDS,
    MANAGER_SLOTS as SLOT_IDS,
    MANAGER_VENUE as VENUE_IDS,
} from "@/constants/testIds";
import BroadcastSheet from "@/components/manager/BroadcastSheet";
import DayOfMode from "@/components/manager/DayOfMode";
import SlotEditor from "@/components/manager/SlotEditor";
import {
    ATTENDANCE_META,
    CAMPAIGN_TYPE_META,
    CardListSkeleton,
    EmptyState,
    ManagerHeader,
    Pill,
    RowListSkeleton,
    TOUCH,
    formatDay,
    formatTime,
    whenText,
} from "@/components/manager/shared";

const TABS = [
    { key: "roster", label: "Roster" },
    { key: "slots", label: "Slots" },
    { key: "venue", label: "Venue" },
];

export default function ManagerCampaign() {
    const { id } = useParams();
    // `?mode=day-of` is how the Today card on the home page arrives here: on
    // the day, the roster is not what you opened this for. Read once as the
    // initial state rather than kept in sync, so toggling out of day-of mode
    // does not fight the URL you came in on.
    const [params] = useSearchParams();
    const [roster, setRoster] = useState(null);
    const [slots, setSlots] = useState(null);
    const [tab, setTab] = useState("roster");
    const [dayOf, setDayOf] = useState(() => params.get("mode") === "day-of");
    const [slotEditor, setSlotEditor] = useState(null);
    const [broadcast, setBroadcast] = useState(false);
    const [broadcastReport, setBroadcastReport] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const [r, s] = await Promise.all([
                api.get(`/manager/campaigns/${id}/roster`),
                api.get(`/manager/campaigns/${id}/slots`),
            ]);
            setRoster(r.data);
            setSlots(s.data.slots);
        } catch (e) {
            notifyError(e);
            setRoster({ roster: [] });
            setSlots([]);
        }
    }, [id]);

    useEffect(() => {
        setRoster(null);
        setSlots(null);
        load();
    }, [load]);

    const expected = useMemo(
        () => (roster?.roster || []).filter((r) => r.attendance === "expected"),
        [roster],
    );

    const campaign = roster
        ? {
              campaign_type: roster.campaign_type,
              event_date: roster.event_date,
              start_date: roster.start_date,
              end_date: roster.end_date,
          }
        : null;

    const saveSlot = async (body) => {
        setBusy(true);
        try {
            if (slotEditor?.slot) {
                await api.patch(`/manager/slots/${slotEditor.slot.id}`, body);
                notifySuccess("Slot updated");
            } else {
                await api.post("/manager/slots", { campaign_id: id, ...body });
                notifySuccess("Slot added");
            }
            setSlotEditor(null);
            await load();
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    const deleteSlot = async (slot) => {
        setBusy(true);
        try {
            await api.delete(`/manager/slots/${slot.id}`);
            notifySuccess("Slot removed");
            await load();
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    const downloadDaysheet = async () => {
        setBusy(true);
        try {
            // Through the API client, so it carries the session and a failure
            // surfaces as a message rather than a downloaded error page.
            const { data } = await api.get(`/manager/campaigns/${id}/daysheet`, {
                responseType: "blob",
            });
            const url = URL.createObjectURL(data);
            const a = document.createElement("a");
            a.href = url;
            a.download = `daysheet-${(roster?.title || "campaign")
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-|-$/g, "")}.csv`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    const send = async (message) => {
        setBusy(true);
        try {
            const { data } = await api.post(`/manager/campaigns/${id}/broadcast`, { message });
            setBroadcastReport(data);
            await load();
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    const loading = !roster || !slots;

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background grain-page">
            <Navbar />
            <main className="mx-auto max-w-3xl px-5 py-8 md:px-6 md:py-12">
                <Link
                    to="/manager"
                    data-testid={IDS.back}
                    className="-my-2 min-h-[2.75rem] py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:my-0 md:min-h-0 md:py-0 inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    All campaigns
                </Link>

                {loading ? (
                    <div className="mt-6">
                        <CardListSkeleton cards={3} testid={IDS.skeleton} />
                    </div>
                ) : (
                    <>
                        <div className="mt-6">
                            <ManagerHeader
                                kicker={whenText({ ...campaign })}
                                title={roster.title}
                                onRefresh={load}
                                refreshTestId={IDS.refresh}
                            >
                                <div className="flex flex-wrap items-center gap-2">
                                    <Pill
                                        meta={CAMPAIGN_TYPE_META}
                                        value={roster.campaign_type}
                                    />
                                    <span
                                        data-testid={ROSTER_IDS.counts}
                                        className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground"
                                    >
                                        {roster.attended} in · {roster.expected} expected
                                        {roster.no_shows > 0 ? ` · ${roster.no_shows} no-show` : ""}
                                    </span>
                                </div>
                            </ManagerHeader>
                        </div>

                        {/* The mode switch sits above everything: on the day it
                            is the first and often only thing tapped. */}
                        <button
                            type="button"
                            onClick={() => setDayOf((v) => !v)}
                            aria-pressed={dayOf}
                            data-testid={IDS.dayOfToggle}
                            className={
                                "mt-7 flex w-full items-center justify-center gap-2 rounded-md border text-sm uppercase tracking-[0.15em] transition-colors duration-200 " +
                                TOUCH +
                                " " +
                                (dayOf
                                    ? "border-ember-500 bg-ember-500 text-black hover:bg-ember-400"
                                    : "border-ember-500/40 bg-ember-500/10 text-ember-500 hover:bg-ember-500/20")
                            }
                        >
                            {dayOf ? (
                                <>
                                    <ArrowLeft className="h-4 w-4" />
                                    Leave day-of mode
                                </>
                            ) : (
                                <>
                                    <Users className="h-4 w-4" />
                                    Start check-in
                                </>
                            )}
                        </button>

                        {dayOf ? (
                            <div className="mt-6">
                                <DayOfMode
                                    roster={roster.roster}
                                    slots={slots}
                                    loading={false}
                                    onChanged={load}
                                />
                            </div>
                        ) : (
                            <>
                                <nav className="mt-7 flex gap-2">
                                    {TABS.map((t) => {
                                        const on = tab === t.key;
                                        return (
                                            <button
                                                key={t.key}
                                                type="button"
                                                aria-pressed={on}
                                                onClick={() => setTab(t.key)}
                                                data-testid={IDS.tab(t.key)}
                                                className={
                                                    "min-h-[3rem] flex-1 rounded-md border px-3 py-3 text-xs uppercase tracking-[0.15em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
                                                    (on
                                                        ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                                        : "border-white/10 text-muted-foreground")
                                                }
                                            >
                                                {t.label}
                                            </button>
                                        );
                                    })}
                                </nav>

                                <div className="mt-6">
                                    {tab === "roster" && (
                                        <RosterList rows={roster.roster} />
                                    )}
                                    {tab === "slots" && (
                                        <SlotList
                                            slots={slots}
                                            busy={busy}
                                            onAdd={() => setSlotEditor({ slot: null })}
                                            onEdit={(slot) => setSlotEditor({ slot })}
                                            onDelete={deleteSlot}
                                        />
                                    )}
                                    {tab === "venue" && <VenuePanel campaign={roster} />}
                                </div>

                                <div className="mt-8 grid gap-3 sm:grid-cols-2">
                                    <Button
                                        type="button"
                                        onClick={() => {
                                            setBroadcastReport(null);
                                            setBroadcast(true);
                                        }}
                                        data-testid={IDS.broadcastOpen}
                                        className={`rounded-md bg-ember-500 text-black hover:bg-ember-400 ${TOUCH}`}
                                    >
                                        <Send className="mr-2 h-4 w-4" />
                                        Message everyone
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        disabled={busy}
                                        onClick={downloadDaysheet}
                                        data-testid={IDS.daysheet}
                                        className={`rounded-md border-white/15 bg-transparent hover:border-ember-500/40 hover:text-ember-500 ${TOUCH}`}
                                    >
                                        <Download className="mr-2 h-4 w-4" />
                                        Day sheet (CSV)
                                    </Button>
                                </div>
                            </>
                        )}
                    </>
                )}
            </main>

            <SlotEditor
                open={Boolean(slotEditor)}
                slot={slotEditor?.slot}
                campaign={campaign}
                busy={busy}
                onClose={() => setSlotEditor(null)}
                onSubmit={saveSlot}
            />

            <BroadcastSheet
                open={broadcast}
                busy={busy}
                report={broadcastReport}
                recipients={expected}
                onSend={send}
                onClose={() => {
                    setBroadcast(false);
                    setBroadcastReport(null);
                }}
            />
        </div>
    );
}

function RosterList({ rows }) {
    if (!rows) return <RowListSkeleton rows={5} testid={ROSTER_IDS.skeleton} />;
    if (rows.length === 0) {
        return (
            <EmptyState testid={ROSTER_IDS.empty} Icon={Users}>
                Nobody is confirmed on this campaign yet. Creators appear here once the
                brand takes them on.
            </EmptyState>
        );
    }
    return (
        <ul data-testid={ROSTER_IDS.list} className="space-y-3">
            {rows.map((r) => (
                <li
                    key={r.collaboration_id}
                    data-testid={ROSTER_IDS.row(r.collaboration_id)}
                    className="flex items-center gap-4 rounded-md border border-white/10 bg-card p-5 grain-surface"
                >
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                            <span
                                data-testid={ROSTER_IDS.rowTime(r.collaboration_id)}
                                className="font-serif text-lg leading-none"
                            >
                                {r.slot_time ? formatTime(r.slot_time) : "No slot"}
                            </span>
                            <Pill
                                meta={ATTENDANCE_META}
                                value={r.attendance}
                                testid={ROSTER_IDS.rowStatus(r.collaboration_id)}
                            />
                        </div>
                        <p
                            data-testid={ROSTER_IDS.rowName(r.collaboration_id)}
                            className="mt-1.5 truncate text-sm"
                        >
                            {r.name}
                        </p>
                        {r.instagram_handle && (
                            <p
                                data-testid={ROSTER_IDS.rowHandle(r.collaboration_id)}
                                className="truncate text-xs text-muted-foreground"
                            >
                                @{r.instagram_handle}
                            </p>
                        )}
                    </div>
                    {r.phone && (
                        <a
                            href={`tel:${r.phone.replace(/\s+/g, "")}`}
                            aria-label={`Call ${r.name}`}
                            data-testid={ROSTER_IDS.rowCall(r.collaboration_id)}
                            className={`grid w-14 flex-none place-items-center rounded-md border border-white/15 text-muted-foreground transition-colors duration-200 hover:text-ember-500 ${TOUCH}`}
                        >
                            <Phone className="h-5 w-5" />
                        </a>
                    )}
                </li>
            ))}
        </ul>
    );
}

function SlotList({ slots, busy, onAdd, onEdit, onDelete }) {
    if (!slots) return <RowListSkeleton rows={4} testid={SLOT_IDS.skeleton} />;
    return (
        <section data-testid={SLOT_IDS.section} className="space-y-3">
            {slots.length === 0 ? (
                <EmptyState testid={SLOT_IDS.empty} Icon={CalendarClock}>
                    No slots yet. Creators can't book until there's something to book
                    into.
                </EmptyState>
            ) : (
                <ul data-testid={SLOT_IDS.list} className="space-y-3">
                    {slots.map((s) => {
                        const full = s.spots_left === 0;
                        return (
                            <li
                                key={s.id}
                                data-testid={SLOT_IDS.row(s.id)}
                                className="flex items-center gap-3 rounded-md border border-white/10 bg-card p-5 grain-surface"
                            >
                                <div className="min-w-0 flex-1">
                                    <p className="font-serif text-lg leading-none">
                                        {formatTime(s.starts_at)}
                                        {s.ends_at ? ` – ${formatTime(s.ends_at)}` : ""}
                                    </p>
                                    <p className="mt-1.5 text-xs text-muted-foreground">
                                        {formatDay(s.starts_at)}
                                    </p>
                                    <p
                                        data-testid={SLOT_IDS.rowFill(s.id)}
                                        className={
                                            "mt-2 text-xs " +
                                            (full ? "text-ember-500" : "text-muted-foreground")
                                        }
                                    >
                                        {s.booked_count}/{s.capacity} taken
                                        {full ? " · full" : ` · ${s.spots_left} left`}
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => onEdit(s)}
                                    aria-label="Edit slot"
                                    data-testid={SLOT_IDS.rowEdit(s.id)}
                                    className={`grid w-14 flex-none place-items-center rounded-md border border-white/15 text-muted-foreground transition-colors duration-200 hover:text-ember-500 ${TOUCH}`}
                                >
                                    <Pencil className="h-4 w-4" />
                                </button>
                                {/* Deleting a booked slot is refused by the
                                    server; not offering it avoids the dead tap. */}
                                {s.booked_count === 0 && (
                                    <button
                                        type="button"
                                        disabled={busy}
                                        onClick={() => onDelete(s)}
                                        aria-label="Delete slot"
                                        data-testid={SLOT_IDS.rowDelete(s.id)}
                                        className={`grid w-14 flex-none place-items-center rounded-md border border-red-500/30 text-red-300 transition-colors duration-200 hover:bg-red-500/10 ${TOUCH}`}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                )}
                            </li>
                        );
                    })}
                </ul>
            )}

            <Button
                type="button"
                onClick={onAdd}
                data-testid={SLOT_IDS.add}
                className={`w-full rounded-md bg-ember-500 text-black hover:bg-ember-400 ${TOUCH}`}
            >
                <Plus className="mr-2 h-4 w-4" />
                Add a slot
            </Button>
        </section>
    );
}

function VenuePanel({ campaign }) {
    const has =
        campaign.venue_address || campaign.venue_instructions || campaign.on_site_contact;
    if (!has) {
        return (
            <EmptyState testid={VENUE_IDS.empty} Icon={MapPin}>
                No venue details on this campaign yet. The brand adds them to the brief —
                ask the WeAre team if you need them.
            </EmptyState>
        );
    }

    // The contact is often "Riya · +91987…", so the number is pulled out to
    // make it dialable rather than something to read aloud and re-type.
    const contactNumber = (campaign.on_site_contact || "").match(/\+?\d[\d\s-]{7,}/)?.[0];

    return (
        <section data-testid={VENUE_IDS.section} className="space-y-4">
            {campaign.venue_address && (
                <div className="rounded-md border border-white/10 bg-card p-5 grain-surface">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Address
                    </p>
                    <p data-testid={VENUE_IDS.address} className="mt-3 text-sm leading-relaxed">
                        {campaign.venue_address}
                    </p>
                    <a
                        href={`https://maps.google.com/?q=${encodeURIComponent(campaign.venue_address)}`}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={VENUE_IDS.map}
                        className={`mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md border border-white/15 text-sm transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 ${TOUCH}`}
                    >
                        <MapPin className="h-4 w-4" />
                        Open in maps
                    </a>
                </div>
            )}

            {campaign.venue_instructions && (
                <div className="rounded-md border border-white/10 bg-card p-5 grain-surface">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        On arrival
                    </p>
                    <p
                        data-testid={VENUE_IDS.instructions}
                        className="mt-3 text-sm leading-relaxed"
                    >
                        {campaign.venue_instructions}
                    </p>
                </div>
            )}

            {campaign.on_site_contact && (
                <div className="rounded-md border border-white/10 bg-card p-5 grain-surface">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        On-site contact
                    </p>
                    <p data-testid={VENUE_IDS.contact} className="mt-3 text-sm">
                        {campaign.on_site_contact}
                    </p>
                    {contactNumber && (
                        <a
                            href={`tel:${contactNumber.replace(/[\s-]/g, "")}`}
                            data-testid={VENUE_IDS.contactCall}
                            className={`mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md border border-white/15 text-sm transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 ${TOUCH}`}
                        >
                            <Phone className="h-4 w-4" />
                            Call them
                        </a>
                    )}
                </div>
            )}
        </section>
    );
}
