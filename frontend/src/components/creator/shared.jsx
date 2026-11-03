// Shared pieces for the creator's home.
//
// Two assumptions run through all of it. The first is a phone: most creators
// open this standing somewhere, often on the way to a venue, so the venue,
// the manager's number and the time are never behind a hover or a tab. The
// second is that motion here is functional — it shows where a number came
// from and where a stage sits — so every piece of it checks
// prefers-reduced-motion and simply arrives at the end state instead.
import React, { useEffect, useRef, useState } from "react";
// `motion` went with `Reveal` — the settle is CSS now. `useReducedMotion`
// stays for `CountUp`, which is a JS tween and has to ask.
import { useReducedMotion } from "framer-motion";
import { IndianRupee } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import Settle from "@/components/motion/Settle";
import { IST } from "@/lib/time";

import { formatRupees } from "@/lib/compensation";
// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

// The one rupee formatter lives in `lib/compensation.js`; re-exported so the
// creator surfaces' imports keep working.
export { formatRupees };

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
            timeZone: IST,
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
            timeZone: IST,
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
            timeZone: IST,
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
            timeZone: IST,
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
// **It is not read here any more.** This file used to hold a six-stage list —
// `LIFECYCLE`, `lifecycleFor`, `stageIndexFor` — because the backend's twelve
// states were unreadable and the creator needed fewer. That was right about
// the problem and wrong about where to fix it: the brand and the admin needed
// the same thing, and ended up with a third and a fourth answer, so "where has
// this got to" had a different picture depending on who was asked.
//
// `_process_flow` on the server is the one answer now — eight stages, decided
// once, shipped with every application payload — and
// `components/application/ProcessFlow.jsx` draws it. `STATE_META` below stays:
// a pill naming one state is a different job from a bar naming the journey.

export const STATE_META = {
    applied: { label: "Applied", tone: "bg-state-pending-wash text-state-pending border-state-pending/30" },
    verified: { label: "With the brand", tone: "bg-state-progress-wash text-state-progress border-state-progress/30" },
    accepted: { label: "Accepted", tone: "bg-state-approved-wash text-state-approved border-state-approved/30" },
    commercial_agreed: {
        label: "Fee agreed",
        tone: "bg-state-approved-wash text-state-approved border-state-approved/30",
    },
    slot_booked: {
        label: "Slot booked",
        tone: "bg-state-approved-wash text-state-approved border-state-approved/30",
    },
    attended: { label: "Attended", tone: "bg-state-done-wash text-state-done border-state-done/30" },
    address_confirmed: {
        label: "Address confirmed",
        tone: "bg-state-approved-wash text-state-approved border-state-approved/30",
    },
    dispatched: {
        label: "On its way",
        tone: "bg-state-progress-wash text-state-progress border-state-progress/30",
    },
    received: { label: "Arrived", tone: "bg-state-done-wash text-state-done border-state-done/30" },
    draft_submitted: {
        label: "Draft in review",
        tone: "bg-state-done-wash text-state-done border-state-done/30",
    },
    draft_approved: {
        label: "Draft approved",
        tone: "bg-state-approved-wash text-state-approved border-state-approved/30",
    },
    content_submitted: {
        label: "In review",
        tone: "bg-state-done-wash text-state-done border-state-done/30",
    },
    content_approved: {
        label: "Approved",
        tone: "bg-state-approved-wash text-state-approved border-state-approved/30",
    },
    in_payment: { label: "In payment", tone: "bg-primary/15 text-primary border-primary/30" },
    closed: { label: "Paid", tone: "bg-muted text-muted-foreground border-input" },
    // A barter collaboration closes at approval with nothing paid, so "Paid"
    // would be the one false word on the row. Not a server state — the
    // Finished list picks it off the row's compensation type.
    closed_barter: { label: "Finished", tone: "bg-muted text-muted-foreground border-input" },
    // Deliberately not "rejected". A brand picking someone else is not a
    // verdict on the creator, and the word it is given shouldn't imply one.
    declined: { label: "Not this time", tone: "bg-muted text-muted-foreground border-input" },
    cancelled: { label: "Cancelled", tone: "bg-muted text-muted-foreground border-input" },
    // The other two exits. Both rendered as the raw state word before —
    // "withdrawn" and "expired" in lower case on a creator's own list.
    // Withdrawn is theirs and no black mark; expired is nobody answering,
    // said the way `_PROCESS_BANNERS` says it rather than as a rejection.
    withdrawn: { label: "Withdrawn", tone: "bg-muted text-muted-foreground border-input" },
    expired: { label: "No answer", tone: "bg-muted text-muted-foreground border-input" },
    pending: { label: "Pending", tone: "bg-state-pending-wash text-state-pending border-state-pending/30" },
    paid: { label: "Paid", tone: "bg-state-approved-wash text-state-approved border-state-approved/30" },
    refunded: { label: "Refunded", tone: "bg-muted text-muted-foreground border-input" },
};

export const StatePill = ({ state, testid }) => {
    const meta = STATE_META[state] || {
        label: state,
        tone: "bg-muted text-muted-foreground border-input",
    };
    return (
        <span
            data-testid={testid || `state-pill-${state}`}
            className={
                "inline-flex flex-none items-center rounded-full border px-2.5 py-1 text-label " +
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
 *
 * **It is the shared CSS settle wearing this file's name.** It used to be its
 * own framer-motion tween at 450ms with a 70ms stagger — its own duration and
 * its own cap, written before there was a product-wide answer. That made the
 * creator's home the one authenticated screen settling at a different speed
 * from every other, which is precisely the drift the marketing site's
 * `motion.js` exists to prevent on its own half.
 *
 * Kept as a named export rather than replaced at its eleven call sites,
 * because `<Reveal>` renders a `<section>` and the dashboard's layout depends
 * on that. The name and the element are this file's; the timing is the
 * product's.
 */
export const Reveal = ({ index = 0, className = "", children, ...rest }) => (
    <Settle
        as="section"
        index={index}
        className={className}
        {...rest}
    >
        {children}
    </Settle>
);

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
        <IndianRupee className={"translate-y-[0.1em] text-primary " + symbolClass} />
        {children}
    </span>
);

// ---------------------------------------------------------------------------
// Layout furniture
// ---------------------------------------------------------------------------

export const SectionHead = ({ kicker, title, aside, className = "" }) => (
    <div className={"flex flex-wrap items-end justify-between gap-3 " + className}>
        <div className="min-w-0">
            <p className="text-label text-muted-foreground">{kicker}</p>
            <h2 className="mt-1.5 text-body-lg font-extrabold leading-snug text-heading">{title}</h2>
        </div>
        {aside}
    </div>
);

export const EmptyState = ({ Icon, title, children, testid, action }) => (
    <div
        data-testid={testid}
        className="flex flex-col items-center gap-3 rounded-lg bg-card px-6 py-12 text-center shadow-card"
    >
        {Icon && <Icon aria-hidden="true" className="h-6 w-6 text-muted-foreground" />}
        {title && <p className="text-body-lg font-extrabold leading-tight text-heading">{title}</p>}
        <p className="max-w-sm text-body leading-relaxed text-muted-foreground">{children}</p>
        {action}
    </div>
);

export const CardSkeleton = () => (
    <div className="rounded-lg bg-card p-5 shadow-card">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-4 h-6 w-2/3" />
        <Skeleton className="mt-6 h-2 w-full rounded-full" />
        <div className="mt-6 flex flex-wrap gap-3">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-24" />
        </div>
        <Skeleton className="mt-6 h-11 w-40 rounded-button" />
    </div>
);

// One active card's shape: the cover strip, the title and its line, the
// bars, and the tinted box with its button.
const ActiveCardSkeleton = () => (
    <div className="overflow-hidden rounded-lg bg-card shadow-card">
        <Skeleton className="aspect-[16/5] w-full rounded-none md:max-h-[7.375rem]" />
        <div className="p-5 md:px-[22px]">
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="mt-2.5 h-3.5 w-1/2" />
            <Skeleton className="mt-5 h-1.5 w-full rounded-full" />
            <Skeleton className="mt-2.5 h-3 w-32" />
            <Skeleton className="mt-4 h-[6.5rem] w-full rounded-[14px]" />
        </div>
    </div>
);

/**
 * The page before the payload: the portrait box and the three tiles, two
 * active cards, and the strip of tab pills — the shapes that occupy the
 * space once it lands.
 */
export const HomeSkeleton = ({ testid }) => (
    <div data-testid={testid}>
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:gap-8">
            <div className="flex min-w-0 flex-1 items-center gap-4 md:gap-6">
                <Skeleton className="h-28 w-[5.6rem] flex-none rounded-xl md:h-40 md:w-32" />
                <div className="min-w-0 flex-1">
                    <Skeleton className="h-6 w-24 rounded-pill" />
                    <Skeleton className="mt-3 h-9 w-3/4" />
                    <Skeleton className="mt-3 h-3.5 w-2/3" />
                </div>
            </div>
            <div className="grid grid-cols-3 gap-2.5 sm:gap-3 xl:flex xl:flex-none">
                <Skeleton className="h-[4.25rem] rounded-tile sm:h-20 xl:w-[9.5rem]" />
                <Skeleton className="h-[4.25rem] rounded-tile sm:h-20 xl:w-[9.5rem]" />
                <Skeleton className="h-[4.25rem] rounded-tile sm:h-20 xl:w-[9.5rem]" />
            </div>
        </div>
        <div className="mt-6">
            <Skeleton className="mb-3.5 h-4 w-48" />
            <div className="grid items-start gap-4 lg:grid-cols-[1.25fr_1fr]">
                <ActiveCardSkeleton />
                <ActiveCardSkeleton />
            </div>
        </div>
        {/* The tab pills, and the first drawer's grid. */}
        <div className="mt-8 flex gap-2 md:mt-10">
            <Skeleton className="h-10 w-32 rounded-pill" />
            <Skeleton className="h-10 w-28 rounded-pill" />
            <Skeleton className="h-10 w-24 rounded-pill" />
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
        </div>
    </div>
);
