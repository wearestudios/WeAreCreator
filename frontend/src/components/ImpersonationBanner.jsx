// The banner that says you are not yourself.
//
// The requirement is "persistent and unmissable", and the failure it exists to
// prevent is an admin forgetting which account they are looking at and telling
// somebody the wrong thing about their own screen.
//
// So it is fixed to the top of the viewport rather than placed in a layout —
// there is no page in this app that can scroll it away, and no route that
// forgets to render it, because it is mounted once above the router. The body
// gets padded by exactly its height so it covers nothing.
//
// It is ember on near-black like everything else, but solid rather than
// tinted: this is the one surface in the product that should not look like
// part of the page it is sitting on.
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Eye, LogOut } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { IMPERSONATION as IDS } from "@/constants/testIds";

/** Minutes left, so an admin is not surprised by a session ending mid-sentence. */
function useMinutesLeft(expiresAt) {
    const [left, setLeft] = useState(null);
    useEffect(() => {
        if (!expiresAt) return undefined;
        const tick = () => {
            const ms = new Date(expiresAt).getTime() - Date.now();
            setLeft(Number.isNaN(ms) ? null : Math.max(0, Math.round(ms / 60000)));
        };
        tick();
        const t = setInterval(tick, 30000);
        return () => clearInterval(t);
    }, [expiresAt]);
    return left;
}

export function ImpersonationBanner() {
    const { user, impersonation, stopImpersonating } = useAuth();
    const [leaving, setLeaving] = useState(false);
    const ref = useRef(null);
    const minutesLeft = useMinutesLeft(impersonation?.expires_at);
    const active = Boolean(impersonation?.active);

    // Push the whole document down by the banner's real measured height rather
    // than a guessed constant — it wraps to two lines on a narrow phone, and a
    // hard-coded offset would put it over the navbar there.
    useLayoutEffect(() => {
        if (!active) {
            document.body.style.paddingTop = "";
            return undefined;
        }
        const set = () => {
            document.body.style.paddingTop = `${ref.current?.offsetHeight || 0}px`;
        };
        set();
        window.addEventListener("resize", set);
        return () => {
            window.removeEventListener("resize", set);
            document.body.style.paddingTop = "";
        };
    }, [active]);

    if (!active) return null;

    const stop = async () => {
        setLeaving(true);
        await stopImpersonating();
    };

    return (
        <div
            ref={ref}
            data-testid={IDS.banner}
            role="status"
            // z-50 clears the navbar's z-40. Nothing in the app sits above it.
            className="fixed inset-x-0 top-0 z-50 border-b border-ember-500/40 bg-ember-500 text-black"
        >
            <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2.5 md:px-6">
                <span className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em]">
                    <Eye className="h-4 w-4" />
                    Viewing as
                </span>
                <span data-testid={IDS.who} className="min-w-0 text-sm font-medium">
                    {user?.name || "Unknown"}
                    <span className="opacity-70"> · {user?.role?.replace(/_/g, " ")}</span>
                </span>
                {/* Said plainly. An admin who tries something and gets a refusal
                    should have already been told why. */}
                <span className="text-xs opacity-80">
                    Read-only — nothing you do here can change anything
                    {minutesLeft != null ? ` · ${minutesLeft}m left` : ""}
                </span>
                <button
                    type="button"
                    onClick={stop}
                    disabled={leaving}
                    data-testid={IDS.stop}
                    className="ml-auto inline-flex min-h-[2.25rem] items-center gap-1.5 rounded-full bg-black/85 px-4 py-1.5 text-xs font-medium uppercase tracking-[0.15em] text-ember-500 transition-colors duration-200 hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 focus-visible:ring-offset-ember-500 disabled:opacity-60"
                >
                    <LogOut className="h-3.5 w-3.5" />
                    {leaving ? "Leaving…" : "Stop"}
                </button>
            </div>
        </div>
    );
}

export default ImpersonationBanner;
