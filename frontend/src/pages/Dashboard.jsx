import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
    ArrowRight,
    CheckCircle2,
    Clock,
    Compass,
    Instagram,
    Loader2,
    Sparkles,
    Users,
    Wallet,
    IndianRupee,
    XCircle,
    CalendarClock,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    lifestyle: "Lifestyle",
};

const STATE_META = {
    applied: {
        label: "Applied",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    },
    vetted: {
        label: "Vetted",
        tone: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    },
    accepted: {
        label: "Accepted",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    commercial_agreed: {
        label: "Commercial agreed",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    slot_booked: {
        label: "Slot booked",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    attended: {
        label: "Attended",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    content_submitted: {
        label: "Content submitted",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    in_payment: {
        label: "In payment",
        tone: "bg-ember-500/15 text-ember-500 border-ember-500/30",
    },
    closed: {
        label: "Closed",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
};

const StatePill = ({ state }) => {
    const meta = STATE_META[state] || {
        label: state,
        tone: "bg-white/5 text-muted-foreground border-white/15",
    };
    return (
        <span
            data-testid={`state-pill-${state}`}
            className={
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                meta.tone
            }
        >
            {meta.label}
        </span>
    );
};

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN") : "—";

const formatCompact = (n) => {
    if (typeof n !== "number") return "—";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
    return n.toString();
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

// ---------------------------------------------------------------------------
// Non-creator dashboards (kept minimal, unchanged behavior)
// ---------------------------------------------------------------------------

const NON_CREATOR_COPY = {
    brand: {
        label: "Brand",
        headline: "your brand workspace.",
        body: "Post briefs, review curated creator shortlists, approve content and pay from a single dashboard.",
    },
    admin: {
        label: "Admin",
        headline: "the WeAre admin console.",
        body: "Approve creator & brand applications, moderate campaigns and see the marketplace pulse.",
    },
};

const NonCreatorDashboard = ({ user }) => {
    const copy = NON_CREATOR_COPY[user.role] || NON_CREATOR_COPY.brand;
    return (
        <div data-testid="dashboard-page" className="min-h-screen bg-background">
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-16">
                <p
                    data-testid="dashboard-role-tag"
                    className="text-xs uppercase tracking-[0.2em] text-ember-500"
                >
                    {copy.label} · Bengaluru
                </p>
                <h1
                    data-testid="dashboard-welcome"
                    className="mt-4 max-w-3xl font-serif text-4xl leading-none tracking-tight md:text-5xl"
                >
                    Hi <span className="italic">{user.name}</span>, welcome to{" "}
                    {copy.headline}
                </h1>
                <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground">
                    {copy.body}
                </p>
                <div className="mt-14 grid gap-6 md:grid-cols-3">
                    <div
                        data-testid="dashboard-tile-campaigns"
                        className="rounded-md border border-white/10 bg-card p-8"
                    >
                        <Compass className="h-5 w-5 text-ember-500" />
                        <div className="mt-6 font-serif text-3xl">Coming soon</div>
                        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                            Post a new campaign or manage the ones you already have.
                        </p>
                    </div>
                    <div className="rounded-md border border-white/10 bg-card p-8">
                        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Applications
                        </div>
                        <div className="mt-6 font-serif text-3xl">Coming soon</div>
                    </div>
                    <div className="rounded-md border border-white/10 bg-card p-8">
                        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Payments
                        </div>
                        <div className="mt-6 font-serif text-3xl">Coming soon</div>
                    </div>
                </div>
                <div className="mt-14 rounded-md border border-white/10 bg-card/40 p-6 text-sm text-muted-foreground">
                    <span className="text-foreground">Signed in as</span> {user.email} ·{" "}
                    <span className="uppercase tracking-[0.15em] text-ember-500">
                        {user.role}
                    </span>
                </div>
            </main>
        </div>
    );
};

// ---------------------------------------------------------------------------
// Creator dashboard
// ---------------------------------------------------------------------------

const VETTING_META = {
    pending: {
        Icon: Clock,
        label: "Under review",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    },
    vetted: {
        Icon: CheckCircle2,
        label: "Vetted",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
    },
    rejected: {
        Icon: XCircle,
        label: "Needs changes",
        tone: "bg-red-500/15 text-red-300 border-red-500/40",
    },
};

const CreatorHeader = ({ user, profile }) => {
    const meta = VETTING_META[profile?.vetting_status] || VETTING_META.pending;
    const handle = profile?.instagram_handle;
    return (
        <header data-testid="creator-header" className="grid gap-6 md:grid-cols-12 md:items-end">
            <div className="md:col-span-8">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Creator · Bengaluru
                </p>
                <h1
                    data-testid="creator-name-heading"
                    className="mt-3 font-serif text-4xl leading-none tracking-tight md:text-5xl"
                >
                    {profile?.name || user.name}
                </h1>
                <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                    {handle ? (
                        <a
                            href={
                                profile?.instagram_profile_url ||
                                `https://instagram.com/${handle}`
                            }
                            target="_blank"
                            rel="noreferrer"
                            data-testid="creator-ig-handle"
                            className="inline-flex items-center gap-1.5 transition-colors duration-200 hover:text-ember-500"
                        >
                            <Instagram className="h-4 w-4" />@{handle}
                        </a>
                    ) : (
                        <span
                            data-testid="creator-ig-handle-empty"
                            className="text-muted-foreground"
                        >
                            No Instagram handle yet
                        </span>
                    )}
                    <span className="text-muted-foreground/60">·</span>
                    <span
                        data-testid={`vetting-badge-${profile?.vetting_status || "pending"}`}
                        className={
                            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] " +
                            meta.tone
                        }
                    >
                        <meta.Icon className="h-3.5 w-3.5" />
                        {meta.label}
                    </span>
                </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 md:col-span-4 md:justify-end">
                <Link to="/onboarding/creator" data-testid="header-edit-profile">
                    <Button
                        variant="outline"
                        className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                    >
                        Edit profile
                    </Button>
                </Link>
                <Link to="/campaigns" data-testid="header-browse-campaigns">
                    <Button className="group rounded-full bg-ember-500 text-black hover:bg-ember-400">
                        Browse campaigns
                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                    </Button>
                </Link>
            </div>
        </header>
    );
};

const StatsPanel = ({ profile }) => {
    const niches = profile?.niches || [];
    return (
        <section
            data-testid="stats-panel"
            className="mt-10 grid gap-4 md:grid-cols-12"
        >
            <div className="rounded-md border border-white/10 bg-card p-7 md:col-span-4">
                <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Followers
                    </p>
                    <Users className="h-4 w-4 text-ember-500" />
                </div>
                <div
                    data-testid="stat-followers"
                    className="mt-6 font-serif text-4xl md:text-5xl"
                >
                    {formatCompact(profile?.follower_count)}
                </div>
                <p
                    data-testid="stat-live-note"
                    className="mt-3 text-xs text-muted-foreground"
                >
                    Self-reported · Live Instagram stats coming soon
                </p>
            </div>

            <div className="rounded-md border border-white/10 bg-card p-7 md:col-span-5">
                <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Your niches
                    </p>
                    <Sparkles className="h-4 w-4 text-ember-500" />
                </div>
                <div data-testid="stat-niches" className="mt-5 flex flex-wrap gap-2">
                    {niches.length === 0 && (
                        <p className="text-sm text-muted-foreground">
                            No niches yet — add some on your profile.
                        </p>
                    )}
                    {niches.map((n) => (
                        <span
                            key={n}
                            data-testid={`stat-niche-${n}`}
                            className="rounded-full bg-ember-500/15 px-3 py-1 text-xs uppercase tracking-[0.15em] text-ember-500"
                        >
                            {n}
                        </span>
                    ))}
                </div>
            </div>

            <div className="rounded-md border border-white/10 bg-card p-7 md:col-span-3">
                <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Base rate
                    </p>
                    <IndianRupee className="h-4 w-4 text-ember-500" />
                </div>
                <div className="mt-6 flex items-baseline font-serif text-4xl md:text-5xl">
                    {profile?.base_rate != null ? (
                        <>
                            <IndianRupee className="h-6 w-6 text-ember-500 md:h-7 md:w-7" />
                            {formatRupees(profile.base_rate)}
                        </>
                    ) : (
                        <span className="text-muted-foreground">—</span>
                    )}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                    Per collab · edit any time
                </p>
            </div>
        </section>
    );
};

const ApplicationsSection = ({ applications }) => (
    <section
        data-testid="applications-section"
        className="mt-14"
    >
        <div className="flex items-baseline justify-between">
            <div>
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    My applications
                </p>
                <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                    Every brief you've pitched on.
                </h2>
            </div>
            <span className="text-xs text-muted-foreground">
                {applications.length}{" "}
                {applications.length === 1 ? "application" : "applications"}
            </span>
        </div>

        <div className="mt-8 overflow-hidden rounded-md border border-white/10 bg-card">
            {applications.length === 0 ? (
                <div
                    data-testid="applications-empty"
                    className="flex flex-col items-center gap-3 px-6 py-16 text-center"
                >
                    <Compass className="h-6 w-6 text-ember-500" />
                    <p className="font-serif text-2xl">
                        You haven't applied to anything yet.
                    </p>
                    <p className="max-w-md text-sm text-muted-foreground">
                        Browse the live campaign feed and pitch on the ones that fit you.
                    </p>
                    <Link
                        to="/campaigns"
                        data-testid="applications-browse-link"
                        className="mt-4"
                    >
                        <Button className="rounded-full bg-ember-500 text-black hover:bg-ember-400">
                            Browse campaigns
                        </Button>
                    </Link>
                </div>
            ) : (
                <ul className="divide-y divide-white/10">
                    {applications.map((a) => (
                        <li
                            key={a.id}
                            data-testid={`application-row-${a.id}`}
                        >
                            <Link
                                to={`/campaigns/${a.campaign_id}`}
                                className="group flex flex-col gap-4 px-5 py-5 transition-colors duration-200 hover:bg-white/5 md:flex-row md:items-center md:gap-6 md:px-6 md:py-6"
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        {a.brand_name || "Brand"}
                                        {a.area ? ` · ${a.area}` : ""}
                                        {a.category ? ` · ${CAT_LABEL[a.category] || a.category}` : ""}
                                    </div>
                                    <div className="mt-1.5 truncate font-serif text-xl leading-tight text-foreground">
                                        {a.campaign_title || "Untitled campaign"}
                                    </div>
                                    <div className="mt-2 text-xs text-muted-foreground">
                                        Applied {formatDate(a.created_at)}
                                    </div>
                                </div>
                                <div className="flex flex-col items-end gap-2 md:min-w-[160px]">
                                    <div className="flex items-baseline font-serif text-2xl">
                                        <IndianRupee className="h-4 w-4 text-ember-500" />
                                        {formatRupees(a.quoted_rate)}
                                    </div>
                                    <StatePill state={a.state} />
                                </div>
                                <ArrowRight className="hidden h-4 w-4 flex-none text-muted-foreground transition-transform duration-200 group-hover:translate-x-1 group-hover:text-ember-500 md:block" />
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    </section>
);

const UpcomingSection = ({ upcoming }) => (
    <section data-testid="upcoming-section" className="mt-14">
        <div className="flex items-baseline justify-between">
            <div>
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Upcoming
                </p>
                <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                    Slots on your calendar.
                </h2>
            </div>
            <span className="text-xs text-muted-foreground">
                {upcoming.length} booked
            </span>
        </div>
        <div className="mt-8 rounded-md border border-white/10 bg-card">
            {upcoming.length === 0 ? (
                <div
                    data-testid="upcoming-empty"
                    className="flex items-center gap-4 px-6 py-10 text-sm text-muted-foreground"
                >
                    <CalendarClock className="h-5 w-5 flex-none text-ember-500" />
                    <p>
                        Nothing on the calendar yet. Once a brand books your slot, it
                        will show up here.
                    </p>
                </div>
            ) : (
                <ul className="divide-y divide-white/10">
                    {upcoming.map((u) => (
                        <li key={u.id} data-testid={`upcoming-row-${u.id}`}>
                            <Link
                                to={`/campaigns/${u.campaign_id}`}
                                className="flex flex-col gap-3 px-6 py-5 transition-colors duration-200 hover:bg-white/5 md:flex-row md:items-center md:gap-6"
                            >
                                <div className="flex-1">
                                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        {u.brand_name || "Brand"}
                                        {u.area ? ` · ${u.area}` : ""}
                                    </div>
                                    <div className="mt-1 font-serif text-xl leading-tight">
                                        {u.campaign_title}
                                    </div>
                                </div>
                                <StatePill state={u.state} />
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    </section>
);

const PaymentsSection = ({ payments, inPaymentCollabs }) => {
    const totalPaid = payments
        .filter((p) => p.state === "paid")
        .reduce((sum, p) => sum + (typeof p.creator_payout === "number" ? p.creator_payout : 0), 0);
    const items = [
        ...payments.map((p) => ({
            id: p.id,
            campaign_id: null,
            campaign_title: p.campaign_title,
            brand_name: p.brand_name,
            amount: p.creator_payout ?? p.agreed_amount,
            state: p.state,
            paid_at: p.paid_at,
        })),
        ...inPaymentCollabs.map((c) => ({
            id: c.id,
            campaign_id: c.campaign_id,
            campaign_title: c.campaign_title,
            brand_name: c.brand_name,
            amount: c.agreed_amount ?? c.quoted_rate,
            state: "in_payment",
            paid_at: null,
        })),
    ];

    return (
        <section data-testid="payments-section" className="mt-14">
            <div className="flex items-baseline justify-between">
                <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Payments
                    </p>
                    <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                        Where your money lives.
                    </h2>
                </div>
                {totalPaid > 0 && (
                    <div className="text-right">
                        <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            Paid to date
                        </div>
                        <div className="mt-1 flex items-baseline font-serif text-3xl">
                            <IndianRupee className="h-5 w-5 text-ember-500" />
                            {formatRupees(totalPaid)}
                        </div>
                    </div>
                )}
            </div>

            <div className="mt-8 rounded-md border border-white/10 bg-card">
                {items.length === 0 ? (
                    <div
                        data-testid="payments-empty"
                        className="flex items-center gap-4 px-6 py-10 text-sm text-muted-foreground"
                    >
                        <Wallet className="h-5 w-5 flex-none text-ember-500" />
                        <p>
                            No payouts yet. Once a brand approves your content, the
                            payment shows up here.
                        </p>
                    </div>
                ) : (
                    <ul className="divide-y divide-white/10">
                        {items.map((p) => (
                            <li
                                key={p.id}
                                data-testid={`payment-row-${p.id}`}
                                className="flex flex-col gap-3 px-6 py-5 md:flex-row md:items-center md:gap-6"
                            >
                                <div className="flex-1">
                                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        {p.brand_name || "Brand"}
                                    </div>
                                    <div className="mt-1 font-serif text-xl leading-tight">
                                        {p.campaign_title || "—"}
                                    </div>
                                    {p.paid_at && (
                                        <div className="mt-1 text-xs text-muted-foreground">
                                            Paid {formatDate(p.paid_at)}
                                        </div>
                                    )}
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                    <div className="flex items-baseline font-serif text-2xl">
                                        <IndianRupee className="h-4 w-4 text-ember-500" />
                                        {formatRupees(p.amount)}
                                    </div>
                                    <StatePill state={p.state} />
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </section>
    );
};

// ---------------------------------------------------------------------------
// Vetting banner (post-onboarding welcome)
// ---------------------------------------------------------------------------

const OnboardedBanner = ({ visible }) => {
    if (!visible) return null;
    return (
        <div
            data-testid="just-onboarded-banner"
            className="mt-8 flex items-start gap-3 rounded-md border border-ember-500/30 bg-ember-500/10 p-4 text-sm text-ember-500/90"
        >
            <Sparkles className="mt-0.5 h-4 w-4 flex-none" />
            <p>
                Thanks — your profile is with the WeAre team. Reviews usually finish
                within 48 hours. Meanwhile, browse open campaigns below.
            </p>
        </div>
    );
};

const CreatorDashboard = ({ user, justOnboarded }) => {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;
        api.get("/creator/dashboard")
            .then(({ data }) => {
                if (!cancelled) setData(data);
            })
            .catch((err) => {
                if (!cancelled) setError(err?.response?.data?.detail || "Failed to load dashboard");
            });
        return () => {
            cancelled = true;
        };
    }, []);

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
                        data-testid="dashboard-error"
                        className="text-sm text-destructive"
                    >
                        {error}
                    </p>
                )}
                {data && (
                    <>
                        <CreatorHeader user={user} profile={data.profile} />
                        <OnboardedBanner visible={justOnboarded} />
                        <StatsPanel profile={data.profile} />
                        <ApplicationsSection applications={data.applications} />
                        <UpcomingSection upcoming={data.upcoming} />
                        <PaymentsSection
                            payments={data.payments}
                            inPaymentCollabs={data.in_payment_collaborations || []}
                        />
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
};

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function Dashboard() {
    const { user } = useAuth();
    const location = useLocation();
    if (!user || user === false) return null;
    const justOnboarded = Boolean(location.state?.justOnboarded);
    if (user.role === "creator") {
        return <CreatorDashboard user={user} justOnboarded={justOnboarded} />;
    }
    return <NonCreatorDashboard user={user} />;
}
