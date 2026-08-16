// The admin console shell.
//
// This is a layout, not a page: it owns the chrome that every admin screen
// shares — the tab strip and the badge counts behind it — and renders whichever
// route matched into the <Outlet>.
//
// It used to be one route with a `useState` tab. That made every screen in the
// console unaddressable: no deep link to a campaign, no back button, nothing to
// paste into a message to a colleague, and a browser reload always landed back
// on Overview. The URL is the state now. `key` is the path segment, so the tab
// list is also the route table.
//
// Every rejection anywhere in here opens a dialog and requires a reason,
// because the person on the other end is told what it said. Approvals are
// optimistic — the row leaves the list on the tap and comes back if the
// request fails.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useOutletContext } from "react-router-dom";
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

// `badge` names which count from /admin/dashboard sits on the tab. `to` is
// relative to /admin, so the strip and the router cannot disagree about where
// a tab goes.
export const ADMIN_TABS = [
    { key: "overview", to: "", label: "Overview", Icon: LayoutDashboard, end: true },
    {
        key: "creator-reviews",
        to: "creator-reviews",
        label: "Creator reviews",
        Icon: BadgeCheck,
        badge: "creators_to_review",
    },
    {
        key: "campaign-reviews",
        to: "campaign-reviews",
        label: "Campaign reviews",
        Icon: Sparkles,
        badge: "campaigns_to_review",
    },
    {
        key: "brand-reviews",
        to: "brand-reviews",
        label: "Brand reviews",
        Icon: Building2,
        badge: "brands_to_verify",
    },
    // Not in the original five, but collaborations mid-pipeline and payouts
    // waiting to be released have no other home, and dropping the queue would
    // leave money with nowhere to be actioned from.
    { key: "queue", to: "queue", label: "Queue", Icon: Inbox, badge: "queue_rest" },
    { key: "creators", to: "creators", label: "Creators", Icon: Users },
    { key: "campaigns", to: "campaigns", label: "Campaigns", Icon: Sparkles },
    { key: "brands", to: "brands", label: "Brands", Icon: Building2 },
    { key: "audit", to: "audit", label: "Audit log", Icon: ScrollText },
];

/**
 * What the shell hands every screen under it: a way to refresh the badge counts
 * after an action, and the platform fee the payment screens quote.
 *
 * Read with `useAdminConsole()` rather than `useOutletContext()` directly, so a
 * screen that is rendered outside the shell fails with a clear message instead
 * of destructuring undefined.
 */
export function useAdminConsole() {
    const ctx = useOutletContext();
    if (!ctx) {
        throw new Error("This screen must be rendered inside the /admin layout.");
    }
    return ctx;
}

export default function AdminConsole() {
    const [counts, setCounts] = useState(null);
    const [feePercent, setFeePercent] = useState(null);
    const navRef = useRef(null);
    const { pathname } = useLocation();

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

    // Keep the active tab in view on a phone, where the strip scrolls. Driven
    // by the URL rather than by the click, so arriving on a deep link scrolls
    // the strip too — the tab you are on should never be off-screen.
    useEffect(() => {
        navRef.current
            ?.querySelector('[aria-current="page"]')
            ?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    }, [pathname]);

    return (
        <div data-testid={SHELL_IDS.page} className="min-h-screen bg-background grain-page">
            <Navbar />

            <main className="mx-auto max-w-7xl px-5 py-8 md:px-6 md:py-12">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    WeAre · Admin console
                </p>

                {/* A scrolling strip rather than a wrapping grid: nine tabs
                    wrapping to three rows on a phone pushes the content off
                    the screen entirely.

                    NavLink rather than a button — these are real links now, so
                    they open in a new tab on middle-click and can be copied. */}
                <nav
                    ref={navRef}
                    data-testid={IDS.nav}
                    // Sticky under the navbar, so which section you are in and
                    // what is waiting in the others survives a long scroll.
                    className="sticky top-16 z-30 -mx-5 mt-6 flex gap-2 overflow-x-auto border-b border-white/10 bg-background/80 px-5 py-3 backdrop-blur-xl md:-mx-6 md:flex-wrap md:overflow-visible md:px-6"
                >
                    {ADMIN_TABS.map(({ key, to, label, Icon, badge, end }) => {
                        const count = badge ? counts?.[badge] ?? 0 : 0;
                        return (
                            <NavLink
                                key={key}
                                to={to}
                                end={end}
                                data-testid={IDS.tab(key)}
                                className={({ isActive }) =>
                                    "inline-flex min-h-[2.75rem] flex-none items-center gap-2 whitespace-nowrap rounded-md border px-4 py-2.5 text-xs uppercase tracking-[0.15em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0 " +
                                    (isActive
                                        ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                        : "border-white/10 text-muted-foreground hover:border-white/25 hover:text-foreground")
                                }
                            >
                                {({ isActive }) => (
                                    <>
                                        <Icon className="h-3.5 w-3.5" />
                                        {label}
                                        {count > 0 && (
                                            <span
                                                data-testid={IDS.badge(key)}
                                                className={
                                                    "grid h-5 min-w-[1.25rem] place-items-center rounded-full px-1.5 text-[10px] font-medium " +
                                                    (isActive
                                                        ? "bg-ember-500 text-black"
                                                        : "bg-white/10 text-foreground")
                                                }
                                            >
                                                {count > 99 ? "99+" : count}
                                            </span>
                                        )}
                                    </>
                                )}
                            </NavLink>
                        );
                    })}
                </nav>

                <div className="mt-10">
                    <Outlet context={{ reloadCounts: loadCounts, feePercent }} />
                </div>
            </main>
        </div>
    );
}
