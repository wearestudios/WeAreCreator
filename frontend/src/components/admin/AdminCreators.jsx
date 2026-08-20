// The creator roster: everyone on the platform, whatever their verification
// status. The verification queue is a to-do list; this is the address book —
// you come here to look somebody up, not to act on them.
//
// **It was a grid of cards.** Cards are right when each item is a thing you
// look *at*, and wrong when they are rows you look *across*: you could not
// compare a follower count in card three with the one in card eleven, and a
// screen that fit nine cards fits about thirty rows. It is a table now, with
// the console's shared machinery behind it — sortable columns, a sticky
// header, a peek panel, keyboard navigation, and filters that survive a trip
// to a detail page.
//
// This screen is the reference implementation for the other list views: the
// shape here is the shape they take.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Plus, Search, Users } from "lucide-react";

import { notifyError } from "@/lib/feedback";
import { api } from "@/lib/api";
import { CITY_OPTIONS, CREATOR_TAXONOMY_TERMS } from "@/lib/taxonomy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    ADMIN_CREATE as CREATE_IDS,
    ADMIN_CREATORS as IDS,
    ADMIN_TABLE as TABLE_IDS,
} from "@/constants/testIds";
import { CreateCreatorDialog } from "./CreateDialogs";
import { FilterChips, ListEmptyState } from "@/components/data/DenseView";

import DataTable, { sortRows } from "./console/DataTable";
import PeekPanel, { PeekField } from "./console/PeekPanel";
import SaveFilter from "./console/SaveFilter";
import StatusTag from "./console/StatusTag";
import { TimeAgo, compact, rupees } from "./console/format";
import { CALM, DENSITY, FOCUS, PANEL, TEXT } from "./console/tokens";
import useListState from "./console/useListState";
import useTableKeys from "./console/useTableKeys";
import { FilterSelect } from "./shared";

const PAGE_SIZE = 50;

const STATUS_OPTIONS = [
    { value: "verified", label: "Verified" },
    { value: "pending", label: "Pending" },
    { value: "rejected", label: "Rejected" },
];

// Drawn from the shared taxonomy rather than a hand-kept copy. The niche
// filter used to be food and nothing but food, so an admin could not filter
// for a fashion or gaming creator at all — the option did not exist.
const NICHE_OPTIONS = CREATOR_TAXONOMY_TERMS.map((n) => ({ value: n, label: n }));

const DEFAULTS = {
    q: "",
    status: "",
    niche: "",
    area: "",
    page: 1,
    sort: { key: "name", dir: "asc" },
};

export default function AdminCreators() {
    const [creating, setCreating] = useState(false);
    const [data, setData] = useState(null);
    const [focused, setFocused] = useState(-1);
    const [peek, setPeek] = useState(null);
    const { state, patch, reset, scrollRef, saved, save, apply } = useListState(
        "creators",
        DEFAULTS,
    );
    const { q, status, niche, area, page, sort } = state;
    const [typed, setTyped] = useState(q);
    const location = useLocation();

    // A saved set arrives through the sidebar as router state rather than a
    // prop, because the sidebar has no way to reach into this screen.
    useEffect(() => {
        if (location.state?.savedFilter) apply(location.state.savedFilter);
    }, [location.state, apply]);

    // Typing shouldn't fire a request per keystroke.
    useEffect(() => {
        const t = setTimeout(() => {
            if (typed.trim() !== q) patch({ q: typed.trim(), page: 1 });
        }, 300);
        return () => clearTimeout(t);
    }, [typed, q, patch]);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: d } = await api.get("/admin/creators", {
                params: {
                    page,
                    page_size: PAGE_SIZE,
                    ...(q ? { q } : {}),
                    ...(status ? { verification_status: status } : {}),
                    ...(niche ? { niche } : {}),
                    ...(area ? { area } : {}),
                },
            });
            setData(d);
        } catch (e) {
            notifyError(e);
            setData({ creators: [], total: 0, pages: 0 });
        }
    }, [page, q, status, niche, area]);

    useEffect(() => {
        load();
    }, [load]);

    const raw = useMemo(() => data?.creators || [], [data]);

    /**
     * The columns.
     *
     * `value` is what the column sorts on, which is not always what it shows:
     * "24k" sorts as 24000 and a relative timestamp sorts as the instant, so
     * the order is the order of the underlying data rather than of its
     * rendering. Sorting a formatted string is how "9k" ends up above "24k".
     */
    const columns = useMemo(
        () => [
            {
                key: "name",
                mobile: "primary",
                header: "Creator",
                sortable: true,
                value: (c) => c.name || "",
                cell: (c) => (
                    <Link
                        to={`/admin/creators/${c.user_id}`}
                        onClick={(e) => e.stopPropagation()}
                        data-testid={IDS.open(c.user_id)}
                        className={`truncate ${CALM} hover:text-ember-500 ${FOCUS}`}
                    >
                        {c.name || "Unnamed"}
                    </Link>
                ),
            },
            {
                key: "verification_status",
                mobile: "meta",
                header: "Status",
                sortable: true,
                width: "w-36",
                cell: (c) => (
                    <StatusTag state={c.verification_status} testid={IDS.rowStatus(c.user_id)} />
                ),
            },
            {
                key: "city",
                mobile: "meta",
                header: "City",
                sortable: true,
                hideBelow: true,
                cell: (c) => c.city || <span className="text-muted-foreground">—</span>,
            },
            {
                key: "niches",
                header: "Niches",
                hideBelow: true,
                cell: (c) => (
                    <span className="block truncate text-muted-foreground">
                        {(c.niches || []).slice(0, 2).join(", ") || "—"}
                    </span>
                ),
            },
            {
                key: "follower_count",
                mobile: "trailing",
                header: "Followers",
                sortable: true,
                numeric: true,
                width: "w-28",
                value: (c) => c.follower_count ?? null,
                cell: (c) => compact(c.follower_count),
            },
            {
                key: "base_rate",
                header: "Base rate",
                sortable: true,
                numeric: true,
                width: "w-32",
                value: (c) => c.base_rate ?? null,
                cell: (c) => rupees(c.base_rate),
            },
            {
                key: "total_earned",
                header: "Earned",
                sortable: true,
                numeric: true,
                width: "w-32",
                value: (c) => c.total_earned ?? null,
                cell: (c) => (
                    <span data-testid={IDS.tileEarned(c.user_id)}>{rupees(c.total_earned)}</span>
                ),
            },
            {
                key: "created_at",
                header: "Joined",
                sortable: true,
                numeric: true,
                width: "w-28",
                hideBelow: true,
                value: (c) => (c.created_at ? new Date(c.created_at).getTime() : null),
                cell: (c) => <TimeAgo iso={c.created_at} />,
            },
        ],
        [],
    );

    // Sorted client-side over the page the server returned. Honest about what
    // it is: the header sorts what is on screen, and the page size is large
    // enough that this is the whole working set in most sessions.
    const rows = useMemo(() => sortRows(raw, columns, sort), [raw, columns, sort]);

    const openPeek = useCallback(
        (i) => {
            setFocused(i);
            setPeek(rows[i] || null);
        },
        [rows],
    );

    useTableKeys({
        count: rows.length,
        focused,
        setFocused,
        onOpen: openPeek,
        onEscape: () => (peek ? setPeek(null) : setFocused(-1)),
        enabled: true,
    });

    const filtered = Boolean(q || status || niche || area);
    const chips = [
        { key: "search", label: "Search", value: q, onRemove: () => { setTyped(""); patch({ q: "", page: 1 }); } },
        { key: "status", label: "Status", value: status, onRemove: () => patch({ status: "", page: 1 }) },
        { key: "niche", label: "Niche", value: niche, onRemove: () => patch({ niche: "", page: 1 }) },
        { key: "area", label: "City", value: area, onRemove: () => patch({ area: "", page: 1 }) },
    ];

    const total = data?.total ?? 0;
    const pages = data?.pages ?? 0;

    return (
        <section data-testid={IDS.section}>
            <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className={TEXT.heading}>Creators</h1>
                    <p
                        data-testid={IDS.count}
                        className={`${TEXT.meta} text-muted-foreground`}
                    >
                        {data ? `${total.toLocaleString("en-IN")} on the platform` : "Loading…"}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {/* This section is admin-only in the first place — a
                        scoped console never reaches the global directory — so
                        there is no role check here to get wrong. */}
                    <Button
                        size="sm"
                        data-testid={CREATE_IDS.creatorOpen}
                        onClick={() => setCreating(true)}
                    >
                        <Plus className="mr-1.5 h-3.5 w-3.5" />
                        New creator
                    </Button>
                    <SaveFilter
                        onSave={save}
                        disabled={!filtered}
                        savedNames={saved.map((s) => s.name)}
                    />
                </div>
            </header>

            <CreateCreatorDialog
                open={creating}
                onOpenChange={setCreating}
                onCreated={() => load()}
            />

            {/* The toolbar. One row, one height, no wrapping panel — the table
                below is the thing, and a filter bar in a card of its own reads
                as a second piece of content. */}
            <div
                data-testid={TABLE_IDS.toolbar}
                className={`mb-3 flex flex-wrap items-center gap-2 ${PANEL} ${DENSITY.row}`}
            >
                <div className="relative min-w-[9rem] flex-1">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={typed}
                        onChange={(e) => setTyped(e.target.value)}
                        placeholder="Name, handle, phone"
                        data-testid={IDS.search}
                        className={`h-8 border-white/10 bg-transparent pl-8 ${TEXT.body}`}
                    />
                </div>
                <FilterSelect
                    dense
                    label="Status"
                    value={status}
                    onChange={(v) => patch({ status: v, page: 1 })}
                    options={STATUS_OPTIONS}
                    testid={IDS.filterStatus}
                />
                <FilterSelect
                    dense
                    label="Niche"
                    value={niche}
                    onChange={(v) => patch({ niche: v, page: 1 })}
                    options={NICHE_OPTIONS}
                    testid={IDS.filterNiche}
                />
                <FilterSelect
                    dense
                    label="City"
                    value={area}
                    onChange={(v) => patch({ area: v, page: 1 })}
                    options={CITY_OPTIONS}
                    testid={IDS.filterArea}
                />
            </div>

            {filtered && (
                <div className="mb-3">
                    <FilterChips
                        chips={chips}
                        onClearAll={() => {
                            setTyped("");
                            reset();
                        }}
                    />
                </div>
            )}

            <DataTable
                columns={columns}
                rows={rows}
                rowKey={(c) => c.user_id}
                rowTestId={(c) => IDS.tile(c.user_id)}
                sort={sort}
                onSortChange={(s) => patch({ sort: s })}
                focused={focused}
                onFocus={setFocused}
                onOpen={openPeek}
                loading={!data}
                scrollRef={scrollRef}
                testid={IDS.table}
                empty={
                    <ListEmptyState
                        Icon={Users}
                        testid={IDS.empty}
                        filtered={filtered}
                        emptyTitle="No creators yet"
                        emptyBody="Creators appear here as soon as they sign up."
                        filteredTitle="No creators match those filters."
                        filteredBody="Widen the search, or clear them to see the roster."
                        onClearFilters={() => {
                            setTyped("");
                            reset();
                        }}
                    />
                }
            />

            {pages > 1 && (
                <div
                    data-testid={IDS.pagination}
                    className={`mt-3 flex items-center justify-between ${TEXT.meta} text-muted-foreground`}
                >
                    <span data-testid={IDS.pageLabel}>
                        Page {page} of {pages}
                    </span>
                    <div className="flex gap-1">
                        <button
                            type="button"
                            disabled={page <= 1}
                            onClick={() => patch({ page: page - 1 })}
                            data-testid={IDS.pagePrev}
                            className={`rounded border border-white/10 px-2 py-1 ${CALM} hover:bg-white/5 disabled:opacity-40 ${FOCUS}`}
                        >
                            Previous
                        </button>
                        <button
                            type="button"
                            disabled={page >= pages}
                            onClick={() => patch({ page: page + 1 })}
                            data-testid={IDS.pageNext}
                            className={`rounded border border-white/10 px-2 py-1 ${CALM} hover:bg-white/5 disabled:opacity-40 ${FOCUS}`}
                        >
                            Next
                        </button>
                    </div>
                </div>
            )}

            <PeekPanel
                open={Boolean(peek)}
                onOpenChange={(o) => !o && setPeek(null)}
                title={peek?.name || "Creator"}
                subtitle={peek?.instagram_handle ? `@${peek.instagram_handle}` : peek?.city}
                href={peek ? `/admin/creators/${peek.user_id}` : undefined}
            >
                {peek && (
                    <div>
                        <PeekField label="Status">
                            <StatusTag state={peek.verification_status} chip />
                        </PeekField>
                        <PeekField label="City">{peek.city}</PeekField>
                        <PeekField label="Followers">{compact(peek.follower_count)}</PeekField>
                        <PeekField label="Base rate">{rupees(peek.base_rate)}</PeekField>
                        <PeekField label="Niches">
                            {(peek.niches || []).join(", ") || "—"}
                        </PeekField>
                        <PeekField label="Joined">
                            <TimeAgo iso={peek.created_at} />
                        </PeekField>
                    </div>
                )}
            </PeekPanel>
        </section>
    );
}
