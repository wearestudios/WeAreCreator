import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu } from "lucide-react";
import { useAuth, homePathFor, isBrandSide } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { NotificationBell } from "@/components/NotificationBell";
import CreatorAvatarMenu from "@/components/CreatorAvatarMenu";
import { api } from "@/lib/api";
import { StudioEndorsement } from "@/components/StudioEndorsement";
import { LANDING_STUDIO as STUDIO_IDS } from "@/constants/testIds";
import {
    Sheet,
    SheetClose,
    SheetContent,
    SheetTitle,
    SheetTrigger,
} from "@/components/ui/sheet";

/**
 * The role-specific links, defined once so the desktop bar and the mobile
 * sheet can't drift apart.
 *
 * Each role gets its own branch and returns from it. Admin used to share the
 * creator branch for the `/campaigns` link, which put the creator's brief feed
 * — a page for deciding what to apply to — in an admin's navigation, next to
 * the console that already lists every campaign with far more on it. Staff
 * navigate to staff tools.
 */
const linksFor = (role) => {
    if (role === "admin") {
        // The console's own sections, so the work is one tap from anywhere
        // rather than a tap to /admin and another to the right tab.
        // `secondary` holds the section shortcuts back to wide screens — four
        // links plus the bell and Log out do not fit beside the wordmark at
        // 640px. They are all in the mobile sheet and in the console's own tab
        // strip regardless, so nothing is only reachable here.
        return [
            { to: "/admin/queue", label: "Queue", testId: "nav-admin-queue", secondary: true },
            { to: "/admin/campaigns", label: "Campaigns", testId: "nav-admin-campaigns", secondary: true },
            { to: "/admin/creators", label: "Creators", testId: "nav-admin-creators", secondary: true },
            { to: "/calendar", label: "Calendar", testId: "nav-calendar", secondary: true },
            { to: "/admin", label: "Admin", testId: "nav-admin", accent: true },
        ];
    }
    if (role === "campaign_manager") {
        // The campaign list is home; the calendar is the same work seen by
        // date, which is how a manager plans and how a brand asks.
        return [
            { to: "/calendar", label: "Calendar", testId: "nav-calendar" },
            { to: "/manager", label: "My campaigns", testId: "nav-manager", accent: true },
        ];
    }
    if (isBrandSide(role)) {
        return [
            { to: "/brand/creators", label: "Creators", testId: "nav-brand-creators" },
            { to: "/calendar", label: "Calendar", testId: "nav-calendar" },
            { to: "/campaigns/new", label: "Post a campaign", testId: "nav-post-campaign" },
            { to: homePathFor(role), label: "Dashboard", testId: "nav-dashboard" },
        ];
    }
    return [
        { to: "/campaigns", label: "Campaigns", testId: "nav-campaigns" },
        { to: homePathFor(role), label: "Dashboard", testId: "nav-dashboard" },
    ];
};

// The pitch, for people who have not signed up. "How it works" and "For brands"
// are conversion copy; showing them to a signed-in admin clearing a review
// queue is noise, and showing "For brands" to a brand is worse than noise.
// The stored role is a wire value; `brand_manager` is not a word anybody says.
const ROLE_LABEL = {
    creator: "Creator",
    brand: "Brand",
    brand_manager: "Brand",
    admin: "WeAre admin",
    campaign_manager: "WeAre manager",
};

const MARKETING_LINKS = [
    { href: "#how-it-works", label: "How it works", testId: "nav-how" },
    { href: "#why", label: "Why WeAre", testId: "nav-why" },
    { to: "/signup?role=brand", label: "For brands →", testId: "nav-for-brands" },
];

export const Navbar = () => {
    const { user, logout } = useAuth();
    // The creator's own photo, for the avatar. Fetched here rather than
    // threaded down because the navbar is on every page and nothing else on
    // most of them knows it.
    const [avatar, setAvatar] = useState(null);
    useEffect(() => {
        if (user?.role !== "creator") return;
        let cancelled = false;
        api.get("/creator/profile")
            .then(({ data }) => !cancelled && setAvatar(data?.profile_image_url || null))
            // A missing photo is the ordinary case, not a failure: the menu
            // falls back to initials and the navbar says nothing about it.
            .catch(() => {});
        return () => {
            cancelled = true;
        };
    }, [user?.role]);
    const navigate = useNavigate();
    const [menuOpen, setMenuOpen] = useState(false);

    // null while /auth/me is in flight, false once we know nobody is signed in.
    const checking = user === null;
    const signedIn = Boolean(user) && user !== false;

    const handleLogout = async () => {
        setMenuOpen(false);
        navigate("/", { replace: true });
        await logout();
    };

    const roleLinks = signedIn ? linksFor(user.role) : [];

    return (
        <header
            data-testid="site-navbar"
            className="sticky top-0 z-40 w-full border-b border-white/10 bg-black/60 backdrop-blur-xl"
        >
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
                {/* Creators keeps the wordmark and the accent; the studio is
                    credited beside it in small caps. An endorsement, not a
                    co-brand — and outside the <Link>, so tapping the logo can
                    only ever go to Creators' own home. */}
                <div className="flex items-center gap-3">
                    <Link
                        to="/"
                        data-testid="nav-logo"
                        className="-my-1 flex min-h-[2.75rem] items-center gap-2 py-1 transition-colors duration-200 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0"
                    >
                        <span className="grid h-8 w-8 place-items-center rounded-md bg-ember-500 font-serif text-lg font-semibold text-black">
                            W
                        </span>
                        <span className="font-serif text-xl tracking-tight">
                            WeAre <span className="text-ember-500">Creators</span>
                        </span>
                    </Link>
                    <span aria-hidden className="hidden h-4 w-px bg-white/15 sm:block" />
                    <StudioEndorsement
                        testid={STUDIO_IDS.nav}
                        className="hidden sm:block"
                    />
                </div>

                {/* Only for people we are still pitching to. A signed-in user
                    has a job in here; "Why WeAre" is not part of it. Hidden
                    while `checking` too, so it doesn't flash in and out once
                    /auth/me answers. */}
                <nav className="hidden items-center gap-8 md:flex">
                    {(checking || signedIn ? [] : MARKETING_LINKS).map((l) =>
                        l.href ? (
                            <a
                                key={l.testId}
                                href={l.href}
                                data-testid={l.testId}
                                className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                            >
                                {l.label}
                            </a>
                        ) : (
                            <Link
                                key={l.testId}
                                to={l.to}
                                data-testid={l.testId}
                                className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                            >
                                {l.label}
                            </Link>
                        ),
                    )}
                </nav>

                <div className="flex items-center gap-3">
                    {/* Until /auth/me resolves we don't know who this is. Showing
                        "Log in" here made every signed-in user flash logged-out on
                        load, so hold the space instead of guessing. */}
                    {checking ? (
                        <div
                            data-testid="nav-auth-loading"
                            aria-hidden
                            className="h-9 w-28 animate-pulse rounded-full bg-white/5"
                        />
                    ) : signedIn ? (
                        <>
                            {roleLinks.map((l) => (
                                <Link
                                    key={l.testId}
                                    to={l.to}
                                    data-testid={l.testId}
                                    className={
                                        "hidden text-sm transition-colors duration-200 " +
                                        (l.secondary ? "lg:inline " : "sm:inline ") +
                                        (l.accent
                                            ? "text-ember-500 hover:text-ember-400"
                                            : "text-muted-foreground hover:text-foreground")
                                    }
                                >
                                    {l.label}
                                </Link>
                            ))}
                            <NotificationBell />
                            {/* Creators get a face and a menu; everyone else
                                keeps the plain button. An admin's navigation
                                is the console and a brand's is its dashboard —
                                neither has a profile this would open onto. */}
                            {user.role === "creator" ? (
                                <CreatorAvatarMenu
                                    user={user}
                                    profileImageUrl={avatar}
                                    onLogout={handleLogout}
                                />
                            ) : (
                                <Button
                                    data-testid="nav-logout-btn"
                                    onClick={handleLogout}
                                    variant="outline"
                                    className="hidden border-white/15 bg-transparent text-foreground hover:bg-white/5 sm:inline-flex"
                                >
                                    Log out
                                </Button>
                            )}
                        </>
                    ) : (
                        <>
                            <Link
                                to="/login"
                                data-testid="nav-login-link"
                                className="hidden text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:inline"
                            >
                                Log in
                            </Link>
                            {/* The primary conversion action stays in the bar at
                                every width; only its label shortens. */}
                            <Link
                                to="/signup?role=creator"
                                data-testid="nav-signup-creator-link"
                            >
                                <Button className="rounded-full bg-ember-500 px-5 text-black hover:bg-ember-400">
                                    <span className="sm:hidden">Sign up</span>
                                    <span className="hidden sm:inline">
                                        Sign up as a creator
                                    </span>
                                </Button>
                            </Link>
                        </>
                    )}

                    {/* Everything above collapses below md; this is the way in. */}
                    <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
                        <SheetTrigger asChild>
                            <button
                                type="button"
                                data-testid="nav-mobile-menu-btn"
                                aria-label="Open menu"
                                className="grid h-11 w-11 place-items-center rounded-md text-muted-foreground transition-colors duration-200 hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:hidden"
                            >
                                <Menu className="h-5 w-5" />
                            </button>
                        </SheetTrigger>
                        <SheetContent
                            side="right"
                            data-testid="nav-mobile-menu"
                            // A menu needs no description; opting out explicitly
                            // keeps Radix from warning about a missing one.
                            aria-describedby={undefined}
                            className="w-[86%] border-l border-white/10 bg-background p-0 sm:max-w-sm"
                        >
                            <SheetTitle className="sr-only">Menu</SheetTitle>

                            <div className="flex h-full flex-col">
                                <div className="flex flex-col gap-1 border-b border-white/10 px-6 py-5">
                                    <span className="font-serif text-xl tracking-tight">
                                        WeAre <span className="text-ember-500">Creators</span>
                                    </span>
                                    <StudioEndorsement testid={STUDIO_IDS.navMobile} />
                                </div>

                                <nav className="flex-1 overflow-y-auto px-6 py-7">
                                    {signedIn && (
                                        <>
                                            <p
                                                data-testid="nav-mobile-role"
                                                className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground"
                                            >
                                                {ROLE_LABEL[user.role] || user.role}
                                            </p>
                                            <div className="mt-4 flex flex-col">
                                                {roleLinks.map((l) => (
                                                    <SheetClose asChild key={l.testId}>
                                                        <Link
                                                            to={l.to}
                                                            data-testid={`${l.testId}-mobile`}
                                                            className={
                                                                "border-b border-white/10 py-3.5 font-serif text-2xl leading-tight transition-colors duration-200 " +
                                                                (l.accent
                                                                    ? "text-ember-500 hover:text-ember-400"
                                                                    : "text-foreground hover:text-ember-500")
                                                            }
                                                        >
                                                            {l.label}
                                                        </Link>
                                                    </SheetClose>
                                                ))}
                                            </div>
                                        </>
                                    )}

                                    {!signedIn && (
                                      <>
                                    <p
                                        className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground"
                                    >
                                        Explore
                                    </p>
                                    <div className="mt-4 flex flex-col">
                                        {MARKETING_LINKS.map((l) => (
                                            <SheetClose asChild key={l.testId}>
                                                {l.href ? (
                                                    <a
                                                        href={l.href}
                                                        data-testid={`${l.testId}-mobile`}
                                                        className="border-b border-white/10 py-3.5 font-serif text-2xl leading-tight text-foreground transition-colors duration-200 hover:text-ember-500"
                                                    >
                                                        {l.label}
                                                    </a>
                                                ) : (
                                                    <Link
                                                        to={l.to}
                                                        data-testid={`${l.testId}-mobile`}
                                                        className="border-b border-white/10 py-3.5 font-serif text-2xl leading-tight text-foreground transition-colors duration-200 hover:text-ember-500"
                                                    >
                                                        {l.label}
                                                    </Link>
                                                )}
                                            </SheetClose>
                                        ))}
                                    </div>
                                      </>
                                    )}
                                </nav>

                                <div className="border-t border-white/10 px-6 py-6">
                                    {checking ? (
                                        <div
                                            aria-hidden
                                            className="h-11 w-full animate-pulse rounded-full bg-white/5"
                                        />
                                    ) : signedIn ? (
                                        <Button
                                            data-testid="nav-logout-btn-mobile"
                                            onClick={handleLogout}
                                            variant="outline"
                                            className="h-11 w-full rounded-full border-white/15 bg-transparent text-foreground hover:bg-white/5"
                                        >
                                            Log out
                                        </Button>
                                    ) : (
                                        <div className="flex flex-col gap-3">
                                            <SheetClose asChild>
                                                <Link
                                                    to="/signup?role=creator"
                                                    data-testid="nav-signup-creator-link-mobile"
                                                >
                                                    <Button className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                                        Sign up as a creator
                                                    </Button>
                                                </Link>
                                            </SheetClose>
                                            <SheetClose asChild>
                                                <Link
                                                    to="/login"
                                                    data-testid="nav-login-link-mobile"
                                                    className="py-2 text-center text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                                                >
                                                    Log in
                                                </Link>
                                            </SheetClose>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </SheetContent>
                    </Sheet>
                </div>
            </div>
        </header>
    );
};
