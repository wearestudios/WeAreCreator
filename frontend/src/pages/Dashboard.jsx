import React from "react";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";

const ROLE_COPY = {
    creator: {
        label: "Creator",
        headline: "Your creator dashboard is coming to life.",
        body: "Soon: discover briefs from Bengaluru's best cafés & brands, apply in one tap, and track deliverables + payments — all here.",
    },
    brand: {
        label: "Brand",
        headline: "Your brand workspace is being prepared.",
        body: "Soon: post briefs, review curated creator shortlists, approve content, and pay from one dashboard.",
    },
    admin: {
        label: "Admin",
        headline: "WeAre admin console.",
        body: "Soon: approve creator/brand applications, moderate campaigns, and see the marketplace pulse.",
    },
};

export default function Dashboard() {
    const { user } = useAuth();
    if (!user || user === false) return null;
    const copy = ROLE_COPY[user.role] || ROLE_COPY.creator;

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
                    Hi <span className="italic">{user.name}</span>, {copy.headline}
                </h1>
                <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground">
                    {copy.body}
                </p>

                <div className="mt-14 grid gap-6 md:grid-cols-3">
                    {["Briefs", "Applications", "Payments"].map((t) => (
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
                                We'll turn this on in the next build step. Tell us which
                                screen to build next.
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
