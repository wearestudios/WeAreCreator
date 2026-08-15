// The creator's home.
//
// One scrolling page, in the order a creator actually reads it: who am I and
// what have I made, what does this thing want from me, what am I working on,
// what could I work on next, what have I pitched, where's my money. Tabs were
// considered and dropped — a creator opens this two or three times a week and
// shouldn't have to remember which drawer the venue address lives in.
//
// Motion is entrance-only and functional. Nothing on this page keeps moving
// once it has arrived, and every piece of it checks prefers-reduced-motion.
import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { Clock, RotateCw, Sparkles, Wallet, XCircle } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { useAuth, homePathFor } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import {
    CREATOR_ACTIVE as ACTIVE_IDS,
    CREATOR_APPLICATIONS as APPLICATIONS_IDS,
    CREATOR_COMPLETENESS as COMPLETENESS_IDS,
    CREATOR_EARNINGS as EARNINGS_IDS,
    CREATOR_HOME as IDS,
    CREATOR_SUGGESTED as SUGGESTED_IDS,
} from "@/constants/testIds";
import { HomeSkeleton, Reveal } from "@/components/creator/shared";
import Hero from "@/components/creator/Hero";
import Completeness from "@/components/creator/Completeness";
import ActiveCampaigns from "@/components/creator/ActiveCampaigns";
import Suggested from "@/components/creator/Suggested";
import Applications from "@/components/creator/Applications";
import Earnings from "@/components/creator/Earnings";
import BrandDashboardView from "@/pages/BrandDashboardView";

// ---------------------------------------------------------------------------
// Banners
// ---------------------------------------------------------------------------

const Banner = ({ Icon, tone, testid, children }) => (
    <div
        data-testid={testid}
        className={"flex items-start gap-3 rounded-md border p-4 text-sm leading-relaxed " + tone}
    >
        <Icon className="mt-0.5 h-4 w-4 flex-none" />
        <p>{children}</p>
    </div>
);

/**
 * The things that stop a creator earning, said out loud.
 *
 * Both of these used to be silent: an unverified profile that couldn't apply,
 * and a finished campaign that couldn't be paid out. Neither is discoverable
 * from anywhere else on the page.
 */
const StatusBanners = ({ profile, justOnboarded }) => {
    const status = profile?.verification_status;
    const items = [];

    if (justOnboarded) {
        items.push(
            <Banner
                key="onboarded"
                testid="just-onboarded-banner"
                Icon={Sparkles}
                tone="border-ember-500/30 bg-ember-500/10 text-ember-500/90"
            >
                Thanks — your profile is with the WeAre team. Reviews usually finish
                within 48 hours, and briefs open up to you the moment you're approved.
            </Banner>,
        );
    }
    if (status === "pending") {
        items.push(
            <Banner
                key="pending"
                testid="verification-pending-banner"
                Icon={Clock}
                tone="border-amber-500/30 bg-amber-500/10 text-amber-200"
            >
                Your profile is under review. You'll be able to pitch on briefs as
                soon as the team approves it — usually within 48 hours.
            </Banner>,
        );
    }
    if (status === "rejected") {
        items.push(
            <Banner
                key="rejected"
                testid="verification-rejected-banner"
                Icon={XCircle}
                tone="border-red-500/30 bg-red-500/10 text-red-200"
            >
                Your profile wasn't approved yet.{" "}
                <Link to="/onboarding/creator" className="underline underline-offset-4 hover:no-underline">
                    Update it
                </Link>{" "}
                and we'll take another look.
            </Banner>,
        );
    }
    if (status === "verified" && profile?.pending_review) {
        items.push(
            <Banner
                key="changes"
                testid="verification-changes-banner"
                Icon={Clock}
                tone="border-sky-500/30 bg-sky-500/10 text-sky-200"
            >
                You're still live and visible to brands. We're just taking a second
                look at the details you changed.
            </Banner>,
        );
    }
    if (status === "verified" && !profile?.payout_ready) {
        items.push(
            <Banner
                key="payout"
                testid="payout-missing-banner"
                Icon={Wallet}
                tone="border-ember-500/30 bg-ember-500/10 text-ember-500/90"
            >
                Add your UPI ID and PAN so we can pay you — we can't release a payout
                without them.{" "}
                <Link
                    to="/onboarding/creator"
                    data-testid="payout-missing-link"
                    className="underline underline-offset-4 hover:no-underline"
                >
                    Add payout details
                </Link>
            </Banner>,
        );
    }

    if (items.length === 0) return null;
    return <div className="space-y-3">{items}</div>;
};

// ---------------------------------------------------------------------------
// The page
// ---------------------------------------------------------------------------

const CreatorHome = ({ user, justOnboarded }) => {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    // Distinct from `!data`: a refresh after booking keeps the page on screen
    // rather than replacing everything the creator was reading with skeletons.
    const [refreshing, setRefreshing] = useState(false);

    const load = useCallback(async () => {
        setRefreshing(true);
        try {
            const res = await api.get("/creator/dashboard");
            setData(res.data);
            setError("");
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const groups = data?.collaborations || {};
    const loading = !data && !error;

    // Section order is the reading order, and the index drives the stagger.
    // Completeness is the only one that can drop out — at 100% there is nothing
    // to say, and an empty wrapper would leave a gap where a panel used to be.
    const completeness = data?.profile_completeness;
    const sections = data
        ? [
              {
                  key: "completeness",
                  testid: COMPLETENESS_IDS.section,
                  show: Boolean(
                      completeness &&
                          !completeness.complete &&
                          (completeness.missing || []).length > 0,
                  ),
                  node: <Completeness completeness={completeness} />,
              },
              {
                  key: "active",
                  testid: ACTIVE_IDS.section,
                  show: true,
                  node: (
                      <ActiveCampaigns collaborations={groups.active} onRefresh={load} />
                  ),
              },
              {
                  key: "suggested",
                  testid: SUGGESTED_IDS.section,
                  show: true,
                  node: <Suggested campaigns={data.suggested_campaigns} />,
              },
              {
                  key: "applications",
                  testid: APPLICATIONS_IDS.section,
                  show: true,
                  node: (
                      <Applications applied={groups.applied} declined={groups.declined} />
                  ),
              },
              {
                  key: "earnings",
                  testid: EARNINGS_IDS.section,
                  show: true,
                  node: (
                      <Earnings
                          payments={data.payments}
                          inPaymentCollabs={data.in_payment_collaborations}
                          earnings={data.earnings}
                      />
                  ),
              },
          ].filter((s) => s.show)
        : [];

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background">
            <Navbar />

            <main className="mx-auto max-w-6xl px-5 py-10 md:px-6 md:py-16">
                {loading && <HomeSkeleton testid={IDS.skeleton} />}

                {error && !data && (
                    <p
                        data-testid={IDS.error}
                        className="rounded-md border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-200"
                    >
                        {error}
                    </p>
                )}

                {data && (
                    <>
                        <Reveal index={0}>
                            <Hero user={user} profile={data.profile} earnings={data.earnings} />
                        </Reveal>

                        <div className="mt-8">
                            <StatusBanners
                                profile={data.profile}
                                justOnboarded={justOnboarded}
                            />
                        </div>

                        {sections.map(({ key, testid, node }, i) => (
                            <Reveal
                                key={key}
                                index={i + 1}
                                data-testid={testid}
                                className="mt-14 md:mt-20"
                            >
                                {node}
                            </Reveal>
                        ))}

                        <footer className="mt-16 flex flex-wrap items-center justify-between gap-4 rounded-md border border-white/10 bg-card/40 p-6 text-sm text-muted-foreground">
                            <p>
                                <span className="text-foreground">Signed in as</span>{" "}
                                {/* Accounts created over WhatsApp have no email. */}
                                {data.profile?.email || user.phone || user.name} ·{" "}
                                <span className="uppercase tracking-[0.15em] text-ember-500">
                                    {user.role}
                                </span>
                            </p>
                            <button
                                type="button"
                                onClick={load}
                                disabled={refreshing}
                                data-testid={IDS.refresh}
                                className="inline-flex min-h-[2.75rem] items-center gap-2 rounded-full border border-white/10 px-4 text-xs uppercase tracking-[0.15em] transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 disabled:opacity-50"
                            >
                                <RotateCw
                                    className={"h-3.5 w-3.5 " + (refreshing ? "animate-spin" : "")}
                                />
                                Refresh
                            </button>
                        </footer>
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
        return <CreatorHome user={user} justOnboarded={justOnboarded} />;
    }
    if (user.role === "brand") {
        return <BrandDashboardView user={user} />;
    }
    // Admins have no dashboard of their own — the console is their home.
    return <Navigate to={homePathFor(user.role)} replace />;
}
