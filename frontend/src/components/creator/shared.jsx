// Shared pieces for the creator's home.
//
// Two assumptions run through all of it. The first is a phone: most creators
// open this standing somewhere, often on the way to a venue, so the venue,
// the manager's number and the time are never behind a hover or a tab. The
// second is that motion here is functional — it shows where a number came
// from and where a stage sits — so every piece of it checks
// prefers-reduced-motion and simply arrives at the end state instead.
import React, { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { IndianRupee } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

export const formatRupees = (n) =>
    typeof n === "number" ? Math.round(n).toLocaleString("en-IN") : "—";

export const formatCompact = (n) => {
    if (typeof n !== "number") return "—";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
    return n.toString();
};

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

export const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    lifestyle: "Lifestyle",
};

// ---------------------------------------------------------------------------
// The lifecycle, as a creator reads it
// ---------------------------------------------------------------------------
//
// Six stages, not the backend's ten. `verified` and `commercial_agreed` are
// our internal bookkeeping — a creator has no idea what happens between the
// brand saying yes and a fee being settled, and showing them a stage they
// cannot act on only makes the bar longer.
export const LIFECYCLE = [
    { key: "applied", label: "Applied", states: ["applied", "verified"] },
    { key: "approved", label: "Approved", states: ["accepted", "commercial_agreed"] },
    { key: "slot", label: "Slot booked", states: ["slot_booked"] },
    { key: "attended", label: "Attended", states: ["attended"] },
    {
        key: "content",
        label: "Content sent",
        states: ["content_submitted", "content_approved"],
    },
    { key: "paid", label: "Paid", states: ["in_payment", "closed"] },
];

// The extra stage on a campaign that reviews drafts, inserted after Attended.
// It is a stage rather than a footnote because it is a wait the creator will
// otherwise read as nothing happening.
const DRAFT_STAGE = {
    key: "draft",
    label: "Draft in review",
    states: ["draft_submitted", "draft_approved"],
};

/**
 * The stages this collaboration actually walks.
 *
 * Per-collaboration rather than a constant, because the campaign decides:
 * with draft review off the bar is the six it has always been. Read off the
 * server's own answer (`draft` present on the row, or a state that only
 * exists on the draft ladder) rather than re-deriving the rule here.
 */
export const lifecycleFor = (collab) => {
    const reviews =
        Boolean(collab?.draft) || DRAFT_STAGE.states.includes(collab?.state);
    if (!reviews) return LIFECYCLE;
    const i = LIFECYCLE.findIndex((s) => s.key === "attended");
    return [...LIFECYCLE.slice(0, i + 1), DRAFT_STAGE, ...LIFECYCLE.slice(i + 1)];
};

/** Which stage a collaboration is standing on. -1 if it left the line. */
export const stageIndexFor = (state, stages = LIFECYCLE) =>
    stages.findIndex((stage) => stage.states.includes(state));

export const STATE_META = {
    applied: { label: "Applied", tone: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    verified: { label: "With the brand", tone: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
    accepted: { label: "Accepted", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    commercial_agreed: {
        label: "Fee agreed",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    slot_booked: {
        label: "Slot booked",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    attended: { label: "Attended", tone: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
    draft_submitted: {
        label: "Draft in review",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    draft_approved: {
        label: "Draft approved",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    content_submitted: {
        label: "In review",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    content_approved: {
        label: "Approved",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    in_payment: { label: "In payment", tone: "bg-ember-500/15 text-ember-500 border-ember-500/30" },
    closed: { label: "Paid", tone: "bg-white/5 text-muted-foreground border-white/15" },
    // Deliberately not "rejected". A brand picking someone else is not a
    // verdict on the creator, and the word it is given shouldn't imply one.
    declined: { label: "Not this time", tone: "bg-white/5 text-muted-foreground border-white/15" },
    cancelled: { label: "Cancelled", tone: "bg-white/5 text-muted-foreground border-white/15" },
    pending: { label: "Pending", tone: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    paid: { label: "Paid", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    refunded: { label: "Refunded", tone: "bg-white/5 text-muted-foreground border-white/15" },
};

export const StatePill = ({ state, testid }) => {
    const meta = STATE_META[state] || {
        label: state,
        tone: "bg-white/5 text-muted-foreground border-white/15",
    };
    return (
        <span
            data-testid={testid || `state-pill-${state}`}
            className={
                "inline-flex flex-none items-center rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                meta.tone
            }
        >
            {meta.label}
        </span>
    );
};

// ---------------------------------------------------------------------------
// Motion
// ---------------------------------------------------------------------------

/**
 * A section that fades and rises into place, staggered by its position.
 *
 * Purely an entrance: it never moves again, so nothing on the page is still
 * animating while somebody is trying to read or tap it. Under
 * prefers-reduced-motion the element is simply there.
 */
export const Reveal = ({ index = 0, className = "", children, ...rest }) => {
    const still = useReducedMotion();
    return (
        <motion.section
            initial={still ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
                duration: 0.45,
                delay: still ? 0 : Math.min(index, 6) * 0.07,
                ease: [0.22, 1, 0.36, 1],
            }}
            className={className}
            {...rest}
        >
            {children}
        </motion.section>
    );
};

/**
 * A number that counts up to its value once.
 *
 * Only worth doing on money: the movement is what makes a creator look at the
 * figure rather than skim past it. It runs on the first real value and not
 * again, so a background refresh doesn't restart the whole thing under
 * somebody's eyes, and reduced motion prints the final number immediately.
 */
export const CountUp = ({ value = 0, duration = 1100, className = "", testid }) => {
    const still = useReducedMotion();
    const target = typeof value === "number" && Number.isFinite(value) ? value : 0;
    const [shown, setShown] = useState(still ? target : 0);
    const played = useRef(false);

    useEffect(() => {
        if (still || played.current || target <= 0) {
            setShown(target);
            if (target > 0) played.current = true;
            return undefined;
        }
        played.current = true;
        let frame;
        const started = performance.now();
        const tick = (now) => {
            const progress = Math.min(1, (now - started) / duration);
            // Ease-out cubic: fast enough to feel responsive, settling rather
            // than stopping dead on the final digit.
            setShown(Math.round(target * (1 - Math.pow(1 - progress, 3))));
            if (progress < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frame);
    }, [target, duration, still]);

    return (
        <span data-testid={testid} className={className}>
            {formatRupees(shown)}
        </span>
    );
};

/** A rupee figure with the symbol sized to sit on the baseline of the number. */
export const Money = ({ children, symbolClass = "h-4 w-4", className = "" }) => (
    <span className={"inline-flex items-baseline " + className}>
        <IndianRupee className={"translate-y-[0.1em] text-ember-500 " + symbolClass} />
        {children}
    </span>
);

// ---------------------------------------------------------------------------
// Layout furniture
// ---------------------------------------------------------------------------

export const SectionHead = ({ kicker, title, aside }) => (
    <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">{kicker}</p>
            <h2 className="mt-3 font-serif text-fluid-3xl leading-none tracking-tight">
                {title}
            </h2>
        </div>
        {aside}
    </div>
);

export const EmptyState = ({ Icon, title, children, testid, action }) => (
    <div
        data-testid={testid}
        className="flex flex-col items-center gap-3 rounded-md border border-white/10 bg-card px-6 py-14 text-center grain-surface"
    >
        {Icon && <Icon className="h-6 w-6 text-ember-500" />}
        {title && <p className="font-serif text-xl leading-tight">{title}</p>}
        <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">{children}</p>
        {action}
    </div>
);

export const CardSkeleton = () => (
    <div className="rounded-md border border-white/10 bg-card p-6 grain-surface">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-4 h-6 w-2/3" />
        <Skeleton className="mt-6 h-2 w-full rounded-full" />
        <div className="mt-6 flex flex-wrap gap-3">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-24" />
        </div>
        <Skeleton className="mt-6 h-11 w-40 rounded-full" />
    </div>
);

export const HomeSkeleton = ({ testid }) => (
    <div data-testid={testid} className="space-y-10 md:space-y-12">
        {/* The header: a photo the size the real one now is, beside the name,
            with the earnings card on the right. */}
        <div className="grid gap-8 md:grid-cols-12">
            <div className="md:col-span-7">
                <Skeleton className="h-3 w-28" />
                <div className="mt-5 flex items-center gap-5 md:gap-7">
                    <Skeleton className="h-28 w-28 flex-none rounded-lg sm:h-32 sm:w-32 md:h-40 md:w-40" />
                    <div className="min-w-0 flex-1">
                        <Skeleton className="h-10 w-3/4" />
                        <Skeleton className="mt-3 h-6 w-28 rounded-full" />
                    </div>
                </div>
                <Skeleton className="mt-5 h-3 w-40" />
            </div>
            <div className="grid grid-cols-2 gap-4 md:col-span-5 md:grid-cols-1">
                <Skeleton className="h-28 rounded-md" />
                <Skeleton className="h-28 rounded-md" />
            </div>
        </div>
        <div className="space-y-4">
            <Skeleton className="h-3 w-36" />
            {/* The active card leads with its cover strip now. */}
            <div className="overflow-hidden rounded-md border border-white/10">
                <Skeleton className="aspect-[16/5] w-full rounded-none" />
                <CardSkeleton />
            </div>
        </div>
        {/* The tab strip, and the first drawer's grid. */}
        <div className="space-y-8">
            <Skeleton className="h-12 w-full max-w-sm rounded-full" />
            <CardSkeleton />
        </div>
    </div>
);
