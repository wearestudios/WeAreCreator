// The admin console shell.
//
// A layout, not a page: it owns the chrome every admin screen shares — the
// sidebar, the badge counts, ⌘K, the shortcuts overlay — and renders whichever
// route matched into the <Outlet>. The URL is still the state; `key` is still
// the path segment, so the section list is also the route table.
//
// **The tab strip became a sidebar.** Nine tabs across the top scrolled
// sideways on anything under a laptop, which put half the sections and all of
// their badge counts off-screen — you could not see that six brands were
// waiting without scrolling the navigation. It also spent the widest dimension
// of the screen on chrome, when the thing that needs width is a table.
//
// **The console is calm now.** No grain, no entrance animations, 150ms
// transitions on colour only. The marketing site's motion is right there and
// wrong here: a list that animates in is a list you cannot read until it has
// finished, and an admin loads it forty times a day. See `console/tokens.js`
// for the density and colour system every screen under here uses.
//
// Every rejection anywhere in here still opens a dialog and requires a reason,
// because the person on the other end is told what it said — including when it
// is reached with the R key. Approvals are still optimistic.
import React, { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation, useOutletContext } from "react-router-dom";
import { Keyboard, Menu } from "lucide-react";

import { Navbar } from "@/components/Navbar";
import ErrorBoundary from "@/components/ErrorBoundary";
import { api } from "@/lib/api";
import { ADMIN_SHELL as SHELL_IDS, ADMIN_SHORTCUTS } from "@/constants/testIds";
import { CommandPalette } from "@/components/admin/CommandPalette";
import AdminSidebar, {
    ADMIN_SECTIONS,
    AdminNavSheet,
} from "@/components/admin/console/Sidebar";
import ShortcutsOverlay from "@/components/admin/console/ShortcutsOverlay";
import { isTyping } from "@/components/admin/console/useTableKeys";
import { CALM, FOCUS, TEXT } from "@/components/admin/console/tokens";

// Kept exported under its old name: `components/admin/routes.jsx` and the
// router build their table from it, and renaming it would be a refactor of
// the routing for no gain.
export const ADMIN_TABS = ADMIN_SECTIONS;

/**
 * What the shell hands every screen under it: a way to refresh the badge
 * counts after an action, and the platform fee the payment screens quote.
 *
 * Read with `useAdminConsole()` rather than `useOutletContext()` directly, so a
 * screen rendered outside the shell fails with a clear message instead of
 * destructuring undefined.
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
    const [showKeys, setShowKeys] = useState(false);
    // The sections, on a screen too narrow for a rail.
    const [showNav, setShowNav] = useState(false);
    const { pathname } = useLocation();

    // One dashboard call feeds every badge, refreshed after any action so a
    // badge always matches what is actually left in its section.
    const loadCounts = useCallback(async () => {
        try {
            const [{ data }, metrics] = await Promise.all([
                api.get("/admin/dashboard", { params: { limit: 1 } }),
                api.get("/admin/metrics"),
            ]);
            const awaiting = data.awaiting || {};
            setCounts({
                ...awaiting,
                // What the action queue holds that the review sections don't.
                queue_rest:
                    (awaiting.collaborations_to_move || 0) +
                    (awaiting.payouts_to_record || 0),
            });
            setFeePercent(metrics.data.platform_fee_percent);
        } catch {
            // Badges are a convenience; the sections work without them.
            setCounts({});
        }
    }, []);

    useEffect(() => {
        loadCounts();
    }, [loadCounts]);

    // "?" from anywhere in the console. The list views bind it too, through
    // `useTableKeys`; this is the fallback for screens with no table on them,
    // so the overlay is reachable from Overview and from a detail page.
    useEffect(() => {
        const onKey = (e) => {
            if (e.key === "?" && !isTyping(e) && !e.metaKey && !e.ctrlKey) {
                e.preventDefault();
                setShowKeys(true);
            }
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, []);

    return (
        // No `grain-page`: the console is a working surface, not a printed one.
        <div data-testid={SHELL_IDS.page} className="min-h-screen bg-background">
            <Navbar />

            <div className="flex">
                <AdminSidebar counts={counts} />

                {/* The canvas. `min-w-0` so a wide table scrolls inside it
                    rather than pushing the sidebar off the screen. */}
                <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-2">
                        <div className="flex min-w-0 items-center gap-2">
                            {/* Below `md` this is the only way to the other
                                sections — the rail is hidden there, because
                                nine unlabelled icons in 56px is navigation you
                                have to already know. */}
                            <button
                                type="button"
                                onClick={() => setShowNav(true)}
                                data-testid={SHELL_IDS.mobileNavOpen}
                                aria-label="Sections"
                                className={`grid h-8 w-8 place-items-center rounded ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground md:hidden ${FOCUS}`}
                            >
                                <Menu className="h-4 w-4" />
                            </button>
                            <p className={`${TEXT.meta} truncate uppercase tracking-[0.16em] text-muted-foreground`}>
                                WeAre · Admin
                            </p>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setShowKeys(true)}
                                data-testid={ADMIN_SHORTCUTS.open}
                                aria-label="Keyboard shortcuts"
                                title="Keyboard shortcuts (?)"
                                className={`hidden h-8 w-8 place-items-center rounded md:grid ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground ${FOCUS}`}
                            >
                                <Keyboard className="h-4 w-4" />
                            </button>
                            {/* Mounted in the shell so ⌘K works on every screen
                                under /admin, detail pages included — and boxed
                                off, because a search result with an unexpected
                                shape must not take the console down with it. */}
                            <ErrorBoundary
                                variant="section"
                                name="command-palette"
                                label="Search is unavailable"
                            >
                                <CommandPalette />
                            </ErrorBoundary>
                        </div>
                    </div>

                    {/* The console's own screen, boxed off from its chrome.
                        Forty endpoints sit behind these routes and any of them
                        can return a shape nobody expected; when one does, the
                        sidebar and the badge counts stay up and the admin can
                        click somewhere else. `resetOn` is the path, so doing
                        that clears the fallback rather than carrying it to the
                        next screen. */}
                    <main className="p-4">
                        <ErrorBoundary
                            variant="section"
                            name="admin-screen"
                            label="This screen couldn't load"
                            resetOn={pathname}
                        >
                            <Outlet context={{ reloadCounts: loadCounts, feePercent }} />
                        </ErrorBoundary>
                    </main>
                </div>
            </div>

            <AdminNavSheet open={showNav} onOpenChange={setShowNav} counts={counts} />
            <ShortcutsOverlay open={showKeys} onOpenChange={setShowKeys} />
        </div>
    );
}
