// The console's one table.
//
// Every list view — creators, campaigns, brands, collaborations, audit — was a
// grid of cards. Cards are right when each item is a thing you look *at* and
// wrong when they are rows you look *across*: you cannot compare a follower
// count in card three with the one in card eleven, and a screen that fits nine
// cards fits about thirty rows.
//
// What a table has to get right to be worth it:
//
//   - **Sortable columns**, because the first thing anybody does with a list
//     of forty is ask which is the biggest or the oldest.
//   - **A sticky header**, because a column you have scrolled past is a column
//     you are guessing at.
//   - **Right-aligned numerics, tabular figures**, because digits that do not
//     line up cannot be compared down a column, which is the whole point.
//   - **A fixed row height** (44px), so the eye tracks a rhythm down the left
//     edge — and so virtualisation needs no measurement.
//   - **A visible focused row**, because the keyboard flow is half the point
//     and focus you cannot see is focus you do not trust.
//
// **Virtualised past a threshold, and not before.** Windowing forty rows costs
// more than it saves and breaks ⌘F; past a few hundred it is the difference
// between a list that scrolls and one that stutters. The switch is automatic
// so no call site has to decide.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import {
    CALM,
    DENSITY,
    FOCUS,
    PANEL,
    ROW_H,
    ROW_PX,
    TEXT,
} from "@/components/admin/console/tokens";
import { ADMIN_TABLE as IDS } from "@/constants/testIds";

/** Rows past which the body is windowed. Below it, everything is in the DOM. */
const VIRTUALISE_ABOVE = 150;
/** Rows rendered beyond the viewport, so a fast scroll does not show gaps. */
const OVERSCAN = 8;

/**
 * A column.
 *
 * @typedef {object} Column
 * @property {string}   key     unique, and the sort key
 * @property {string}   header  the column label
 * @property {Function} cell    (row) => node
 * @property {boolean} [numeric] right-align and use tabular figures
 * @property {boolean} [sortable]
 * @property {Function} [value] (row) => comparable, for sorting
 * @property {string}  [width]  a Tailwind width, for columns that must not flex
 * @property {boolean} [hideBelow] hide under `lg` — secondary columns
 */

function SortIcon({ dir }) {
    const Icon = dir === "asc" ? ArrowUp : dir === "desc" ? ArrowDown : ChevronsUpDown;
    return (
        <Icon
            className={`h-3 w-3 shrink-0 ${dir ? "text-ember-500" : "text-muted-foreground/50"}`}
        />
    );
}

/**
 * Sort rows by a column, stably and without mutating the input.
 *
 * Nullish sorts last in both directions — a row with no value is not "the
 * smallest", it is a row we know nothing about, and burying it under the real
 * data in both orders is the honest placement.
 */
export function sortRows(rows, columns, sort) {
    if (!sort?.key) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const read = col.value || ((r) => r[col.key]);
    const dir = sort.dir === "desc" ? -1 : 1;
    return [...rows].sort((a, b) => {
        const x = read(a);
        const y = read(b);
        if (x == null && y == null) return 0;
        if (x == null) return 1;
        if (y == null) return -1;
        if (typeof x === "number" && typeof y === "number") return (x - y) * dir;
        return String(x).localeCompare(String(y), "en") * dir;
    });
}

export function DataTable({
    columns,
    rows,
    rowKey = (r, i) => r.id ?? r._id ?? i,
    // A screen that already had a row id keeps it. The card grids each had
    // one, and "the element for creator X on the creator list" is a promise a
    // test id makes — changing the layout is not a reason to break it.
    rowTestId,
    sort,
    onSortChange,
    focused = -1,
    onFocus,
    onOpen,
    loading = false,
    empty = null,
    testid = IDS.root,
    maxHeight = "max-h-[calc(100vh-16rem)]",
    // **A floor, under which the table scrolls sideways rather than squashing.**
    // `table-fixed` honours the sized columns first, so on a 390px screen the
    // numerics took everything and the name column collapsed to nothing —
    // measured: the creator list showed two overlapping headers and no names.
    // With a minimum the container scrolls instead, which is the same thing
    // `ScrollTable` does elsewhere in the app, and the identity column is
    // leftmost so it is what you see before scrolling.
    minWidth = "min-w-[52rem]",
    scrollRef,
}) {
    const localRef = useRef(null);
    const bodyRef = scrollRef || localRef;
    const [range, setRange] = useState({ start: 0, end: 60 });

    const virtual = rows.length > VIRTUALISE_ABOVE;

    const recompute = useCallback(() => {
        const el = bodyRef.current;
        if (!el || !virtual) return;
        const start = Math.max(0, Math.floor(el.scrollTop / ROW_PX) - OVERSCAN);
        const visible = Math.ceil(el.clientHeight / ROW_PX) + OVERSCAN * 2;
        setRange({ start, end: Math.min(rows.length, start + visible) });
    }, [bodyRef, virtual, rows.length]);

    useEffect(() => {
        if (!virtual) return undefined;
        recompute();
        const el = bodyRef.current;
        if (!el) return undefined;
        el.addEventListener("scroll", recompute, { passive: true });
        window.addEventListener("resize", recompute);
        return () => {
            el.removeEventListener("scroll", recompute);
            window.removeEventListener("resize", recompute);
        };
    }, [virtual, recompute, bodyRef]);

    const slice = useMemo(
        () => (virtual ? rows.slice(range.start, range.end) : rows),
        [virtual, rows, range.start, range.end],
    );
    const padTop = virtual ? range.start * ROW_PX : 0;
    const padBottom = virtual ? Math.max(0, (rows.length - range.end) * ROW_PX) : 0;

    const toggleSort = (col) => {
        if (!col.sortable || !onSortChange) return;
        onSortChange(
            sort?.key === col.key
                ? { key: col.key, dir: sort.dir === "asc" ? "desc" : "asc" }
                : // First click on a numeric column sorts biggest-first, which
                  // is what somebody asking "who is the biggest" wants; text
                  // starts A–Z.
                  { key: col.key, dir: col.numeric ? "desc" : "asc" },
        );
    };

    if (loading) return <TableSkeleton columns={columns} testid={testid} />;
    if (!rows.length && empty) return empty;

    return (
        <div className={`${PANEL} overflow-hidden`} data-testid={testid}>
            <div ref={bodyRef} className={`overflow-auto ${maxHeight}`}>
                {/* **`table-fixed`, not auto.** With auto layout a cell's
                    `truncate` does nothing — the table just grows to fit the
                    longest string, and the columns on the right go off the
                    edge. Measured on the action queue: the decision column,
                    which is the only reason that screen exists, was scrolled
                    out of sight. Fixed layout gives the sized columns their
                    width and splits the rest evenly, so a long title
                    ellipsises instead of pushing the buttons away. */}
                <table className={`w-full table-fixed border-collapse text-left ${minWidth}`}>
                    <thead className="sticky top-0 z-10 bg-card">
                        <tr className="border-b border-white/10">
                            {columns.map((col) => (
                                <th
                                    key={col.key}
                                    scope="col"
                                    // A screen whose sort control already had an
                                    // id keeps it: the control moved into the
                                    // header, it did not stop existing.
                                    data-testid={col.testid || IDS.header(col.key)}
                                    className={`${DENSITY.row} ${TEXT.meta} font-medium uppercase tracking-[0.08em] text-muted-foreground ${
                                        col.numeric ? "text-right" : "text-left"
                                    } ${col.width || ""} ${col.hideBelow ? "hidden lg:table-cell" : ""}`}
                                >
                                    {col.sortable ? (
                                        <button
                                            type="button"
                                            onClick={() => toggleSort(col)}
                                            aria-sort={
                                                sort?.key === col.key
                                                    ? sort.dir === "asc"
                                                        ? "ascending"
                                                        : "descending"
                                                    : "none"
                                            }
                                            // The case and tracking are repeated
                                            // here rather than inherited from the
                                            // `th`: the UA stylesheet sets
                                            // `text-transform: none` on a button,
                                            // which won — measured as a header row
                                            // where the sortable columns read
                                            // "Followers" and the rest "NICHES".
                                            className={`inline-flex items-center gap-1.5 rounded uppercase tracking-[0.08em] ${CALM} hover:text-foreground ${FOCUS} ${
                                                col.numeric ? "flex-row-reverse" : ""
                                            }`}
                                        >
                                            {col.header}
                                            <SortIcon
                                                dir={sort?.key === col.key ? sort.dir : null}
                                            />
                                        </button>
                                    ) : (
                                        col.header
                                    )}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {padTop > 0 && (
                            <tr aria-hidden style={{ height: padTop }}>
                                <td colSpan={columns.length} />
                            </tr>
                        )}
                        {slice.map((row, i) => {
                            const index = (virtual ? range.start : 0) + i;
                            const isFocused = index === focused;
                            return (
                                <tr
                                    key={rowKey(row, index)}
                                    data-row-index={index}
                                    data-testid={
                                        rowTestId
                                            ? rowTestId(row, index)
                                            : IDS.row(rowKey(row, index))
                                    }
                                    tabIndex={0}
                                    onFocus={() => onFocus?.(index)}
                                    onClick={() => onOpen?.(index)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" || e.key === " ") {
                                            e.preventDefault();
                                            onOpen?.(index);
                                        }
                                    }}
                                    className={`${ROW_H} cursor-pointer border-b border-white/5 ${CALM} ${FOCUS} ${
                                        isFocused
                                            ? // The focused row is a left rule
                                              // plus a lift in the surface, not
                                              // a colour — it has to be legible
                                              // beside a status colour without
                                              // competing with it.
                                              "bg-white/[0.06] shadow-[inset_2px_0_0_0_theme(colors.ember.500)]"
                                            : "hover:bg-white/[0.03]"
                                    }`}
                                >
                                    {columns.map((col) => (
                                        <td
                                            key={col.key}
                                            // `overflow-hidden` so a cell that
                                            // overruns is clipped at its own
                                            // edge rather than printed over the
                                            // next column — measured on the
                                            // queue, where a brand name ran
                                            // into the state beside it.
                                            className={`${DENSITY.row} ${TEXT.body} overflow-hidden align-middle ${
                                                col.numeric
                                                    ? "text-right tabular-nums"
                                                    : "text-left"
                                            } ${col.hideBelow ? "hidden lg:table-cell" : ""}`}
                                        >
                                            {col.cell(row, index)}
                                        </td>
                                    ))}
                                </tr>
                            );
                        })}
                        {padBottom > 0 && (
                            <tr aria-hidden style={{ height: padBottom }}>
                                <td colSpan={columns.length} />
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

/**
 * The loading state: the table's own shape.
 *
 * Same columns, same row height, same header — so the swap when data arrives
 * costs no layout shift and the eye is already where the first row will be.
 */
export function TableSkeleton({ columns, rows = 10, testid, minWidth = "min-w-[52rem]" }) {
    return (
        <div className={`${PANEL} overflow-hidden`} data-testid={testid ? `${testid}-skeleton` : undefined}>
            {/* The same overflow container, the same `table-fixed`, the same
                minimum width. A skeleton whose shape differs from the table it
                stands in for is a layout shift with extra steps. */}
            <div className="overflow-hidden">
            <table className={`w-full table-fixed border-collapse ${minWidth}`}>
                <thead className="bg-card">
                    <tr className="border-b border-white/10">
                        {columns.map((col) => (
                            <th
                                key={col.key}
                                className={`${DENSITY.row} ${TEXT.meta} text-left font-medium uppercase tracking-[0.08em] text-muted-foreground ${
                                    col.hideBelow ? "hidden lg:table-cell" : ""
                                }`}
                            >
                                {col.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody aria-hidden>
                    {Array.from({ length: rows }).map((_, r) => (
                        <tr key={r} className={`${ROW_H} border-b border-white/5`}>
                            {columns.map((col) => (
                                <td key={col.key} className={`${DENSITY.row} ${col.hideBelow ? "hidden lg:table-cell" : ""}`}>
                                    <div
                                        className={`h-3 rounded bg-white/5 ${
                                            col.numeric ? "ml-auto w-12" : "w-3/4"
                                        }`}
                                    />
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
            </div>
        </div>
    );
}

export default DataTable;
