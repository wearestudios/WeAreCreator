// Shared pieces for the dense, data-heavy views: the admin console, the
// campaigns lists, the creator directory, the applicant board and the audit
// log. Five surfaces that were each solving the same five problems slightly
// differently — or not at all.
//
// The rules they encode:
//
//   * Context stays on screen. A filter bar you have to scroll back up to read
//     is a filter bar you forget you set.
//   * A list that can be empty says what would be in it, and how to get some.
//     A blank rectangle is indistinguishable from a broken page.
//   * Loading looks like the thing that is loading. A spinner tells you to
//     wait; a skeleton tells you what you are waiting for, and reserves the
//     space so the page does not jump when it arrives.
//   * You can always see how many results you are looking at and why. Every
//     active filter is visible and removable in one tap.
import React from "react";
import { Filter, X } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { DENSE } from "@/constants/testIds";

// ---------------------------------------------------------------------------
// Sticky
// ---------------------------------------------------------------------------

/**
 * The one place the sticky offsets and z-indexes are written down.
 *
 * The navbar is `sticky top-0 z-40 h-16`. Everything that sticks below it has
 * to clear 4rem and sit under z-40, or it slides over the navigation. Getting
 * this wrong is invisible until you scroll, which is why it is a constant
 * rather than a number typed at each call site.
 */
export const STICKY = {
    // Below the navbar, above the list.
    header: "sticky top-16 z-30",
    // The same, but only once there is room for it. A filter bar whose four
    // controls stack into a column is 400px tall on a phone — pinning that
    // under the navbar leaves a third of an 844px screen for the list it is
    // meant to help you read. Below `md` the bar scrolls away like any other
    // content, and the chips summarise what is set when you scroll back.
    headerFromMd: "md:sticky md:top-16 md:z-30",
    // Below a sticky header that is already occupying the space under the nav.
    barUnderHeader: "sticky top-16 z-20",
    // A table head inside its own scroll container: it sticks to the container,
    // not the viewport, so the offset is zero.
    tableHead: "sticky top-0 z-10",
    // The pinned first column of a horizontally scrolling table.
    pinnedCell: "sticky left-0 z-[11]",
};

/**
 * A bar that stays put while the list scrolls under it.
 *
 * Opaque enough to read against whatever is passing behind, blurred so it
 * reads as glass rather than as a lid. The negative margin plus padding is
 * what stops the blur cutting off at the container edge and showing a seam.
 */
export function StickyBar({
    children,
    className = "",
    // "header" pins at every width; "headerFromMd" only once the controls stop
    // stacking. Use the second for any bar with more than one row of controls.
    level = "header",
    // The bar has to bleed out to the edges of its container and repaint the
    // gutter, or the blurred panel stops short and you see a strip of
    // unblurred list sliding past beside it. Match the page's own padding.
    bleed = "-mx-5 px-5 md:-mx-6 md:px-6",
    testid,
}) {
    return (
        <div
            data-testid={testid}
            className={
                `${STICKY[level]} ${bleed} border-b border-white/10 bg-background/80 ` +
                `py-3 backdrop-blur-xl ${className}`
            }
        >
            {children}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Counts and active filters
// ---------------------------------------------------------------------------

/**
 * "12 of 48 creators". The denominator only appears when filtering has
 * actually removed something, so an unfiltered list reads "48 creators"
 * rather than the same number twice.
 */
export function ResultCount({ shown, total, noun, nounPlural, testid, className = "" }) {
    const plural = nounPlural || `${noun}s`;
    const word = shown === 1 ? noun : plural;
    const filtered = typeof total === "number" && total !== shown;
    return (
        <p
            data-testid={testid || DENSE.count}
            className={
                "text-xs uppercase tracking-[0.18em] text-muted-foreground " + className
            }
        >
            {filtered ? (
                <>
                    <span className="text-foreground">{shown}</span> of {total} {plural}
                </>
            ) : (
                <>
                    <span className="text-foreground">{shown}</span> {word}
                </>
            )}
        </p>
    );
}

/**
 * One chip per active filter, each removable on its own, plus a clear-all.
 *
 * `chips` is `[{ key, label, value, onRemove }]`. The label is what the filter
 * is, the value is what it is set to — "Area: Indiranagar" reads at a glance
 * where a bare "Indiranagar" makes you work out which control it came from.
 *
 * Renders nothing at all when no filter is set: an empty row of chrome above a
 * list is the sort of thing that makes a dense view feel heavier than it is.
 */
export function FilterChips({ chips, onClearAll, testid, className = "" }) {
    const active = (chips || []).filter((c) => c && c.value != null && c.value !== "");
    if (active.length === 0) return null;
    return (
        <div
            data-testid={testid || DENSE.chips}
            className={"flex flex-wrap items-center gap-2 " + className}
        >
            <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                <Filter className="h-3 w-3" />
                Filtered by
            </span>
            {active.map((c) => (
                <button
                    key={c.key}
                    type="button"
                    onClick={c.onRemove}
                    data-testid={DENSE.chip(c.key)}
                    // The whole chip is the target, not a 12px × inside it —
                    // these get tapped on a phone.
                    aria-label={`Remove filter ${c.label}: ${c.value}`}
                    className="group inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.04] py-1 pl-3 pr-2 text-xs transition-colors duration-200 hover:border-ember-500/50 hover:bg-ember-500/10"
                >
                    <span className="text-muted-foreground">{c.label}:</span>
                    <span className="max-w-[12rem] truncate">{c.value}</span>
                    <X className="h-3 w-3 flex-none text-muted-foreground transition-colors duration-200 group-hover:text-ember-500" />
                </button>
            ))}
            {active.length > 1 && onClearAll && (
                <button
                    type="button"
                    onClick={onClearAll}
                    data-testid={DENSE.clearAll}
                    className="rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    Clear all
                </button>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Empty
// ---------------------------------------------------------------------------

/**
 * What an empty list says for itself.
 *
 * `title` is the state, `children` is what would be here, `action` is how to
 * get some. The distinction that matters is between "nothing here yet" and
 * "nothing matches your filters" — the second has an obvious next step and the
 * first does not, so the caller passes a different `action` for each.
 */
export function EmptyState({ Icon, title, children, action, testid, className = "" }) {
    return (
        <div
            data-testid={testid}
            className={
                "flex flex-col items-start gap-3 rounded-lg border border-dashed border-white/15 " +
                "bg-card/40 px-6 py-10 md:px-8 md:py-12 " + className
            }
        >
            {Icon && <Icon className="h-5 w-5 text-ember-500" />}
            {title && <p className="font-serif text-2xl leading-tight">{title}</p>}
            <p className="max-w-lg text-sm leading-relaxed text-muted-foreground">
                {children}
            </p>
            {action}
        </div>
    );
}

/** The two-branch case, which is most of them. */
export function ListEmptyState({
    Icon,
    filtered,
    onClearFilters,
    emptyTitle,
    emptyBody,
    filteredTitle = "Nothing matches those filters.",
    filteredBody = "Widen or clear them to see the rest.",
    clearLabel = "Clear filters",
    action,
    testid,
}) {
    return (
        <EmptyState
            Icon={Icon}
            testid={testid}
            title={filtered ? filteredTitle : emptyTitle}
            action={
                filtered && onClearFilters ? (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onClearFilters}
                        data-testid={DENSE.emptyClear}
                        className="mt-1 rounded-full"
                    >
                        {clearLabel}
                    </Button>
                ) : (
                    action
                )
            }
        >
            {filtered ? filteredBody : emptyBody}
        </EmptyState>
    );
}

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
//
// Each of these mirrors a real component's box model — same padding, same
// border, same row height — so the content does not move when it lands. That
// is the whole point of using one instead of a spinner, and it is the part
// that quietly rots, so the shapes live next to each other here rather than
// beside the components they stand in for.

/** A row in a divided list: avatar, two lines, a pill on the right. */
export function RowSkeleton({ className = "" }) {
    return (
        <div className={"flex items-center gap-4 px-5 py-5 md:px-6 " + className}>
            <Skeleton className="h-11 w-11 flex-none rounded-full" />
            <div className="min-w-0 flex-1 space-y-2">
                <Skeleton className="h-4 w-40 max-w-[60%]" />
                <Skeleton className="h-3 w-56 max-w-[80%]" />
            </div>
            <Skeleton className="h-6 w-20 flex-none rounded-full" />
        </div>
    );
}

export function ListSkeleton({ rows = 5, testid }) {
    return (
        <div
            data-testid={testid || DENSE.skeleton}
            aria-hidden="true"
            className="divide-y divide-white/10 overflow-hidden rounded-lg border border-white/10 bg-card grain-surface"
        >
            {Array.from({ length: rows }).map((_, i) => (
                <RowSkeleton key={i} />
            ))}
        </div>
    );
}

/** A card in a grid: title, meta line, body, a footer row of controls. */
export function CardSkeleton({ cover = false }) {
    if (cover) {
        // A card with a picture on it: the picture is most of the card's
        // height, so a skeleton that leaves it out is a skeleton that shifts by
        // the height of the picture. The 16/9 box matches CampaignCover's.
        return (
            <div className="overflow-hidden rounded-lg border border-white/10 bg-card grain-surface">
                <Skeleton className="aspect-[16/9] w-full rounded-none" />
                <div className="p-6 md:p-7">
                    <Skeleton className="h-5 w-3/4" />
                    <div className="mt-3 flex gap-3">
                        <Skeleton className="h-3 w-20" />
                        <Skeleton className="h-3 w-16" />
                    </div>
                    <div className="mt-6 space-y-2">
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-3 w-5/6" />
                    </div>
                    <div className="mt-7 flex items-center justify-between">
                        <Skeleton className="h-7 w-24" />
                        <Skeleton className="h-8 w-8 rounded-full" />
                    </div>
                </div>
            </div>
        );
    }
    return (
        <div className="rounded-lg border border-white/10 bg-card p-6 grain-surface md:p-7">
            <Skeleton className="h-5 w-3/4" />
            <div className="mt-3 flex gap-3">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-3 w-16" />
            </div>
            <div className="mt-6 space-y-2">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
            </div>
            <div className="mt-7 flex items-center justify-between">
                <Skeleton className="h-7 w-24" />
                <Skeleton className="h-8 w-8 rounded-full" />
            </div>
        </div>
    );
}

export function CardGridSkeleton({
    cards = 6,
    columns = "sm:grid-cols-2 lg:grid-cols-3",
    cover = false,
    testid,
}) {
    return (
        <div
            data-testid={testid || DENSE.skeleton}
            aria-hidden="true"
            className={`grid grid-cols-1 gap-5 ${columns}`}
        >
            {Array.from({ length: cards }).map((_, i) => (
                <CardSkeleton key={i} cover={cover} />
            ))}
        </div>
    );
}

/** A creator card: avatar beside a name, stats, then a row of niches. */
export function CreatorCardSkeleton() {
    return (
        <div className="rounded-lg border border-white/10 bg-card p-6 grain-surface">
            <div className="flex items-start gap-4">
                <Skeleton className="aspect-square h-14 w-14 flex-none rounded-full" />
                <div className="min-w-0 flex-1 space-y-2">
                    <Skeleton className="h-5 w-2/3" />
                    <Skeleton className="h-3 w-1/2" />
                </div>
            </div>
            <div className="mt-6 flex gap-2">
                <Skeleton className="h-6 w-20 rounded-full" />
                <Skeleton className="h-6 w-16 rounded-full" />
            </div>
            <div className="mt-6 flex items-center justify-between">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
            </div>
        </div>
    );
}

export function CreatorGridSkeleton({ cards = 6, testid }) {
    return (
        <div
            data-testid={testid || DENSE.skeleton}
            aria-hidden="true"
            className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3"
        >
            {Array.from({ length: cards }).map((_, i) => (
                <CreatorCardSkeleton key={i} />
            ))}
        </div>
    );
}

/** An applicant row: photo, name, pitch, the fee on the right, then actions. */
export function ApplicantSkeleton() {
    return (
        <div className="flex flex-col gap-5 px-5 py-6 md:px-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:gap-6">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                        <Skeleton className="aspect-square h-10 w-10 flex-none rounded-full" />
                        <Skeleton className="h-7 w-44 max-w-[50%]" />
                    </div>
                    <div className="mt-3 flex flex-wrap gap-3">
                        <Skeleton className="h-3 w-24" />
                        <Skeleton className="h-3 w-20" />
                        <Skeleton className="h-3 w-24" />
                    </div>
                </div>
                <div className="flex flex-none flex-col items-end gap-2">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-8 w-28" />
                </div>
            </div>
            <Skeleton className="h-12 w-full" />
            <div className="flex gap-3">
                <Skeleton className="h-9 w-28 rounded-full" />
                <Skeleton className="h-9 w-24 rounded-full" />
            </div>
        </div>
    );
}

export function ApplicantListSkeleton({ rows = 3, testid }) {
    return (
        <div
            data-testid={testid || DENSE.skeleton}
            aria-hidden="true"
            className="divide-y divide-white/10 overflow-hidden rounded-lg border border-white/10 bg-card grain-surface"
        >
            {Array.from({ length: rows }).map((_, i) => (
                <ApplicantSkeleton key={i} />
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

/**
 * A table that survives a 390px screen.
 *
 * Horizontal scroll with the first column pinned, because that column is the
 * row's identity — scroll the audit log sideways without it and you are
 * reading five columns of values with no idea which entry they belong to.
 *
 * The header sticks to the top of this container rather than to the viewport,
 * which is the only thing that can work: `overflow-x: auto` computes
 * `overflow-y` to `auto` as well, making this element the scroll container for
 * everything inside it. That is why the container takes a max height — a
 * sticky header with nothing to stick against does nothing at all.
 */
export function ScrollTable({ children, maxHeight = "max-h-[70vh]", className = "", testid }) {
    return (
        <div
            data-testid={testid}
            className={`overflow-auto ${maxHeight} rounded-lg border border-white/10 bg-card grain-surface ${className}`}
        >
            {children}
        </div>
    );
}

export const tableHeadClass =
    `${STICKY.tableHead} bg-card/95 px-5 py-3 text-left text-[10px] font-medium ` +
    "uppercase tracking-[0.2em] text-muted-foreground backdrop-blur-xl";

/** The pinned column needs an opaque ground or the scrolled cells show through. */
// The rule down the right edge is what makes the pin legible: without it the
// scrolled columns slide up against the timestamp with no seam, and the eye
// reads the two as one column.
export const pinnedHeadClass =
    `${tableHeadClass} ${STICKY.pinnedCell} border-r border-white/10 bg-card`;
export const pinnedCellClass = `${STICKY.pinnedCell} border-r border-white/10 bg-card`;

export default {
    STICKY,
    StickyBar,
    ResultCount,
    FilterChips,
    EmptyState,
    ListEmptyState,
    ListSkeleton,
    CardGridSkeleton,
    CreatorGridSkeleton,
    ApplicantListSkeleton,
    ScrollTable,
};
