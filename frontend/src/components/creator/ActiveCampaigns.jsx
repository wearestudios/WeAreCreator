// Live collaborations — the part of this page that is actually work.
//
// One card per collaboration, carrying everything needed to turn up: where the
// creator is in the process, what they have to do next in words they'd use
// themselves, the manager's number as a link that dials, the venue, and the
// time. Nothing here is behind a tap, because half the time this is being read
// on a footpath outside the venue.
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    CalendarClock,
    FileVideo,
    Loader2,
    MapPin,
    Phone,
    Rocket,
    Send,
    Upload,
    Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { CREATOR_ACTIVE as IDS } from "@/constants/testIds";
import {
    EmptyState,
    LIFECYCLE,
    Money,
    SectionHead,
    formatDateTime,
    formatRupees,
    lifecycleFor,
    stageIndexFor,
} from "./shared";
import BrandAvatar from "@/components/BrandAvatar";
import CampaignCover from "@/components/CampaignCover";
import SlotPicker from "./SlotPicker";
import SubmitContentDialog from "./SubmitContentDialog";
import SubmitDraftDialog from "./SubmitDraftDialog";

// ---------------------------------------------------------------------------
// The tracker
// ---------------------------------------------------------------------------

const Tracker = ({ collabId, state, stages = LIFECYCLE }) => {
    const still = useReducedMotion();
    const current = stageIndexFor(state, stages);
    const filled = current < 0 ? 0 : current / (stages.length - 1);

    return (
        <div data-testid={IDS.tracker(collabId)} className="mt-6">
            {/* The rail is one element rather than six joined segments, so the
                fill can move as a single stroke when a stage completes. The
                markers sit on it at their true fraction — laying them out in
                the six label columns would put "Paid" five-sixths along a bar
                that a finished collaboration fills to the end. */}
            <div className="relative h-[2px] w-full rounded-full bg-white/10">
                <motion.div
                    className="absolute inset-y-0 left-0 w-full origin-left rounded-full bg-ember-500"
                    initial={still ? false : { scaleX: 0 }}
                    animate={{ scaleX: filled }}
                    transition={{ duration: still ? 0 : 0.7, ease: [0.22, 1, 0.36, 1] }}
                />
                {stages.map((stage, i) => (
                    <span
                        key={stage.key}
                        aria-hidden="true"
                        style={{ left: `${(i / (stages.length - 1)) * 100}%` }}
                        className={
                            "absolute top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full transition-colors duration-300 " +
                            (i <= current ? "bg-ember-500" : "bg-white/25")
                        }
                    />
                ))}
            </div>

            {/* First and last labels align to the ends of the rail; the rest
                centre in their column, which lands close enough to their
                marker to read as attached to it. */}
            {/* Six columns, or seven where a draft is reviewed. The count is a
                style rather than a class because Tailwind can only see the
                classes written literally in the source. */}
            <ol
                className="mt-3 grid gap-1"
                style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}
            >
                {stages.map((stage, i) => {
                    const done = i < current;
                    const here = i === current;
                    const align =
                        i === 0
                            ? "text-left"
                            : i === stages.length - 1
                            ? "text-right"
                            : "text-center";
                    return (
                        <li
                            key={stage.key}
                            data-testid={IDS.stage(collabId, stage.key)}
                            aria-current={here ? "step" : undefined}
                            className={
                                "min-w-0 text-[9px] leading-tight sm:text-[10px] " +
                                align +
                                " " +
                                (here
                                    ? "text-ember-500"
                                    : done
                                    ? "text-muted-foreground"
                                    : "text-muted-foreground/50")
                            }
                        >
                            {stage.label}
                        </li>
                    );
                })}
            </ol>
        </div>
    );
};

// ---------------------------------------------------------------------------
// The card
// ---------------------------------------------------------------------------

const ACTION_ICON = {
    book_slot: CalendarClock,
    submit_draft: FileVideo,
    resubmit_draft: FileVideo,
    submit_content: Upload,
    resubmit_content: Send,
    add_payout_details: Wallet,
};

const Detail = ({ Icon, children, testid }) => (
    <div data-testid={testid} className="flex items-start gap-2 text-sm text-muted-foreground">
        <Icon className="mt-0.5 h-4 w-4 flex-none text-ember-500/80" />
        <span className="min-w-0 leading-relaxed">{children}</span>
    </div>
);

const ActiveCard = ({ collab, onBook, onSubmit, onDraft, onRefresh }) => {
    const still = useReducedMotion();
    const [releasing, setReleasing] = useState(false);
    const next = collab.next_action || {};
    const Icon = ACTION_ICON[next.action];
    const amount = collab.agreed_amount ?? collab.quoted_rate;

    const cancelSlot = async () => {
        setReleasing(true);
        try {
            await api.post(`/creator/collaborations/${collab.id}/cancel-slot`, {});
            notifySuccess("Slot released — pick another when you're ready");
            onRefresh?.();
        } catch (e) {
            notifyError(e);
        } finally {
            setReleasing(false);
        }
    };

    const action = (() => {
        if (next.action === "book_slot") {
            return (
                <Button
                    data-testid={IDS.primary(collab.id)}
                    onClick={() => onBook(collab)}
                    className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400 sm:w-auto"
                >
                    <Icon className="mr-2 h-4 w-4" />
                    Pick your slot
                </Button>
            );
        }
        if (next.action === "submit_draft" || next.action === "resubmit_draft") {
            return (
                <Button
                    data-testid={IDS.primary(collab.id)}
                    onClick={() => onDraft(collab)}
                    className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400 sm:w-auto"
                >
                    <Icon className="mr-2 h-4 w-4" />
                    {next.action === "resubmit_draft" ? "Replace your draft" : "Send your draft"}
                </Button>
            );
        }
        if (next.action === "submit_content" || next.action === "resubmit_content") {
            return (
                <Button
                    data-testid={IDS.primary(collab.id)}
                    onClick={() => onSubmit(collab)}
                    className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400 sm:w-auto"
                >
                    <Icon className="mr-2 h-4 w-4" />
                    {next.action === "resubmit_content" ? "Update your links" : "Upload your content link"}
                </Button>
            );
        }
        if (next.action === "attend" && collab.venue?.address) {
            // Standing on a footpath, "where exactly" is the only question
            // left, and it is one the phone can answer better than we can.
            return (
                <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(collab.venue.address)}`}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={IDS.primary(collab.id)}
                >
                    <Button className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400 sm:w-auto">
                        <MapPin className="mr-2 h-4 w-4" />
                        Get directions
                    </Button>
                </a>
            );
        }
        if (next.action === "add_payout_details") {
            return (
                <Link to="/onboarding/creator" data-testid={IDS.primary(collab.id)}>
                    <Button className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400 sm:w-auto">
                        <Icon className="mr-2 h-4 w-4" />
                        Add payout details
                    </Button>
                </Link>
            );
        }
        return null;
    })();

    return (
        <motion.li
            data-testid={IDS.card(collab.id)}
            whileHover={still ? undefined : { y: -2 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden rounded-md border border-white/10 bg-card transition-colors duration-200 hover:border-white/20 grain-surface"
        >
            {/* A slim slice of the campaign's own cover, so a card of work
                reads as a place rather than a form. 16:5, not 16:9 — this is
                a work card and the tracker below it is the point. */}
            <CampaignCover
                campaign={{
                    id: collab.campaign_id,
                    cover_image_url: collab.cover_image_url,
                    brand_name: collab.brand_name,
                    title: collab.campaign_title,
                }}
                ratio="aspect-[16/5]"
                rounded="rounded-none"
                // aspect-ratio yields to max-height: on a phone the strip is
                // 16:5 of the card, on a desktop-width card it stops growing
                // at 11rem instead of becoming a 350px wall of tint.
                className="border-0 border-b md:max-h-44"
            />
            <div className="p-6 md:p-7">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                    <p className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        <BrandAvatar brand={collab} size="h-6 w-6" />
                        <span className="truncate">
                            {collab.brand_name || "Brand"}
                            {collab.area ? ` · ${collab.area}` : ""}
                        </span>
                    </p>
                    <Link
                        to={`/campaigns/${collab.campaign_id}`}
                        data-testid={IDS.title(collab.id)}
                        className="mt-2 block font-serif text-2xl leading-tight transition-colors duration-200 hover:text-ember-500"
                    >
                        {collab.campaign_title || "Untitled campaign"}
                    </Link>
                </div>
                <Money
                    symbolClass="h-4 w-4"
                    className="font-serif text-2xl leading-none"
                >
                    <span data-testid={IDS.amount(collab.id)}>{formatRupees(amount)}</span>
                </Money>
            </div>

            <Tracker
                collabId={collab.id}
                state={collab.state}
                stages={lifecycleFor(collab)}
            />

            {next.label && (
                <p
                    data-testid={IDS.nextAction(collab.id)}
                    className={
                        "mt-6 rounded-md border px-4 py-3 text-sm leading-relaxed " +
                        (next.waiting_on === "you"
                            ? "border-ember-500/30 bg-ember-500/10 text-ember-500"
                            : "border-white/10 bg-background/60 text-muted-foreground")
                    }
                >
                    {next.label}
                </p>
            )}

            {(collab.slot_starts_at || collab.venue?.address || collab.manager?.name) && (
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    {collab.slot_starts_at && (
                        <Detail Icon={CalendarClock} testid={IDS.slotTime(collab.id)}>
                            {formatDateTime(collab.slot_starts_at)}
                        </Detail>
                    )}
                    {collab.venue?.address && (
                        <Detail Icon={MapPin} testid={IDS.venue(collab.id)}>
                            {collab.venue.address}
                            {collab.venue.instructions && (
                                <span className="mt-1 block text-xs text-muted-foreground/80">
                                    {collab.venue.instructions}
                                </span>
                            )}
                        </Detail>
                    )}
                    {collab.manager?.name && (
                        <Detail Icon={Phone} testid={IDS.manager(collab.id)}>
                            {collab.manager.phone ? (
                                // Tap to call: standing outside a venue that
                                // can't find your booking, this is the whole
                                // reason the page is open.
                                <a
                                    href={`tel:${collab.manager.phone.replace(/\s+/g, "")}`}
                                    data-testid={IDS.call(collab.id)}
                                    className="underline underline-offset-4 transition-colors duration-200 hover:text-ember-500"
                                >
                                    {collab.manager.name} · {collab.manager.phone}
                                </a>
                            ) : (
                                <>{collab.manager.name} · no number on file</>
                            )}
                        </Detail>
                    )}
                </div>
            )}

            {(action || collab.can_cancel_slot) && (
                <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
                    {action}
                    {collab.can_cancel_slot && (
                        <button
                            type="button"
                            data-testid={IDS.cancelSlot(collab.id)}
                            onClick={cancelSlot}
                            disabled={releasing}
                            className="inline-flex min-h-[3rem] items-center justify-start gap-2 self-start text-sm text-muted-foreground transition-colors duration-200 hover:text-ember-500 disabled:opacity-50"
                        >
                            {releasing && <Loader2 className="h-4 w-4 animate-spin" />}
                            {/* Up to the cutoff. The server refuses inside it and
                                says so, rather than us guessing at the clock. */}
                            Can't make it? Release this slot
                        </button>
                    )}
                </div>
            )}
            </div>
        </motion.li>
    );
};

// ---------------------------------------------------------------------------

export default function ActiveCampaigns({ collaborations, onRefresh }) {
    const [booking, setBooking] = useState(null);
    const [submitting, setSubmitting] = useState(null);
    const [drafting, setDrafting] = useState(null);
    const rows = collaborations || [];

    return (
        <>
            <SectionHead
                kicker="Live right now"
                title="What you're working on."
                aside={
                    rows.length > 0 && (
                        <span
                            data-testid={IDS.count}
                            className="text-xs text-muted-foreground"
                        >
                            {rows.length} {rows.length === 1 ? "collaboration" : "collaborations"}
                        </span>
                    )
                }
            />

            <div className="mt-8">
                {rows.length === 0 ? (
                    <EmptyState
                        testid={IDS.empty}
                        Icon={Rocket}
                        title="Nothing live yet."
                        action={
                            <Link to="/campaigns" className="mt-2">
                                <Button className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                    Find a campaign
                                </Button>
                            </Link>
                        }
                    >
                        The moment a brand takes you on, the campaign shows up here
                        with the venue, the time and who to call.
                    </EmptyState>
                ) : (
                    <ul data-testid={IDS.list} className="space-y-4">
                        {rows.map((c) => (
                            <ActiveCard
                                key={c.id}
                                collab={c}
                                onBook={setBooking}
                                onSubmit={setSubmitting}
                                onDraft={setDrafting}
                                onRefresh={onRefresh}
                            />
                        ))}
                    </ul>
                )}
            </div>

            <SlotPicker
                open={Boolean(booking)}
                onOpenChange={(v) => !v && setBooking(null)}
                collab={booking}
                onBooked={onRefresh}
            />
            <SubmitContentDialog
                open={Boolean(submitting)}
                onOpenChange={(v) => !v && setSubmitting(null)}
                collab={submitting}
                onSubmitted={onRefresh}
            />
            <SubmitDraftDialog
                open={Boolean(drafting)}
                onOpenChange={(v) => !v && setDrafting(null)}
                collab={drafting}
                onSubmitted={onRefresh}
            />
        </>
    );
}
