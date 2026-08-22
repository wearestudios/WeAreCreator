// The creator's home.
//
// Above the fold, without scrolling: who am I (a photo big enough to say so),
// what I've earned, what I'm working on and what I do next. Everything else —
// briefs that might suit them, past pitches, the money ledger — lives in tabs
// below the live work. The first version stacked all of it vertically and the
// page was mostly scrolling; the one thing that must never go behind a tab is
// the active work, because a venue address in a drawer is a creator lost on a
// footpath. Status banners and the completeness nudge also stay outside the
// tabs: a blocked account is not a section, it is the situation.
//
// Motion is entrance-only and functional. Nothing on this page keeps moving
// once it has arrived, and every piece of it checks prefers-reduced-motion.
import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { Clock, RotateCw, Send, Sparkles, Wallet, XCircle } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Navbar } from "@/components/Navbar";
import { useAuth, homePathFor, isBrandSide } from "@/context/AuthContext";
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
import { SafeSection } from "@/components/ErrorBoundary";
import Hero from "@/components/creator/Hero";
import Completeness from "@/components/creator/Completeness";
import VerificationExpiry from "@/components/VerificationExpiry";
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
const StatusBanners = ({ profile, completeness, justOnboarded }) => {
    const status = profile?.verification_status;
    const items = [];

    // Finished but never sent. Without this a creator can sit at 100% forever
    // waiting on a review nobody was asked for — the completeness panel hides
    // itself at 100%, so this is the only thing left to say it.
    if (
        status !== "verified" &&
        completeness?.complete &&
        !profile?.submitted_for_review_at
    ) {
        items.push(
            <Banner
                key="ready"
                testid="profile-ready-banner"
                Icon={Send}
                tone="border-ember-500/30 bg-ember-500/10 text-ember-500/90"
            >
                Your profile is finished but we haven't seen it yet.{" "}
                <Link
                    to="/onboarding/creator"
                    data-testid="profile-ready-link"
                    className="underline underline-offset-4 hover:no-underline"
                >
                    Send it for review
                </Link>{" "}
                and we'll come back within 48 hours.
            </Banner>,
        );
    }

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
    if (status === "pending" && profile?.submitted_for_review_at) {
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

    // First login after signup: signup collects a name and a number and
    // nothing else, so a creator who has filled in none of their profile has
    // no dashboard worth reading yet — send them to the builder instead.
    // Once per browser session, so "Finish later" actually works and somebody
    // who just wants to browse isn't bounced back every time.
    const untouched =
        Boolean(data) &&
        (data.profile_completeness?.percent ?? 0) === 0 &&
        !data.profile?.submitted_for_review_at;
    const alreadySteered =
        typeof sessionStorage !== "undefined" &&
        sessionStorage.getItem("weare.builder-steered") === "1";
    if (untouched && !alreadySteered) {
        try {
            sessionStorage.setItem("weare.builder-steered", "1");
        } catch {
            // Private mode. Worst case they get steered again next load.
        }
        return <Navigate to="/onboarding/creator" replace />;
    }

    // Completeness can drop out — at 100% there is nothing to say, and an
    // empty wrapper would leave a gap where a panel used to be.
    const completeness = data?.profile_completeness;
    const showCompleteness = Boolean(
        completeness &&
            !completeness.complete &&
            (completeness.missing || []).length > 0,
    );
    const suggestedCount = (data?.suggested_campaigns || []).length;
    // Invitations sit in this tab and count toward its badge: an invitation
    // the creator has not answered is the most actionable thing in there, and
    // a badge that ignores it is a badge that says "nothing for you".
    const applicationsCount =
        (groups.applied || []).length +
        (groups.declined || []).length +
        (data?.invitations || []).filter((i) => i.open).length;

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background grain-page">
            <Navbar />

            <main className="mx-auto max-w-6xl px-5 py-8 md:px-6 md:py-14">
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
                        {/* Six panels off one payload, each rendering a
                            different slice of it. A creator whose earnings row
                            has an unexpected shape should still see what they
                            are booked on this week — before this, that one bad
                            row blanked the page and the creator's evidence was
                            "the app is broken". */}
                        <SafeSection name="hero" label="Your header couldn't load">
                            <Reveal index={0}>
                                <Hero
                                    user={user}
                                    profile={data.profile}
                                    earnings={data.earnings}
                                />
                            </Reveal>
                        </SafeSection>

                        <SafeSection name="banners" className="mt-8">
                            <StatusBanners
                                profile={data.profile}
                                completeness={data.profile_completeness}
                                justOnboarded={justOnboarded}
                            />
                        </SafeSection>

                        {/* **Outside the tabs, like every other status.** A
                            check that is about to run out is the situation
                            rather than a section, and the profile form is the
                            one screen a verified creator has no reason to
                            open — so telling them there would be telling them
                            nowhere. Renders nothing until the window opens. */}
                        <SafeSection name="revalidate" className="mt-4">
                            <VerificationExpiry
                                verification={data.profile?.verification}
                                kind="creator"
                                onConfirmed={load}
                            />
                        </SafeSection>

                        {showCompleteness && (
                            <SafeSection name="completeness" className="mt-10 md:mt-12">
                                <Reveal index={1} data-testid={COMPLETENESS_IDS.section}>
                                    <Completeness completeness={completeness} />
                                </Reveal>
                            </SafeSection>
                        )}

                        {/* The live work stays outside the tabs, always. This
                            is the reason the page gets opened, and a venue
                            address in a drawer is a creator lost on a
                            footpath. */}
                        <SafeSection name="active" className="mt-10 md:mt-12">
                            <Reveal index={2} data-testid={ACTIVE_IDS.section}>
                                <ActiveCampaigns
                                    collaborations={groups.active}
                                    onRefresh={load}
                                />
                            </Reveal>
                        </SafeSection>

                        {/* Everything a creator consults rather than acts on,
                            one drawer each. Radix tabs, so arrow keys walk the
                            strip and the panels stay in the accessibility
                            tree's good books. */}
                        <SafeSection name="drawers" className="mt-10 md:mt-14">
                            <Reveal index={3}>
                                <Tabs defaultValue="suggested" data-testid={IDS.tabs}>
                                    <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto rounded-full border border-white/10 bg-card/60 p-1.5">
                                        {[
                                            {
                                                value: "suggested",
                                                label: "For you",
                                                count: suggestedCount,
                                            },
                                            {
                                                value: "applications",
                                                label: "Applications",
                                                count: applicationsCount,
                                            },
                                            { value: "earnings", label: "Earnings" },
                                        ].map((t) => (
                                            <TabsTrigger
                                                key={t.value}
                                                value={t.value}
                                                data-testid={IDS.tab(t.value)}
                                                className="min-h-[2.5rem] flex-none rounded-full px-4 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 data-[state=active]:bg-ember-500/15 data-[state=active]:text-ember-500"
                                            >
                                                {t.label}
                                                {t.count > 0 && (
                                                    <span className="ml-2 rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] tabular-nums text-foreground/70">
                                                        {t.count}
                                                    </span>
                                                )}
                                            </TabsTrigger>
                                        ))}
                                    </TabsList>

                                    <TabsContent value="suggested" className="mt-8">
                                        <SafeSection name="suggested">
                                            <div data-testid={SUGGESTED_IDS.section}>
                                                <Suggested campaigns={data.suggested_campaigns} />
                                            </div>
                                        </SafeSection>
                                    </TabsContent>
                                    <TabsContent value="applications" className="mt-8">
                                        <SafeSection name="applications">
                                            <div data-testid={APPLICATIONS_IDS.section}>
                                                <Applications
                                                    applied={groups.applied}
                                                    declined={groups.declined}
                                                    invitations={data?.invitations}
                                                    onChanged={load}
                                                />
                                            </div>
                                        </SafeSection>
                                    </TabsContent>
                                    <TabsContent value="earnings" className="mt-8">
                                        <SafeSection name="earnings">
                                            <div data-testid={EARNINGS_IDS.section}>
                                                <Earnings
                                                    payments={data.payments}
                                                    inPaymentCollabs={data.in_payment_collaborations}
                                                    earnings={data.earnings}
                                                />
                                            </div>
                                        </SafeSection>
                                    </TabsContent>
                                </Tabs>
                            </Reveal>
                        </SafeSection>

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
    if (isBrandSide(user.role)) {
        return <BrandDashboardView user={user} justOnboarded={justOnboarded} />;
    }
    // Admins have no dashboard of their own — the console is their home.
    return <Navigate to={homePathFor(user.role)} replace />;
}
