import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
    ArrowLeft,
    ArrowRight,
    CalendarDays,
    Check,
    IndianRupee,
    Loader2,
    MapPin,
    Send,
    Users,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    lifestyle: "Lifestyle",
};

const formatDate = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        });
    } catch {
        return iso;
    }
};

export default function CampaignDetail() {
    const { id } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();
    const [campaign, setCampaign] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [applying, setApplying] = useState(false);

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

    const handleApply = async () => {
        if (!campaign || applying) return;
        setApplying(true);
        try {
            await api.post(`/campaigns/${campaign.id}/apply`);
            setCampaign((c) => (c ? { ...c, has_applied: true } : c));
            toast.success("Application submitted");
        } catch (err) {
            const msg = formatApiError(err);
            // Duplicate application → treat as already applied.
            if (err?.response?.status === 409) {
                setCampaign((c) => (c ? { ...c, has_applied: true } : c));
                toast.info(msg);
            } else {
                toast.error(msg);
            }
        } finally {
            setApplying(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <div className="grid place-items-center py-32 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                </div>
            </div>
        );
    }

    if (!campaign) {
        return (
            <div className="min-h-screen bg-background">
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

    const isLive = campaign.status === "open";
    const canApply = user?.role === "creator";

    return (
        <div
            data-testid="campaign-detail-page"
            className="min-h-screen bg-background text-foreground"
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
                    <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        {campaign.brand_name || "Brand"}
                    </span>
                </div>

                <h1
                    data-testid="detail-title"
                    className="mt-4 max-w-3xl font-serif text-4xl leading-none tracking-tight md:text-6xl"
                >
                    {campaign.title}
                </h1>

                <div className="mt-10 grid gap-10 md:grid-cols-12">
                    {/* Main content */}
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

                        <section className="mt-12 rounded-md border border-white/10 bg-card p-8">
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

                    {/* Sidebar */}
                    <aside className="md:col-span-4">
                        <div className="sticky top-24 rounded-md border border-white/10 bg-card p-7">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                Budget per creator
                            </div>
                            <div
                                data-testid="detail-budget"
                                className="mt-2 flex items-baseline font-serif text-4xl text-foreground"
                            >
                                <IndianRupee className="h-6 w-6 text-ember-500" />
                                {typeof campaign.budget_per_creator === "number"
                                    ? campaign.budget_per_creator.toLocaleString("en-IN")
                                    : "—"}
                            </div>

                            <dl className="mt-7 space-y-4 border-t border-white/10 pt-6 text-sm">
                                <div className="flex items-start gap-3">
                                    <MapPin className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
                                    <div>
                                        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                            Area
                                        </dt>
                                        <dd className="mt-1">{campaign.area || "—"}</dd>
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

                            <div className="mt-8">
                                {canApply ? (
                                    campaign.has_applied ? (
                                        <Button
                                            data-testid="detail-applied-badge"
                                            disabled
                                            className="h-12 w-full rounded-full bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/20"
                                        >
                                            <Check className="mr-2 h-4 w-4" />
                                            Application submitted
                                        </Button>
                                    ) : (
                                        <Button
                                            data-testid="detail-apply-btn"
                                            onClick={handleApply}
                                            disabled={applying}
                                            className="group h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                                        >
                                            {applying ? (
                                                <>
                                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                    Applying…
                                                </>
                                            ) : (
                                                <>
                                                    <Send className="mr-2 h-4 w-4" />
                                                    Apply
                                                    <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                                </>
                                            )}
                                        </Button>
                                    )
                                ) : (
                                    <div className="rounded-md border border-white/10 bg-background/60 p-4 text-xs leading-relaxed text-muted-foreground">
                                        You're signed in as{" "}
                                        <span className="uppercase tracking-[0.15em] text-ember-500">
                                            {user?.role}
                                        </span>
                                        . Only creator accounts can apply to campaigns.
                                    </div>
                                )}
                            </div>
                        </div>
                    </aside>
                </div>
            </main>
        </div>
    );
}
