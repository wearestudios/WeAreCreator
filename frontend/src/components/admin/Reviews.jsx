// The three review queues: creators, campaigns, brands.
//
// Same shape each time — a list of things waiting, each expanding to whatever
// you need to make the call, with approve and reject inline. They are separate
// tabs rather than one list because the three decisions need different things
// in front of you: a creator's Instagram, a campaign's brief, a brand's
// paperwork.
//
// Approving is one tap. Rejecting always opens a dialog and always requires a
// reason, because the person on the other end is told what it said.
import React, { useCallback, useEffect, useState } from "react";
import { notifyError } from "@/lib/feedback";
import {
    Building2,
    CheckCircle2,
    ChevronDown,
    ExternalLink,
    Instagram,
    Sparkles,
    XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ADMIN_REVIEWS as IDS } from "@/constants/testIds";
import { ConfirmDialog } from "./dialogs";
import { useOptimisticList } from "./useOptimistic";
import {
    CAMPAIGN_STATUS_META,
    CreatorAvatar,
    EmptyState,
    ListSkeleton,
    Pill,
    SectionHeader,
    formatCompact,
    formatDate,
    formatRupees,
    timeAgo,
} from "./shared";

/**
 * One review queue. The three tabs differ only in what they fetch, what each
 * row says, and what the two buttons call — so that is all `config` carries.
 */
function ReviewQueue({ config, onChanged }) {
    const { rows, setRows, removeOptimistically, isBusy } = useOptimisticList(null);
    const [openId, setOpenId] = useState(null);
    const [confirm, setConfirm] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get(config.endpoint);
            setRows(config.filter ? data.filter(config.filter) : data);
        } catch (e) {
            notifyError(e);
            setRows([]);
        }
    }, [config, setRows]);

    useEffect(() => {
        load();
    }, [load]);

    const approve = (row) => {
        const id = config.idOf(row);
        removeOptimistically(id, () => api.post(config.approvePath(row)), {
            successMessage: config.approvedMessage(row),
            onDone: () => onChanged?.(),
        });
    };

    const reject = (row) => {
        const id = config.idOf(row);
        setConfirm({
            row,
            onSubmit: async (body) => {
                setSubmitting(true);
                const ok = await removeOptimistically(
                    id,
                    () => api.post(config.rejectPath(row), body),
                    { successMessage: config.rejectedMessage(row), onDone: () => onChanged?.() },
                );
                setSubmitting(false);
                if (ok) setConfirm(null);
            },
        });
    };

    const count = rows?.length ?? 0;

    return (
        <section data-testid={IDS.section(config.kind)}>
            <SectionHeader
                kicker={config.kicker}
                title={count === 0 && rows ? config.clearTitle : config.title}
                blurb={config.blurb}
                onRefresh={load}
                refreshTestId={IDS.refresh(config.kind)}
            />

            {config.note && rows && count > 0 && (
                <p
                    data-testid={IDS.blockedNote}
                    className="mt-6 rounded-md border border-ember-500/30 bg-ember-500/10 px-5 py-4 text-sm leading-relaxed text-ember-500"
                >
                    {config.note}
                </p>
            )}

            <div className="mt-6">
                {!rows ? (
                    <ListSkeleton rows={4} testid={IDS.skeleton(config.kind)} />
                ) : count === 0 ? (
                    <EmptyState testid={IDS.empty(config.kind)} Icon={CheckCircle2}>
                        {config.emptyText}
                    </EmptyState>
                ) : (
                    <ul
                        data-testid={IDS.list(config.kind)}
                        className="space-y-3"
                    >
                        {rows.map((row) => {
                            const id = config.idOf(row);
                            const open = openId === id;
                            const busy = isBusy(id);
                            return (
                                <li
                                    key={id}
                                    data-testid={IDS.row(id)}
                                    className="overflow-hidden rounded-md border border-white/10 bg-card grain-surface"
                                >
                                    <button
                                        type="button"
                                        aria-expanded={open}
                                        onClick={() => setOpenId(open ? null : id)}
                                        data-testid={IDS.expand(id)}
                                        className="flex w-full items-start gap-4 p-5 text-left transition-colors duration-200 hover:bg-white/5"
                                    >
                                        {config.renderAvatar?.(row)}
                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                                                {config.renderBadge?.(row)}
                                                <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                                                    waiting {timeAgo(config.since(row))}
                                                </span>
                                            </div>
                                            <p className="mt-1.5 truncate text-sm text-foreground">
                                                {config.primary(row)}
                                            </p>
                                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                                                {config.secondary(row)}
                                            </p>
                                        </div>
                                        <ChevronDown
                                            className={
                                                "mt-1 h-4 w-4 flex-none text-muted-foreground transition-transform duration-200 " +
                                                (open ? "rotate-180" : "")
                                            }
                                        />
                                    </button>

                                    {open && (
                                        <div
                                            data-testid={IDS.detail(id)}
                                            className="border-t border-white/10 px-5 py-5"
                                        >
                                            {config.renderDetail(row)}
                                        </div>
                                    )}

                                    <div className="flex flex-col gap-2 border-t border-white/10 p-4 sm:flex-row sm:justify-end">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            disabled={busy}
                                            onClick={() => reject(row)}
                                            data-testid={IDS.reject(id)}
                                            className="h-11 rounded-full border-red-500/30 bg-transparent px-5 text-sm text-red-300 hover:bg-red-500/10 hover:text-red-200 sm:h-9"
                                        >
                                            <XCircle className="mr-1.5 h-4 w-4" />
                                            {config.rejectLabel}
                                        </Button>
                                        <Button
                                            type="button"
                                            disabled={busy}
                                            onClick={() => approve(row)}
                                            data-testid={IDS.approve(id)}
                                            className="h-11 rounded-full bg-ember-500 px-5 text-sm text-black hover:bg-ember-400 sm:h-9"
                                        >
                                            <CheckCircle2 className="mr-1.5 h-4 w-4" />
                                            {config.approveLabel}
                                        </Button>
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            {rows && count > 0 && (
                <p
                    data-testid={IDS.count(config.kind)}
                    className="mt-4 text-xs uppercase tracking-[0.18em] text-muted-foreground"
                >
                    {count} waiting
                </p>
            )}

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                destructive
                kicker={config.rejectKicker}
                title={confirm ? config.rejectTitle(confirm.row) : ""}
                description={config.rejectDescription}
                placeholder="What should they know?"
                confirmLabel={config.rejectLabel}
                onSubmit={(body) => confirm?.onSubmit(body)}
            />
        </section>
    );
}

// --- Creators ---------------------------------------------------------------

export function CreatorReviews({ onChanged }) {
    return (
        <ReviewQueue
            onChanged={onChanged}
            config={{
                kind: "creators",
                endpoint: "/admin/creators/pending",
                kicker: "Creator reviews",
                title: "Pending creator approvals",
                clearTitle: "No creators waiting.",
                blurb:
                    "Nobody can pitch on a brief until we've approved them, so this queue is the thing standing between a creator and their first job.",
                emptyText: "Inbox zero — every creator who finished signing up has an answer.",
                idOf: (r) => r.user_id,
                since: (r) => r.created_at,
                primary: (r) => r.name || "Unnamed creator",
                secondary: (r) =>
                    [
                        r.instagram_handle ? `@${r.instagram_handle}` : null,
                        r.city,
                        typeof r.follower_count === "number"
                            ? `${formatCompact(r.follower_count)} followers`
                            : null,
                    ]
                        .filter(Boolean)
                        .join(" · "),
                renderAvatar: (r) => <CreatorAvatar creator={r} size="h-11 w-11" />,
                renderDetail: (r) => (
                    <div className="space-y-4 text-sm">
                        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                            {[
                                ["Email", r.email],
                                ["Phone", r.phone],
                                ["City", r.city],
                                ["Area", r.address],
                                [
                                    "Base rate",
                                    r.base_rate != null ? `₹${formatRupees(r.base_rate)}` : null,
                                ],
                                [
                                    "Followers",
                                    typeof r.follower_count === "number"
                                        ? r.follower_count.toLocaleString("en-IN")
                                        : null,
                                ],
                                ["Joined", formatDate(r.created_at)],
                            ]
                                .filter(([, v]) => v)
                                .map(([label, value]) => (
                                    <div key={label}>
                                        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            {label}
                                        </dt>
                                        <dd className="mt-1 break-words">{value}</dd>
                                    </div>
                                ))}
                        </dl>

                        {r.niches?.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                                {r.niches.map((n) => (
                                    <span
                                        key={n}
                                        className="rounded-full bg-ember-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-ember-500"
                                    >
                                        {n}
                                    </span>
                                ))}
                            </div>
                        )}

                        {/* The single most useful thing on this screen: you
                            cannot vet a creator without looking at their feed. */}
                        {r.instagram_handle && (
                            <a
                                href={
                                    r.instagram_profile_url ||
                                    `https://instagram.com/${r.instagram_handle}`
                                }
                                target="_blank"
                                rel="noreferrer"
                                data-testid={IDS.instagram(r.user_id)}
                                className="inline-flex h-11 items-center gap-2 rounded-md border border-white/15 px-4 text-sm transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                            >
                                <Instagram className="h-4 w-4" />
                                Open @{r.instagram_handle}
                                <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                        )}
                    </div>
                ),
                approveLabel: "Approve",
                rejectLabel: "Reject",
                approvePath: (r) => `/admin/creators/${r.user_id}/approve`,
                rejectPath: (r) => `/admin/creators/${r.user_id}/reject`,
                approvedMessage: (r) => `${r.name || "Creator"} verified`,
                rejectedMessage: (r) => `${r.name || "Creator"} rejected`,
                rejectKicker: "Reject creator",
                rejectTitle: (r) => `Reject ${r.name || "this creator"}?`,
                rejectDescription:
                    "They're told why, and briefs stay closed to them until we approve. They can fix their profile and come back.",
            }}
        />
    );
}

// --- Campaigns --------------------------------------------------------------

export function CampaignReviews({ onChanged }) {
    return (
        <ReviewQueue
            onChanged={onChanged}
            config={{
                kind: "campaigns",
                endpoint: "/admin/campaigns/pending",
                kicker: "Campaign reviews",
                title: "Briefs waiting to go live",
                clearTitle: "No briefs waiting.",
                blurb:
                    "A campaign reaches creators when it's approved here, and not before. Read the brief; it's what a creator will act on.",
                emptyText: "Nothing submitted for review.",
                idOf: (r) => r.id,
                since: (r) => r.submitted_for_review_at || r.created_at,
                primary: (r) => r.title,
                secondary: (r) =>
                    [
                        r.brand_name || "Unknown brand",
                        r.budget_per_creator != null
                            ? `₹${formatRupees(r.budget_per_creator)} per creator`
                            : null,
                        r.area,
                    ]
                        .filter(Boolean)
                        .join(" · "),
                renderBadge: (r) => (
                    <Pill meta={CAMPAIGN_STATUS_META} value="pending_review" />
                ),
                renderDetail: (r) => (
                    <div className="space-y-5 text-sm">
                        {/* A brand that lost its verification while the brief
                            sat here can't have it approved — say so up front. */}
                        {!r.brand_verified && (
                            <p className="rounded-md border border-ember-500/30 bg-ember-500/10 px-4 py-3 text-xs leading-relaxed text-ember-500">
                                {r.brand_name || "This brand"} isn't verified. Approve them
                                in Brand reviews first — this brief can't go live until
                                they are.
                            </p>
                        )}

                        {r.previous_review_reason && (
                            <p className="rounded-md border border-white/10 bg-background/60 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
                                Last time we sent this back: “{r.previous_review_reason}”
                            </p>
                        )}

                        <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                The brief
                            </p>
                            <p className="mt-2 whitespace-pre-wrap leading-relaxed">
                                {r.brief}
                            </p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                Deliverables
                            </p>
                            <p className="mt-2 whitespace-pre-wrap leading-relaxed">
                                {r.deliverables}
                            </p>
                        </div>

                        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                            {[
                                ["Brand", r.brand_name],
                                ["Type", (r.campaign_type || "").replace(/_/g, " ")],
                                [
                                    "Budget",
                                    r.budget_per_creator != null
                                        ? `₹${formatRupees(r.budget_per_creator)} per creator`
                                        : null,
                                ],
                                ["Creators needed", r.creators_needed],
                                ["Area", r.area],
                                ["Category", r.category],
                                // Whichever dates this type actually carries.
                                ["Event day", r.event_date ? formatDate(r.event_date) : null],
                                [
                                    "Booking window",
                                    r.start_date
                                        ? `${formatDate(r.start_date)} – ${formatDate(r.end_date)}`
                                        : null,
                                ],
                                ["Submitted", formatDate(r.submitted_for_review_at)],
                            ]
                                .filter(([, v]) => v)
                                .map(([label, value]) => (
                                    <div key={label}>
                                        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            {label}
                                        </dt>
                                        <dd className="mt-1 capitalize">{value}</dd>
                                    </div>
                                ))}
                        </dl>
                    </div>
                ),
                approveLabel: "Approve & publish",
                rejectLabel: "Send back",
                approvePath: (r) => `/admin/campaigns/${r.id}/approve`,
                rejectPath: (r) => `/admin/campaigns/${r.id}/reject`,
                approvedMessage: (r) => `“${r.title}” is live`,
                rejectedMessage: (r) => `“${r.title}” sent back to the brand`,
                rejectKicker: "Send back",
                rejectTitle: (r) => `Send “${r.title}” back?`,
                rejectDescription:
                    "It returns to the brand as a draft with your reason attached, so they can fix it and submit again.",
            }}
        />
    );
}

// --- Brands -----------------------------------------------------------------

export function BrandReviews({ onChanged }) {
    return (
        <ReviewQueue
            onChanged={onChanged}
            config={{
                kind: "brands",
                endpoint: "/admin/brands/pending",
                // Somebody we already refused is not waiting on us.
                filter: (r) => r.verification_state !== "rejected",
                kicker: "Brand reviews",
                title: "Pending brand approvals",
                clearTitle: "No brands waiting.",
                blurb:
                    "An unverified brand can draft campaigns but cannot submit one, so nothing they write reaches a creator until this is done.",
                note:
                    "These brands cannot post campaigns. They can write drafts, but submitting one is blocked until you verify them.",
                emptyText: "Every brand that signed up has an answer.",
                idOf: (r) => r.user_id,
                since: (r) => r.signed_up_at || r.created_at,
                primary: (r) => r.business_name || r.name || "Unnamed brand",
                secondary: (r) =>
                    [r.category, r.email || r.phone, (r.areas || []).join(", ")]
                        .filter(Boolean)
                        .join(" · "),
                renderAvatar: () => (
                    <span className="grid h-11 w-11 flex-none place-items-center rounded-md border border-white/10 bg-ember-500/10 text-ember-500">
                        <Building2 className="h-5 w-5" />
                    </span>
                ),
                renderDetail: (r) => (
                    <div className="space-y-4 text-sm">
                        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                            {[
                                ["Business name", r.business_name],
                                ["Contact name", r.name],
                                ["Email", r.email],
                                ["Phone", r.phone],
                                ["Category", r.category],
                                ["Areas", (r.areas || []).join(", ")],
                                ["Signed up", formatDate(r.signed_up_at || r.created_at)],
                                [
                                    "Terms accepted",
                                    r.terms_accepted_at ? formatDate(r.terms_accepted_at) : null,
                                ],
                            ]
                                .filter(([, v]) => v)
                                .map(([label, value]) => (
                                    <div key={label}>
                                        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            {label}
                                        </dt>
                                        <dd className="mt-1 break-words capitalize">{value}</dd>
                                    </div>
                                ))}
                        </dl>

                        {/* Briefs stacked up behind this decision make it urgent
                            in a way the signup date alone doesn't show. */}
                        {r.campaigns_awaiting_review > 0 && (
                            <p className="inline-flex items-center gap-2 rounded-md border border-ember-500/30 bg-ember-500/10 px-4 py-2.5 text-xs text-ember-500">
                                <Sparkles className="h-3.5 w-3.5" />
                                {r.campaigns_awaiting_review} brief
                                {r.campaigns_awaiting_review === 1 ? "" : "s"} queued behind
                                this decision
                            </p>
                        )}

                        {r.campaign_count > 0 && (
                            <p className="text-xs text-muted-foreground">
                                {r.campaign_count} campaign
                                {r.campaign_count === 1 ? "" : "s"} written so far.
                            </p>
                        )}
                    </div>
                ),
                approveLabel: "Verify",
                rejectLabel: "Reject",
                approvePath: (r) => `/admin/brands/${r.user_id}/verify`,
                rejectPath: (r) => `/admin/brands/${r.user_id}/reject`,
                approvedMessage: (r) => `${r.business_name || "Brand"} verified`,
                rejectedMessage: (r) => `${r.business_name || "Brand"} rejected`,
                rejectKicker: "Reject brand",
                rejectTitle: (r) => `Reject ${r.business_name || "this brand"}?`,
                rejectDescription:
                    "They're told why, and any briefs of theirs waiting for review go back to draft. They can fix it and reapply.",
            }}
        />
    );
}
