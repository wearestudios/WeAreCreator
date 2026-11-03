/**
 * The signed-in app's layout: the navy sidebar, and the page beside it.
 *
 * A layout route in `App.js` around every app path except the console (which
 * has a sidebar of its own, built from the same parts in `SideNav.jsx`). It
 * stays mounted while somebody moves between the pages inside it, so the
 * navigation never re-draws under their cursor and a count it was given is
 * still there on the next page.
 *
 * **Only real destinations.** The boards draw "Campaigns", "Applicants",
 * "Content" and "Payments" for a brand; none of those is a page here — a
 * brand's campaigns, applicants and content live on its dashboard and each
 * brief's board — so the sidebar carries what exists: the dashboard, posting
 * a brief, the calendar and the brand's profile. A link to a page that does
 * not exist is worse than no link.
 *
 * **Its own Suspense, around the page only.** The app-level one replaces the
 * whole tree, which on a move between two app pages in different chunks
 * would take the sidebar down for the length of a download. This one keeps
 * the column and holds the page's space.
 */
import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import {
    Building2,
    CalendarDays,
    Home,
    Inbox,
    LayoutDashboard,
    LogOut,
    PlusCircle,
    Search,
    UserRound,
    X,
} from "lucide-react";

import { useAuth, isBrandSide } from "@/context/AuthContext";
import useWide from "@/lib/useWide";
import { isAllAccess, isConsoleRole } from "@/lib/consoleScope";
import { NotificationBell } from "@/components/NotificationBell";
import AdminAccountMenu from "@/components/admin/AdminAccountMenu";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingAnnouncement } from "@/components/data/PageSkeleton";
import {
    AppTopBar,
    ShellContext,
    SideNavAccount,
    SideNavBadge,
    SideNavFrame,
    SideNavItem,
    SideNavLogo,
    SHELL_ROLE_LABEL,
} from "@/components/app/SideNav";
import { APP_SHELL as IDS } from "@/constants/testIds";
import { BadgeContext } from "@/components/app/shellContext";

/**
 * Each role's destinations. `testId` keeps the id the old top bar's link
 * carried, so "the dashboard link" is the same element to a test as it was.
 * `badge` names a count a page may publish with `useShellBadges`.
 */
export function shellNavFor(role) {
    if (isConsoleRole(role)) {
        return [
            { key: "console", to: "/admin", label: isAllAccess(role) ? "Console" : "Your console", Icon: LayoutDashboard, end: true, testId: "nav-admin" },
            { key: "queue", to: "/admin/queue", label: "Action queue", Icon: Inbox, testId: "nav-admin-queue" },
            { key: "calendar", to: "/calendar", label: "Calendar", Icon: CalendarDays, testId: "nav-calendar" },
        ];
    }
    if (role === "campaign_manager") {
        return [
            { key: "manager", to: "/manager", label: "Your campaigns", Icon: LayoutDashboard, testId: "nav-manager" },
            { key: "calendar", to: "/calendar", label: "Calendar", Icon: CalendarDays, testId: "nav-calendar" },
        ];
    }
    if (isBrandSide(role)) {
        // No creator directory: a brand reaches creators through its own
        // briefs, so there is nothing to put here for them.
        return [
            { key: "dashboard", to: "/dashboard", label: "Overview", Icon: LayoutDashboard, end: true, testId: "nav-dashboard", badge: "needs" },
            { key: "post", to: "/campaigns/new", label: "Post a brief", Icon: PlusCircle, end: true, testId: "nav-post-campaign" },
            { key: "calendar", to: "/calendar", label: "Calendar", Icon: CalendarDays, testId: "nav-calendar" },
            { key: "profile", to: "/onboarding/brand", label: "Brand profile", Icon: Building2, testId: "nav-brand-profile" },
        ];
    }
    return [
        { key: "dashboard", to: "/dashboard", label: "Home", Icon: Home, end: true, testId: "nav-dashboard", badge: "invitations" },
        // The brief feed is a public page, so this leaves the shell; it is
        // still the first place a creator goes looking for work.
        { key: "briefs", to: "/campaigns", label: "Find briefs", Icon: Search, testId: "nav-campaigns" },
        { key: "profile", to: "/profile", label: "Profile", Icon: UserRound, testId: "nav-profile" },
    ];
}

// ---------------------------------------------------------------------------
// Counts a page can hand the sidebar
// ---------------------------------------------------------------------------

export { useShellBadges } from "@/components/app/shellContext";

// ---------------------------------------------------------------------------
// The shell
// ---------------------------------------------------------------------------

function ContentFallback() {
    return (
        <div data-testid={IDS.loading} className="mx-auto max-w-6xl px-6 py-10">
            <div aria-hidden="true" className="space-y-5">
                <Skeleton className="h-3 w-28" />
                <Skeleton className="h-10 w-2/3 max-w-md" />
                <Skeleton className="h-40 w-full rounded-lg" />
            </div>
            <LoadingAnnouncement>Loading this page…</LoadingAnnouncement>
        </div>
    );
}

function NavList({ items, badges, onNavigate, mobile = false }) {
    return items.map((item) => (
        <SideNavItem
            key={item.key}
            to={item.to}
            end={item.end}
            Icon={item.Icon}
            label={item.label}
            onNavigate={onNavigate}
            testid={mobile ? `${item.testId}-mobile` : item.testId}
            badge={<SideNavBadge count={item.badge ? badges[item.badge] : 0} testid={IDS.badge(item.key)} />}
        />
    ));
}

export default function AppShell() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [badges, setBadges] = useState({});
    const [sheetOpen, setSheetOpen] = useState(false);
    // One bell on screen: in the column from `md`, in the top bar below it.
    // Both are mounted otherwise, and each asks for the notifications.
    const wide = useWide();
    const [consoleTheme, setConsoleTheme] = useState(user?.console_theme ?? null);
    useEffect(() => setConsoleTheme(user?.console_theme ?? null), [user?.console_theme]);

    const publish = useCallback((next) => {
        setBadges((prev) => {
            const merged = { ...prev, ...next };
            return JSON.stringify(merged) === JSON.stringify(prev) ? prev : merged;
        });
    }, []);

    const signedIn = Boolean(user) && user !== false;
    const role = signedIn ? user.role : null;
    const items = useMemo(() => (role ? shellNavFor(role) : []), [role]);

    const handleLogout = useCallback(async () => {
        setSheetOpen(false);
        navigate("/", { replace: true });
        await logout();
    }, [navigate, logout]);

    // Signed out: the route under this is about to redirect, and a sidebar
    // drawn for the length of that redirect is a flash of somebody else's app.
    if (user === false) return <Outlet />;

    const controls = (
        <>
            {wide && <NotificationBell />}
            {isConsoleRole(role) ? (
                <AdminAccountMenu
                    user={user}
                    theme={consoleTheme}
                    onThemeChange={setConsoleTheme}
                    onLogout={handleLogout}
                    placement="up"
                />
            ) : (
                <button
                    type="button"
                    onClick={handleLogout}
                    data-testid="nav-logout-btn"
                    aria-label="Log out"
                    title="Log out"
                    className="grid h-11 w-11 place-items-center rounded-button text-muted-foreground transition-colors duration-150 hover:bg-tint/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:h-9 md:w-9"
                >
                    <LogOut className="h-4 w-4" />
                </button>
            )}
        </>
    );

    return (
        <ShellContext.Provider value={true}>
            <BadgeContext.Provider value={publish}>
                <div data-testid={IDS.root} className="flex min-h-screen bg-background">
                    <SideNavFrame>
                        <SideNavLogo to={role ? (isConsoleRole(role) ? "/admin" : role === "campaign_manager" ? "/manager" : "/dashboard") : "/"} />
                        <div className="flex-1 space-y-1 overflow-y-auto">
                            <NavList items={items} badges={badges} />
                        </div>
                        {signedIn ? (
                            <SideNavAccount
                                name={user.name}
                                role={SHELL_ROLE_LABEL[role] || role}
                                controls={controls}
                            />
                        ) : (
                            <div aria-hidden="true" className="mt-3 h-[60px] rounded-[14px] bg-tint/[0.07]" />
                        )}
                    </SideNavFrame>

                    <div className="flex min-w-0 flex-1 flex-col">
                        <AppTopBar onMenu={() => setSheetOpen(true)} bell={!wide} />
                        <div data-testid={IDS.content} className="min-w-0 flex-1 overflow-x-clip">
                            <Suspense fallback={<ContentFallback />}>
                                <Outlet />
                            </Suspense>
                        </div>
                    </div>

                    <Dialog.Root open={sheetOpen} onOpenChange={setSheetOpen}>
                        <Dialog.Portal>
                            <Dialog.Overlay className="fixed inset-0 z-50 bg-scrim/50 md:hidden" />
                            <Dialog.Content
                                data-testid={IDS.sheet}
                                aria-describedby={undefined}
                                data-surface="inverse"
                                className="fixed inset-y-0 left-0 z-50 flex w-[84%] max-w-xs flex-col bg-card px-3 pb-4 pt-4 text-foreground md:hidden"
                            >
                                <div className="mb-3 flex items-center justify-between">
                                    <Dialog.Title className="sr-only">Menu</Dialog.Title>
                                    <SideNavLogo />
                                    <Dialog.Close
                                        aria-label="Close menu"
                                        className="-mt-5 grid h-11 w-11 place-items-center rounded-button text-muted-foreground hover:bg-tint/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                    >
                                        <X className="h-5 w-5" />
                                    </Dialog.Close>
                                </div>
                                <div className="flex-1 space-y-1 overflow-y-auto">
                                    <NavList items={items} badges={badges} onNavigate={() => setSheetOpen(false)} mobile />
                                </div>
                                {signedIn && (
                                    <div className="mt-3 flex items-center gap-3 rounded-[14px] bg-tint/[0.07] p-3">
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate text-[13.5px] font-bold">{user.name || "Signed in"}</p>
                                            <p className="truncate text-xs font-semibold text-muted-foreground">
                                                {SHELL_ROLE_LABEL[role] || role}
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={handleLogout}
                                            data-testid="nav-logout-btn-mobile"
                                            className="min-h-[2.75rem] rounded-button bg-tint/10 px-3.5 text-meta font-bold text-foreground hover:bg-tint/15"
                                        >
                                            Log out
                                        </button>
                                    </div>
                                )}
                            </Dialog.Content>
                        </Dialog.Portal>
                    </Dialog.Root>
                </div>
            </BadgeContext.Provider>
        </ShellContext.Provider>
    );
}
