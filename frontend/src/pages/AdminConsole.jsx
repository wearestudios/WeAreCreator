// The admin console.
//
// Tabs rather than a single scrolling page: the console does two different
// jobs, and mixing them meant scrolling past the ones you weren't doing.
// Overview is for looking at the business; the three review tabs are for
// clearing a queue; the last four are for looking things up.
//
// Every rejection anywhere in here opens a dialog and requires a reason,
// because the person on the other end is told what it said. Approvals are
// optimistic — the row leaves the list on the tap and comes back if the
// request fails.
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
    BadgeCheck,
    Building2,
    Inbox,
    LayoutDashboard,
    ScrollText,
    Sparkles,
    Users,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api } from "@/lib/api";
import { ADMIN_SHELL as SHELL_IDS, ADMIN_TABS as IDS } from "@/constants/testIds";
import Overview from "@/components/admin/Overview";
import { BrandReviews, CampaignReviews, CreatorReviews } from "@/components/admin/Reviews";
import ActionQueue from "@/components/admin/ActionQueue";
import AdminCreators from "@/components/admin/AdminCreators";
import AdminCampaigns from "@/components/admin/AdminCampaigns";
import AdminBrands from "@/components/admin/AdminBrands";
import AdminAudit from "@/components/admin/AdminAudit";

// `badge` names which count from /admin/dashboard sits on the tab.
const TABS = [
    { key: "overview", label: "Overview", Icon: LayoutDashboard },
    {
        key: "creator-reviews",
        label: "Creator reviews",
        Icon: BadgeCheck,
        badge: "creators_to_review",
    },
    {
        key: "campaign-reviews",
        label: "Campaign reviews",
        Icon: Sparkles,
        badge: "campaigns_to_review",
    },
    {
        key: "brand-reviews",
        label: "Brand reviews",
        Icon: Building2,
        badge: "brands_to_verify",
    },
    // Not in the original five, but collaborations mid-pipeline and payouts
    // waiting to be released have no other home, and dropping the queue would
    // leave money with nowhere to be actioned from.
    { key: "queue", label: "Queue", Icon: Inbox, badge: "queue_rest" },
    { key: "creators", label: "Creators", Icon: Users },
    { key: "campaigns", label: "Campaigns", Icon: Sparkles },
    { key: "brands", label: "Brands", Icon: Building2 },
    { key: "audit", label: "Audit log", Icon: ScrollText },
];

export default function AdminConsole() {
    const [active, setActive] = useState("overview");
    const [counts, setCounts] = useState(null);
    const [feePercent, setFeePercent] = useState(null);
    // Set when the Brands tab hands off to Campaigns filtered to one brand.
    const [brandFilter, setBrandFilter] = useState("");
    const navRef = useRef(null);

    // One dashboard call feeds every badge, refreshed after any action so a
    // badge always matches what is actually left in its tab.
    const loadCounts = useCallback(async () => {
        try {
            const [{ data }, metrics] = await Promise.all([
                api.get("/admin/dashboard", { params: { limit: 1 } }),
                api.get("/admin/metrics"),
            ]);
            const awaiting = data.awaiting || {};
            setCounts({
                ...awaiting,
                // What the queue tab holds that the review tabs don't.
                queue_rest:
                    (awaiting.collaborations_to_move || 0) +
                    (awaiting.payouts_to_record || 0),
            });
            setFeePercent(metrics.data.platform_fee_percent);
        } catch {
            // Badges are a convenience; the tabs work without them.
            setCounts({});
        }
    }, []);

    useEffect(() => {
        loadCounts();
    }, [loadCounts]);

    const goToBrandCampaigns = (brandId) => {
        setBrandFilter(brandId);
        setActive("campaigns");
    };

    const select = (key) => {
        setActive(key);
        // Keep the chosen tab in view on a phone, where the strip scrolls.
        navRef.current
            ?.querySelector(`[data-testid="${IDS.tab(key)}"]`)
            ?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    };

    return (
        <div data-testid={SHELL_IDS.page} className="min-h-screen bg-background grain-page">
            <Navbar />

            <main className="mx-auto max-w-7xl px-5 py-8 md:px-6 md:py-12">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    WeAre · Admin console
                </p>
                <h1
                    data-testid={SHELL_IDS.heading}
                    className="mt-2 font-serif text-fluid-4xl leading-none tracking-tight"
                >
                    Everything, and what needs you.
                </h1>

                {/* A scrolling strip rather than a wrapping grid: nine tabs
                    wrapping to three rows on a phone pushes the content off
                    the screen entirely. */}
                <nav
                    ref={navRef}
                    data-testid={IDS.nav}
                    // Sticky under the navbar, so which section you are in and
                    // what is waiting in the others survives a long scroll.
                    // The horizontal strip keeps its own bleed: nine tabs
                    // wrapping to three rows on a phone would push the content
                    // off the screen entirely.
                    className="sticky top-16 z-30 -mx-5 mt-8 flex gap-2 overflow-x-auto border-b border-white/10 bg-background/80 px-5 py-3 backdrop-blur-xl md:-mx-6 md:flex-wrap md:overflow-visible md:px-6"
                >
                    {TABS.map(({ key, label, Icon, badge }) => {
                        const on = active === key;
                        const count = badge ? counts?.[badge] ?? 0 : 0;
                        return (
                            <button
                                key={key}
                                type="button"
                                aria-current={on ? "page" : undefined}
                                onClick={() => select(key)}
                                data-testid={IDS.tab(key)}
                                className={
                                    "inline-flex min-h-[2.75rem] flex-none items-center gap-2 whitespace-nowrap rounded-md border px-4 py-2.5 text-xs uppercase tracking-[0.15em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0 " +
                                    (on
                                        ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                        : "border-white/10 text-muted-foreground hover:border-white/25 hover:text-foreground")
                                }
                            >
                                <Icon className="h-3.5 w-3.5" />
                                {label}
                                {count > 0 && (
                                    <span
                                        data-testid={IDS.badge(key)}
                                        className={
                                            "grid h-5 min-w-[1.25rem] place-items-center rounded-full px-1.5 text-[10px] font-medium " +
                                            (on
                                                ? "bg-ember-500 text-black"
                                                : "bg-white/10 text-foreground")
                                        }
                                    >
                                        {count > 99 ? "99+" : count}
                                    </span>
                                )}
                            </button>
                        );
                    })}
                </nav>

                <div
                    data-testid={SHELL_IDS.section(active)}
                    className="mt-10"
                >
                    {active === "overview" && <Overview onChanged={loadCounts} />}
                    {active === "creator-reviews" && <CreatorReviews onChanged={loadCounts} />}
                    {active === "campaign-reviews" && <CampaignReviews onChanged={loadCounts} />}
                    {active === "brand-reviews" && <BrandReviews onChanged={loadCounts} />}
                    {active === "queue" && (
                        <ActionQueue onChanged={loadCounts} feePercent={feePercent} />
                    )}
                    {active === "creators" && <AdminCreators />}
                    {active === "campaigns" && (
                        <AdminCampaigns
                            brandFilter={brandFilter}
                            onClearBrand={() => setBrandFilter("")}
                            onChanged={loadCounts}
                        />
                    )}
                    {active === "brands" && (
                        <AdminBrands
                            onChanged={loadCounts}
                            onViewCampaigns={goToBrandCampaigns}
                        />
                    )}
                    {active === "audit" && <AdminAudit />}
                </div>
            </main>
        </div>
    );
}
