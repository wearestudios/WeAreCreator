// Density — two of them, one component set, admin only.
//
// Comfortable is the default for everybody and the only option a creator or a
// brand ever gets. Compact exists for an admin working a long queue: 9px row
// padding instead of 22, 14px body instead of 16, 13px meta instead of 14,
// avatar blocks dropped, 16px between sections instead of 26. Colours, radii
// and focus styles do not change — those are not in the compact block in
// index.css at all, which is how that is held.
//
// **The mechanism is one attribute.** `data-density` on a wrapper redefines
// the custom properties every row, cell and type token already reads. No
// duplicated components, no second stylesheet, no className that branches on
// the density — `DataTable` reads `--row-h` off the element for its windowing
// arithmetic rather than knowing a number.
//
// **Where it may go is enforced, not documented.** `DensityScope` is the only
// thing that writes the attribute; it takes a `surface` from
// `DENSITY_SURFACES` and throws in development when handed anything else or
// rendered off an /admin route — so wrapping the app, a creator screen or the
// overview in compact fails loudly the first time anybody loads it, and
// `test_density.py` fails CI before that.
//
// **Persistence is the account, cached in the browser.** The choice lives on
// the admin's own user record (`PUT /auth/me/density`, admin-only, a 403 for
// every other role) so it follows them across devices; localStorage holds a
// copy so the first paint of a table is already the right density instead of
// snapping after `/auth/me` lands.
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { ADMIN_DENSITY as IDS } from "@/constants/testIds";
import { CALM, FOCUS } from "./tokens";

export const DENSITIES = ["comfortable", "compact"];
export const DEFAULT_DENSITY = "comfortable";
export const DENSITY_STORAGE_KEY = "weare:admin-density";

/**
 * The console sections that may be compact: the action queue, the data tables
 * and the audit log. Keyed by the section's path under /admin.
 *
 * **The overview is not here and must never be**: it is the screen somebody
 * reads to find out what is wrong, not one they work down, and compacting it
 * trades legibility for a density nobody needs on twelve tiles. Health,
 * analytics, settings and the case-study editor are not tables either.
 */
export const DENSITY_SURFACES = [
    "queue",
    "creator-reviews",
    "campaign-reviews",
    "brand-reviews",
    "disputes",
    "circumvention",
    "enquiries",
    "creators",
    "campaigns",
    "brands",
    "audit",
    "team",
    "deletions",
    "dormant",
];

const valid = (d) => (DENSITIES.includes(d) ? d : null);

function cached() {
    try {
        return valid(window.localStorage?.getItem(DENSITY_STORAGE_KEY));
    } catch {
        // Private windows throw on access. The table still has to render.
        return null;
    }
}

function cache(d) {
    try {
        window.localStorage?.setItem(DENSITY_STORAGE_KEY, d);
    } catch {
        // A worse experience, not a broken one: the account still has it.
    }
}

const DensityContext = createContext({
    density: DEFAULT_DENSITY,
    setDensity: () => {},
    // Off by default: outside the console's provider there is nothing to set.
    adjustable: false,
});

/** The density in force here. Comfortable outside the console. */
export const useDensity = () => useContext(DensityContext);

/**
 * Holds an admin's density for the console. Mounted once, in `AdminConsole`,
 * and only for an admin — `weare_team` sees the console comfortable and gets
 * no control, because the server refuses to store a choice for them.
 */
export function DensityProvider({ user, children }) {
    const isAdmin = user?.role === "admin";
    const fromAccount = isAdmin ? valid(user?.admin_density) : null;
    const [density, setLocal] = useState(
        () => (isAdmin ? fromAccount || cached() || DEFAULT_DENSITY : DEFAULT_DENSITY),
    );

    // The account is the record. When /auth/me lands with a value different
    // from the cache, the account wins and the cache is corrected.
    useEffect(() => {
        if (!fromAccount) return;
        setLocal(fromAccount);
        cache(fromAccount);
    }, [fromAccount]);

    const setDensity = useCallback(
        async (next) => {
            if (!isAdmin || !valid(next)) return;
            const previous = density;
            // Optimistic: the table changes on the frame of the click.
            setLocal(next);
            cache(next);
            try {
                await api.put("/auth/me/density", { density: next });
            } catch (err) {
                setLocal(previous);
                cache(previous);
                notifyError(err);
            }
        },
        [isAdmin, density],
    );

    const value = useMemo(
        () => ({ density: isAdmin ? density : DEFAULT_DENSITY, setDensity, adjustable: isAdmin }),
        [isAdmin, density, setDensity],
    );
    return <DensityContext.Provider value={value}>{children}</DensityContext.Provider>;
}

const ON_DEV = process.env.NODE_ENV !== "production";

/** Whether `surface` may carry a density at this pathname. Exported for the
 *  test and for the header control, so the two cannot disagree. */
export function densityAllowed(surface, pathname) {
    if (!DENSITY_SURFACES.includes(surface)) return false;
    // The section's own list, exactly. A record's detail page under it
    // (`/admin/campaigns/:id`) is a page somebody reads, not a table.
    const path = String(pathname || "").replace(/\/$/, "");
    return path === `/admin/${surface}`;
}

/**
 * The one writer of `data-density`.
 *
 * In development a surface outside the list, or a render off its own /admin
 * route, throws: a mistake here should stop the screen in front of whoever
 * made it, not ship a creator's dashboard in 13px type. In production it
 * renders comfortable instead and logs, because a guard that takes down an
 * admin's working screen is worse than the density it was guarding.
 */
export function DensityScope({ surface, children }) {
    const { pathname } = useLocation();
    const { density } = useDensity();
    const allowed = densityAllowed(surface, pathname);
    if (!allowed) {
        const message =
            `DensityScope: "${surface}" at ${pathname} is not a density surface. ` +
            "Compact is for the admin action queue, the console's data tables " +
            "and the audit log only — see DENSITY_SURFACES.";
        if (ON_DEV) throw new Error(message);
        // eslint-disable-next-line no-console
        console.error(message);
    }
    return (
        <div data-density={allowed ? density : DEFAULT_DENSITY} data-testid={IDS.scope}>
            {children}
        </div>
    );
}

/**
 * Comfortable | Compact — a two-state segmented pill in the console's page
 * header. Two real buttons with `aria-pressed`, not an icon and not a menu:
 * the state is the label, and both are always visible.
 *
 * Renders only for an admin, and only on a section that can be compact — a
 * control that does nothing on the overview is a control that looks broken.
 */
export function DensityToggle() {
    const { pathname } = useLocation();
    const { density, setDensity, adjustable } = useDensity();
    const section = String(pathname || "").split("/")[2] || "";
    if (!adjustable || !densityAllowed(section, `/admin/${section}`)) return null;
    return (
        <div
            role="group"
            aria-label="Row density"
            data-testid={IDS.toggle}
            // Hidden below `sm`: on a phone the console's rows are a stacked
            // list rather than a table, and the pill pushed the console's own
            // label out of a 390px header. The stored choice still applies.
            className="hidden items-center rounded-pill border border-border bg-card p-0.5 sm:inline-flex"
        >
            {DENSITIES.map((d) => {
                const on = density === d;
                return (
                    <button
                        key={d}
                        type="button"
                        aria-pressed={on}
                        data-testid={IDS.option(d)}
                        onClick={() => setDensity(d)}
                        className={`min-h-[2.25rem] rounded-pill px-3 text-meta ${CALM} ${FOCUS} ${
                            on
                                ? "bg-primary text-primary-foreground"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        {d === "comfortable" ? "Comfortable" : "Compact"}
                    </button>
                );
            })}
        </div>
    );
}
