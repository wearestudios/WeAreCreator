// Shared pieces for the manager interface.
//
// Everything here assumes a phone held in one hand in a room with people in it:
// touch targets are at least 56px, actions sit at the bottom of the screen
// where a thumb reaches, and nothing important is behind a hover.
import React from "react";
import { Loader2, RotateCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

// Minimum comfortable one-handed target. Below this you get mis-taps, and a
// mis-tap here marks the wrong person as a no-show.
export const TOUCH = "min-h-[3.5rem]";

export const CAMPAIGN_TYPE_META = {
    launch: { label: "Launch", blurb: "One day, everyone at once" },
    group_event: { label: "Group event", blurb: "One day, everyone at once" },
    personal_table: { label: "Personal table", blurb: "Creators book a window" },
};

export const ATTENDANCE_META = {
    expected: {
        label: "Expected",
        tone: "border-white/15 bg-white/5 text-muted-foreground",
    },
    attended: {
        label: "Checked in",
        tone: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
    },
    no_show: {
        label: "No-show",
        tone: "border-red-500/25 bg-red-500/10 text-red-300/80",
    },
};

export const formatTime = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleTimeString("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return "—";
    }
};

export const formatDay = (iso) => {
    if (!iso) return null;
    try {
        return new Date(iso).toLocaleDateString("en-IN", {
            weekday: "short",
            day: "2-digit",
            month: "short",
        });
    } catch {
        return null;
    }
};

/** When a campaign happens, in the shape its type actually has. */
export const whenText = (campaign) => {
    if (!campaign) return "—";
    if (campaign.campaign_type === "personal_table") {
        const from = formatDay(campaign.start_date);
        const to = formatDay(campaign.end_date);
        if (from && to) return `${from} – ${to}`;
        return from || to || "Dates not set";
    }
    return formatDay(campaign.event_date) || "Date not set";
};

export const Pill = ({ meta, value, testid, className = "" }) => {
    const m = meta[value] || {
        label: value || "—",
        tone: "border-white/15 bg-white/5 text-muted-foreground",
    };
    return (
        <span
            data-testid={testid}
            className={
                "inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                m.tone +
                " " +
                className
            }
        >
            {m.label}
        </span>
    );
};

/** A phone number you can actually ring, which is the point of it being here. */
export const CallLink = ({ phone, testid, label, className = "" }) => {
    if (!phone) {
        return (
            <span className="text-xs text-muted-foreground">No number on file</span>
        );
    }
    return (
        <a
            href={`tel:${phone.replace(/\s+/g, "")}`}
            data-testid={testid}
            className={
                "inline-flex items-center justify-center gap-2 rounded-md border border-white/15 px-4 text-sm transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 " +
                TOUCH +
                " " +
                className
            }
        >
            {label || phone}
        </a>
    );
};

export const ManagerHeader = ({ kicker, title, sub, onRefresh, refreshTestId, children }) => (
    <header className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    {kicker}
                </p>
                <h1 className="mt-2 font-serif text-fluid-4xl leading-none tracking-tight">
                    {title}
                </h1>
                {sub && (
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                        {sub}
                    </p>
                )}
            </div>
            {onRefresh && (
                <button
                    type="button"
                    onClick={onRefresh}
                    aria-label="Refresh"
                    data-testid={refreshTestId}
                    className={
                        "grid w-14 flex-none place-items-center rounded-md border border-white/10 text-muted-foreground transition-colors duration-200 hover:text-ember-500 " +
                        TOUCH
                    }
                >
                    <RotateCw className="h-4 w-4" />
                </button>
            )}
        </div>
        {children}
    </header>
);

export const EmptyState = ({ Icon, children, testid }) => (
    <div
        data-testid={testid}
        className="flex flex-col items-center gap-4 rounded-md border border-white/10 bg-card px-6 py-12 text-center text-sm text-muted-foreground grain-surface"
    >
        {Icon && <Icon className="h-6 w-6 text-ember-500" />}
        <p className="max-w-xs leading-relaxed">{children}</p>
    </div>
);

export const CardSkeleton = () => (
    <div className="rounded-md border border-white/10 bg-card p-6 grain-surface">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-4 h-5 w-3/4" />
        <div className="mt-6 flex gap-3">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-20" />
        </div>
    </div>
);

export const CardListSkeleton = ({ cards = 3, testid }) => (
    <div data-testid={testid} className="space-y-4">
        {Array.from({ length: cards }).map((_, i) => (
            <CardSkeleton key={i} />
        ))}
    </div>
);

export const RowSkeleton = () => (
    <div className="flex items-center gap-4 rounded-md border border-white/10 bg-card p-5 grain-surface">
        <Skeleton className="h-10 w-16 flex-none rounded-md" />
        <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-3 w-1/3" />
        </div>
        <Skeleton className="h-8 w-20 flex-none rounded-full" />
    </div>
);

export const RowListSkeleton = ({ rows = 5, testid }) => (
    <div data-testid={testid} className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
            <RowSkeleton key={i} />
        ))}
    </div>
);

/** A full-width action, sized for a thumb. */
export const BigButton = ({ children, busy, className = "", ...props }) => (
    <Button
        {...props}
        disabled={busy || props.disabled}
        className={`w-full rounded-md text-base ${TOUCH} ${className}`}
    >
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
        {children}
    </Button>
);
