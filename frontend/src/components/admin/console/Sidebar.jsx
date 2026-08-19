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
import {
    Activity,
    BadgeCheck,
    Building2,
    ChevronsLeft,
    ChevronsRight,
    Inbox,
    LayoutDashboard,
    ScrollText,
    Sparkles,
    Stethoscope,
    Users,
    X,
} from "lucide-react";

import { CALM, DENSITY, FOCUS, TEXT } from "@/components/admin/console/tokens";
import { readSavedFilters } from "@/components/admin/console/useListState";
import { ADMIN_SIDEBAR as IDS } from "@/constants/testIds";

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
    { key: "creators", to: "creators", label: "Creators", Icon: Users },
    { key: "campaigns", to: "campaigns", label: "Campaigns", Icon: Sparkles },
    { key: "brands", to: "brands", label: "Brands", Icon: Building2 },
    { key: "performance", to: "performance", label: "Performance", Icon: Activity },
    { key: "health", to: "health", label: "Health", Icon: Stethoscope, badge: "health_issues" },
    { key: "audit", to: "audit", label: "Audit", Icon: ScrollText },
];

/**
 * How many are waiting.
 *
 * Two forms, and the narrow one is not a smaller number — it is a dot. A
 * two-digit count in a 56px rail is unreadable, but "something is waiting
 * here" still has to survive, and it is the only thing on the rail that could
 * make somebody open it.
 */
function Badge({ count, active, dotOnly = false }) {
    if (!count) return null;
    const dot = (
        <span
            aria-label={`${count} waiting`}
            className={`ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-ember-500 ${
                dotOnly ? "" : "md:hidden"
            }`}
        />
    );
    if (dotOnly) return dot;
    return (
        <>
            {dot}
            <span
                className={`ml-auto hidden h-5 min-w-[1.25rem] shrink-0 place-items-center rounded px-1 md:grid ${TEXT.meta} tabular-nums ${
                    active ? "bg-ember-500 text-black" : "bg-white/10 text-foreground"
                }`}
            >
                {count > 99 ? "99+" : count}
            </span>
        </>
    );
}

export function AdminSidebar({ counts }) {
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
            // **Below `md` the rail is the only form.** 224px of a 390px screen
            // spent on navigation leaves 166px for the table it is navigating
            // to, which is not a working surface — it is a list that scrolls
            // sideways. Expanded is a choice you can only make where there is
            // room for it.
            className={`sticky top-16 flex h-[calc(100vh-4rem)] shrink-0 flex-col border-r border-white/10 bg-card/40 ${CALM} ${
                collapsed ? "w-14" : "w-14 md:w-56"
            }`}
        >
            <div className="flex-1 overflow-y-auto py-2">
                {ADMIN_SECTIONS.map(({ key, to, label, Icon, badge, end }) => {
                    const count = badge ? counts?.[badge] ?? 0 : 0;
                    const sets = saved[key] || [];
                    return (
                        <div key={key}>
                            <NavLink
                                to={to}
                                end={end}
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
                                        {!collapsed && (
                                            <span className="hidden truncate md:inline">{label}</span>
                                        )}
                                        {count > 0 && (
                                            <span
                                                data-testid={IDS.badge(key)}
                                                className="ml-auto flex items-center"
                                            >
                                                <Badge
                                                    count={count}
                                                    active={isActive}
                                                    dotOnly={collapsed}
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
                                        onClick={() =>
                                            navigate(`/admin/${to}`, {
                                                state: { savedFilter: set.state },
                                            })
                                        }
                                        className={`mx-1 hidden h-8 w-[calc(100%-0.5rem)] items-center gap-2 rounded pl-9 pr-2 text-left md:flex ${TEXT.meta} ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground ${FOCUS}`}
                                    >
                                        <span className="truncate">{set.name}</span>
                                    </button>
                                ))}
                        </div>
                    );
                })}
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
