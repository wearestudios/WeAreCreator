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
    BadgeCheck,
    Building2,
    ChevronsLeft,
    ChevronsRight,
    Inbox,
    LayoutDashboard,
    MoonStar,
    ScrollText,
    Sparkles,
    Stethoscope,
    Timer,
    UserCog,
    UserX,
    Users,
    X,
} from "lucide-react";

import { CALM, DENSITY, FOCUS, TEXT } from "@/components/admin/console/tokens";
import { readSavedFilters } from "@/components/admin/console/useListState";
import { ADMIN_SHELL as SHELL_IDS, ADMIN_SIDEBAR as IDS } from "@/constants/testIds";
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
    { key: "creators", to: "creators", label: "Creators", Icon: Users, adminOnly: true },
    { key: "campaigns", to: "campaigns", label: "Campaigns", Icon: Sparkles },
    { key: "brands", to: "brands", label: "Brands", Icon: Building2 },
    { key: "performance", to: "performance", label: "Performance", Icon: Activity },
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
    // Re-engagement, which is nobody's queue — it is the work that only gets
    // done if somebody can see who to do it for.
    { key: "dormant", to: "dormant", label: "Gone quiet", Icon: MoonStar },
    // **The standard every other section is measured against**, so somebody
    // whose queue is being measured is not the one who can move the line.
    {
        key: "settings",
        to: "settings",
        label: "Targets",
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
 * How many are waiting.
 *
 * **A dot is what a number becomes when there is no room to read it** — a
 * two-digit count in a 56px rail is a smudge, but "something is waiting here"
 * is the only thing on that rail that would make anybody open it. Anywhere
 * with room says the number.
 *
 * @param {"rail"|"full"} form  `rail` is the collapsed sidebar: a dot.
 */
function Badge({ count, active, form = "full" }) {
    if (!count) return null;
    if (form === "rail") {
        return (
            <span
                aria-label={`${count} waiting`}
                className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-ember-500"
            />
        );
    }
    return (
        <span
            className={`ml-auto grid h-5 min-w-[1.25rem] shrink-0 place-items-center rounded px-1 ${TEXT.meta} tabular-nums ${
                active ? "bg-ember-500 text-black" : "bg-white/10 text-foreground"
            }`}
        >
            {count > 99 ? "99+" : count}
        </span>
    );
}

/**
 * One section, as it appears in both forms.
 *
 * The rail and the sheet are the same list with the same badges and the same
 * saved sets — written once, because a phone finding a different set of
 * sections from a laptop is the bug this shape exists to prevent.
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
                    `mx-1 flex h-9 items-center gap-2.5 rounded ${DENSITY.row} ${TEXT.body} ${CALM} ${FOCUS} ` +
                    (isActive
                        ? "bg-ember-500/10 text-ember-500"
                        : "text-muted-foreground hover:bg-white/5 hover:text-foreground")
                }
            >
                {({ isActive }) => (
                    <>
                        <Icon className="h-4 w-4 shrink-0" />
                        {!collapsed && <span className={labelClass}>{label}</span>}
                        {count > 0 && (
                            <span data-testid={IDS.badge(key)} className="ml-auto flex items-center">
                                <Badge
                                    count={count}
                                    active={isActive}
                                    form={collapsed ? "rail" : "full"}
                                />
                            </span>
                        )}
                    </>
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
                        className={`mx-1 h-8 w-[calc(100%-0.5rem)] items-center gap-2 rounded pl-9 pr-2 text-left ${labelClass ? "flex" : "hidden"} ${TEXT.meta} ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground ${FOCUS}`}
                    >
                        <span className="truncate">{set.name}</span>
                    </button>
                ))}
        </div>
    );
}

/**
 * The sections on a phone: a sheet, opened from the console's own header.
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
                <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 md:hidden" />
                <Dialog.Content
                    data-testid={SHELL_IDS.mobileNav}
                    aria-describedby={undefined}
                    className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-white/10 bg-card md:hidden"
                >
                    <div className="flex items-center justify-between border-b border-white/10 px-3 py-2.5">
                        <Dialog.Title className={`${TEXT.meta} uppercase tracking-[0.16em] text-muted-foreground`}>
                            Sections
                        </Dialog.Title>
                        <Dialog.Close
                            aria-label="Close"
                            className={`grid h-8 w-8 place-items-center rounded ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground ${FOCUS}`}
                        >
                            <X className="h-4 w-4" />
                        </Dialog.Close>
                    </div>
                    <div className="flex-1 overflow-y-auto py-2">
                        {sectionsFor(role).map((section) => (
                            <SectionLink
                                key={section.key}
                                section={section}
                                counts={counts}
                                saved={saved}
                                collapsed={false}
                                labelClass="truncate"
                                onNavigate={() => onOpenChange(false)}
                            />
                        ))}
                    </div>
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    );
}

export function AdminSidebar({ counts, role }) {
    const navigate = useNavigate();
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
        <nav
            data-testid={IDS.root}
            data-collapsed={collapsed ? "true" : "false"}
            aria-label="Admin sections"
            // **`hidden md:flex`.** Below that the sections are a sheet, not a
            // rail: see `AdminNavSheet`. A 56px column of unlabelled icons is
            // navigation you have to already know.
            className={`sticky top-16 hidden h-[calc(100vh-4rem)] shrink-0 flex-col border-r border-white/10 bg-card/40 md:flex ${CALM} ${
                collapsed ? "w-14" : "w-56"
            }`}
        >
            <div className="flex-1 overflow-y-auto py-2">
                {sectionsFor(role).map((section) => (
                    <SectionLink
                        key={section.key}
                        section={section}
                        counts={counts}
                        saved={saved}
                        collapsed={collapsed}
                        labelClass="truncate"
                    />
                ))}
            </div>

            <button
                type="button"
                onClick={toggle}
                data-testid={IDS.collapse}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                aria-expanded={!collapsed}
                className={`m-1 flex h-9 items-center gap-2.5 rounded ${DENSITY.row} ${TEXT.meta} ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground ${FOCUS}`}
            >
                {collapsed ? (
                    <ChevronsRight className="h-4 w-4" />
                ) : (
                    <>
                        <ChevronsLeft className="h-4 w-4" />
                        <span className="hidden md:inline">Collapse</span>
                    </>
                )}
            </button>
        </nav>
    );
}

export default AdminSidebar;
