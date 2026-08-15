// Connecting Instagram for official stats.
//
// This replaces a scraper that breached Instagram's terms and put the Meta
// Business account at risk. The sanctioned route is "Instagram API with
// Instagram Login" — not the Facebook-Login one, which would make every
// creator link a Facebook Page they mostly don't have.
//
// Three things the copy here has to carry, because getting any of them wrong
// costs a connection:
//   - what we can and can't see (two read scopes, nothing that can post),
//   - that a personal account can't do this and how to change that,
//   - that the whole thing is optional and self-reported numbers still work.
import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
    AlertCircle,
    BadgeCheck,
    Instagram,
    Loader2,
    Lock,
    RefreshCw,
    Unlink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, apiErrorCode, formatApiError } from "@/lib/api";
import { CREATOR_INSTAGRAM as IDS } from "@/constants/testIds";
import { formatCompact, formatDateTime } from "./shared";

/** The one failure people get stuck on, and the thirty seconds that fixes it. */
export const NotProfessionalHelp = ({ testid, message }) => (
    <div
        data-testid={testid}
        className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-relaxed text-amber-100"
    >
        <p className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-none" />
            <span>
                {message ||
                    "Instagram only shares stats with Professional accounts, and yours is still a personal one."}
            </span>
        </p>
        <ol className="mt-4 list-decimal space-y-1 pl-8 text-amber-100/90">
            <li>Open Instagram and go to your profile</li>
            <li>Tap the menu, then <span className="text-amber-50">Settings and privacy</span></li>
            <li>Tap <span className="text-amber-50">Account type and tools</span></li>
            <li>Tap <span className="text-amber-50">Switch to professional account</span> and pick <span className="text-amber-50">Creator</span></li>
        </ol>
        <p className="mt-4 text-xs text-amber-100/80">
            {/* The actual worry, answered before they ask it. */}
            It's free, your account stays public, and nothing about your posts or
            followers changes.
        </p>
    </div>
);

const Stat = ({ label, value, testid }) => (
    <div>
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
        <p data-testid={testid} className="mt-1 font-serif text-xl leading-none">
            {typeof value === "number" ? formatCompact(value) : "—"}
        </p>
    </div>
);

export default function InstagramConnect({ onChanged }) {
    const [data, setData] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [notProfessional, setNotProfessional] = useState("");

    const load = useCallback(async () => {
        try {
            const res = await api.get("/creator/instagram");
            setData(res.data);
        } catch (e) {
            setError(formatApiError(e));
            setData({ configured: false, connected: false });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const connect = async () => {
        setBusy(true);
        setError("");
        setNotProfessional("");
        try {
            const { data: start } = await api.post("/creator/instagram/connect");
            // Instagram takes over from here and redirects back to the
            // callback route, which posts the code and comes back.
            window.location.assign(start.authorize_url);
        } catch (e) {
            setError(formatApiError(e));
            setBusy(false);
        }
    };

    const disconnect = async () => {
        setBusy(true);
        setError("");
        try {
            await api.delete("/creator/instagram");
            await load();
            toast.success("Instagram disconnected — back to your own figure");
            onChanged?.();
        } catch (e) {
            setError(formatApiError(e));
        } finally {
            setBusy(false);
        }
    };

    const refresh = async () => {
        setBusy(true);
        setError("");
        try {
            const { data: fresh } = await api.post("/creator/instagram/refresh");
            setData(fresh);
            onChanged?.();
        } catch (e) {
            if (apiErrorCode(e) === "not_professional") setNotProfessional(formatApiError(e));
            else setError(formatApiError(e));
        } finally {
            setBusy(false);
        }
    };

    if (!data) {
        return (
            <div data-testid={IDS.skeleton} className="rounded-md border border-white/10 bg-card p-6">
                <Skeleton className="h-3 w-40" />
                <Skeleton className="mt-4 h-6 w-2/3" />
                <Skeleton className="mt-6 h-12 w-48 rounded-full" />
            </div>
        );
    }

    const stats = data.stats || {};
    const connected = data.connected;
    const stale = data.status === "stale";

    return (
        <div data-testid={IDS.card} className="rounded-md border border-white/10 bg-card p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                    <p className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        <Instagram className="h-3.5 w-3.5" />
                        Instagram stats
                    </p>
                    <p data-testid={IDS.status} className="mt-3 font-serif text-xl leading-tight">
                        {connected
                            ? "Connected — your numbers are verified."
                            : stale
                            ? "Reconnect to keep your verified numbers."
                            : "Connect to show brands verified numbers."}
                    </p>
                </div>
                {connected && (
                    <span
                        data-testid={IDS.badge}
                        className="inline-flex flex-none items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-300"
                    >
                        <BadgeCheck className="h-3.5 w-3.5" />
                        Verified
                    </span>
                )}
            </div>

            {connected && (
                <>
                    <p data-testid={IDS.username} className="mt-3 text-sm text-muted-foreground">
                        @{data.username}
                        {data.account_type ? ` · ${data.account_type.replace("_", " ").toLowerCase()}` : ""}
                    </p>
                    <div className="mt-6 grid grid-cols-2 gap-5 sm:grid-cols-4">
                        <Stat label="Followers" value={stats.followers_count} testid={IDS.stat("followers")} />
                        <Stat label="Posts" value={stats.media_count} testid={IDS.stat("media")} />
                        <Stat label="Reach" value={stats.reach} testid={IDS.stat("reach")} />
                        <Stat label="Interactions" value={stats.engagement} testid={IDS.stat("engagement")} />
                    </div>
                    <p data-testid={IDS.updated} className="mt-4 text-xs text-muted-foreground">
                        {/* Says why the number didn't move when they tapped
                            refresh, instead of leaving it looking broken. */}
                        {data.stats_fetched_at
                            ? `Updated ${formatDateTime(data.stats_fetched_at)}. Refreshed automatically every 12 hours.`
                            : "Waiting for the first reading."}
                    </p>
                </>
            )}

            {stale && (
                <p
                    data-testid={IDS.stale}
                    className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-relaxed text-amber-100"
                >
                    {data.stale_reason || "Instagram access lapsed."} Your self-reported
                    figure is showing in the meantime.
                </p>
            )}

            {!data.configured && (
                <p data-testid={IDS.unavailable} className="mt-4 text-sm leading-relaxed text-muted-foreground">
                    {/* Honest about why the button is dead. "Coming soon" with
                        no reason reads as broken. */}
                    Not switched on yet — our Instagram app is with Meta for review.
                    Your self-reported follower count is fine in the meantime, and
                    we'll let you know the moment this opens up.
                </p>
            )}

            {notProfessional && (
                <div className="mt-4">
                    <NotProfessionalHelp testid={IDS.notProfessional} message={notProfessional} />
                </div>
            )}

            {error && (
                <p data-testid={IDS.error} className="mt-4 text-sm text-destructive">
                    {error}
                </p>
            )}

            <div className="mt-6 flex flex-wrap items-center gap-3">
                {!connected && (
                    <Button
                        type="button"
                        onClick={connect}
                        disabled={!data.configured || busy}
                        data-testid={stale ? IDS.reconnect : IDS.connect}
                        className={
                            "h-12 rounded-full " +
                            // A dimmed ember button still reads as tappable.
                            // While the app is in review this is genuinely
                            // inert, so it looks inert: no brand colour, no
                            // hover, and a cursor that says so.
                            (data.configured
                                ? "bg-ember-500 text-black hover:bg-ember-400 disabled:opacity-60"
                                : "cursor-not-allowed border border-white/10 bg-white/5 text-muted-foreground hover:bg-white/5")
                        }
                    >
                        {busy ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : data.configured ? (
                            <Instagram className="mr-2 h-4 w-4" />
                        ) : (
                            <Lock className="mr-2 h-4 w-4" />
                        )}
                        {!data.configured
                            ? "Connect Instagram (not open yet)"
                            : stale
                            ? "Reconnect Instagram"
                            : "Connect Instagram"}
                    </Button>
                )}
                {connected && (
                    <>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={refresh}
                            disabled={busy}
                            data-testid={IDS.refresh}
                            className="h-12 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                        >
                            {busy ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCw className="mr-2 h-4 w-4" />
                            )}
                            Refresh now
                        </Button>
                        <button
                            type="button"
                            onClick={disconnect}
                            disabled={busy}
                            data-testid={IDS.disconnect}
                            className="inline-flex min-h-[3rem] items-center gap-2 text-sm text-muted-foreground transition-colors duration-200 hover:text-red-300 disabled:opacity-50"
                        >
                            <Unlink className="h-4 w-4" />
                            Disconnect
                        </button>
                    </>
                )}
            </div>

            <p data-testid={IDS.scopes} className="mt-5 text-xs leading-relaxed text-muted-foreground">
                {/* Naming the limits is the whole reason somebody says yes. */}
                We ask Instagram for two things only: your profile basics and your
                insights. We can't post, message, or change anything on your
                account, and you can disconnect here whenever you like. Instagram
                requires a Professional (Business or Creator) account.
            </p>
        </div>
    );
}
