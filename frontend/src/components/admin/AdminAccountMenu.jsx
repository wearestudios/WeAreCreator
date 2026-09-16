// The admin's own account, in the navbar, and the theme control inside it.
//
// There was no admin account menu: an admin got a plain "Log out" button where
// a creator gets a face and two things behind it. That was fine while there
// was one thing to do; the theme is the second, and a toggle floating in the
// layout is a control somebody hits by accident reaching for a table.
//
// **Console roles only.** `weare_team` reads the same console and sits in
// front of it just as long, so the preference is theirs too — the endpoint
// behind this is guarded by `CONSOLE_ROLES` for the same reason.
import React, { useEffect, useRef, useState } from "react";
import { LogOut, Monitor, Moon, Sun } from "lucide-react";

import { api } from "@/lib/api";
import {
    applyTheme,
    rememberTheme,
    resolveTheme,
    systemTheme,
} from "@/lib/consoleTheme";

/** Initials, for a menu button with no photograph behind it. */
const initials = (name) =>
    (name || "")
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase() || "?";

/**
 * Three options rather than a two-way switch.
 *
 * "System" is not a third theme — it is the absence of a choice, which is a
 * different thing from having chosen the one that happens to match today. An
 * admin who tried light and wants to stop thinking about it should be able to
 * hand the question back to their machine, and a two-way toggle gives them
 * nowhere to put that.
 */
const OPTIONS = [
    { value: null, label: "System", Icon: Monitor },
    { value: "light", label: "Light", Icon: Sun },
    { value: "dark", label: "Dark", Icon: Moon },
];

export default function AdminAccountMenu({ user, theme, onThemeChange, onLogout }) {
    const [open, setOpen] = useState(false);
    const [saving, setSaving] = useState(false);
    const wrapRef = useRef(null);

    // Close on an outside click or Escape. A menu that only closes by picking
    // something is a menu people tap around.
    useEffect(() => {
        if (!open) return;
        const onDown = (e) => {
            if (!wrapRef.current?.contains(e.target)) setOpen(false);
        };
        const onKey = (e) => e.key === "Escape" && setOpen(false);
        document.addEventListener("mousedown", onDown);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDown);
            document.removeEventListener("keydown", onKey);
        };
    }, [open]);

    /**
     * **Applied on the frame of the click, saved afterwards.**
     *
     * The same rule every other mutation in the console holds: the reader sees
     * the new value before the server confirms it, because the overwhelming
     * majority succeed and optimising for the failure makes every success feel
     * slow. Here it is starker than usual — a theme that waited for a round
     * trip would mean pressing "Light" and watching a dark screen for 300ms,
     * which reads as the button not working.
     *
     * A failure leaves the theme applied rather than snapping it back. The
     * request is what makes it follow them to another machine; losing that is
     * worth a quiet retry next time, not undoing what they just asked for in
     * front of them.
     */
    const choose = async (value) => {
        const next = resolveTheme(value);
        applyTheme(next);
        rememberTheme(value);
        onThemeChange?.(value);
        setOpen(false);
        setSaving(true);
        try {
            await api.put("/auth/me/console-theme", { theme: value });
        } catch {
            // Deliberately silent. It is applied, it is remembered in this
            // browser, and a toast about a preference not syncing is a toast
            // about something the reader cannot act on.
        } finally {
            setSaving(false);
        }
    };

    const active = theme ?? null;

    return (
        <div ref={wrapRef} className="relative">
            <button
                type="button"
                data-testid="admin-account-button"
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label="Your account"
                onClick={() => setOpen((v) => !v)}
                className="grid h-10 w-10 place-items-center rounded-full border border-tint/15 bg-card text-sm tracking-wide text-muted-foreground transition-colors duration-150 hover:border-primary/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
                {initials(user?.name)}
            </button>

            {open && (
                <div
                    role="menu"
                    data-testid="admin-account-menu"
                    className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-lg border border-tint/15 bg-popover shadow-lg shadow-scrim/30"
                >
                    <div className="border-b border-tint/10 px-3 py-2.5">
                        <p className="truncate text-sm text-foreground">
                            {user?.name || "Your account"}
                        </p>
                        <p className="truncate text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                            {String(user?.role || "").replace(/_/g, " ")}
                        </p>
                    </div>

                    <div className="px-3 py-2.5">
                        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            Appearance
                        </p>
                        <div
                            role="radiogroup"
                            aria-label="Console theme"
                            className="mt-2 grid grid-cols-3 gap-1"
                        >
                            {OPTIONS.map(({ value, label, Icon }) => {
                                const on = active === value;
                                return (
                                    <button
                                        key={label}
                                        type="button"
                                        role="radio"
                                        aria-checked={on}
                                        disabled={saving}
                                        data-testid={`admin-theme-${value || "system"}`}
                                        onClick={() => choose(value)}
                                        className={
                                            "flex flex-col items-center gap-1 rounded-md border px-2 py-2 text-[11px] transition-colors duration-150 disabled:opacity-60 " +
                                            (on
                                                ? "border-primary/50 bg-primary/10 text-primary-ink"
                                                : "border-tint/10 bg-tint/[0.03] text-muted-foreground hover:border-tint/20 hover:text-foreground")
                                        }
                                    >
                                        <Icon className="h-4 w-4" aria-hidden="true" />
                                        {label}
                                    </button>
                                );
                            })}
                        </div>
                        {/* Said rather than implied: "System" on a machine set
                            to light is light, and somebody who cannot see why
                            the console changed at dusk deserves the sentence. */}
                        {active === null && (
                            <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                                Following this device — {systemTheme()} right now.
                            </p>
                        )}
                    </div>

                    <button
                        type="button"
                        role="menuitem"
                        data-testid="admin-account-logout"
                        onClick={onLogout}
                        className="flex w-full items-center gap-2 border-t border-tint/10 px-3 py-2.5 text-left text-sm text-muted-foreground transition-colors duration-150 hover:bg-tint/5 hover:text-foreground"
                    >
                        <LogOut className="h-4 w-4" aria-hidden="true" />
                        Log out
                    </button>
                </div>
            )}
        </div>
    );
}
