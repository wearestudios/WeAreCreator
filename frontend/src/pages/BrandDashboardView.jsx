import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
    ArrowRight,
    Building2,
    CalendarDays,
    Compass,
    IndianRupee,
    Loader2,
    MapPin,
    Plus,
    Sparkles,
    Users,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    lifestyle: "Lifestyle",
};

const STATUS_META = {
    draft: {
        label: "Draft",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
    upcoming: {
        label: "Upcoming",
        tone: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    },
    open: {
        label: "Live",
        tone: "bg-ember-500/15 text-ember-500 border-ember-500/30",
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
        });
    } catch {
        return iso;
    }
};

const StatTile = ({ label, value, Icon }) => (
    <div className="rounded-md border border-white/10 bg-card p-5">
        <div className="flex items-center justify-between">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {label}
            </p>
            {Icon && <Icon className="h-4 w-4 text-ember-500" />}
        </div>
        <div className="mt-4 font-serif text-3xl md:text-4xl">{value}</div>
    </div>
);

export default function BrandDashboardView({ user }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;
        api.get("/brand/dashboard")
            .then(({ data }) => {
                if (!cancelled) setData(data);
            })
            .catch((err) => {
                if (!cancelled) setError(formatApiError(err));
            });
        return () => {
            cancelled = true;
        };
    }, []);

    const profileMissing =
        data && (!data.profile || !data.profile.business_name);
    const businessName =
        data?.profile?.business_name || user.name || "Your brand";

    return (
        <div data-testid="dashboard-page" className="min-h-screen bg-background">
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-12 md:py-16">
                {!data && !error && (
                    <div className="grid place-items-center py-24 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" />
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
                                    Brand · India
                                </p>
                                <h1
                                    data-testid="brand-name-heading"
                                    className="mt-3 font-serif text-4xl leading-none tracking-tight md:text-5xl"
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
                                <Link to="/campaigns/new" data-testid="brand-header-post-btn">
                                    <Button className="group rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                        <Plus className="mr-1 h-4 w-4" />
                                        Post a campaign
                                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </Button>
                                </Link>
                            </div>
                        </header>

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
                            <StatTile
                                label="Live campaigns"
                                value={data.totals.live_campaigns}
                                Icon={Compass}
                            />
                            <StatTile
                                label="Draft"
                                value={data.totals.draft_campaigns}
                                Icon={CalendarDays}
                            />
                            <StatTile
                                label="Total campaigns"
                                value={data.totals.total_campaigns}
                                Icon={Building2}
                            />
                            <StatTile
                                label="Applications received"
                                value={data.totals.total_applications}
                                Icon={Users}
                            />
                        </section>

                        <section data-testid="brand-campaigns-section" className="mt-14">
                            <div className="flex items-baseline justify-between">
                                <div>
                                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                        Your campaigns
                                    </p>
                                    <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
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

                            <div className="mt-8 overflow-hidden rounded-md border border-white/10 bg-card">
                                {data.campaigns.length === 0 ? (
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
                                            reaching vetted creators across India immediately.
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
                                        {data.campaigns.map((c) => {
                                            const canBrowsePublicly = c.status === "open" || c.status === "upcoming";
                                            return (
                                                <li
                                                    key={c.id}
                                                    data-testid={`brand-campaign-row-${c.id}`}
                                                    className="flex flex-col gap-4 px-5 py-5 transition-colors duration-200 hover:bg-white/5 md:flex-row md:items-center md:gap-6 md:px-6 md:py-6"
                                                >
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
                                                            <span className="inline-flex items-center gap-1">
                                                                <IndianRupee className="h-3.5 w-3.5" />
                                                                {formatRupees(c.budget_per_creator)} / creator
                                                            </span>
                                                            <span>·</span>
                                                            <span className="inline-flex items-center gap-1">
                                                                <Users className="h-3.5 w-3.5" />
                                                                {c.creators_needed} needed
                                                            </span>
                                                        </div>
                                                    </div>

                                                    <div className="flex items-center gap-6 md:min-w-[220px] md:justify-end">
                                                        <div className="text-right">
                                                            <div
                                                                data-testid={`brand-campaign-applicants-${c.id}`}
                                                                className="font-serif text-2xl leading-none"
                                                            >
                                                                {c.applicant_count}
                                                            </div>
                                                            <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                                                {c.applicant_count === 1
                                                                    ? "applicant"
                                                                    : "applicants"}
                                                            </div>
                                                        </div>
                                                        <div className="flex flex-col items-end gap-2">
                                                            <StatusPill status={c.status} />
                                                            {canBrowsePublicly && (
                                                                <Link
                                                                    to={`/campaigns/${c.id}`}
                                                                    data-testid={`brand-campaign-view-${c.id}`}
                                                                    className="inline-flex items-center gap-1 text-xs uppercase tracking-[0.18em] text-ember-500 transition-colors duration-200 hover:text-ember-400"
                                                                >
                                                                    View <ArrowRight className="h-3.5 w-3.5" />
                                                                </Link>
                                                            )}
                                                        </div>
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
                            {user.email} ·{" "}
                            <span className="uppercase tracking-[0.15em] text-ember-500">
                                {user.role}
                            </span>
                        </div>
                    </>
                )}
            </main>
        </div>
    );
}
