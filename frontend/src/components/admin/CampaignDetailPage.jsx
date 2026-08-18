// One campaign, at /admin/campaigns/:id.
//
// The console used to answer "which campaign is this" by highlighting a row.
// This is the screen that answers it: the brief, whose it is, who runs it, what
// it pays, the slots and who is in them, everyone who applied, what has been
// paid, and everything that has ever happened to it — with the actions that
// change any of those sitting next to the thing they change.
//
// Three calls rather than one. The detail, the applicants and the trail change
// at different rates and are refetched independently, so accepting one creator
// does not re-download the audit log.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
    CalendarDays,
    IndianRupee,
    MapPin,
    Pause,
    Play,
    Send,
    UserCog,
    Users,
    XCircle,
} from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { formatCompensation, isBarter, compensationLabel } from "@/lib/compensation";
import { isPrivate, visibilityLabel } from "@/lib/visibility";
import ExecutionBadge, { ExecutionNote } from "@/components/ExecutionBadge";
import BrandAvatar from "@/components/BrandAvatar";
import ImageUploadField from "@/components/ImageUploadField";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    ADMIN_CAMPAIGN_PAGE as IDS,
    ADMIN_DETAIL as DIDS,
    COVER,
} from "@/constants/testIds";
import {
    AuditTrail,
    DetailShell,
    Field,
    Panel,
    Section,
    Stat,
} from "@/components/admin/DetailPage";
import {
    CAMPAIGN_STATUS_META,
    INVITABLE_STATUSES,
    Pill,
    StatePill,
    formatDate,
    formatDateTime,
    formatRupees,
} from "@/components/admin/shared";
import { ConfirmDialog, CampaignEditDialog } from "@/components/admin/dialogs";
import InviteCreatorsDialog from "@/components/admin/InviteCreatorsDialog";
import { CollaborationLink, CreatorLink } from "@/components/admin/links";
import { PerformanceRollup, ReportActions } from "@/components/admin/Performance";
import { useAdminConsole } from "@/pages/AdminConsole";

// The applicant board's columns, in pipeline order. The server groups them;
// this names them.
// These keys are the ones GET /admin/campaigns/{id}/applicants actually
// returns — it spreads `_APPLICANT_BUCKETS` by name. They used to be
// active/completed/ended, which match nothing on the server, so every group
// resolved to undefined and the section rendered its empty state however many
// applicants a campaign had.
const GROUPS = [
    { key: "applied", label: "Waiting on us" },
    { key: "approved", label: "Approved" },
    { key: "rejected", label: "Declined & cancelled" },
];

export default function CampaignDetailPage() {
    const { id } = useParams();
    const { reloadCounts } = useAdminConsole();

    const [detail, setDetail] = useState(null);
    const [applicants, setApplicants] = useState(null);
    const [audit, setAudit] = useState(null);
    const [managers, setManagers] = useState([]);
    const [error, setError] = useState("");
    const [notFound, setNotFound] = useState(false);
    const [busy, setBusy] = useState(null);
    const [dialog, setDialog] = useState({ kind: null });

    const loadDetail = useCallback(async () => {
        try {
            const { data } = await api.get(`/admin/campaigns/${id}`);
            setDetail(data);
            setError("");
        } catch (err) {
            if (err?.response?.status === 404) setNotFound(true);
            else setError(formatApiError(err));
        }
    }, [id]);

    const loadApplicants = useCallback(async () => {
        try {
            const { data } = await api.get(`/admin/campaigns/${id}/applicants`);
            setApplicants(data);
        } catch {
            setApplicants({});
        }
    }, [id]);

    const loadAudit = useCallback(async () => {
        try {
            const { data } = await api.get("/admin/audit", {
                params: { campaign_id: id, limit: 200 },
            });
            setAudit(data);
        } catch {
            setAudit([]);
        }
    }, [id]);

    const loadAll = useCallback(async () => {
        await Promise.all([loadDetail(), loadApplicants(), loadAudit()]);
        reloadCounts?.();
    }, [loadDetail, loadApplicants, loadAudit, reloadCounts]);

    useEffect(() => {
        // Reset on id change or the previous campaign shows while the next loads.
        setDetail(null);
        setApplicants(null);
        setAudit(null);
        setNotFound(false);
        loadDetail();
        loadApplicants();
        loadAudit();
    }, [id, loadDetail, loadApplicants, loadAudit]);

    // Only fetched when the reassign control is opened — most visits never
    // touch it, and it is a whole extra request on a page that already makes
    // three.
    const loadManagers = useCallback(async () => {
        if (managers.length) return;
        try {
            const { data } = await api.get("/admin/managers");
            setManagers(Array.isArray(data) ? data : []);
        } catch {
            /* the picker stays empty and says so */
        }
    }, [managers.length]);

    const campaign = detail?.campaign;

    const act = async (key, request, message) => {
        setBusy(key);
        try {
            await request();
            notifySuccess(message);
            setDialog({ kind: null });
            await loadAll();
        } catch (err) {
            notifyError(err, { onRetry: () => act(key, request, message) });
        } finally {
            setBusy(null);
        }
    };

    const status = campaign?.status;
    const canPause = ["upcoming", "open", "in_progress"].includes(status);
    const canResume = status === "paused";
    const canReview = status === "pending_review";
    const canClose = !["closed", "completed"].includes(status);
    const canInvite = INVITABLE_STATUSES.includes(status);

    const groups = useMemo(() => {
        if (!applicants) return null;
        return GROUPS.map((g) => ({ ...g, rows: applicants[g.key] || [] }));
    }, [applicants]);

    const money = campaign ? formatCompensation(campaign) : null;

    return (
        <DetailShell
            testid={IDS.page}
            backTo="/admin/campaigns"
            backLabel="All campaigns"
            crumbs={[
                { key: "console", label: "Console", to: "/admin" },
                { key: "campaigns", label: "Campaigns", to: "/admin/campaigns" },
                // The brand sits between the list and this campaign because
                // that is what a campaign is inside — jumping to it is the
                // move an admin makes next about half the time.
                detail?.brand && {
                    key: "brand",
                    label: detail.brand.business_name || "Brand",
                    to: `/admin/brands/${detail.brand.user_id}`,
                },
                { key: "campaign", label: campaign?.title || "Campaign" },
            ]}
            kicker={campaign?.brand_name || "Campaign"}
            title={campaign?.title || "Campaign"}
            loading={!detail && !error && !notFound}
            error={error}
            notFound={notFound}
            notFoundMessage="This campaign doesn't exist, or it was removed."
            subtitle={
                campaign && (
                    <>
                        <Pill
                            meta={CAMPAIGN_STATUS_META}
                            value={status}
                            testid={IDS.status}
                        />
                        {campaign.area && (
                            <span className="inline-flex items-center gap-1.5">
                                <MapPin className="h-3.5 w-3.5" />
                                {campaign.area}
                            </span>
                        )}
                        <span
                            data-testid={IDS.compensation}
                            className="inline-flex items-center gap-1.5"
                        >
                            {isBarter(campaign) ? (
                                "Barter"
                            ) : (
                                <>
                                    <IndianRupee className="h-3.5 w-3.5" />
                                    {money.amount ?? "—"} · {compensationLabel(campaign)}
                                </>
                            )}
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                            <CalendarDays className="h-3.5 w-3.5" />
                            {campaign.campaign_type === "personal_table"
                                ? `${formatDate(campaign.start_date)} – ${formatDate(campaign.end_date)}`
                                : formatDate(campaign.event_date)}
                        </span>
                    </>
                )
            }
            aside={
                campaign && (
                    <>
                        {canReview && (
                            <>
                                <Button
                                    data-testid={DIDS.action("approve")}
                                    disabled={busy === "approve"}
                                    onClick={() =>
                                        act(
                                            "approve",
                                            () => api.post(`/admin/campaigns/${id}/approve`),
                                            "Campaign is live",
                                        )
                                    }
                                    className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                                >
                                    Approve
                                </Button>
                                <Button
                                    variant="outline"
                                    data-testid={DIDS.action("reject")}
                                    onClick={() => setDialog({ kind: "reject" })}
                                    className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                >
                                    Send back
                                </Button>
                            </>
                        )}
                        {canPause && (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("pause")}
                                onClick={() => setDialog({ kind: "pause" })}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                <Pause className="mr-2 h-4 w-4" />
                                Pause
                            </Button>
                        )}
                        {canResume && (
                            <Button
                                data-testid={DIDS.action("resume")}
                                disabled={busy === "resume"}
                                onClick={() =>
                                    act(
                                        "resume",
                                        () => api.post(`/admin/campaigns/${id}/resume`, {}),
                                        "Back on the feed",
                                    )
                                }
                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                <Play className="mr-2 h-4 w-4" />
                                Resume
                            </Button>
                        )}
                        {canInvite && (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("invite")}
                                onClick={() => setDialog({ kind: "invite" })}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                <Send className="mr-2 h-4 w-4" />
                                Invite
                            </Button>
                        )}
                        <Button
                            variant="outline"
                            data-testid={DIDS.action("edit")}
                            onClick={() => setDialog({ kind: "edit" })}
                            className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                        >
                            Edit
                        </Button>
                        {canClose && (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("close")}
                                onClick={() => setDialog({ kind: "close" })}
                                className="rounded-full border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10"
                            >
                                <XCircle className="mr-2 h-4 w-4" />
                                Close
                            </Button>
                        )}
                    </>
                )
            }
        >
            {detail && (
                <>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <Stat
                            testid={DIDS.stat("filled")}
                            label="Filled"
                            value={`${detail.totals.filled_slots}/${detail.totals.creators_needed}`}
                            highlight={detail.totals.spots_left > 0}
                        />
                        <Stat
                            testid={DIDS.stat("slots")}
                            label="Slot capacity"
                            value={`${detail.totals.slot_booked}/${detail.totals.slot_capacity}`}
                        />
                        <Stat
                            testid={DIDS.stat("paid")}
                            label="Paid out"
                            value={`₹${formatRupees(detail.totals.paid_out)}`}
                        />
                        <Stat
                            testid={DIDS.stat("committed")}
                            label="Still owed"
                            value={`₹${formatRupees(detail.totals.committed)}`}
                        />
                    </div>

                    <div className="grid gap-8 lg:grid-cols-3">
                        <Section id="brief" title="The brief" className="lg:col-span-2">
                            <Panel className="space-y-6">
                                <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                                    {campaign.brief}
                                </p>
                                <div>
                                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                        Deliverables
                                    </p>
                                    <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed">
                                        {campaign.deliverables}
                                    </p>
                                </div>
                                <dl className="grid gap-5 border-t border-white/10 pt-6 sm:grid-cols-3">
                                    <Field label="Category">{campaign.category}</Field>
                                    <Field label="Type">
                                        {(campaign.campaign_type || "—").replace(/_/g, " ")}
                                    </Field>
                                    <Field label="Compensation">
                                        {compensationLabel(campaign)}
                                    </Field>
                                    <Field label="Visibility">
                                        {visibilityLabel(campaign)}
                                        {isPrivate(campaign) && (
                                            <span className="mt-1 block text-xs text-muted-foreground">
                                                Invite-only — reachable through invites,
                                                never through browse or the share page.
                                            </span>
                                        )}
                                    </Field>
                                    <Field label="Venue" className="sm:col-span-3">
                                        {campaign.venue_address}
                                    </Field>
                                    <Field label="Arrival" className="sm:col-span-2">
                                        {campaign.venue_instructions}
                                    </Field>
                                    <Field label="On-site contact">
                                        {campaign.on_site_contact}
                                    </Field>
                                </dl>
                                {campaign.review_reason && (
                                    <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-xs leading-relaxed text-amber-200">
                                        Sent back: {campaign.review_reason}
                                    </p>
                                )}
                                {campaign.pause_reason && (
                                    <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-xs leading-relaxed text-amber-200">
                                        Paused: {campaign.pause_reason}
                                    </p>
                                )}
                            </Panel>
                        </Section>

                        <div className="space-y-8">
                            <Section id="cover" title="Cover image">
                                <Panel>
                                    {/* The same control the brand's own form
                                        uses, against the same route — an admin
                                        fixing a brief should not be editing it
                                        through a different door. */}
                                    <ImageUploadField
                                        hint="Shown on the brief and on shared links. Optional — a brief with none gets a generated cover."
                                        shape="cover"
                                        value={campaign.cover_image_url}
                                        onChange={loadDetail}
                                        endpoint={`/brand/campaigns/${id}/cover`}
                                        responseKey="cover_image_url"
                                        testids={{
                                            input: COVER.input,
                                            choose: COVER.choose,
                                            remove: COVER.remove,
                                            preview: COVER.preview,
                                            error: COVER.error,
                                        }}
                                    />
                                </Panel>
                            </Section>

                            <Section id="brand" title="Brand">
                                <Panel>
                                    <Link
                                        to={`/admin/brands/${detail.brand.user_id}`}
                                        data-testid={IDS.brandLink}
                                        className="flex items-center gap-3 font-serif text-xl transition-colors duration-200 hover:text-ember-500"
                                    >
                                        <BrandAvatar brand={detail.brand} />
                                        {detail.brand.business_name || "Unknown brand"}
                                    </Link>
                                    <dl className="mt-5 space-y-4">
                                        <Field label="Verification">
                                            {detail.brand.verified
                                                ? "Verified"
                                                : (detail.brand.verification_state || "").replace(
                                                      /_/g,
                                                      " ",
                                                  )}
                                        </Field>
                                        <Field label="Contact">
                                            {detail.brand.contact_person_name}
                                        </Field>
                                        <Field label="Phone">
                                            {detail.brand.contact_phone}
                                        </Field>
                                        <Field label="Email">{detail.brand.contact_email}</Field>
                                    </dl>
                                </Panel>
                            </Section>

                            <Section
                                id="manager"
                                title="Campaign manager"
                                action={
                                    <button
                                        type="button"
                                        data-testid={DIDS.action("reassign")}
                                        onClick={() => {
                                            loadManagers();
                                            setDialog({ kind: "reassign" });
                                        }}
                                        className="inline-flex min-h-[2.75rem] items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 md:min-h-0"
                                    >
                                        <UserCog className="h-3.5 w-3.5" />
                                        Reassign
                                    </button>
                                }
                            >
                                <Panel>
                                    {/* Who runs it sits above who runs it *for*
                                        us: assigning a WeAre manager is what
                                        makes a campaign ours, so the two belong
                                        in one place or they read as unrelated. */}
                                    <div className="mb-4 flex flex-wrap items-center gap-3">
                                        <ExecutionBadge campaign={campaign} />
                                        <ExecutionNote campaign={campaign} className="min-w-0 text-xs" />
                                    </div>
                                    <p
                                        data-testid={IDS.managerName}
                                        className="font-serif text-xl"
                                    >
                                        {campaign.manager_name || "Nobody assigned"}
                                    </p>
                                    <dl className="mt-5 space-y-4">
                                        <Field label="Phone">{campaign.manager_phone}</Field>
                                        <Field label="Email">{campaign.manager_email}</Field>
                                    </dl>
                                </Panel>
                            </Section>
                        </div>
                    </div>

                    {/* Above the slots: this is the answer to "did it work",
                        which is what anyone opening a finished campaign came
                        for. */}
                    <PerformanceRollup
                        performance={detail.performance}
                        scope="campaign"
                        action={
                            <ReportActions
                                campaignId={id}
                                showcase={campaign.showcase}
                                busy={busy === "showcase"}
                                onToggleShowcase={() =>
                                    act(
                                        "showcase",
                                        () =>
                                            api.post(`/admin/campaigns/${id}/showcase`, {
                                                showcase: !campaign.showcase,
                                            }),
                                        campaign.showcase
                                            ? "Removed from showcase"
                                            : "Marked as showcase",
                                    )
                                }
                            />
                        }
                    />

                    <Section
                        id="slots"
                        title="Slots"
                        count={detail.slots.length}
                    >
                        {detail.slots.length === 0 ? (
                            <p
                                data-testid={IDS.slotsEmpty}
                                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground grain-surface"
                            >
                                No slots yet. The campaign manager sets these once the brief is
                                approved — until then nobody can book a time.
                            </p>
                        ) : (
                            <ul className="divide-y divide-white/10 rounded-md border border-white/10 bg-card grain-surface">
                                {detail.slots.map((s) => (
                                    <li
                                        key={s.id}
                                        data-testid={IDS.slot(s.id)}
                                        className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                    >
                                        <span className="w-56 flex-none text-sm">
                                            {formatDateTime(s.starts_at)}
                                            {s.ends_at ? ` – ${formatDateTime(s.ends_at)}` : ""}
                                        </span>
                                        <span className="flex-none text-xs uppercase tracking-[0.18em] text-muted-foreground">
                                            {s.booked_count}/{s.capacity} booked
                                        </span>
                                        <span className="flex min-w-0 flex-1 flex-wrap gap-2">
                                            {s.bookings.length === 0 ? (
                                                <span className="text-xs text-muted-foreground">
                                                    Nobody yet
                                                </span>
                                            ) : (
                                                s.bookings.map((b) => (
                                                    <Link
                                                        key={b.collaboration_id}
                                                        to={`/admin/collaborations/${b.collaboration_id}`}
                                                        data-testid={IDS.slotBooking(
                                                            b.collaboration_id,
                                                        )}
                                                        className="rounded-full border border-white/10 px-2.5 py-1 text-xs transition-colors duration-200 hover:border-ember-500 hover:text-ember-500"
                                                    >
                                                        {b.creator_name || "Creator"}
                                                    </Link>
                                                ))
                                            )}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </Section>

                    <Section
                        id="applicants"
                        title="Applicants"
                        count={
                            groups
                                ? groups.reduce((n, g) => n + g.rows.length, 0)
                                : undefined
                        }
                    >
                        {!groups ? null : groups.every((g) => g.rows.length === 0) ? (
                            <p
                                data-testid={IDS.applicantsEmpty}
                                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground grain-surface"
                            >
                                Nobody has applied yet. Invite creators, or wait — a brief
                                usually takes a day or two to gather applications.
                            </p>
                        ) : (
                            <div className="space-y-8">
                                {groups
                                    .filter((g) => g.rows.length > 0)
                                    .map((g) => (
                                        <div
                                            key={g.key}
                                            data-testid={IDS.applicantGroup(g.key)}
                                        >
                                            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                                {g.label}
                                                <span className="ml-2 text-ember-500">
                                                    {g.rows.length}
                                                </span>
                                            </p>
                                            <ul className="mt-3 divide-y divide-white/10 rounded-md border border-white/10 bg-card grain-surface">
                                                {g.rows.map((a) => (
                                                    <li
                                                        key={a.collaboration_id}
                                                        data-testid={IDS.applicant(
                                                            a.collaboration_id,
                                                        )}
                                                        className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                                    >
                                                        {/* Flat on this endpoint — there is no
                                                            nested `creator` block here, unlike the
                                                            brand's board. */}
                                                        <CreatorLink
                                                            id={a.creator_id}
                                                            name={a.name}
                                                            className="min-w-0 flex-1 text-sm"
                                                        />
                                                        <span className="flex-none text-xs text-muted-foreground">
                                                            quoted ₹
                                                            {formatRupees(a.quoted_rate)}
                                                            {a.agreed_amount != null
                                                                ? ` · agreed ₹${formatRupees(a.agreed_amount)}`
                                                                : ""}
                                                        </span>
                                                        <StatePill state={a.state} />
                                                        <Link
                                                            to={`/admin/applications/${a.collaboration_id}`}
                                                            className="flex-none text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                                                        >
                                                            Open
                                                        </Link>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    ))}
                            </div>
                        )}
                    </Section>

                    <Section id="payments" title="Payments" count={detail.payments.length}>
                        {detail.payments.length === 0 ? (
                            <p
                                data-testid={IDS.paymentsEmpty}
                                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground grain-surface"
                            >
                                No payments yet. One is raised when a collaboration reaches
                                payment.
                            </p>
                        ) : (
                            <ul className="divide-y divide-white/10 rounded-md border border-white/10 bg-card grain-surface">
                                {detail.payments.map((p) => (
                                    <li
                                        key={p.id}
                                        data-testid={IDS.payment(p.id)}
                                        className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                    >
                                        <span className="min-w-0 flex-1 text-sm">
                                            <CreatorLink
                                                id={p.creator_id}
                                                name={p.creator_name}
                                            />
                                            <CollaborationLink
                                                id={p.collaboration_id}
                                                className="ml-3 text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                            >
                                                application
                                            </CollaborationLink>
                                        </span>
                                        <span className="flex-none text-sm">
                                            ₹{formatRupees(p.creator_payout)}
                                        </span>
                                        <span className="flex-none text-xs uppercase tracking-[0.18em] text-muted-foreground">
                                            {p.state}
                                        </span>
                                        <span className="w-40 flex-none text-xs text-muted-foreground">
                                            {p.paid_at ? formatDateTime(p.paid_at) : "—"}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </Section>

                    <Section id="audit" title="Everything that happened" count={audit?.length}>
                        <AuditTrail
                            rows={audit}
                            formatWhen={formatDateTime}
                            emptyMessage="Nothing has happened on this campaign yet."
                        />
                    </Section>
                </>
            )}

            {/* ---- dialogs ---- */}
            <ConfirmDialog
                open={dialog.kind === "reject"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Send back"
                title={campaign?.title}
                description="The brand is told what you write here, and it's what they'll fix before resubmitting."
                confirmLabel="Send back"
                submitting={busy === "reject"}
                onSubmit={(body) =>
                    act(
                        "reject",
                        () => api.post(`/admin/campaigns/${id}/reject`, body),
                        "Sent back to the brand",
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "pause"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Pause"
                title={campaign?.title}
                description="Stops new applications. Work already under way carries on, and resuming puts it back where it was."
                confirmLabel="Pause"
                submitting={busy === "pause"}
                onSubmit={(body) =>
                    act(
                        "pause",
                        () => api.post(`/admin/campaigns/${id}/pause`, body),
                        "Paused",
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "close"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Close"
                title={campaign?.title}
                description="Ends the campaign. Applications stop and it leaves the feed for good — this cannot be undone."
                confirmLabel="Close campaign"
                destructive
                submitting={busy === "close"}
                onSubmit={(body) =>
                    act("close", () => api.post(`/admin/campaigns/${id}/close`, body), "Closed")
                }
            />
            <CampaignEditDialog
                campaign={campaign}
                open={dialog.kind === "edit"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                submitting={busy === "edit"}
                onSubmit={(changes) =>
                    act(
                        "edit",
                        () => api.patch(`/admin/campaigns/${id}`, changes),
                        "Campaign updated",
                    )
                }
            />
            <InviteCreatorsDialog
                campaign={campaign}
                open={dialog.kind === "invite"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                onSent={loadAll}
            />
            <ReassignManagerDialog
                open={dialog.kind === "reassign"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                managers={managers}
                currentId={campaign?.manager_id}
                submitting={busy === "reassign"}
                onSubmit={(managerUserId) =>
                    act(
                        "reassign",
                        () =>
                            api.post(`/admin/campaigns/${id}/assign-manager`, {
                                manager_user_id: managerUserId,
                            }),
                        "Manager reassigned",
                    )
                }
            />
        </DetailShell>
    );
}

/**
 * Hand a campaign to a WeAre manager.
 *
 * Campaigns default to the brand's own person, so this is how one moves to
 * staff. Its own dialog rather than ConfirmDialog: that one collects a reason
 * in a textarea, and this collects a choice from a list. Kept local to this
 * page — it is the only place a campaign is reassigned.
 */
function ReassignManagerDialog({
    open,
    onOpenChange,
    managers,
    currentId,
    onSubmit,
    submitting,
}) {
    const [picked, setPicked] = useState("");

    useEffect(() => {
        if (open) setPicked(currentId || "");
    }, [open, currentId]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DIDS.action("reassign-dialog")}
                className="max-w-md rounded-md border border-white/10 bg-card grain-surface"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Reassign
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        Who runs this campaign
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        They get the roster, the daysheet and the check-in screen, and the
                        brand is told who to contact.
                    </DialogDescription>
                </DialogHeader>

                <form
                    noValidate
                    className="mt-4 space-y-5"
                    onSubmit={(e) => {
                        e.preventDefault();
                        if (picked) onSubmit(picked);
                    }}
                >
                    <Select value={picked} onValueChange={setPicked}>
                        <SelectTrigger
                            data-testid={DIDS.action("reassign-picker")}
                            aria-label="Campaign manager"
                            className="h-11 rounded-md border-white/10 bg-background/60"
                        >
                            <SelectValue placeholder="Pick a manager" />
                        </SelectTrigger>
                        <SelectContent className="rounded-md border-white/10 bg-card grain-surface">
                            {managers.map((m) => (
                                <SelectItem key={m.user_id} value={m.user_id}>
                                    {m.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {managers.length === 0 && (
                        <p className="text-xs leading-relaxed text-muted-foreground">
                            There are no WeAre managers yet. Create one first — until then a
                            campaign stays with the brand's own person.
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Back
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            disabled={submitting || !picked || picked === currentId}
                            data-testid={DIDS.action("reassign-submit")}
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {submitting ? "Reassigning…" : "Reassign"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
