import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { notifyInfo, notifySuccess } from "@/lib/feedback";
import {
    ArrowLeft,
    ArrowRight,
    CalendarDays,
    Check,
    Clock,
    IndianRupee,
    Info,
    Loader2,
    MapPin,
    Send,
    ShieldCheck,
    Users,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import {
    DetailPageSkeleton,
    LoadingAnnouncement,
} from "@/components/data/PageSkeleton";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { compensationType, isBarter } from "@/lib/compensation";
import ExecutionBadge, { ExecutionNote } from "@/components/ExecutionBadge";
import ShareButton from "@/components/ShareButton";
import BrandName from "@/components/BrandName";
import CampaignCover from "@/components/CampaignCover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    lifestyle: "Lifestyle",
};

const STATE_LABEL = {
    applied: "With the WeAre team",
    verified: "With the brand",
    accepted: "Accepted",
    commercial_agreed: "Fee agreed",
    slot_booked: "Slot booked",
    attended: "Attended",
    content_submitted: "In review",
    content_approved: "Approved",
    in_payment: "Payment in progress",
    closed: "Paid",
    declined: "Not taken forward",
    cancelled: "Cancelled",
};

const formatDate = (iso, opts) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            ...opts,
        });
    } catch {
        return iso;
    }
};

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN") : "—";

function ApplyDialog({ open, onOpenChange, campaign, onApplied }) {
    const [pitch, setPitch] = useState("");
    const [rate, setRate] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    // Re-seed the rate from the campaign budget every time the dialog opens.
    // Not on a barter brief: the stored budget is a leftover from before we
    // converted it, so pre-filling it would quote a fee nobody is paying.
    useEffect(() => {
        if (open && campaign) {
            setPitch("");
            setRate(
                !isBarter(campaign) && campaign.budget_per_creator != null
                    ? String(campaign.budget_per_creator)
                    : "",
            );
            setError("");
        }
    }, [open, campaign]);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        const trimmedPitch = pitch.trim();
        if (!trimmedPitch) {
            setError("Please write a one or two line pitch.");
            return;
        }
        if (rate === "" || rate === null || rate === undefined) {
            setError("Please enter a valid quoted rate.");
            return;
        }
        const numericRate = Number(rate);
        if (!Number.isFinite(numericRate) || numericRate < 0) {
            setError("Please enter a valid quoted rate.");
            return;
        }
        setSubmitting(true);
        try {
            const { data } = await api.post(`/campaigns/${campaign.id}/apply`, {
                pitch: trimmedPitch,
                quoted_rate: numericRate,
            });
            notifySuccess("Application submitted");
            onApplied(data);
            onOpenChange(false);
        } catch (err) {
            const status = err?.response?.status;
            if (status === 409) {
                onApplied({ duplicate: true });
                onOpenChange(false);
                notifyInfo("You've already applied to this campaign");
            } else {
                setError(formatApiError(err));
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid="apply-dialog"
                className="max-w-lg overflow-hidden rounded-md border border-white/10 bg-card p-0 sm:rounded-md grain-surface"
            >
                <div className="border-b border-white/10 bg-background/50 px-6 pt-6 pb-5">
                    <DialogHeader className="text-left">
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            Apply to campaign
                        </p>
                        <DialogTitle className="mt-3 font-serif text-fluid-3xl leading-tight tracking-tight text-foreground">
                            {campaign?.title}
                        </DialogTitle>
                        <DialogDescription className="mt-2 text-sm text-muted-foreground">
                            {campaign?.brand_name || "Brand"} · {campaign?.area || "—"}
                        </DialogDescription>
                    </DialogHeader>
                </div>

                <form onSubmit={submit} noValidate className="space-y-6 px-6 py-6">
                    <div>
                        <Label
                            htmlFor="apply-pitch"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            Your pitch — one or two lines
                        </Label>
                        <Textarea
                            id="apply-pitch"
                            data-testid="apply-pitch-input"
                            rows={3}
                            maxLength={1000}
                            value={pitch}
                            onChange={(e) => setPitch(e.target.value)}
                            className="mt-2 min-h-[92px] border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            placeholder="Why you're the right creator for this brief."
                        />
                        <p className="mt-2 text-xs text-muted-foreground">
                            Tip: mention 1 relevant collab you've done and how you'd approach this one.
                        </p>
                    </div>

                    <div>
                        <Label
                            htmlFor="apply-rate"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            Your quoted rate
                        </Label>
                        <div className="relative mt-2">
                            <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                id="apply-rate"
                                data-testid="apply-rate-input"
                                type="number"
                                min="0"
                                step="100"
                                inputMode="numeric"
                                value={rate}
                                onChange={(e) => setRate(e.target.value)}
                                className="h-11 border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                                placeholder="e.g. 8000"
                            />
                        </div>
                        <p
                            data-testid="apply-fee-note"
                            className="mt-3 flex items-start gap-2 rounded-md border border-ember-500/25 bg-ember-500/10 p-3 text-xs leading-relaxed text-ember-500/90"
                        >
                            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 flex-none" />
                            {isBarter(campaign)
                                ? "This brief is barter — there's no fee attached to it. Quote what you'd want if that changes, or leave it blank."
                                : "You receive 100% of this amount. The platform fee is charged to the brand on top."}
                        </p>
                        {!isBarter(campaign) && (
                            <p className="mt-2 text-xs text-muted-foreground">
                                Budget on this brief:{" "}
                                <span className="text-foreground">
                                    ₹{formatRupees(campaign?.budget_per_creator)}
                                </span>
                                . Feel free to quote lower or higher — brands consider both.
                            </p>
                        )}
                    </div>

                    {error && (
                        <p
                            data-testid="apply-error"
                            className="text-sm text-destructive"
                        >
                            {error}
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                data-testid="apply-cancel-btn"
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            data-testid="apply-submit-btn"
                            disabled={submitting}
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Submitting…
                                </>
                            ) : (
                                <>
                                    <Send className="mr-2 h-4 w-4" />
                                    Submit application
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

function AppliedCard({ application }) {
    if (!application) return null;
    return (
        <div
            data-testid="applied-status-card"
            className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-5"
        >
            <div className="flex items-center gap-2 text-emerald-300">
                <Check className="h-4 w-4" />
                <span className="text-xs uppercase tracking-[0.2em]">
                    Application submitted
                </span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-foreground/90">
                {application.state === "applied"
                    ? "Our team is reviewing your pitch before it goes to the brand. We'll message you on WhatsApp as it moves."
                    : "Your pitch is with the brand. We'll message you on WhatsApp as it moves."}
            </p>

            <dl className="mt-5 space-y-3 border-t border-emerald-500/20 pt-4 text-sm">
                <div>
                    <dt className="text-[10px] uppercase tracking-[0.2em] text-emerald-300/80">
                        Status
                    </dt>
                    <dd
                        data-testid="applied-state"
                        className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs uppercase tracking-[0.15em] text-emerald-300"
                    >
                        <Clock className="h-3 w-3" />
                        {STATE_LABEL[application.state] || application.state}
                    </dd>
                </div>
                {application.pitch && (
                    <div>
                        <dt className="text-[10px] uppercase tracking-[0.2em] text-emerald-300/80">
                            Your pitch
                        </dt>
                        <dd
                            data-testid="applied-pitch"
                            className="mt-1 whitespace-pre-line text-sm leading-relaxed text-foreground/85"
                        >
                            {application.pitch}
                        </dd>
                    </div>
                )}
                {application.quoted_rate != null && (
                    <div>
                        <dt className="text-[10px] uppercase tracking-[0.2em] text-emerald-300/80">
                            Your quoted rate
                        </dt>
                        <dd
                            data-testid="applied-rate"
                            className="mt-1 flex items-baseline font-serif text-2xl text-foreground"
                        >
                            <IndianRupee className="h-4 w-4 text-emerald-300" />
                            {formatRupees(application.quoted_rate)}
                        </dd>
                    </div>
                )}
                <div>
                    <dt className="text-[10px] uppercase tracking-[0.2em] text-emerald-300/80">
                        Submitted
                    </dt>
                    <dd className="mt-1 text-sm text-foreground/85">
                        {formatDate(application.created_at)}
                    </dd>
                </div>
            </dl>
        </div>
    );
}

export default function CampaignDetail() {
    const { id } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();
    const [campaign, setCampaign] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [dialogOpen, setDialogOpen] = useState(false);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        api.get(`/campaigns/${id}`)
            .then(({ data }) => {
                if (!cancelled) setCampaign(data);
            })
            .catch((err) => {
                if (!cancelled) setError(formatApiError(err));
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [id]);

    const refetch = async () => {
        try {
            const { data } = await api.get(`/campaigns/${id}`);
            setCampaign(data);
        } catch {
            /* noop */
        }
    };

    const handleApplied = async (result) => {
        // On duplicate, just refresh state from the server.
        if (result?.duplicate) {
            await refetch();
            return;
        }
        // Optimistically flip; then refetch to pick up server-authoritative fields.
        setCampaign((c) =>
            c
                ? {
                      ...c,
                      has_applied: true,
                      application: {
                          id: result.id,
                          state: result.state || "applied",
                          pitch: result.pitch,
                          quoted_rate: result.quoted_rate,
                          created_at: result.created_at,
                      },
                  }
                : c,
        );
        refetch();
    };

    const isLive = campaign?.status === "open";
    const isCreator = user?.role === "creator";

    const sidebarContent = useMemo(() => {
        if (!campaign) return null;
        if (!isCreator) {
            return (
                <div className="rounded-md border border-white/10 bg-background/60 p-4 text-xs leading-relaxed text-muted-foreground">
                    <Info className="mb-2 h-4 w-4 text-ember-500" />
                    You're signed in as{" "}
                    <span className="uppercase tracking-[0.15em] text-ember-500">
                        {user?.role}
                    </span>
                    . Only creator accounts can apply to campaigns.
                </div>
            );
        }
        if (campaign.has_applied) {
            return <AppliedCard application={campaign.application} />;
        }
        // The server decides eligibility — verification, and whether slots remain.
        if (campaign.apply_blocked_reason) {
            return (
                <div
                    data-testid="detail-apply-blocked"
                    className="rounded-md border border-amber-500/30 bg-amber-500/10 p-5 text-sm leading-relaxed text-amber-200"
                >
                    <Info className="mb-2 h-4 w-4" />
                    {campaign.apply_blocked_reason}
                    <Link
                        to="/onboarding/creator"
                        data-testid="detail-apply-blocked-link"
                        className="mt-3 block underline underline-offset-4 hover:no-underline"
                    >
                        Review your profile →
                    </Link>
                </div>
            );
        }
        return (
            <Button
                data-testid="detail-apply-btn"
                onClick={() => setDialogOpen(true)}
                className="group h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
            >
                <Send className="mr-2 h-4 w-4" />
                Apply
                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
            </Button>
        );
    }, [campaign, isCreator, user]);

    if (loading) {
        // Same wrapper and the same <main> as the loaded page, so the swap
        // moves the header and the sidebar by nothing. A centred spinner used
        // to sit in a py-32 box and everything then jumped up when it left.
        return (
            <div
                data-testid="campaign-detail-loading"
                className="min-h-screen bg-background grain-page"
            >
                <Navbar />
                <main className="mx-auto max-w-5xl px-6 py-12 md:py-16">
                    <LoadingAnnouncement>Loading campaign…</LoadingAnnouncement>
                    <DetailPageSkeleton testid="campaign-detail-skeleton" cover />
                </main>
            </div>
        );
    }

    if (!campaign) {
        return (
            <div className="min-h-screen bg-background grain-page">
                <Navbar />
                <div className="mx-auto max-w-2xl px-6 py-24 text-center">
                    <p className="font-serif text-3xl">Campaign not found</p>
                    <p className="mt-4 text-sm text-muted-foreground">
                        {error || "It may have been closed or moved."}
                    </p>
                    <Button
                        onClick={() => navigate("/campaigns")}
                        className="mt-8 rounded-full bg-ember-500 text-black hover:bg-ember-400"
                    >
                        Back to campaigns
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div
            data-testid="campaign-detail-page"
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <Navbar />
            <main className="mx-auto max-w-5xl px-6 py-12 md:py-16">
                <Link
                    to="/campaigns"
                    data-testid="detail-back-link"
                    className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    All campaigns
                </Link>

                <div className="mt-6 flex flex-wrap items-center gap-2">
                    <span
                        data-testid={`detail-status-${campaign.status}`}
                        className={
                            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                            (isLive
                                ? "bg-ember-500/15 text-ember-500"
                                : "border border-white/15 bg-white/5 text-muted-foreground")
                        }
                    >
                        <span
                            className={
                                "inline-block h-1.5 w-1.5 rounded-full " +
                                (isLive
                                    ? "bg-ember-500 animate-pulse"
                                    : "bg-muted-foreground")
                            }
                        />
                        {isLive ? "Live" : "Upcoming"}
                    </span>
                    <BrandName
                        brand={campaign}
                        avatarSize="h-6 w-6"
                        className="text-xs uppercase tracking-[0.2em] text-muted-foreground"
                    />
                </div>

                <h1
                    data-testid="detail-title"
                    className="mt-4 max-w-3xl font-serif text-fluid-6xl-wide leading-none tracking-tight"
                >
                    {campaign.title}
                </h1>

                {/* Who runs it, said plainly and near the top — a creator
                    deciding whether to give up a day is deciding partly on who
                    they will be dealing with when something goes wrong. */}
                <div className="mt-5 flex flex-wrap items-center gap-3">
                    <ShareButton
                        campaignId={campaign.id}
                        title={campaign.title}
                        summary={campaign.deliverables}
                    />
                    <ExecutionBadge campaign={campaign} audience="creator" />
                    <ExecutionNote campaign={campaign} audience="creator" className="min-w-0" />
                </div>

                {/* Below the header rather than above it: the eyebrow, the
                    title and the brand are what a creator is deciding on, and a
                    16:9 band at this width pushes all three off a phone screen
                    if it goes first. The picture is a pixel of scroll away. */}
                <CampaignCover
                    campaign={campaign}
                    priority
                    className="mt-8 max-w-3xl"
                />

                <div className="mt-10 grid gap-10 md:grid-cols-12">
                    <div className="md:col-span-8">
                        <section>
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                The brief
                            </p>
                            <p
                                data-testid="detail-brief"
                                className="mt-4 whitespace-pre-line text-base leading-relaxed text-foreground/90"
                            >
                                {campaign.brief}
                            </p>
                        </section>

                        <section className="mt-12 rounded-md border border-white/10 bg-card p-8 grain-surface">
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                Deliverables
                            </p>
                            <p
                                data-testid="detail-deliverables"
                                className="mt-4 whitespace-pre-line font-serif text-2xl leading-snug"
                            >
                                {campaign.deliverables}
                            </p>
                        </section>
                    </div>

                    <aside className="md:col-span-4">
                        <div className="sticky top-24 space-y-4">
                            <div className="rounded-md border border-white/10 bg-card p-7 grain-surface">
                                <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                    {isBarter(campaign)
                                        ? "What you get"
                                        : "Budget per creator"}
                                </div>
                                <div
                                    data-testid="detail-budget"
                                    className="mt-2 flex items-baseline font-serif text-4xl text-foreground"
                                >
                                    {isBarter(campaign) ? (
                                        "Barter"
                                    ) : (
                                        <>
                                            <IndianRupee className="h-6 w-6 text-ember-500" />
                                            {formatRupees(campaign.budget_per_creator)}
                                        </>
                                    )}
                                </div>
                                {/* The one thing a creator most needs to know
                                  * before giving up a day, said where the fee
                                  * would otherwise be. */}
                                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                    {isBarter(campaign)
                                        ? "No fee on this one — what's offered is in the brief. Read it before you apply."
                                        : compensationType(campaign) === "negotiated"
                                          ? "A guide, not a fixed fee. You quote your rate and the brand agrees it with you."
                                          : "You receive 100% of this. The platform fee is charged to the brand."}
                                </p>

                                <dl className="mt-7 space-y-4 border-t border-white/10 pt-6 text-sm">
                                    <div className="flex items-start gap-3">
                                        <MapPin className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
                                        <div>
                                            <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                                Area
                                            </dt>
                                            <dd className="mt-1">
                                                {campaign.area || "—"}
                                            </dd>
                                        </div>
                                    </div>
                                    <div className="flex items-start gap-3">
                                        <Users className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
                                        <div>
                                            <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                                Creators needed
                                            </dt>
                                            <dd className="mt-1">
                                                {campaign.creators_needed} ·{" "}
                                                <span className="text-muted-foreground">
                                                    {CAT_LABEL[campaign.category] ||
                                                        campaign.category ||
                                                        "—"}
                                                </span>
                                            </dd>
                                        </div>
                                    </div>
                                    <div className="flex items-start gap-3">
                                        <CalendarDays className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
                                        <div>
                                            <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                                Window
                                            </dt>
                                            <dd className="mt-1 leading-relaxed">
                                                {formatDate(campaign.start_date)} →{" "}
                                                {formatDate(campaign.end_date)}
                                            </dd>
                                        </div>
                                    </div>
                                </dl>
                            </div>

                            {sidebarContent}
                        </div>
                    </aside>
                </div>
            </main>

            <ApplyDialog
                open={dialogOpen}
                onOpenChange={setDialogOpen}
                campaign={campaign}
                onApplied={handleApplied}
            />
        </div>
    );
}
