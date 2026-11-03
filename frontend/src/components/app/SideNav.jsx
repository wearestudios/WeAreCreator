/**
 * The app's navy sidebar, as parts — one look for every signed-in surface.
 *
 * The brand, the creator, the manager and the console all navigate from the
 * same column: the logo at the top, items in Manrope 600 with a white-10%
 * pill on the one you are on, red count badges, small sentence-case headings
 * where there are groups, and the account at the foot. `AppShell` assembles
 * it for the first three; the console's `AdminSidebar` assembles it around
 * its own sections, collapse and saved filter sets. Two assemblies, one set
 * of parts, so the console and a dashboard cannot drift into two sidebars.
 *
 * **Inverse chrome.** `data-surface="inverse"` redefines the semantic tokens
 * for everything inside, so a link here says `text-muted-foreground` and gets
 * the light ink on navy, and the logo paints white by the rule `.weare-logo`
 * already has.
 *
 * `ShellContext` is how a page knows it is inside one of these: the shared
 * `Navbar` returns nothing there, so the nineteen pages that render it keep
 * rendering it, and it shows up only where there is no sidebar.
 */
import React from "react";
import { Link, NavLink } from "react-router-dom";
import { Menu } from "lucide-react";

import Logo from "@/components/brand/Logo";
import { NotificationBell } from "@/components/NotificationBell";
import { APP_SHELL as IDS } from "@/constants/testIds";

const cx = (...parts) => parts.filter(Boolean).join(" ");

export { ShellContext, useInShell } from "@/components/app/shellContext";

/** The role, in words somebody would say. */
export const SHELL_ROLE_LABEL = {
    creator: "Creator",
    brand: "Brand manager",
    brand_manager: "Brand manager",
    campaign_manager: "WeAre manager",
    admin: "Admin",
    weare_team: "WeAre team",
};

/** The sidebar's width. The fallback reserves the same column. */
export const SIDEBAR_W = "w-[244px]";

const FOCUS =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

/** The column itself. Sticky, full height, `hidden md:flex` — below `md`
 * the same items are a sheet opened from the top bar. */
export function SideNavFrame({ children, label = "Main", width = SIDEBAR_W, testid = IDS.sidebar, ...rest }) {
    return (
        <nav
            data-testid={testid}
            aria-label={label}
            data-surface="inverse"
            className={cx(
                "sticky top-0 hidden h-screen shrink-0 flex-col bg-card px-3 pb-4 pt-5 text-foreground transition-[width] duration-150 md:flex",
                width,
            )}
            {...rest}
        >
            {children}
        </nav>
    );
}

/** The logo at the head of the column, linking home. */
export function SideNavLogo({ to = "/", compact = false }) {
    return (
        <Link
            to={to}
            data-testid={IDS.logo}
            aria-label="WeAre Creators — home"
            className={cx("mb-5 flex min-h-[2.5rem] items-center rounded-button px-2.5", FOCUS)}
        >
            <Logo variant={compact ? "mark" : "horizontal"} height={compact ? 26 : 28} />
        </Link>
    );
}

/** A small sentence-case heading over a group of items. */
export function SideNavHeading({ children, hidden = false }) {
    if (hidden) return <div className="mx-3 my-2 h-px bg-tint/10" aria-hidden="true" />;
    return <p className="px-3.5 pb-1.5 pt-4 text-xs font-bold text-muted-foreground/80">{children}</p>;
}

/** A count on an item: red, a number, and "99+" past that. */
export function SideNavBadge({ count, testid }) {
    if (!count) return null;
    return (
        <span
            data-testid={testid}
            className="ml-auto grid h-5 min-w-[1.375rem] shrink-0 place-items-center rounded-pill bg-accent-ink px-1.5 text-label font-bold tabular-nums text-brand-white"
        >
            {count > 99 ? "99+" : count}
        </span>
    );
}

/** One destination. Manrope 600; the white-10% pill marks where you are. */
export function SideNavItem({ to, end, Icon, label, count, badge, onNavigate, testid, compact = false, children }) {
    return (
        <NavLink
            to={to}
            end={end}
            onClick={onNavigate}
            data-testid={testid}
            title={compact ? label : undefined}
            className={({ isActive }) =>
                cx(
                    "flex min-h-[2.75rem] items-center gap-3 rounded-button px-3.5 text-[14.5px] font-semibold transition-colors duration-150 md:min-h-[2.5rem]",
                    FOCUS,
                    isActive
                        ? "bg-tint/10 text-foreground"
                        : "text-muted-foreground hover:bg-tint/5 hover:text-foreground",
                )
            }
        >
            {Icon ? <Icon aria-hidden="true" className="h-[18px] w-[18px] shrink-0" /> : null}
            {!compact && <span className="truncate">{label}</span>}
            {badge ?? (compact ? null : <SideNavBadge count={count} />)}
            {children}
        </NavLink>
    );
}

/** The account at the foot of the column: who is signed in, and their
 * controls (the bell, the menu or a sign-out) beside it. */
export function SideNavAccount({ name, role, controls, compact = false }) {
    return (
        <div
            data-testid={IDS.account}
            className={cx(
                "mt-3 flex items-center gap-2 rounded-[14px] bg-tint/[0.07]",
                compact ? "flex-col p-2" : "p-3",
            )}
        >
            {!compact && (
                <div className="min-w-0 flex-1">
                    <p className="truncate text-[13.5px] font-bold text-foreground">{name || "Signed in"}</p>
                    <p className="truncate text-xs font-semibold text-muted-foreground">{role}</p>
                </div>
            )}
            <div className={cx("flex items-center gap-1", compact && "flex-col")}>{controls}</div>
        </div>
    );
}

/**
 * The bar a phone gets instead of the column: the logo, the bell, and the
 * menu that opens the same items as a sheet. `bell` is false where the column
 * is showing: one bell per screen, because each one asks the server for the
 * notifications on mount. `h-16`, which is what `--nav-h`
 * says below `md`, so everything sticky clears it.
 */
export function AppTopBar({ onMenu, menuTestId = IDS.menuOpen, home = "/", bell = true }) {
    return (
        <header
            data-testid={IDS.topBar}
            className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-border bg-background/90 px-4 backdrop-blur-xl md:hidden"
        >
            <Link to={home} aria-label="WeAre Creators — home" className={cx("rounded-button", FOCUS)}>
                <Logo variant="horizontal" height={26} />
            </Link>
            <div className="flex items-center gap-1">
                {bell && <NotificationBell />}
                <button
                    type="button"
                    onClick={onMenu}
                    data-testid={menuTestId}
                    aria-label="Open menu"
                    className={cx(
                        "grid h-11 w-11 place-items-center rounded-button text-muted-foreground transition-colors duration-150 hover:bg-tint/5 hover:text-foreground",
                        FOCUS,
                    )}
                >
                    <Menu className="h-5 w-5" />
                </button>
            </div>
        </header>
    );
}
