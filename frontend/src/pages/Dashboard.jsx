import React, { useEffect, useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { Clock, CheckCircle2, XCircle, ArrowRight, Compass } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

const VETTING_META = {
    pending: {
        Icon: Clock,
        tone: "text-amber-300",
        bg: "bg-amber-500/10 border-amber-500/30",
        label: "Under review",
        body:
            "Your profile is with the WeAre team. Reviews usually finish within 48 hours. In the meantime, feel free to browse open campaigns.",
    },
    vetted: {
        Icon: CheckCircle2,
        tone: "text-emerald-300",
        bg: "bg-emerald-500/10 border-emerald-500/30",
        label: "Vetted",
        body:
            "You're in. Brands can now discover you and you can apply to any open campaign.",
    },
    rejected: {
        Icon: XCircle,
        tone: "text-red-300",
        bg: "bg-red-500/10 border-red-500/30",
        label: "Needs changes",
        body:
            "The WeAre team flagged something on your profile. Update it and resubmit — we'll review again.",
    },
};

const ROLE_COPY = {
    creator: {
        label: "Creator",
        headline: "your creator workspace.",
        body: "Discover live paid briefs from Bengaluru's best cafés & lifestyle brands, apply in one tap and track deliverables + payments — all here.",
    },
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

export default function Dashboard() {
    const { user } = useAuth();
    const location = useLocation();
    const [creatorProfile, setCreatorProfile] = useState(null);

    useEffect(() => {
        if (user && user !== false && user.role === "creator") {
            api.get("/creator/profile")
                .then(({ data }) => setCreatorProfile(data))
                .catch(() => setCreatorProfile(null));
        }
    }, [user]);

    if (!user || user === false) return null;
    const copy = ROLE_COPY[user.role] || ROLE_COPY.creator;
    const justOnboarded = Boolean(location.state?.justOnboarded);

    const isCreator = user.role === "creator";
    const vettingStatus = creatorProfile?.vetting_status;
    const vettingMeta = vettingStatus ? VETTING_META[vettingStatus] : null;

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
                    Hi <span className="italic">{user.name}</span>, welcome to {copy.headline}
                </h1>
                <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground">
                    {copy.body}
                </p>

                {/* Creator vetting banner */}
                {isCreator && vettingMeta && (
                    <div
                        data-testid={`vetting-banner-${vettingStatus}`}
                        className={
                            "mt-10 flex flex-col gap-4 rounded-md border p-6 md:flex-row md:items-center md:justify-between " +
                            vettingMeta.bg
                        }
                    >
                        <div className="flex items-start gap-4">
                            <vettingMeta.Icon
                                className={"mt-0.5 h-6 w-6 flex-none " + vettingMeta.tone}
                            />
                            <div>
                                <p className={"text-xs uppercase tracking-[0.2em] " + vettingMeta.tone}>
                                    {justOnboarded && vettingStatus === "pending"
                                        ? "Profile submitted"
                                        : vettingMeta.label}
                                </p>
                                <p className="mt-2 max-w-xl text-sm leading-relaxed text-foreground/90">
                                    {justOnboarded && vettingStatus === "pending"
                                        ? "Thanks — the WeAre team has your profile. Reviews usually finish within 48 hours. Meanwhile, you can browse campaigns below."
                                        : vettingMeta.body}
                                </p>
                            </div>
                        </div>
                        <div className="flex gap-2 md:flex-none">
                            <Link
                                to="/onboarding/creator"
                                data-testid="edit-profile-link"
                            >
                                <Button
                                    variant="outline"
                                    className="border-white/15 bg-transparent hover:bg-white/5"
                                >
                                    {vettingStatus === "rejected"
                                        ? "Update profile"
                                        : "Edit profile"}
                                </Button>
                            </Link>
                        </div>
                    </div>
                )}

                {/* Placeholder tiles */}
                <div className="mt-14 grid gap-6 md:grid-cols-3">
                    <Link
                        to={isCreator ? "/campaigns" : "/dashboard"}
                        data-testid="dashboard-tile-campaigns"
                        className="group rounded-md border border-white/10 bg-card p-8 transition-colors duration-200 hover:border-ember-500/50"
                    >
                        <div className="flex items-center justify-between">
                            <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                {isCreator ? "Open campaigns" : "Campaigns"}
                            </div>
                            <Compass className="h-5 w-5 text-muted-foreground transition-colors duration-200 group-hover:text-ember-500" />
                        </div>
                        <div className="mt-6 font-serif text-3xl">
                            {isCreator ? "Browse now" : "Coming soon"}
                        </div>
                        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                            {isCreator
                                ? "Live paid briefs from Bengaluru brands — hand-picked, budgets shown upfront."
                                : "Post a new campaign or manage the ones you already have — coming next."}
                        </p>
                        {isCreator && (
                            <div className="mt-6 inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-ember-500">
                                Browse campaigns <ArrowRight className="h-3.5 w-3.5" />
                            </div>
                        )}
                    </Link>
                    {["Applications", "Payments"].map((t) => (
                        <div
                            key={t}
                            data-testid={`dashboard-tile-${t.toLowerCase()}`}
                            className="rounded-md border border-white/10 bg-card p-8 transition-colors duration-200 hover:border-ember-500/40"
                        >
                            <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                {t}
                            </div>
                            <div className="mt-6 font-serif text-3xl">Coming soon</div>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                We'll turn this on shortly. Tell us which screen to build next.
                            </p>
                        </div>
                    ))}
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
}
