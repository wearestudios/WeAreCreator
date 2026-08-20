// One application, on its own screen.
//
// Applications used to live inside the campaign view, as rows on a board — so
// deciding about one person meant reading a table, and the decision itself
// happened in a dialog with no room for the reasoning behind it. This is the
// same application given a page: where it stands, who it is, what the brief
// is, what it pays, what was said, and every action that is currently legal.
//
// **One component, two routes.** The admin opens it at /admin/applications/:id
// and the brand at /brand/applications/:id. That is deliberate: the two
// consoles previously read the same collaboration through different endpoints
// and described it differently — an approved application showed as approved to
// one and pending to the other. Sharing the component makes that class of bug
// impossible rather than merely fixed.
//
// Everything role-dependent is decided by the server and arrives in `actions`,
// so this file never asks "am I an admin"; it asks "may this be done".
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { formatCompensation, isBarter } from "@/lib/compensation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { DetailShell, Field, Section, Stat } from "@/components/admin/DetailPage";
import { BrandLink, CampaignLink, CreatorLink } from "@/components/admin/links";
import WorkNotes from "@/components/brand/WorkNotes";
import QuestionThread from "@/components/questions/QuestionThread";
import BrandAvatar from "@/components/BrandAvatar";
import BrandName from "@/components/BrandName";
import { Navbar } from "@/components/Navbar";
import { APPLICATION } from "@/constants/testIds";

import DraftReview from "./DraftReview";
import AgeBadge from "@/components/AgeBadge";
import Shortfall from "@/components/Shortfall";
import RateCollaboration from "@/components/RateCollaboration";
import { ReliabilityBadge, ReliabilityPanel } from "@/components/ReliabilityBadge";
import { RELIABILITY, SHORTFALL } from "@/constants/testIds";
import ProcessFlow from "./ProcessFlow";
import { IST } from "@/lib/time";

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : "—";

/** "20 Aug, 7:00 pm" — a time somebody has to turn up at, so it carries one. */
const formatDateTime = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
        timeZone: IST,
    });
};

const formatDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: IST });
};

/**
 * The fee field, which is three different controls depending on how the brief
 * pays. The server decides which via `amount_required` / `amount_locked` /
 * `amount_applies` — the client must not infer it from a budget, because a
 * barter brief keeps whatever budget it was posted with.
 */
function CommercialInput({ commercial, value, onChange, disabled }) {
    if (!commercial.amount_applies) {
        return (
            <p
                data-testid={APPLICATION.amountBarter}
                className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-muted-foreground"
            >
                Barter — there's no amount to agree. A meal, a stay, a product.
            </p>
        );
    }
    if (commercial.amount_locked) {
        return (
            <div
                data-testid={APPLICATION.amountLocked}
                className="rounded-md border border-white/10 bg-white/5 px-3 py-2"
            >
                <p className="text-sm">₹{formatRupees(commercial.locked_amount)}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                    Fixed by the brief — the same for every creator on this campaign, so
                    it isn't editable here.
                </p>
            </div>
        );
    }
    return (
        <div>
            <Input
                data-testid={APPLICATION.amountInput}
                type="number"
                inputMode="numeric"
                min="1"
                placeholder="What was agreed"
                value={value}
                disabled={disabled}
                onChange={(e) => onChange(e.target.value)}
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
                Negotiated offline. This is the figure the creator is paid and the one
                the invoice is built from, so it has to be the real one.
            </p>
        </div>
    );
}

export default function ApplicationDetail({
    backTo,
    backLabel,
    crumbs,
    // The cross-links go to /admin/* pages. A brand cannot open those, so on
    // the brand route the same facts render as plain text rather than as links
    // to a console they will be bounced out of.
    entityLinks = false,
    // The admin route renders inside the console shell, which already provides
    // the navbar and the <main> wrapper. The brand route stands on its own and
    // has to bring its own chrome, at the brand pages' width.
    standalone = false,
    // **Where the booking handshake is answered.** `_answer_slot_request` is
    // one implementation behind four routes — the brand's pair and the WeAre
    // manager's — because which of them answers depends on `execution_owner`,
    // and a booking that meant different things depending on who confirmed it
    // would not be a confirmation. The *route* differs by caller, so the route
    // is told rather than sniffed: this component still never asks what role
    // is looking, which is the rule it has always held.
    //
    // Only the slot pair takes it. Accept, decline and the agreed amount are
    // brand-owned transitions the server never offers a manager, so their
    // buttons do not render for one and their paths stay `/brand`.
    slotBase = "/brand",
}) {
    const { id } = useParams();
    const [app, setApp] = useState(null);
    const [error, setError] = useState("");
    const [notFound, setNotFound] = useState(false);
    const [busy, setBusy] = useState(null);
    const [amount, setAmount] = useState("");
    // The reason a time was turned down. Required, because without it the
    // creator picks the same impossible slot again.
    const [decliningSlot, setDecliningSlot] = useState(false);
    const [slotReason, setSlotReason] = useState("");

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/applications/${id}`);
            setApp(data);
            setError("");
            // Seed from whatever is already agreed so reopening the screen
            // doesn't present an empty box beside a settled number.
            if (data?.commercial?.agreed_amount != null) {
                setAmount(String(data.commercial.agreed_amount));
            }
        } catch (err) {
            if (err?.response?.status === 404) setNotFound(true);
            else setError(formatApiError(err));
        }
    }, [id]);

    useEffect(() => {
        setApp(null);
        setNotFound(false);
        setError("");
        load();
    }, [load]);

    /** Run one mutation, then refetch. Always refetch: the lifecycle, the
     *  available actions and the commercial all move together, and guessing
     *  the new shape locally is how a screen starts disagreeing with the API. */
    const act = useCallback(
        async (key, request, successMessage) => {
            setBusy(key);
            try {
                await request();
                notifySuccess(successMessage);
                await load();
            } catch (err) {
                notifyError(formatApiError(err));
            } finally {
                setBusy(null);
            }
        },
        [load],
    );

    const commercial = app?.commercial;
    const actions = app?.actions || {};

    // Approving the commercial is blocked client-side under exactly the
    // condition the server refuses, so the button explains itself rather than
    // producing a 422 the person has to read as a toast.
    const amountMissing = useMemo(
        () => Boolean(commercial?.amount_required) && !String(amount).trim(),
        [commercial, amount],
    );

    // One endpoint for both consoles. /brand/collaborations/{id}/agreed-amount
    // takes BRAND_ROLES *and* admin, records the figure and moves the
    // collaboration to commercial_agreed in one write — so the shared
    // component does not need to know which role is looking at it.
    const agreeCommercial = () =>
        act(
            "agree",
            () =>
                api.post(`/brand/collaborations/${id}/agreed-amount`, {
                    // Omitted entirely for barter and for a locked fee: the
                    // server owns those numbers, and sending one back is how a
                    // stale form rewrites a commercial.
                    ...(commercial.amount_required
                        ? { agreed_amount: Number(amount) }
                        : {}),
                }),
            "Amount recorded — it's the creator's move now",
        );

    const shell = (
        <DetailShell
            testid={APPLICATION.page}
            backTo={backTo}
            backLabel={backLabel}
            crumbs={crumbs}
            kicker={app?.reference ? `Application · ${app.reference}` : "Application"}
            title={app?.creator?.name || "Application"}
            subtitle={app ? app.campaign?.title : undefined}
            loading={!app && !error && !notFound}
            error={error}
            notFound={notFound}
            notFoundMessage="That application doesn't exist, or isn't yours to see."
        >
            {app && (
                <div className="mt-8 space-y-8">
                    {/* One process, eight stages, the same on all three
                        views of it. The server decides the stage and the
                        voice; see ProcessFlow. */}
                    <ProcessFlow process={app.lifecycle?.process} />

                    {/* How long this has been where it is, under the flow that
                        says where that is. The queue that opens onto this page
                        says "9 days over"; a detail page that said nothing is
                        one people stop trusting. It renders nothing on a state
                        with no clock — a finished collaboration, or one waiting
                        on a date rather than on a person. */}
                    <AgeBadge ageing={app.ageing} testid={APPLICATION.ageing} />

                    <Section id="commercial" title="Commercial">
                        <div
                            data-testid={APPLICATION.commercial}
                            className="grid gap-4 sm:grid-cols-3"
                        >
                            <Stat
                                testid={APPLICATION.commercialType}
                                label="Compensation"
                                value={
                                    formatCompensation(commercial, {
                                        per: "per creator",
                                    }).text
                                }
                            />
                            <Stat
                                testid={APPLICATION.commercialQuoted}
                                label="Creator quoted"
                                value={
                                    commercial.quoted_rate != null
                                        ? `₹${formatRupees(commercial.quoted_rate)}`
                                        : "—"
                                }
                            />
                            <Stat
                                testid={APPLICATION.commercialAgreed}
                                label="Agreed"
                                highlight={commercial.agreed_amount != null}
                                value={
                                    commercial.agreed_amount != null
                                        ? `₹${formatRupees(commercial.agreed_amount)}`
                                        : isBarter(commercial)
                                          ? "Barter"
                                          : "Not yet"
                                }
                            />
                        </div>

                        {actions.can_agree_commercial && (
                            <div className="mt-6 max-w-md space-y-3">
                                <CommercialInput
                                    commercial={commercial}
                                    value={amount}
                                    onChange={setAmount}
                                    disabled={busy === "agree"}
                                />
                                <Button
                                    data-testid={APPLICATION.agreeCommercial}
                                    onClick={agreeCommercial}
                                    disabled={busy === "agree" || amountMissing}
                                    className="min-h-[2.75rem] w-full sm:w-auto"
                                >
                                    {busy === "agree" && (
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    )}
                                    Record and hand over to the creator
                                </Button>
                                {amountMissing && (
                                    <p
                                        data-testid={APPLICATION.amountError}
                                        className="text-xs text-amber-300"
                                    >
                                        This brief is negotiated, so it has no fee until
                                        somebody agrees one. Enter the amount to continue.
                                    </p>
                                )}
                            </div>
                        )}
                    </Section>

                    {/* **What they are like to work with, before deciding.**
                        The band comes on the creator block for everybody; the
                        counts behind it arrive only for staff, so this panel
                        is the record on an admin's screen and the badge alone
                        on a brand's — decided by what the server sent, never
                        by asking what role is looking. */}
                    <Section id="reliability" title="Track record">
                        <ReliabilityBadge
                            reliability={app.creator?.reliability}
                            testid={RELIABILITY.badge(app.creator?.user_id || "x")}
                            className="mb-4"
                        />
                        {app.reliability !== undefined && (
                            <ReliabilityPanel stats={app.reliability} testid={RELIABILITY.panel} />
                        )}
                    </Section>

                    {/* What arrived against what was asked. Renders nothing
                        where there is nothing counted to say. */}
                    {app.shortfall && (
                        <Section id="shortfall" title="Delivered">
                            <Shortfall
                                shortfall={app.shortfall}
                                testid={SHORTFALL.block(id)}
                            />
                        </Section>
                    )}

                    <Section id="creator" title="Creator">
                        <div
                            data-testid={APPLICATION.creator}
                            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                        >
                            <Field label="Name">
                                {entityLinks ? (
                                    <CreatorLink
                                        id={app.creator?.id}
                                        name={app.creator?.name}
                                    />
                                ) : (
                                    app.creator?.name || "—"
                                )}
                            </Field>
                            <Field label="Instagram">
                                {app.creator?.instagram_handle
                                    ? `@${app.creator.instagram_handle}`
                                    : "—"}
                            </Field>
                            <Field label="Followers">
                                {formatRupees(app.creator?.follower_count)}
                            </Field>
                            <Field label="City">{app.creator?.city || "—"}</Field>
                            <Field label="Niches">
                                {(app.creator?.niches || []).join(", ") || "—"}
                            </Field>
                            <Field label="Base rate">
                                {app.creator?.base_rate != null
                                    ? `₹${formatRupees(app.creator.base_rate)}`
                                    : "—"}
                            </Field>
                        </div>
                        {app.pitch && (
                            <div className="mt-6">
                                <Field label="Their pitch">{app.pitch}</Field>
                            </div>
                        )}
                    </Section>

                    <Section id="campaign" title="Campaign">
                        <div
                            data-testid={APPLICATION.campaign}
                            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                        >
                            {/* Both destinations work for whoever is looking.
                                The admin gets the console's own pages, which
                                carry more; everybody else gets the pages their
                                role can actually open. Which one is decided by
                                the route that mounted this, never by asking
                                here what the user is. */}
                            <Field label="Brief">
                                {entityLinks ? (
                                    <CampaignLink
                                        id={app.campaign?.id}
                                        title={app.campaign?.title}
                                        testid={APPLICATION.campaignLink}
                                    />
                                ) : (
                                    <Link
                                        to={`/campaigns/${app.campaign?.id}`}
                                        data-testid={APPLICATION.campaignLink}
                                        className="transition-colors duration-200 hover:text-ember-500"
                                    >
                                        {app.campaign?.title || "Untitled campaign"}
                                    </Link>
                                )}
                            </Field>
                            <Field label="Brand">
                                {entityLinks ? (
                                    <span className="inline-flex items-center gap-2">
                                        <BrandAvatar
                                            brand={app.campaign}
                                            size="h-5 w-5"
                                        />
                                        <BrandLink
                                            id={app.campaign?.brand_id}
                                            name={app.campaign?.brand_name}
                                            testid={APPLICATION.brandLink}
                                        />
                                    </span>
                                ) : (
                                    <BrandName
                                        brand={app.campaign}
                                        avatarSize="h-5 w-5"
                                        testid={APPLICATION.brandLink}
                                    />
                                )}
                            </Field>
                            <Field label="Status">{app.campaign?.status || "—"}</Field>
                            <Field label="Area">{app.campaign?.area || "—"}</Field>
                            <Field label="Date">
                                {formatDate(
                                    app.campaign?.event_date || app.campaign?.start_date,
                                )}
                            </Field>
                            <Field label="Creators wanted">
                                {app.campaign?.creators_needed ?? "—"}
                            </Field>
                        </div>
                    </Section>

                    {/* The second half of the booking handshake. Offered only
                        to whoever runs this campaign — the server decides —
                        because a creator's chosen time is a request until the
                        person holding the venue's diary says yes. */}
                    {actions.can_confirm_slot && (
                        <Section id="slot" title="Slot to confirm">
                            <p
                                data-testid={APPLICATION.slotPending}
                                className="text-sm text-muted-foreground"
                            >
                                {app.creator?.name || "The creator"} asked for{" "}
                                <span className="text-foreground">
                                    {formatDateTime(app.scheduled_at)}
                                </span>
                                . Nothing is agreed until you say so.
                            </p>
                            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                                <Button
                                    data-testid={APPLICATION.confirmSlot}
                                    disabled={busy === "confirm-slot"}
                                    className="min-h-[2.75rem]"
                                    onClick={() =>
                                        act(
                                            "confirm-slot",
                                            () =>
                                                api.post(
                                                    `${slotBase}/collaborations/${id}/slot/confirm`,
                                                ),
                                            "Slot confirmed — the creator has been told",
                                        )
                                    }
                                >
                                    {busy === "confirm-slot" && (
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    )}
                                    Confirm this time
                                </Button>
                                <Button
                                    data-testid={APPLICATION.declineSlot}
                                    variant="outline"
                                    disabled={busy === "confirm-slot"}
                                    className="min-h-[2.75rem]"
                                    onClick={() => setDecliningSlot(true)}
                                >
                                    This time doesn't work
                                </Button>
                            </div>
                        </Section>
                    )}

                    {/* Every action that is currently legal, on the page rather
                        than behind a row menu. The server decided which; an
                        empty set means it is somebody else's move and the bar
                        above already says whose. */}
                    {(actions.can_approve_profile ||
                        actions.can_accept ||
                        actions.can_decline) && (
                        <Section id="actions" title="Actions">
                            <div
                                data-testid={APPLICATION.actions}
                                className="flex flex-col gap-3 sm:flex-row sm:flex-wrap"
                            >
                                {actions.can_approve_profile && (
                                    <Button
                                        data-testid={APPLICATION.approveProfile}
                                        disabled={busy === "approve"}
                                        className="min-h-[2.75rem]"
                                        onClick={() =>
                                            act(
                                                "approve",
                                                () =>
                                                    api.post(
                                                        `/admin/collaborations/${id}/advance`,
                                                        { from_state: app.state },
                                                    ),
                                                "Profile approved — over to the brand",
                                            )
                                        }
                                    >
                                        {busy === "approve" && (
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        )}
                                        Approve the profile
                                    </Button>
                                )}
                                {actions.can_accept && (
                                    <Button
                                        data-testid={APPLICATION.accept}
                                        disabled={busy === "accept"}
                                        className="min-h-[2.75rem]"
                                        onClick={() =>
                                            act(
                                                "accept",
                                                () =>
                                                    api.post(
                                                        `/brand/collaborations/${id}/accept`,
                                                    ),
                                                "Accepted",
                                            )
                                        }
                                    >
                                        {busy === "accept" && (
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        )}
                                        Accept
                                    </Button>
                                )}
                                {actions.can_decline && (
                                    <Button
                                        data-testid={APPLICATION.decline}
                                        variant="outline"
                                        disabled={busy === "decline"}
                                        className="min-h-[2.75rem]"
                                        onClick={() =>
                                            act(
                                                "decline",
                                                () =>
                                                    api.post(
                                                        `/brand/collaborations/${id}/decline`,
                                                    ),
                                                "Declined",
                                            )
                                        }
                                    >
                                        {busy === "decline" && (
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        )}
                                        Decline
                                    </Button>
                                )}
                            </div>
                        </Section>
                    )}

                    {/* The draft, where the campaign reviews one. `draft` is
                        null — not an empty object — on a campaign that
                        doesn't, so the panel is absent rather than a section
                        explaining that there is nothing in it. */}
                    {app.draft && (
                        <Section id="draft" title="Draft review">
                            <DraftReview
                                collaborationId={id}
                                draft={app.draft}
                                canReview={actions.can_review_draft}
                                onDecided={load}
                            />
                        </Section>
                    )}

                    {/* The creator's question thread — a different audience
                        from the work notes below it, and the server says who
                        gets it: questions_enabled is false for a brand on a
                        weare-run campaign, where the thread is not theirs to
                        read. */}
                    {app.questions_enabled && app.campaign?.id && app.creator?.user_id && (
                        <Section id="questions" title="Creator questions">
                            <QuestionThread
                                campaignId={app.campaign.id}
                                creatorId={app.creator.user_id}
                                emptyText="This creator hasn't asked anything."
                            />
                        </Section>
                    )}

                    {/* Open by default here, unlike on a list row: this whole
                        page is about one application, so the thread is the
                        thing you came to read rather than a detail to expand. */}
                    {/* Rating opens when the collaboration closes, and the
                        component renders nothing until then — a score given
                        while the work is still in flight is leverage rather
                        than a record. */}
                    <RateCollaboration collabId={id} />

                    <Section id="notes" title="Work notes">
                        <WorkNotes
                            collaborationId={id}
                            agreedAmount={commercial.agreed_amount}
                            quotedRate={commercial.quoted_rate}
                            defaultOpen
                        />
                    </Section>
                </div>
            )}

            {/* Turning a time down is destructive — the seat goes back on
                sale — so it is confirmed, and the reason is required rather
                than optional: it is the only thing that stops the creator
                picking the same impossible slot again. */}
            <Dialog
                open={decliningSlot}
                onOpenChange={(v) => {
                    if (!v) {
                        setDecliningSlot(false);
                        setSlotReason("");
                    }
                }}
            >
                <DialogContent className="max-w-md rounded-md border border-white/10 bg-card">
                    <DialogHeader className="text-left">
                        <DialogTitle className="font-serif text-2xl leading-tight">
                            That time doesn't work?
                        </DialogTitle>
                        <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                            The place goes back on sale and the creator is asked
                            to pick another. Tell them why, or they'll pick the
                            same one.
                        </DialogDescription>
                    </DialogHeader>
                    <Textarea
                        rows={3}
                        value={slotReason}
                        onChange={(e) => setSlotReason(e.target.value)}
                        placeholder="e.g. the kitchen is closed that afternoon — anything after 6pm works"
                        data-testid={APPLICATION.declineSlotReason}
                        className="border-white/10 bg-background/60"
                    />
                    <DialogFooter className="flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setDecliningSlot(false)}
                            className="h-12 rounded-full border-white/15 bg-transparent px-5 sm:h-11"
                        >
                            Back
                        </Button>
                        <Button
                            type="button"
                            disabled={!slotReason.trim() || busy === "decline-slot"}
                            data-testid={APPLICATION.declineSlotSubmit}
                            onClick={() => {
                                setDecliningSlot(false);
                                act(
                                    "decline-slot",
                                    () =>
                                        api.post(
                                            `${slotBase}/collaborations/${id}/slot/decline`,
                                            { reason: slotReason.trim() },
                                        ),
                                    "The creator has been asked to pick another time",
                                );
                                setSlotReason("");
                            }}
                            className="h-12 rounded-full px-6 sm:h-11"
                        >
                            {busy === "decline-slot" && (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            )}
                            Ask for another time
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </DetailShell>
    );

    if (!standalone) return shell;
    return (
        <div className="min-h-screen bg-background text-foreground grain-page">
            <Navbar />
            <main className="mx-auto max-w-5xl px-6 py-12 md:py-16">{shell}</main>
        </div>
    );
}
