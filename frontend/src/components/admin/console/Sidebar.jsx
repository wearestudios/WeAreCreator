// The console's persistent left sidebar.
//
// It replaced a horizontal tab strip of nine items, which had two problems a
// working tool cannot carry. The strip scrolled sideways on anything under a
// laptop, so half the sections were off-screen and the badge counts with them
// — you could not see that six brands were waiting without scrolling the
// navigation. And nine tabs across the top spent the widest dimension of the
// screen on chrome, when the thing that actually needs width is a table.
//
// A sidebar is always visible, always the same order, and collapses to icons
// when the canvas needs the room. **Collapse persists**, because it is a
// preference about how somebody works rather than a per-visit choice.
//
// Saved filter sets appear under their section, indented. They are the one
// piece of console state that outlives the session — naming one is a
// deliberate act, so it should still be there next week.
import React, { useCallback, useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import {
    Activity,
    TrendingUp,
    BadgeCheck,
    Building2,
    CalendarDays,
    ChevronsLeft,
    ClipboardList,
    ChevronsRight,
    Inbox,
    LayoutDashboard,
    MoonStar,
    Newspaper,
    Archive,
    Scale,
    ShieldAlert,
    ScrollText,
    Sparkles,
    Stethoscope,
    Timer,
    UserCog,
    UserRoundPen,
    UserX,
    Users,
    X,
} from "lucide-react";

import { CALM, FOCUS, TEXT } from "@/components/admin/console/tokens";
import { readSavedFilters } from "@/components/admin/console/useListState";
import { ADMIN_SHELL as SHELL_IDS, ADMIN_SIDEBAR as IDS } from "@/constants/testIds";
import AnimatedNumber from "@/components/motion/AnimatedNumber";
import {
    SIDEBAR_W,
    SideNavAccount,
    SideNavFrame,
    SideNavHeading,
    SideNavItem,
    SideNavLogo,
} from "@/components/app/SideNav";
import { INT } from "@/lib/motion";
import { isAllAccess } from "@/lib/consoleScope";

const COLLAPSE_KEY = "weare.admin.sidebar";

/**
 * The sections, in working order: what needs doing, then the records, then the
 * instruments.
 *
 * `badge` names which count from /admin/dashboard sits on the item — only the
 * sections where a number means "this many are waiting for you". A badge on
 * Creators would just be how many creators exist, which is not news.
 *
 * `to` is relative to /admin, so the sidebar and the router cannot disagree.
 *
 * `adminOnly` marks the sections that are the *platform's* rather than a
 * brand's — the global creator directory and its review queue, the
 * platform-wide instruments, and the settings that hand out scope. They are
 * admin-only on the server; this flag is what stops a team member being shown
 * a door that answers 403. Everything unmarked is scoped to the caller's
 * brands and reads correctly for both roles.
 */
export const ADMIN_SECTIONS = [
    { key: "overview", to: "", label: "Overview", Icon: LayoutDashboard, end: true },
    { key: "queue", to: "queue", label: "Action queue", Icon: Inbox, badge: "queue_rest" },
    {
        key: "creator-reviews",
        to: "creator-reviews",
        label: "Creator reviews",
        Icon: BadgeCheck,
        badge: "creators_to_review",
        adminOnly: true,
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
    // **Its own section rather than a filter on the collaborations list.**
    // Every open row here is a frozen collaboration and usually a payment not
    // going out — the one queue where the cost of not looking is measured in
    // days of somebody's income.
    {
        key: "disputes",
        to: "disputes",
        label: "Disputes",
        Icon: Scale,
        badge: "disputes_open",
    },
    // **Admin-only, like the creator queues beside it.** A creator works
    // across every brand, so deciding whether one keeps their account is not
    // scoped work — the same line `ADMIN_ONLY_EXPORTS` draws.
    {
        key: "circumvention",
        to: "circumvention",
        label: "Off-platform",
        Icon: ShieldAlert,
        badge: "circumvention_open",
        adminOnly: true,
    },
    // **Admin-only for the reason the survey is.** An enquiry is attached to
    // no brand, so there is nothing for a scoped console to be scoped to —
    // narrowing it returns an empty list rather than a smaller one.
    {
        key: "enquiries",
        to: "enquiries",
        label: "Enquiries",
        Icon: Inbox,
        badge: "enquiries_unhandled",
        adminOnly: true,
    },
    { key: "creators", to: "creators", label: "Creators", Icon: Users, adminOnly: true },
    { key: "campaigns", to: "campaigns", label: "Campaigns", Icon: Sparkles },
    { key: "brands", to: "brands", label: "Brands", Icon: Building2 },
    // **Admin-only: `/admin/intelligence` is.** It was unmarked, so a team
    // member was offered a section whose only read answered 403 and drew an
    // empty page. The flag is now checked against the server's own guard.
    {
        key: "performance",
        to: "performance",
        label: "Performance",
        Icon: Activity,
        adminOnly: true,
    },
    // The four ratios the business is judged on, as opposed to Performance,
    // which is what the *content* did. Admin-only like every other
    // platform-wide instrument: a repeat rate across every brand is a fact
    // about the business, not about the brands a scoped team member works on.
    {
        key: "analytics",
        to: "analytics",
        label: "Analytics",
        Icon: TrendingUp,
        adminOnly: true,
    },
    {
        key: "health",
        to: "health",
        label: "Health",
        Icon: Stethoscope,
        badge: "health_issues",
        adminOnly: true,
    },
    { key: "audit", to: "audit", label: "Audit", Icon: ScrollText, adminOnly: true },
    { key: "team", to: "team", label: "Team", Icon: UserCog, adminOnly: true },
    // A right being exercised against the whole company, not scoped work.
    {
        key: "deletions",
        to: "deletions",
        label: "Deletions",
        Icon: UserX,
        badge: "deletions_waiting",
        adminOnly: true,
    },
    // **Finished work, turned into what sells the next campaign.** Not a
    // queue and not a record: nothing arrives here to be worked, and nothing
    // here is the system of record for anything. It is the one section whose
    // output is read by strangers, which is also why it is admin-only —
    // `weare_team` is scoped to brands, and what the platform says about
    // itself in public is not a brand-scoped decision.
    {
        key: "case-studies",
        to: "case-studies",
        label: "Case studies",
        Icon: Newspaper,
        adminOnly: true,
    },
    // Re-engagement, which is nobody's queue — it is the work that only gets
    // done if somebody can see who to do it for.
    { key: "dormant", to: "dormant", label: "Gone quiet", Icon: MoonStar },
    // Signed up and stalled — the other half of re-engagement, and the one
    // with a reminder to send. Drawn from the global roster, so admin-only.
    {
        key: "unfinished",
        to: "unfinished",
        label: "Unfinished profiles",
        Icon: UserRoundPen,
        adminOnly: true,
    },
    // The anonymous research survey. Nobody in it is attached to a brand, so
    // there is nothing for a scoped console to be scoped to.
    {
        key: "survey",
        to: "survey",
        label: "Creator survey",
        Icon: ClipboardList,
        adminOnly: true,
    },
    // What we keep and for how long, served rather than only documented so
    // the privacy page and the code cannot say different things.
    {
        key: "retention",
        to: "retention",
        label: "Retention",
        Icon: Archive,
        adminOnly: true,
    },
    // **The standard every other section is measured against**, so somebody
    // whose queue is being measured is not the one who can move the line —
    // and, since it grew the payment terms, somebody whose brand owes us
    // money is not the one who can move that either.
    {
        key: "settings",
        to: "settings",
        label: "Settings",
        Icon: Timer,
        adminOnly: true,
    },
];

/**
 * The sections this role may work in.
 *
 * One function, used by the rail and by the sheet, so a phone cannot find a
 * different set of sections from a laptop — the rule that shape already held,
 * now holding across roles as well.
 */
export const sectionsFor = (role) =>
    isAllAccess(role) ? ADMIN_SECTIONS : ADMIN_SECTIONS.filter((s) => !s.adminOnly);

/**
 * Which heading a section sits under. Overview and the action queue sit above
 * every heading — they are where a working day starts. The headings are small
 * and sentence case, the way the app labels everything now.
 */
export const SECTION_GROUP = {
    "creator-reviews": "Reviews",
    "campaign-reviews": "Reviews",
    "brand-reviews": "Reviews",
    disputes: "Reviews",
    circumvention: "Reviews",
    enquiries: "Reviews",
    creators: "Work",
    campaigns: "Work",
    brands: "Work",
    performance: "Work",
    analytics: "Work",
    health: "Work",
    audit: "Records",
    team: "Records",
    deletions: "Records",
    "case-studies": "Records",
    dormant: "Records",
    unfinished: "Records",
    survey: "Records",
    retention: "Records",
    settings: "Records",
};

/** The heading before `section`, when it opens a new group. */
const headingBefore = (section, i, all) => {
    const group = SECTION_GROUP[section.key];
    if (!group) return null;
    return i === 0 || SECTION_GROUP[all[i - 1].key] !== group ? group : null;
};

/**
 * How many are waiting.
 *
 * **A dot is what a number becomes when there is no room to read it** — a
 * two-digit count in a 56px rail is a smudge, but "something is waiting here"
 * is the only thing on that rail that would make anybody open it. Anywhere
 * with room says the number, on the app's red count badge.
 *
 * @param {"rail"|"full"} form  `rail` is the collapsed sidebar: a dot.
 */
function Badge({ count, form = "full" }) {
    if (!count) return null;
    if (form === "rail") {
        return (
            <span
                aria-label={`${count} waiting`}
                className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-accent"
            />
        );
    }
    return (
        <span className="ml-auto grid h-5 min-w-[1.375rem] shrink-0 place-items-center rounded-pill bg-urgent px-1.5 text-label font-bold tabular-nums text-brand-white">
            {/* **It travels rather than snapping**, which is the only thing
                on the sidebar that tells an admin something arrived while
                they were reading a different section. Over 99 it is a word,
                and tweening to a word is nonsense, so that case prints. */}
            {count > 99 ? "99+" : <AnimatedNumber value={count} format={INT} />}
        </span>
    );
}

/**
 * One section, as it appears in both forms.
 *
 * The rail and the sheet are the same list with the same badges and the same
 * saved sets — written once, because a phone finding a different set of
 * sections from a laptop is the bug this shape exists to prevent. The look is
 * the app's navy item: Manrope 600, the white-10% pill on the current one.
 */
function SectionLink({ section, counts, saved, collapsed, onNavigate, labelClass }) {
    const navigate = useNavigate();
    const { key, to, label, Icon, badge, end } = section;
    const count = badge ? counts?.[badge] ?? 0 : 0;
    const sets = saved[key] || [];
    return (
        <div>
            <NavLink
                to={to}
                end={end}
                onClick={onNavigate}
                data-testid={IDS.item(key)}
                title={label}
                className={({ isActive }) =>
                    `relative flex min-h-[2.5rem] items-center gap-3 rounded-button px-3 text-[14.5px] font-semibold ${CALM} ${FOCUS} ` +
                    (collapsed ? "justify-center " : "") +
                    (isActive
                        ? "bg-tint/10 text-foreground"
                        : "text-muted-foreground hover:bg-tint/5 hover:text-foreground")
                }
            >
                <Icon aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />
                {!collapsed && <span className={labelClass}>{label}</span>}
                {count > 0 && (
                    <span
                        data-testid={IDS.badge(key)}
                        className={collapsed ? "absolute right-1.5 top-1.5 flex" : "ml-auto flex items-center"}
                    >
                        <Badge count={count} form={collapsed ? "rail" : "full"} />
                    </span>
                )}
            </NavLink>

            {/* Saved filter sets, under the section they filter. */}
            {!collapsed &&
                sets.map((set) => (
                    <button
                        key={set.name}
                        type="button"
                        data-testid={IDS.savedFilter(key, set.name)}
                        onClick={() => {
                            navigate(`/admin/${to}`, { state: { savedFilter: set.state } });
                            onNavigate?.();
                        }}
                        className={`h-8 w-full items-center gap-2 rounded-button pl-10 pr-2 text-left ${labelClass ? "flex" : "hidden"} ${TEXT.meta} ${CALM} text-muted-foreground hover:bg-tint/5 hover:text-foreground ${FOCUS}`}
                    >
                        <span className="truncate">{set.name}</span>
                    </button>
                ))}
        </div>
    );
}

/**
 * The sections on a phone: a sheet, opened from the console's top bar.
 *
 * **Not the icon rail.** 56px of a 390px screen is 14% of the width spent on
 * nine unlabelled glyphs, and a touch screen has no hover to explain them —
 * the `title` that carries the rail on a laptop is invisible on a phone. A
 * sheet costs nothing until it is opened, says the words, and gives the list
 * underneath the whole width.
 */
export function AdminNavSheet({ open, onOpenChange, counts, role }) {
    const [saved, setSaved] = useState(() => readSavedFilters());

    useEffect(() => {
        const sync = () => setSaved(readSavedFilters());
        window.addEventListener("weare:saved-filters", sync);
        return () => window.removeEventListener("weare:saved-filters", sync);
    }, []);

    return (
        <Dialog.Root open={open} onOpenChange={onOpenChange}>
            <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-scrim/50 md:hidden" />
                <Dialog.Content
                    data-testid={SHELL_IDS.mobileNav}
                    aria-describedby={undefined}
                    // Inverse chrome, like the column it stands in for.
                    data-surface="inverse"
                    className="fixed inset-y-0 left-0 z-50 flex w-[84%] max-w-xs flex-col bg-card px-3 pb-4 pt-4 text-foreground md:hidden"
                >
                    <div className="mb-2 flex items-center justify-between">
                        <Dialog.Title className="px-2.5 text-body font-extrabold">Sections</Dialog.Title>
                        <Dialog.Close
                            aria-label="Close"
                            className={`grid h-11 w-11 place-items-center rounded-button ${CALM} text-muted-foreground hover:bg-tint/5 hover:text-foreground ${FOCUS}`}
                        >
                            <X className="h-5 w-5" />
                        </Dialog.Close>
                    </div>
                    <div className="flex-1 space-y-0.5 overflow-y-auto">
                        {sectionsFor(role).map((section, i, all) => (
                            <React.Fragment key={section.key}>
                                {headingBefore(section, i, all) && (
                                    <SideNavHeading>{headingBefore(section, i, all)}</SideNavHeading>
                                )}
                                <SectionLink
                                    section={section}
                                    counts={counts}
                                    saved={saved}
                                    collapsed={false}
                                    labelClass="truncate"
                                    onNavigate={() => onOpenChange(false)}
                                />
                            </React.Fragment>
                        ))}
                        <SideNavItem
                            to="/calendar"
                            Icon={CalendarDays}
                            label="Calendar"
                            testid={IDS.item("calendar")}
                            onNavigate={() => onOpenChange(false)}
                        />
                    </div>
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    );
}

/**
 * The console's column: the logo, the sections under their headings, the
 * calendar (which is a page of its own outside `/admin`), the collapse, and
 * the account — the same navy parts every app surface navigates from.
 */
export function AdminSidebar({ counts, role, account }) {
    const [collapsed, setCollapsed] = useState(() => {
        try {
            return window.localStorage.getItem(COLLAPSE_KEY) === "1";
        } catch {
            return false;
        }
    });
    const [saved, setSaved] = useState(() => readSavedFilters());

    // The list view writes saved sets and fires this; without it the sidebar
    // would only pick a new one up on a full reload, which is exactly when
    // somebody has just named it and is looking for it.
    useEffect(() => {
        const sync = () => setSaved(readSavedFilters());
        window.addEventListener("weare:saved-filters", sync);
        window.addEventListener("storage", sync);
        return () => {
            window.removeEventListener("weare:saved-filters", sync);
            window.removeEventListener("storage", sync);
        };
    }, []);

    const toggle = useCallback(() => {
        setCollapsed((c) => {
            try {
                window.localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
            } catch {
                /* Preference only. */
            }
            return !c;
        });
    }, []);

    return (
        // **`hidden md:flex`** (in the frame). Below that the sections are a
        // sheet, not a rail: see `AdminNavSheet`.
        <SideNavFrame
            testid={IDS.root}
            label="Admin sections"
            width={collapsed ? "w-[72px]" : SIDEBAR_W}
            data-collapsed={collapsed ? "true" : "false"}
        >
            <SideNavLogo to="/admin" compact={collapsed} />
            <div className="-mx-1 flex-1 space-y-0.5 overflow-y-auto px-1">
                {sectionsFor(role).map((section, i, all) => (
                    <React.Fragment key={section.key}>
                        {headingBefore(section, i, all) && (
                            <SideNavHeading hidden={collapsed}>{headingBefore(section, i, all)}</SideNavHeading>
                        )}
                        <SectionLink
                            section={section}
                            counts={counts}
                            saved={saved}
                            collapsed={collapsed}
                            labelClass="truncate"
                        />
                    </React.Fragment>
                ))}
                <SideNavHeading hidden={collapsed}>Elsewhere</SideNavHeading>
                <SideNavItem
                    to="/calendar"
                    Icon={CalendarDays}
                    label="Calendar"
                    compact={collapsed}
                    testid={IDS.item("calendar")}
                />
            </div>

            <button
                type="button"
                onClick={toggle}
                data-testid={IDS.collapse}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                aria-expanded={!collapsed}
                className={`mt-2 flex min-h-[2.5rem] items-center gap-3 rounded-button px-3 text-meta font-semibold ${CALM} text-muted-foreground hover:bg-tint/5 hover:text-foreground ${FOCUS} ${collapsed ? "justify-center" : ""}`}
            >
                {collapsed ? (
                    <ChevronsRight className="h-4 w-4" />
                ) : (
                    <>
                        <ChevronsLeft className="h-4 w-4" />
                        <span>Collapse</span>
                    </>
                )}
            </button>

            {account ? <SideNavAccount {...account} compact={collapsed} /> : null}
        </SideNavFrame>
    );
}

export default AdminSidebar;
