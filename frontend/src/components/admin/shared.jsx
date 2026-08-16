// Pieces shared by the admin console sections. Extracted so the roster, the
// campaign oversight view and the collaborations board render a state pill or a
// rupee figure the same way rather than three ways.
import React from "react";
import { CalendarDays, RotateCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { mediaUrl } from "@/lib/api";

export const STATE_ORDER = [
    "applied",
    "verified",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
    "declined",
    "cancelled",
];

export const STATE_META = {
    applied: { label: "Applied", tone: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    verified: { label: "Verified", tone: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
    accepted: { label: "Accepted", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    commercial_agreed: { label: "Commercial agreed", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    slot_booked: { label: "Slot booked", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    attended: { label: "Attended", tone: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
    content_submitted: { label: "Content submitted", tone: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
    content_approved: { label: "Content approved", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    in_payment: { label: "In payment", tone: "bg-ember-500/15 text-ember-500 border-ember-500/30" },
    closed: { label: "Closed", tone: "bg-white/5 text-muted-foreground border-white/15" },
    declined: { label: "Declined", tone: "bg-white/5 text-muted-foreground border-white/15" },
    cancelled: { label: "Cancelled", tone: "bg-red-500/10 text-red-300/80 border-red-500/25" },
};

export const CAMPAIGN_STATUS_META = {
    draft: { label: "Draft", tone: "bg-white/5 text-muted-foreground border-white/15" },
    pending_review: {
        label: "In review",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    },
    upcoming: { label: "Upcoming", tone: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
    open: { label: "Open", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    in_progress: { label: "In progress", tone: "bg-ember-500/15 text-ember-500 border-ember-500/30" },
    paused: {
        label: "Paused",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    },
    completed: { label: "Completed", tone: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
    closed: { label: "Closed", tone: "bg-white/5 text-muted-foreground border-white/15" },
};

export const VERIFICATION_META = {
    verified: { label: "Verified", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    pending: { label: "Pending", tone: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    rejected: { label: "Rejected", tone: "bg-red-500/10 text-red-300/80 border-red-500/25" },
};

// Campaigns you can still invite someone to. Mirrors INVITABLE_CAMPAIGN_STATUSES
// on the server, which is what actually enforces it. Drafts, briefs in review
// and paused ones are out — the creator could not open what they were sent.
export const INVITABLE_STATUSES = ["upcoming", "open", "in_progress"];

export const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN") : "—";

export const formatDate = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        });
    } catch {
        return iso;
    }
};

export const formatDateTime = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleString("en-IN", {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return iso;
    }
};

/**
 * How long something has been waiting, in the shortest true form. The queue is
 * read at a glance, and "3d" lands faster than a date does.
 */
export const timeAgo = (iso) => {
    if (!iso) return "—";
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return "—";
    const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours}h`;
    const days = Math.round(hours / 24);
    if (days < 14) return `${days}d`;
    return `${Math.round(days / 7)}w`;
};

// Anything older than this has been ignored rather than queued.
export const STALE_AFTER_HOURS = 48;

export const isStale = (iso) => {
    if (!iso) return false;
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return false;
    return Date.now() - then > STALE_AFTER_HOURS * 3600 * 1000;
};

export const formatCompact = (n) => {
    if (typeof n !== "number") return "—";
    if (n >= 10000000) return `${(n / 10000000).toFixed(1)}Cr`;
    if (n >= 100000) return `${(n / 100000).toFixed(1)}L`;
    if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K`;
    return String(n);
};

export const Pill = ({ meta, value, testid }) => {
    const m = meta[value] || {
        label: value || "—",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    };
    return (
        <span
            data-testid={testid}
            className={
                "inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                m.tone
            }
        >
            {m.label}
        </span>
    );
};

export const StatePill = ({ state }) => (
    <Pill meta={STATE_META} value={state} testid={`admin-state-pill-${state}`} />
);

/**
 * A creator's photo, falling back to their initial. The fallback is a real
 * element rather than a broken image, and carries its own testid so a test can
 * tell "no photo uploaded" from "photo failed to load".
 */
export const CreatorAvatar = ({ creator, size = "h-12 w-12", testids = {} }) => {
    const [broken, setBroken] = React.useState(false);
    const src = creator?.profile_image_url ? mediaUrl(creator.profile_image_url) : null;
    const monogram = (creator?.name || creator?.instagram_handle || "?")
        .trim()
        .charAt(0)
        .toUpperCase();

    if (src && !broken) {
        return (
            <img
                src={src}
                alt=""
                loading="lazy"
                data-testid={testids.photo}
                onError={() => setBroken(true)}
                className={`${size} aspect-square flex-none rounded-md border border-white/10 object-cover`}
            />
        );
    }
    return (
        <span
            aria-hidden="true"
            data-testid={testids.monogram}
            className={`${size} grid flex-none place-items-center rounded-md border border-white/10 bg-ember-500/10 font-serif text-lg text-ember-500`}
        >
            {monogram}
        </span>
    );
};

export const SectionHeader = ({ kicker, title, blurb, onRefresh, refreshTestId, children }) => (
    <div className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between gap-6">
            <div>
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">{kicker}</p>
                <h2 className="mt-3 font-serif text-fluid-4xl leading-none tracking-tight">
                    {title}
                </h2>
            </div>
            {onRefresh && (
                <button
                    type="button"
                    onClick={onRefresh}
                    data-testid={refreshTestId}
                    className="inline-flex flex-none items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <RotateCw className="h-3.5 w-3.5" />
                    Refresh
                </button>
            )}
        </div>
        {blurb && (
            <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">{blurb}</p>
        )}
        {children}
    </div>
);

// Raw <select> is out per the design brief, so every filter is the shadcn one.
// "All" is a sentinel rather than an empty value because Radix reserves "".
export const ALL = "__all__";

export const FilterSelect = ({ label, value, onChange, options, testid, className = "" }) => (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
        <SelectTrigger
            data-testid={testid}
            aria-label={label}
            className={
                "h-10 w-full rounded-md border-white/10 bg-background/60 text-sm capitalize focus:ring-ember-500 sm:w-44 " +
                className
            }
        >
            <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent className="max-h-72 rounded-md border-white/10 bg-card grain-surface">
            <SelectItem value={ALL} className="text-sm">
                {label}
            </SelectItem>
            {options.map((o) => (
                <SelectItem key={o.value} value={o.value} className="text-sm capitalize">
                    {o.label}
                </SelectItem>
            ))}
        </SelectContent>
    </Select>
);

/** Skeletons. One shape per section, so a loading console reads like the loaded one. */
export const TileSkeleton = () => (
    <div className="rounded-md border border-white/10 bg-card p-6 grain-surface">
        <div className="flex items-start gap-4">
            <Skeleton className="h-12 w-12 flex-none rounded-md" />
            <div className="min-w-0 flex-1 space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-1/2" />
            </div>
        </div>
        <div className="mt-6 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/4" />
        </div>
    </div>
);

export const RowSkeleton = () => (
    <div className="flex items-center gap-6 px-6 py-6">
        <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
        </div>
        <Skeleton className="h-6 w-24 flex-none rounded-full" />
    </div>
);

export const ListSkeleton = ({ rows = 4, testid }) => (
    <div data-testid={testid} className="divide-y divide-white/10">
        {Array.from({ length: rows }).map((_, i) => (
            <RowSkeleton key={i} />
        ))}
    </div>
);

// Dates go through the shadcn calendar — the design brief rules out raw date
// inputs. Value is a Date or null.
export const DateFilter = ({ value, onChange, label, testid }) => {
    const [open, setOpen] = React.useState(false);
    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <button
                    type="button"
                    data-testid={testid}
                    className={
                        "inline-flex h-10 items-center gap-2 rounded-md border border-white/10 bg-background/60 px-3 text-sm transition-colors duration-200 hover:border-white/25 " +
                        (value ? "text-foreground" : "text-muted-foreground")
                    }
                >
                    <CalendarDays className="h-4 w-4" />
                    {value ? formatDate(value.toISOString()) : label}
                </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-auto rounded-md border-white/10 bg-card p-0 grain-surface">
                <Calendar
                    mode="single"
                    selected={value || undefined}
                    onSelect={(d) => {
                        onChange(d || null);
                        setOpen(false);
                    }}
                />
                {value && (
                    <button
                        type="button"
                        onClick={() => {
                            onChange(null);
                            setOpen(false);
                        }}
                        className="w-full border-t border-white/10 px-3 py-2 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                    >
                        Clear
                    </button>
                )}
            </PopoverContent>
        </Popover>
    );
};

// Through the end of the chosen day, not its first second.
export const endOfDay = (d) =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59);

export const EmptyState = ({ Icon, children, testid }) => (
    <div
        data-testid={testid}
        className="flex items-center gap-4 rounded-md border border-white/10 bg-card px-6 py-10 text-sm text-muted-foreground grain-surface"
    >
        {Icon && <Icon className="h-5 w-5 flex-none text-ember-500" />}
        <p>{children}</p>
    </div>
);

export const TableSkeleton = ({ rows = 8, cols = 4, testid }) => (
    <div data-testid={testid} className="divide-y divide-white/10">
        {Array.from({ length: rows }).map((_, r) => (
            <div key={r} className="flex items-center gap-4 px-5 py-3">
                {Array.from({ length: cols }).map((__, c) => (
                    <Skeleton
                        key={c}
                        className={"h-3 " + (c === cols - 1 ? "flex-1" : "w-24 flex-none")}
                    />
                ))}
            </div>
        ))}
    </div>
);

export const GridSkeleton = ({ tiles = 6, testid }) => (
    <div
        data-testid={testid}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
    >
        {Array.from({ length: tiles }).map((_, i) => (
            <TileSkeleton key={i} />
        ))}
    </div>
);
