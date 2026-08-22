import React, { useCallback, useEffect, useState } from "react";
import ExecutionBadge from "@/components/ExecutionBadge";
import CampaignCover from "@/components/CampaignCover";
import { isPrivate } from "@/lib/visibility";
import { EXECUTION_FILTERS, executionOwner } from "@/lib/execution";
import { EXECUTION } from "@/constants/testIds";
import { Link, useNavigate } from "react-router-dom";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    ArrowRight,
    Building2,
    CalendarDays,
    Compass,
    Copy,
    Eye,
    IndianRupee,
    Loader2,
    Lock,
    MapPin,
    MessageSquare,
    Pause,
    Pencil,
    Play,
    Plus,
    Send,
    Sparkles,
    Trash2,
    Users,
    XCircle,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";
import { formatCompensation, isBarter } from "@/lib/compensation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { ListSkeleton } from "@/components/data/DenseView";
import { BRAND_CAMPAIGN_CONTROLS, CAMPAIGN_TEMPLATES as TEMPLATES, VISIBILITY } from "@/constants/testIds";
import { SaveAsTemplate } from "@/components/brand/CampaignTemplates";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { IST } from "@/lib/time";

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    real_estate: "Real Estate",
    fashion: "Fashion",
    travel: "Travel",
    wellness: "Wellness",
    lifestyle: "Lifestyle",
};

const STATUS_META = {
    draft: {
        label: "Draft",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
    // With us, not with creators — see publish_brand_campaign on the server.
    pending_review: {
        label: "In review",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    },
    upcoming: {
        label: "Upcoming",
        tone: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    },
    open: {
        label: "Live",
        tone: "bg-ember-500/15 text-ember-500 border-ember-500/30",
    },
    // Stopped by us, not over — see pause_campaign on the server.
    paused: {
        label: "Paused",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    },
    in_progress: {
        label: "In progress",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    completed: {
        label: "Completed",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    closed: {
        label: "Closed",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
};

const StatusPill = ({ status }) => {
    const meta = STATUS_META[status] || {
        label: status,
        tone: "bg-white/5 text-muted-foreground border-white/15",
    };
    return (
        <span
            data-testid={`brand-campaign-status-${status}`}
            className={
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                meta.tone
            }
        >
            {status === "open" && (
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-ember-500 animate-pulse" />
            )}
            {meta.label}
        </span>
    );
};

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN") : "—";

const formatDate = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            timeZone: IST,
        });
    } catch {
        return iso;
    }
};

const StatTile = ({ label, value, Icon, highlight }) => (
    <div
        className={
            "rounded-md border p-5 transition-colors duration-200 " +
            (highlight
                ? "border-ember-500/40 bg-ember-500/10"
                : "border-white/10 bg-card grain-surface")
        }
    >
        <div className="flex items-center justify-between">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {label}
            </p>
            {Icon && <Icon className="h-4 w-4 text-ember-500" />}
        </div>
        <div
            className={
                "mt-4 font-serif text-3xl md:text-4xl " +
                (highlight ? "text-ember-500" : "")
            }
        >
            {value}
        </div>
    </div>
);

export default function BrandDashboardView({ user, justOnboarded = false }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [busyId, setBusyId] = useState(null);
    const [confirm, setConfirm] = useState({ kind: null, campaign: null });
    // Pausing needs a reason the server insists on, so it gets its own dialog
    // rather than the yes/no AlertDialog the other two share.
    const [pausing, setPausing] = useState({ campaign: null, reason: "" });
    // Filtered in the browser rather than by refetching: the dashboard already
    // has every campaign this brand owns in hand, and a brand has tens of
    // them, not thousands. The server takes the same parameter for anything
    // that does need to ask.
    const [execution, setExecution] = useState("all");

    // Derived once: both the list and its empty state need to agree about
    // what the filter left behind.
    const visibleCampaigns = (data?.campaigns || []).filter(
        (c) => execution === "all" || executionOwner(c) === execution,
    );

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/brand/dashboard");
            setData(data);
            setError("");
        } catch (err) {
            setError(formatApiError(err));
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const runAction = async (campaign, fn, successMessage) => {
        setBusyId(campaign.id);
        try {
            await fn();
            notifySuccess(successMessage);
            setConfirm({ kind: null, campaign: null });
            await load();
        } catch (err) {
            notifyError(err, { onRetry: () => runAction(campaign, fn, successMessage) });
        } finally {
            setBusyId(null);
        }
    };

    const publish = (c) =>
        runAction(
            c,
            () => api.post(`/brand/campaigns/${c.id}/publish`),
            "Sent for review — we'll publish it once we've read it",
        );

    /**
     * "That one again, on a different day."
     *
     * Straight to the new draft's edit screen rather than back to the list:
     * the one thing a duplicate is missing is its dates, so leaving somebody
     * on a list with a new untitled draft on it is leaving them to find the
     * one field they have to fill in.
     */
    const duplicate = async (c) => {
        setBusyId(c.id);
        try {
            const { data } = await api.post(`/brand/campaigns/${c.id}/duplicate`, {});
            notifySuccess("Copied — set the dates and it's ready");
            navigate(`/campaigns/${data.id}/edit`);
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be duplicated." });
        } finally {
            setBusyId(null);
        }
    };

    const navigate = useNavigate();

    const closeCampaign = (c) =>
        runAction(
            c,
            () => api.post(`/brand/campaigns/${c.id}/close`, {}),
            "Campaign closed",
        );

    const deleteDraft = (c) =>
        runAction(c, () => api.delete(`/brand/campaigns/${c.id}`), "Draft deleted");

    // Pausing stops new applications. Work already under way carries on, and
    // resuming puts the campaign back in whichever state it was paused from.
    const pauseCampaign = async (c, reason) => {
        await runAction(
            c,
            () => api.post(`/brand/campaigns/${c.id}/pause`, { reason }),
            "Paused — no new applications until you resume",
        );
        setPausing({ campaign: null, reason: "" });
    };

    const resumeCampaign = (c) =>
        runAction(
            c,
            () => api.post(`/brand/campaigns/${c.id}/resume`, {}),
            "Back on the feed",
        );

    const profileMissing =
        data && (!data.profile || !data.profile.business_name);
    const businessName =
        data?.profile?.business_name || user.name || "Your brand";

    return (
        <div data-testid="dashboard-page" className="min-h-screen bg-background grain-page">
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-12 md:py-16">
                {!data && !error && (
                    <div data-testid="brand-dashboard-skeleton" aria-hidden="true">
                        <Skeleton className="h-3 w-40" />
                        <Skeleton className="mt-6 h-11 w-2/3 max-w-md" />
                        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <div
                                    key={i}
                                    className="rounded-lg border border-white/10 bg-card p-6 grain-surface"
                                >
                                    <Skeleton className="h-3 w-24" />
                                    <Skeleton className="mt-4 h-8 w-16" />
                                </div>
                            ))}
                        </div>
                        <div className="mt-12">
                            <ListSkeleton rows={3} />
                        </div>
                    </div>
                )}
                {error && (
                    <p
                        data-testid="brand-dashboard-error"
                        className="text-sm text-destructive"
                    >
                        {error}
                    </p>
                )}
                {data && (
                    <>
                        <header data-testid="brand-header" className="grid gap-6 md:grid-cols-12 md:items-end">
                            <div className="md:col-span-8">
                                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                    Brand · Bengaluru
                                </p>
                                <h1
                                    data-testid="brand-name-heading"
                                    className="mt-3 font-serif text-fluid-5xl leading-none tracking-tight"
                                >
                                    {businessName}
                                </h1>
                                {data.profile && (
                                    <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                                        {data.profile.category && (
                                            <span className="inline-flex items-center gap-1.5">
                                                <Building2 className="h-4 w-4" />
                                                {CAT_LABEL[data.profile.category] ||
                                                    data.profile.category}
                                            </span>
                                        )}
                                        {data.profile.areas?.length > 0 && (
                                            <span className="inline-flex flex-wrap items-center gap-1.5">
                                                <MapPin className="h-4 w-4" />
                                                {data.profile.areas.join(" · ")}
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                            <div className="flex flex-wrap items-center gap-3 md:col-span-4 md:justify-end">
                                <Link to="/onboarding/brand" data-testid="brand-header-edit">
                                    <Button
                                        variant="outline"
                                        className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                    >
                                        Edit brand
                                    </Button>
                                </Link>
                                <Link to="/brand/creators" data-testid="brand-header-browse-creators-btn">
                                    <Button
                                        variant="outline"
                                        className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                    >
                                        Browse creators
                                    </Button>
                                </Link>
                                <Link to="/campaigns/new" data-testid="brand-header-post-btn">
                                    <Button className="group rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                        <Plus className="mr-1 h-4 w-4" />
                                        Post a campaign
                                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </Button>
                                </Link>
                            </div>
                        </header>

                        {/* What happens next, said once, on the way in from
                            onboarding. A brand that has just filled in a form
                            and landed on an empty dashboard has no idea
                            whether anything is happening — and the honest
                            answer is "not until you post a brief, and then
                            not instantly", which is much better said than
                            discovered over three silent days. */}
                        {justOnboarded && (
                            <div
                                data-testid="brand-what-happens-next"
                                className="mt-8 rounded-md border border-ember-500/30 bg-ember-500/10 p-5 md:p-6"
                            >
                                <p className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-ember-500">
                                    <Sparkles className="h-4 w-4" />
                                    What happens next
                                </p>
                                <ol className="mt-4 space-y-3 text-sm leading-relaxed text-foreground/90">
                                    <li>
                                        <span className="text-ember-500">1 ·</span> We check
                                        your business details. That usually takes a working
                                        day, and we'll WhatsApp you either way.
                                    </li>
                                    <li>
                                        <span className="text-ember-500">2 ·</span> Post your
                                        first brief. You can write and save it now — it goes
                                        in front of creators once you're verified.
                                    </li>
                                    <li>
                                        <span className="text-ember-500">3 ·</span> Expect the
                                        first applications within a day or two of going live,
                                        and most of them inside the first week. A brief with a
                                        cover image and a clear fee fills faster than one
                                        without.
                                    </li>
                                </ol>
                                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                                    Nothing to chase in the meantime — we'll come to you.
                                </p>
                            </div>
                        )}

                        {profileMissing && (
                            <div
                                data-testid="brand-profile-incomplete"
                                className="mt-8 flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300"
                            >
                                <Sparkles className="mt-0.5 h-4 w-4 flex-none" />
                                <p>
                                    Finish your brand profile so creators know who they're working with.{" "}
                                    <Link
                                        to="/onboarding/brand"
                                        className="underline underline-offset-4 hover:no-underline"
                                    >
                                        Complete now →
                                    </Link>
                                </p>
                            </div>
                        )}

                        <section
                            data-testid="brand-stats-panel"
                            className="mt-10 grid gap-4 sm:grid-cols-2 md:grid-cols-4"
                        >
                            {/* The two tiles that mean "somebody do something" come first. */}
                            <StatTile
                                label="Waiting on you"
                                value={data.totals.awaiting_decision ?? 0}
                                Icon={Users}
                                highlight={(data.totals.awaiting_decision ?? 0) > 0}
                            />
                            <StatTile
                                label="Content to review"
                                value={data.totals.content_to_review ?? 0}
                                Icon={MessageSquare}
                                highlight={(data.totals.content_to_review ?? 0) > 0}
                            />
                            <StatTile
                                label="Live campaigns"
                                value={data.totals.live_campaigns}
                                Icon={Compass}
                            />
                            <StatTile
                                label="Applications received"
                                value={data.totals.total_applications}
                                Icon={Building2}
                            />
                        </section>

                        <section data-testid="brand-campaigns-section" className="mt-14">
                            <div className="flex items-baseline justify-between">
                                <div>
                                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                        Your campaigns
                                    </p>
                                    <h2 className="mt-3 font-serif text-fluid-4xl leading-none tracking-tight">
                                        Every brief you've posted.
                                    </h2>
                                </div>
                                <Link
                                    to="/campaigns/new"
                                    data-testid="brand-campaigns-post-link"
                                >
                                    <Button
                                        variant="outline"
                                        className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                    >
                                        <Plus className="mr-1.5 h-4 w-4" />
                                        New campaign
                                    </Button>
                                </Link>
                            </div>

                            {/* One chip per owner, plus "anyone". Three states
                                on a two-valued field, so a segmented control
                                rather than a select — there is nothing to
                                collapse into a dropdown. */}
                            <div
                                data-testid={EXECUTION.filter}
                                role="radiogroup"
                                aria-label="Filter campaigns by who runs them"
                                className="mt-8 flex flex-wrap gap-2"
                            >
                                {EXECUTION_FILTERS.map((opt) => {
                                    const on = execution === opt.value;
                                    return (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            role="radio"
                                            aria-checked={on}
                                            data-testid={EXECUTION.filterOption(opt.value)}
                                            onClick={() => setExecution(opt.value)}
                                            className={
                                                "min-h-[2.75rem] rounded-full border px-4 text-xs uppercase tracking-[0.15em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0 md:py-1.5 " +
                                                (on
                                                    ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                                    : "border-white/10 text-muted-foreground hover:border-white/25")
                                            }
                                        >
                                            {opt.label}
                                        </button>
                                    );
                                })}
                            </div>

                            <div className="mt-4 overflow-hidden rounded-md border border-white/10 bg-card grain-surface">
                                {data.campaigns.length > 0 && visibleCampaigns.length === 0 ? (
                                    <div
                                        data-testid="brand-campaigns-filtered-empty"
                                        className="px-6 py-12 text-center"
                                    >
                                        <p className="text-sm text-muted-foreground">
                                            No campaign here is{" "}
                                            {execution === "weare" ? "WeAre-run" : "brand-run"}.
                                        </p>
                                        <button
                                            type="button"
                                            onClick={() => setExecution("all")}
                                            className="mt-3 min-h-[2.75rem] text-xs uppercase tracking-[0.18em] text-ember-500 transition-colors duration-200 hover:text-ember-400 md:min-h-0"
                                        >
                                            Show all campaigns
                                        </button>
                                    </div>
                                ) : data.campaigns.length === 0 ? (
                                    <div
                                        data-testid="brand-campaigns-empty"
                                        className="flex flex-col items-center gap-3 px-6 py-16 text-center"
                                    >
                                        <Compass className="h-6 w-6 text-ember-500" />
                                        <p className="font-serif text-2xl">
                                            No campaigns yet.
                                        </p>
                                        <p className="max-w-md text-sm text-muted-foreground">
                                            Post your first paid brief and it will start
                                            reaching verified creators across Bengaluru immediately.
                                        </p>
                                        <Link to="/campaigns/new" className="mt-4">
                                            <Button className="rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                                <Plus className="mr-1 h-4 w-4" />
                                                Post a campaign
                                            </Button>
                                        </Link>
                                    </div>
                                ) : (
                                    <ul className="divide-y divide-white/10">
                                        {visibleCampaigns.map((c) => {
                                            const canBrowsePublicly =
                                                c.status === "open" || c.status === "upcoming";
                                            const busy = busyId === c.id;
                                            return (
                                                <li
                                                    key={c.id}
                                                    data-testid={`brand-campaign-row-${c.id}`}
                                                    className="flex flex-col gap-4 px-5 py-5 md:px-6 md:py-6"
                                                >
                                                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
                                                        {/* Small, but present: this is where a
                                                            brand notices a brief went out with
                                                            no picture on it. */}
                                                        <CampaignCover
                                                            campaign={c}
                                                            className="w-24 flex-none"
                                                        />
                                                        <div className="min-w-0 flex-1">
                                                            <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                                                {CAT_LABEL[c.category] || c.category || "—"}
                                                                {c.area ? ` · ${c.area}` : ""}
                                                                {c.start_date
                                                                    ? ` · ${formatDate(c.start_date)}${
                                                                          c.end_date
                                                                              ? " → " + formatDate(c.end_date)
                                                                              : ""
                                                                      }`
                                                                    : ""}
                                                            </div>
                                                            <div className="mt-1.5 truncate font-serif text-xl leading-tight text-foreground">
                                                                {c.title}
                                                            </div>
                                                            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                                                {/* The owner always knows which shelf a
                                                                    brief is on — a private one that the
                                                                    brand believes is public gets zero
                                                                    applicants and no explanation. */}
                                                                <span
                                                                    data-testid={VISIBILITY.badge(c.id)}
                                                                    className={
                                                                        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] " +
                                                                        (isPrivate(c)
                                                                            ? "border-ember-500/40 bg-ember-500/10 text-ember-500"
                                                                            : "border-white/10 text-muted-foreground")
                                                                    }
                                                                >
                                                                    {isPrivate(c) ? (
                                                                        <>
                                                                            <Lock className="h-3 w-3" />
                                                                            Invite-only
                                                                        </>
                                                                    ) : (
                                                                        "Public"
                                                                    )}
                                                                </span>
                                                                <span className="inline-flex items-center gap-1">
                                                                    {isBarter(c) ? (
                                                                        "Barter"
                                                                    ) : (
                                                                        <>
                                                                            <IndianRupee className="h-3.5 w-3.5" />
                                                                            {formatCompensation(c).amount ?? "—"}
                                                                            {" / creator"}
                                                                            {formatCompensation(c).suffix
                                                                                ? ` · ${formatCompensation(c).suffix}`
                                                                                : ""}
                                                                        </>
                                                                    )}
                                                                </span>
                                                                <span>·</span>
                                                                <span className="inline-flex items-center gap-1">
                                                                    <Users className="h-3.5 w-3.5" />
                                                                    {c.filled_slots ?? 0} of {c.creators_needed}{" "}
                                                                    confirmed
                                                                </span>
                                                            </div>
                                                        </div>

                                                        <div className="flex items-center gap-6 md:min-w-[240px] md:justify-end">
                                                            <Link
                                                                to={`/brand/campaigns/${c.id}/applicants`}
                                                                data-testid={`brand-campaign-applicants-link-${c.id}`}
                                                                className="group text-right transition-colors duration-200 hover:text-ember-500"
                                                            >
                                                                <div
                                                                    data-testid={`brand-campaign-applicants-${c.id}`}
                                                                    className="font-serif text-2xl leading-none"
                                                                >
                                                                    {c.applicant_count}
                                                                </div>
                                                                <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-muted-foreground group-hover:text-ember-500">
                                                                    {c.applicant_count === 1
                                                                        ? "applicant"
                                                                        : "applicants"}
                                                                </div>
                                                            </Link>
                                                            <div className="flex flex-col items-end gap-2">
                                                                <StatusPill status={c.status} />
                                                                <ExecutionBadge campaign={c} />
                                                                {c.awaiting_decision > 0 && (
                                                                    <span
                                                                        data-testid={`brand-campaign-awaiting-${c.id}`}
                                                                        className="inline-flex items-center gap-1.5 rounded-full border border-ember-500/40 bg-ember-500/10 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-ember-500"
                                                                    >
                                                                        {c.awaiting_decision} waiting on you
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Actions — a draft used to be a dead end here. */}
                                                    <div className="flex flex-wrap items-center gap-2 border-t border-white/10 pt-4">
                                                        <Link
                                                            to={`/brand/campaigns/${c.id}/applicants`}
                                                            data-testid={`brand-campaign-review-${c.id}`}
                                                        >
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                                            >
                                                                <Users className="mr-1.5 h-3.5 w-3.5" />
                                                                Applicants
                                                            </Button>
                                                        </Link>

                                                        {c.can_publish && (
                                                            <Button
                                                                size="sm"
                                                                disabled={busy}
                                                                data-testid={`brand-campaign-publish-${c.id}`}
                                                                onClick={() => publish(c)}
                                                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                                                            >
                                                                <Send className="mr-1.5 h-3.5 w-3.5" />
                                                                Send for review
                                                            </Button>
                                                        )}

                                                        {/* **"That one again."** Offered on every
                                                            campaign whatever its status, because the
                                                            one most worth repeating is the one that
                                                            finished. Lands as a draft with the dates
                                                            cleared, which is the only thing that
                                                            changes between one run and the next. */}
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            disabled={busy}
                                                            data-testid={TEMPLATES.duplicate(c.id)}
                                                            onClick={() => duplicate(c)}
                                                            className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                                        >
                                                            <Copy className="mr-1.5 h-3.5 w-3.5" />
                                                            Duplicate
                                                        </Button>

                                                        <SaveAsTemplate
                                                            campaignId={c.id}
                                                            defaultName={c.title}
                                                        />

                                                        {c.can_edit && (
                                                            <Link
                                                                to={`/campaigns/${c.id}/edit`}
                                                                data-testid={`brand-campaign-edit-${c.id}`}
                                                            >
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                                                >
                                                                    <Pencil className="mr-1.5 h-3.5 w-3.5" />
                                                                    Edit
                                                                </Button>
                                                            </Link>
                                                        )}

                                                        {canBrowsePublicly && (
                                                            <Link
                                                                to={`/campaigns/${c.id}`}
                                                                data-testid={`brand-campaign-view-${c.id}`}
                                                            >
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                                                >
                                                                    <Eye className="mr-1.5 h-3.5 w-3.5" />
                                                                    Preview
                                                                </Button>
                                                            </Link>
                                                        )}

                                                        {["upcoming", "open", "in_progress"].includes(
                                                            c.status,
                                                        ) && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={busy}
                                                                data-testid={BRAND_CAMPAIGN_CONTROLS.pause(
                                                                    c.id,
                                                                )}
                                                                onClick={() =>
                                                                    setPausing({
                                                                        campaign: c,
                                                                        reason: "",
                                                                    })
                                                                }
                                                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                                            >
                                                                <Pause className="mr-1.5 h-3.5 w-3.5" />
                                                                Pause
                                                            </Button>
                                                        )}

                                                        {c.status === "paused" && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={busy}
                                                                data-testid={BRAND_CAMPAIGN_CONTROLS.resume(
                                                                    c.id,
                                                                )}
                                                                onClick={() => resumeCampaign(c)}
                                                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                                            >
                                                                <Play className="mr-1.5 h-3.5 w-3.5" />
                                                                Resume
                                                            </Button>
                                                        )}

                                                        {c.can_close && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={busy}
                                                                data-testid={`brand-campaign-close-${c.id}`}
                                                                onClick={() =>
                                                                    setConfirm({ kind: "close", campaign: c })
                                                                }
                                                                className="rounded-full border-white/15 bg-transparent text-muted-foreground hover:bg-white/5 hover:text-foreground"
                                                            >
                                                                <XCircle className="mr-1.5 h-3.5 w-3.5" />
                                                                Close
                                                            </Button>
                                                        )}

                                                        {c.can_delete && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={busy}
                                                                data-testid={`brand-campaign-delete-${c.id}`}
                                                                onClick={() =>
                                                                    setConfirm({ kind: "delete", campaign: c })
                                                                }
                                                                className="rounded-full border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10"
                                                            >
                                                                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                                                                Delete
                                                            </Button>
                                                        )}

                                                        {busy && (
                                                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                                        )}
                                                    </div>
                                                </li>
                                            );
                                        })}
                                    </ul>
                                )}
                            </div>
                        </section>

                        <div className="mt-16 rounded-md border border-white/10 bg-card/40 p-6 text-sm text-muted-foreground">
                            <span className="text-foreground">Signed in as</span>{" "}
                            {/* Accounts created over WhatsApp have no email. */}
                            {user.email || user.phone || user.name} ·{" "}
                            <span className="uppercase tracking-[0.15em] text-ember-500">
                                {user.role}
                            </span>
                        </div>
                    </>
                )}
            </main>

            <Dialog
                open={pausing.campaign !== null}
                onOpenChange={(v) => !v && setPausing({ campaign: null, reason: "" })}
            >
                <DialogContent
                    data-testid={BRAND_CAMPAIGN_CONTROLS.pauseDialog}
                    className="rounded-md border border-white/10 bg-card grain-surface"
                >
                    <DialogHeader>
                        <DialogTitle className="font-serif text-2xl">
                            Pause this campaign?
                        </DialogTitle>
                        <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                            “{pausing.campaign?.title}” comes off the feed and stops taking
                            new applications. Creators already working on it carry on, and
                            resuming puts it back exactly where it was.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex flex-col gap-2">
                        <Textarea
                            rows={3}
                            value={pausing.reason}
                            onChange={(e) =>
                                setPausing((p) => ({ ...p, reason: e.target.value }))
                            }
                            placeholder="e.g. Kitchen closed for renovation until the 20th"
                            data-testid={BRAND_CAMPAIGN_CONTROLS.pauseReason}
                            aria-label="Why you're pausing"
                        />
                        <span className="text-[11px] text-muted-foreground">
                            A line for your own records and ours — it isn't shown to creators.
                        </span>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="ghost"
                            onClick={() => setPausing({ campaign: null, reason: "" })}
                            className="rounded-full"
                        >
                            Keep it running
                        </Button>
                        <Button
                            disabled={
                                pausing.reason.trim().length < 3 ||
                                busyId === pausing.campaign?.id
                            }
                            data-testid={BRAND_CAMPAIGN_CONTROLS.pauseConfirm}
                            onClick={() =>
                                pauseCampaign(pausing.campaign, pausing.reason.trim())
                            }
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            Pause campaign
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <AlertDialog
                open={confirm.kind !== null}
                onOpenChange={(v) => !v && setConfirm({ kind: null, campaign: null })}
            >
                <AlertDialogContent
                    data-testid="brand-campaign-confirm"
                    className="rounded-md border border-white/10 bg-card grain-surface"
                >
                    <AlertDialogHeader>
                        <AlertDialogTitle className="font-serif text-2xl">
                            {confirm.kind === "delete"
                                ? "Delete this draft?"
                                : "Close this campaign?"}
                        </AlertDialogTitle>
                        <AlertDialogDescription className="text-sm text-muted-foreground">
                            {confirm.kind === "delete" ? (
                                <>
                                    “{confirm.campaign?.title}” hasn't been published and has
                                    no applicants. This can't be undone.
                                </>
                            ) : (
                                <>
                                    “{confirm.campaign?.title}” will stop accepting
                                    applications. Anyone still waiting on a decision is told
                                    it's closed. Collaborations already under way carry on
                                    as normal.
                                </>
                            )}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel
                            data-testid="brand-campaign-confirm-cancel"
                            className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                        >
                            Keep it
                        </AlertDialogCancel>
                        <AlertDialogAction
                            data-testid="brand-campaign-confirm-ok"
                            onClick={() =>
                                confirm.kind === "delete"
                                    ? deleteDraft(confirm.campaign)
                                    : closeCampaign(confirm.campaign)
                            }
                            className={
                                confirm.kind === "delete"
                                    ? "rounded-full bg-red-500/90 text-black hover:bg-red-400"
                                    : "rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            }
                        >
                            {confirm.kind === "delete" ? "Delete draft" : "Close campaign"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
