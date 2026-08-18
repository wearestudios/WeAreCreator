// The creator's own face in the navbar, and the two things behind it.
//
// A creator had no way to look at their own profile: the only route to their
// own details was the edit form, so "what does my profile actually say" meant
// opening a builder and reading it out of input boxes. This is the way in.
//
// Deliberately creator-only. An admin's navigation is the console, a brand's
// is their dashboard, and a manager has one page — none of them have a profile
// of this kind, so an avatar there would open onto nothing.
import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LogOut, User } from "lucide-react";

import { NAV } from "@/constants/testIds";

/** Initials, for a creator who hasn't uploaded a photo yet. */
const initials = (name) =>
    (name || "")
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase() || "?";

export default function CreatorAvatarMenu({ user, profileImageUrl, onLogout }) {
    const [open, setOpen] = useState(false);
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

    return (
        <div ref={wrapRef} className="relative">
            <button
                type="button"
                data-testid={NAV.avatarButton}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label="Your account"
                onClick={() => setOpen((v) => !v)}
                className="grid h-10 w-10 place-items-center overflow-hidden rounded-full border border-white/15 bg-card transition-colors duration-200 hover:border-ember-500/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
                {profileImageUrl ? (
                    <img
                        src={profileImageUrl}
                        alt=""
                        width={40}
                        height={40}
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <span className="text-xs font-medium tracking-wide text-muted-foreground">
                        {initials(user?.name)}
                    </span>
                )}
            </button>

            {open && (
                <div
                    role="menu"
                    data-testid={NAV.avatarMenu}
                    className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-md border border-white/10 bg-card shadow-lg"
                >
                    {/* Whose account this is. Two accounts on one laptop is
                        common enough that the menu should say. */}
                    <div className="border-b border-white/10 px-4 py-3">
                        <p className="truncate text-sm">{user?.name || "Your account"}</p>
                        {user?.phone && (
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                                {user.phone}
                            </p>
                        )}
                    </div>
                    <Link
                        to="/profile"
                        role="menuitem"
                        data-testid={NAV.myProfile}
                        onClick={() => setOpen(false)}
                        className="flex min-h-[2.75rem] items-center gap-2.5 px-4 text-sm transition-colors duration-200 hover:bg-white/5 focus-visible:outline-none focus-visible:bg-white/5"
                    >
                        <User className="h-4 w-4 text-muted-foreground" />
                        My profile
                    </Link>
                    <button
                        type="button"
                        role="menuitem"
                        data-testid={NAV.avatarLogout}
                        onClick={() => {
                            setOpen(false);
                            onLogout();
                        }}
                        className="flex min-h-[2.75rem] w-full items-center gap-2.5 border-t border-white/10 px-4 text-left text-sm transition-colors duration-200 hover:bg-white/5 focus-visible:outline-none focus-visible:bg-white/5"
                    >
                        <LogOut className="h-4 w-4 text-muted-foreground" />
                        Log out
                    </button>
                </div>
            )}
        </div>
    );
}
