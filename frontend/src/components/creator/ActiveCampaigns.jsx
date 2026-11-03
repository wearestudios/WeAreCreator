// Live collaborations — the part of this page that is actually work.
//
// One card per collaboration, carrying everything needed to turn up: where the
// creator is in the process, what they have to do next in words they'd use
// themselves, the manager's number as a link that dials, the venue, and the
// time. None of that is behind a tap, because half the time this is being
// read on a footpath outside the venue — only the reference half (the brief's
// checklist, accepted terms, the draft on file, the fee's history) folds
// under the work.
//
// Laid out as board 26 draws it: the cover slice, the title over brand ·
// deliverables · fee, whose move it is, the stages as segmented bars, and one
// tinted box holding the next step and its button.
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    CalendarClock,
    ChevronDown,
    FileVideo,
    Loader2,
    MapPin,
    PackageCheck,
    Phone,
    Rocket,
    Send,
    Upload,
    Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
    CREATOR_ACTIVE as IDS,
    CREATOR_DRAFT_SUMMARY as DRAFT_IDS,
    REVIEW_WINDOW as WINDOW_IDS,
} from "@/constants/testIds";
import ReviewWindowNote from "@/components/collab/ReviewWindowNote";
import NegotiationHistory from "@/components/collab/NegotiationHistory";
import { EmptyState, formatDateTime } from "./shared";
import { CardHeading, MetaLine, Pill } from "@/components/app/ui";
import { DeliverableSummary } from "@/components/Deliverables";
import { hasBriefDetails } from "@/lib/briefDetails";
import ProcessFlow from "@/components/application/ProcessFlow";
import Shortfall from "@/components/Shortfall";
import { formatCollabMoney, formatInr } from "@/lib/compensation";
import BrandAvatar from "@/components/BrandAvatar";
import CampaignCover from "@/components/CampaignCover";
import DisputePanel from "@/components/DisputePanel";
import TakedownPanel from "@/components/TakedownPanel";
import { TermsCard } from "@/components/campaign/CampaignTerms";
import BriefChecklist from "@/components/campaign/BriefChecklist";
import { PayoutDue } from "@/components/campaign/PayoutNote";
import OnBehalfNote from "@/components/collab/OnBehalfNote";
import SlotPicker from "./SlotPicker";
import SubmitContentDialog from "./SubmitContentDialog";
import SubmitDraftDialog from "./SubmitDraftDialog";

import RevisionAllowance from "@/components/collab/RevisionAllowance";
// The tracker that used to live here — a six-stage rail with its own labels —
// is gone. It was the third copy of the lifecycle in this repository, and the
// three disagreed: a creator saw six stages, the console saw the raw twelve,
// and the brand saw neither. `ProcessFlow` is the one answer now, and the
// stages come from the server.
// ---------------------------------------------------------------------------
// The card
// ---------------------------------------------------------------------------

const ACTION_ICON = {
    book_slot: CalendarClock,
    // The delivery half. `await_dispatch` has no icon on purpose: it is the
    // one row where the creator's next action is to do nothing, and an icon
    // beside a button that is not there reads as a control that failed to
    // render.
    confirm_address: MapPin,
    confirm_received: PackageCheck,
    submit_draft: FileVideo,
    resubmit_draft: FileVideo,
    submit_content: Upload,
    resubmit_content: Send,
    add_payout_details: Wallet,
};

// Whose move it is, in two words, on the card's corner.
const MOVE = {
    creator: { label: "Your move", tone: "warn" },
    brand: { label: "Brand's move", tone: "info" },
    admin: { label: "WeAre's move", tone: "info" },
};

const Detail = ({ Icon, children, testid }) => (
    <div data-testid={testid} className="flex items-start gap-2 text-meta text-muted-foreground">
        <Icon className="mt-0.5 h-4 w-4 flex-none text-primary/80" />
        <span className="min-w-0 leading-relaxed">{children}</span>
    </div>
);

const ActiveCard = ({ collab, onBook, onSubmit, onDraft, onRefresh }) => {
    const [releasing, setReleasing] = useState(false);
    const next = collab.next_action || {};
    const Icon = ACTION_ICON[next.action];
    // **Barter reads as barter.** This was `agreed_amount ?? quoted_rate`
    // with a rupee sign, and a barter collaboration has no agreed amount on
    // purpose — so the card printed the creator's own quote as if somebody
    // had agreed it, on a brief that pays a dinner.
    const money = formatCollabMoney({
        compensationType: collab.compensation_type,
        agreed: collab.agreed_amount,
        quoted: collab.quoted_rate,
        barterTerms: collab.barter_terms,
    });
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

    // **Two states, one pattern, and both are the creator's own.** Confirming
    // an address and confirming an arrival are POSTs with an optional note and
    // no form worth the name — a dialog for either would be two taps where one
    // does. Optimistic like every other mutation here: the row answers on the
    // frame of the click rather than after a round trip.
    const [confirming, setConfirming] = useState(null);
    const confirmDelivery = async (what) => {
        setConfirming(what);
        try {
            await api.post(
                `/creator/collaborations/${collab.id}/${
                    what === "address" ? "confirm-address" : "confirm-received"
                }`,
                {},
            );
            notifySuccess(
                what === "address"
                    ? "Address confirmed — we'll send it shortly"
                    : "Thanks — you can shoot whenever you're ready",
            );
            onRefresh?.();
        } catch (e) {
            notifyError(e);
        } finally {
            setConfirming(null);
        }
    };

    // **Whose move it is, from the server's owner of the next step.** That
    // owner is mapped through `execution_owner`, so a draft our manager is
    // reviewing reads as ours rather than the brand's. The card's own
    // `waiting_on` is the fallback for a row whose flow has no next step.
    const owner = collab.process?.next_action?.owner || (next.waiting_on === "you" ? "creator" : null);
    const mine = owner === "creator";
    const move = MOVE[owner];
    // Their move: the card's own sentence, which knows about slots, venues and
    // drafts. Somebody else's: the flow's, which names the wait without
    // putting it on the wrong party.
    const nextText = mine
        ? next.label || collab.process?.next_action?.label
        : collab.process?.next_action?.label || next.label;
    const buttonVariant = mine ? "urgent" : "solid";
    const BUTTON = "h-11 w-full sm:w-auto";

    const action = (() => {
        if (next.action === "confirm_address") {
            return (
                <Button
                    data-testid={IDS.primary(collab.id)}
                    variant={buttonVariant}
                    disabled={confirming === "address"}
                    onClick={() => confirmDelivery("address")}
                    className={BUTTON}
                >
                    <Icon className="mr-2 h-4 w-4" />
                    {confirming === "address" ? "Confirming…" : "Confirm my address"}
                </Button>
            );
        }
        if (next.action === "confirm_received") {
            return (
                <Button
                    data-testid={IDS.primary(collab.id)}
                    variant={buttonVariant}
                    disabled={confirming === "received"}
                    onClick={() => confirmDelivery("received")}
                    className={BUTTON}
                >
                    <Icon className="mr-2 h-4 w-4" />
                    {confirming === "received" ? "Confirming…" : "It arrived"}
                </Button>
            );
        }
        if (next.action === "book_slot") {
            return (
                <Button
                    data-testid={IDS.primary(collab.id)}
                    variant={buttonVariant}
                    onClick={() => onBook(collab)}
                    className={BUTTON}
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
                    variant={buttonVariant}
                    onClick={() => onDraft(collab)}
                    className={BUTTON}
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
                    variant={buttonVariant}
                    onClick={() => onSubmit(collab)}
                    className={BUTTON}
                >
                    <Icon className="mr-2 h-4 w-4" />
                    {/* **"Upload your content link" is a lie on a brief whose
                        ask is all stories** — there the link is dead before
                        anybody reads it and the screenshots are the delivery,
                        so the button says what is actually being asked for.
                        `link_optional` is the server's answer, like every
                        other flag on this card. */}
                    {next.action === "resubmit_content"
                        ? "Update what you delivered"
                        : collab.proof?.link_optional
                        ? "Send your screenshots"
                        : "Upload your content link"}
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
                    <Button variant={buttonVariant} className={BUTTON}>
                        <MapPin className="mr-2 h-4 w-4" />
                        Get directions
                    </Button>
                </a>
            );
        }
        if (next.action === "add_payout_details") {
            return (
                <Link to="/onboarding/creator" data-testid={IDS.primary(collab.id)}>
                    <Button variant={buttonVariant} className={BUTTON}>
                        <Icon className="mr-2 h-4 w-4" />
                        Add payout details
                    </Button>
                </Link>
            );
        }
        return null;
    })();

    // The reference half of the card — the brief's checklist, the terms
    // already accepted, the draft on file, how the fee was agreed and the
    // door to a dispute — folds under the work. None of it is the next thing to do, and drawn open it
    // made a two-up card a 1,400px tower with the button somewhere in the
    // middle. Terms still waiting on their tap stay out in the open, because
    // that one *is* a thing to do.
    const termsToAccept = Boolean(collab.terms && collab.can_accept_terms);
    // A dispute that exists is the situation and goes first; the button to
    // raise one is a door kept for when it is needed, and drawn open on every
    // card it was the loudest thing on the page while nothing was wrong.
    const dispute = (
        <DisputePanel
            collaborationId={collab.id}
            dispute={collab.dispute}
            actions={{
                can_raise_dispute: collab.can_raise_dispute,
                can_withdraw_dispute: collab.can_withdraw_dispute,
            }}
            onChanged={onRefresh}
        />
    );
    const canRaise = !collab.dispute && Boolean(collab.can_raise_dispute);
    const hasMore =
        canRaise ||
        hasBriefDetails(collab.brief_details) ||
        (collab.terms && !termsToAccept) ||
        Boolean(collab.draft?.submitted_at) ||
        collab.negotiation?.entries?.length > 0;

    return (
        <li
            data-testid={IDS.card(collab.id)}
            className="flex min-w-0 flex-col overflow-hidden rounded-lg bg-card shadow-card"
        >
            {/* A slim slice of the campaign's own cover, so a card of work
                reads as a place rather than a form. 16:5 on a phone, capped
                at 118px from `md` — aspect-ratio yields to max-height, which
                is what stops a wide card growing a wall of tint. */}
            <CampaignCover
                campaign={{
                    id: collab.campaign_id,
                    cover_image_url: collab.cover_image_url,
                    brand_name: collab.brand_name,
                    title: collab.campaign_title,
                }}
                ratio="aspect-[16/5]"
                rounded="rounded-none"
                className="border-0 md:max-h-[7.375rem]"
            />
            <div className="flex flex-1 flex-col p-5 md:px-[22px]">
                <div className="flex items-start justify-between gap-3">
                    <Link
                        to={`/campaigns/${collab.campaign_id}`}
                        data-testid={IDS.title(collab.id)}
                        className="min-w-0 text-body-lg font-extrabold leading-snug text-heading transition-colors duration-200 hover:text-primary"
                    >
                        {collab.campaign_title || "Untitled campaign"}
                    </Link>
                    {move && (
                        <Pill tone={move.tone} data-testid={IDS.move(collab.id)} className="mt-0.5 flex-none">
                            {move.label}
                        </Pill>
                    )}
                </div>
                {/* Brand · what they asked for · what it pays — the full
                    width of the card, so the pill above never squeezes it. */}
                <MetaLine className="mt-1.5 text-meta font-semibold text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                        <BrandAvatar brand={collab} size="h-5 w-5" />
                        {collab.brand_name || "Brand"}
                    </span>
                    {(collab.deliverable_items?.length > 0 || collab.deliverables) && (
                        <DeliverableSummary campaign={collab} />
                    )}
                    {money.isBarter ? (
                        <span data-testid={IDS.amount(collab.id)} data-barter="true">
                            {money.text}
                        </span>
                    ) : (
                        <span data-testid={IDS.amount(collab.id)} className="tabular-nums text-foreground">
                            {formatInr(amount)}
                        </span>
                    )}
                </MetaLine>

                {/* **The same eight stages the brand and the admin read**, as
                    segmented bars. The stages, the position and any banner all
                    come from the server; the next step is the box below. */}
                <ProcessFlow process={collab.process} variant="bars" className="mt-4" />

                {/* **The creator sees these first.** A freeze on their own
                    payment, a request to pull their own post, what arrived
                    short, a step WeAre took for them, terms waiting on their
                    tap, an extra round asked of them. Each renders nothing
                    when there is nothing to say, and what they may do comes
                    off the row rather than being worked out here. */}
                <div className="mt-4 space-y-3 empty:hidden">
                    {collab.dispute && dispute}
                    <TakedownPanel
                        collaborationId={collab.id}
                        takedown={collab.takedown}
                        canRespond={Boolean(collab.can_respond_takedown)}
                        onChanged={onRefresh}
                    />
                    {collab.partial_delivery && (
                        <Shortfall
                            shortfall={collab.shortfall}
                            note={collab.partial_note}
                            testid={IDS.shortfall(collab.id)}
                        />
                    )}
                    {/* A booking they did not make must never read as one
                        they did. */}
                    <OnBehalfNote onBehalf={collab.on_behalf} voice="you" testid={IDS.onBehalf(collab.id)} />
                    {/* **Their copy of what was agreed, and their one tap.**
                        The shared application page is mounted at no creator
                        route, so this card is the only place they can accept. */}
                    {termsToAccept && (
                        <TermsCard
                            terms={collab.terms}
                            collabId={collab.id}
                            canAccept
                            onAccepted={onRefresh}
                        />
                    )}
                    {/* "1 of 2 used" — and, when the reviewer has asked for
                        one more round, the creator's two answers. */}
                    <RevisionAllowance
                        collabId={collab.id}
                        revisions={collab.revisions}
                        canAnswer={collab.can_answer_extra_revision}
                        onChanged={onRefresh}
                    />
                </div>

                {/* **One box, one button.** Tinted red when the move is
                    theirs and navy while they wait; the button fills the one
                    `IDS.primary` slot whichever action it is. */}
                {(nextText || action) && (
                    <div className={"mt-4 rounded-[14px] px-4 py-3.5 " + (mine ? "bg-wash-red" : "bg-wash-navy")}>
                        {nextText && (
                            <p
                                data-testid={IDS.nextAction(collab.id)}
                                className="text-body font-bold leading-snug text-heading"
                            >
                                {nextText}
                            </p>
                        )}
                        <ReviewWindowNote
                            reviewWindow={collab.draft?.review_window}
                            testid={WINDOW_IDS.creatorNote(collab.id)}
                        />
                        {(action || collab.can_cancel_slot || collab.cancel_blocked_reason) && (
                            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4">
                                {action}
                                {/* **Disabled with the reason, not offered and
                                    refused.** Inside the cutoff, or past the
                                    reschedule cap, the route answers 409 — so
                                    the server sends why instead. */}
                                {!collab.can_cancel_slot && collab.cancel_blocked_reason && (
                                    <p
                                        data-testid={IDS.cancelBlocked(collab.id)}
                                        className="text-meta leading-relaxed text-muted-foreground"
                                    >
                                        {collab.cancel_blocked_reason}
                                    </p>
                                )}
                                {collab.can_cancel_slot && (
                                    <button
                                        type="button"
                                        data-testid={IDS.cancelSlot(collab.id)}
                                        onClick={cancelSlot}
                                        disabled={releasing}
                                        className="inline-flex min-h-[2.75rem] items-center justify-start gap-2 self-start text-meta font-semibold text-muted-foreground transition-colors duration-200 hover:text-primary disabled:opacity-50 sm:self-auto"
                                    >
                                        {releasing && <Loader2 className="h-4 w-4 animate-spin" />}
                                        Can't make it? Release this slot
                                        {/* How many of their moves are left,
                                            from the numbers the cap is
                                            checked against. */}
                                        {collab.reschedule_limit > 0 && (
                                            <span data-testid={IDS.moves(collab.id)} className="font-normal">
                                                ({collab.reschedule_count} of {collab.reschedule_limit} moves used)
                                            </span>
                                        )}
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* Where, when and who to call — never behind a tap, because
                    half the time this is being read outside the venue. */}
                {(collab.slot_starts_at || collab.venue?.address || collab.manager?.name) && (
                    <div className="mt-4 grid gap-2.5">
                        {collab.slot_starts_at && (
                            <Detail Icon={CalendarClock} testid={IDS.slotTime(collab.id)}>
                                {formatDateTime(collab.slot_starts_at)}
                            </Detail>
                        )}
                        {collab.venue?.address && (
                            <Detail Icon={MapPin} testid={IDS.venue(collab.id)}>
                                {collab.venue.address}
                                {collab.venue.instructions && (
                                    <span className="mt-1 block text-meta text-muted-foreground/80">
                                        {collab.venue.instructions}
                                    </span>
                                )}
                            </Detail>
                        )}
                        {collab.manager?.name && (
                            <Detail Icon={Phone} testid={IDS.manager(collab.id)}>
                                {collab.manager.phone ? (
                                    // Tap to call: standing outside a venue
                                    // that can't find your booking, this is
                                    // the whole reason the page is open.
                                    <a
                                        href={`tel:${collab.manager.phone.replace(/\s+/g, "")}`}
                                        data-testid={IDS.call(collab.id)}
                                        className="underline underline-offset-4 transition-colors duration-200 hover:text-primary"
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

                {/* **Why the runner moved it**, on the card of the person
                    whose day it is. */}
                {collab.reschedule_reason && (
                    <p
                        data-testid={IDS.rescheduleReason(collab.id)}
                        className="mt-3 text-meta leading-relaxed text-muted-foreground"
                    >
                        Your booking was moved
                        {collab.rescheduled_at ? ` on ${formatDateTime(collab.rescheduled_at)}` : ""}:{" "}
                        {collab.reschedule_reason}
                    </p>
                )}

                {/* **The date, once the work has been approved** — a day they
                    can hold us to. Absent on every row before approval. */}
                <PayoutDue dueAt={collab.payout_due_at} className="mt-3" />

                {hasMore && (
                    <details data-testid={IDS.more(collab.id)} className="group mt-4 border-t border-divider pt-3">
                        <summary className="flex min-h-[2.75rem] cursor-pointer list-none items-center gap-2 text-meta font-semibold text-foreground transition-colors duration-200 hover:text-primary [&::-webkit-details-marker]:hidden">
                            <ChevronDown
                                aria-hidden="true"
                                className="h-4 w-4 transition-transform duration-200 group-open:rotate-180"
                            />
                            More about this job
                        </summary>
                        <div className="mt-2 space-y-4">
                            {/* **The checklist, while there is still time to
                                act on it** — at draft review the fix is a
                                reshoot. */}
                            <BriefChecklist details={collab.brief_details} title="What this brief asks for" />
                            {!termsToAccept && (
                                <TermsCard terms={collab.terms} collabId={collab.id} onAccepted={onRefresh} />
                            )}
                            {/* **What they sent, and what became of it**, so a
                                creator can check which version is in front of
                                the reviewer. */}
                            {collab.draft?.submitted_at && (
                                <div
                                    data-testid={DRAFT_IDS.block(collab.id)}
                                    className="rounded-md bg-wash-warm px-4 py-3 text-meta leading-relaxed text-muted-foreground"
                                >
                                    <p className="text-foreground">
                                        Draft sent {formatDateTime(collab.draft.submitted_at)}
                                        {collab.draft.kind === "link" && collab.draft.draft_url ? (
                                            <>
                                                {" · "}
                                                <a
                                                    href={collab.draft.draft_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="underline underline-offset-4"
                                                >
                                                    the link you sent
                                                </a>
                                            </>
                                        ) : collab.draft.original_name ? (
                                            ` · ${collab.draft.original_name}`
                                        ) : null}
                                    </p>
                                    <p className="mt-1">
                                        {collab.draft.revision_count > 0
                                            ? `Sent back ${collab.draft.revision_count} time${collab.draft.revision_count === 1 ? "" : "s"}`
                                            : "Not sent back"}
                                        {collab.draft.approved_at
                                            ? ` · approved ${formatDateTime(collab.draft.approved_at)}`
                                            : ""}
                                    </p>
                                </div>
                            )}
                            {/* **How the fee got here**, in their own card. */}
                            {collab.negotiation?.entries?.length > 0 && (
                                <div>
                                    <p className="mb-3 text-label text-muted-foreground">How the fee was agreed</p>
                                    <NegotiationHistory negotiation={collab.negotiation} compact />
                                </div>
                            )}
                            {canRaise && dispute}
                        </div>
                    </details>
                )}
            </div>
        </li>
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
            <CardHeading
                aside={
                    rows.length > 0 && (
                        <span data-testid={IDS.count}>
                            {rows.length} {rows.length === 1 ? "collaboration" : "collaborations"}
                        </span>
                    )
                }
            >
                What you&apos;re working on
            </CardHeading>

            {rows.length === 0 ? (
                <EmptyState
                    testid={IDS.empty}
                    Icon={Rocket}
                    title="Nothing live yet."
                    action={
                        <Link to="/campaigns" className="mt-2">
                            <Button variant="solid" className="h-11">
                                Find a brief
                            </Button>
                        </Link>
                    }
                >
                    The moment a brand takes you on, the campaign shows up here
                    with the venue, the time and who to call.
                </EmptyState>
            ) : (
                // Two up from `lg`, the first a little wider (the board's
                // 1.25 : 1). One card takes the row — a lone card in the
                // wider column would leave a hole beside it.
                <ul
                    data-testid={IDS.list}
                    className={
                        "grid items-start gap-4 " +
                        (rows.length > 1 ? "lg:grid-cols-[1.25fr_1fr]" : "")
                    }
                >
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
