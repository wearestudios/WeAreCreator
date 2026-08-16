// The creator roster: everyone on the platform, whatever their verification
// status. The verification queue upstairs is a to-do list; this is the address
// book — you come here to look someone up, not to act on them.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { notifyError } from "@/lib/feedback";
import {
    ChevronLeft,
    ChevronRight,
    ExternalLink,
    IndianRupee,
    Instagram,
    Search,
    Users,
    X,
} from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Sheet,
    SheetClose,
    SheetContent,
    SheetDescription,
    SheetTitle,
} from "@/components/ui/sheet";
import {
    ADMIN_CREATORS as IDS,
    ADMIN_CREATOR_DETAIL as DETAIL_IDS,
    STICKY_BAR,
} from "@/constants/testIds";
import { FilterChips, ListEmptyState, StickyBar } from "@/components/data/DenseView";
import {
    CreatorAvatar,
    FilterSelect,
    GridSkeleton,
    Pill,
    SectionHeader,
    StatePill,
    VERIFICATION_META,
    formatCompact,
    formatDate,
    formatRupees,
} from "./shared";

const PAGE_SIZE = 12;

const STATUS_OPTIONS = [
    { value: "verified", label: "Verified" },
    { value: "pending", label: "Pending" },
    { value: "rejected", label: "Rejected" },
];

// Kept in step with the onboarding list — these are what creators actually pick.
const NICHE_OPTIONS = [
    "cafe", "brunch", "bakery", "fine dining", "lifestyle", "coffee", "dessert",
    "brewery", "cocktails", "home chef", "healthy", "street food", "fashion", "wellness",
].map((n) => ({ value: n, label: n }));

const AREA_OPTIONS = [
    "Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Pune", "Chennai",
    "Kolkata", "Goa", "Ahmedabad", "Jaipur", "Chandigarh", "Kochi",
].map((c) => ({ value: c, label: c }));

const GROUPS = [
    { key: "ongoing", label: "Ongoing", empty: "Nothing in flight." },
    { key: "completed", label: "Completed", empty: "No campaign closed out yet." },
    { key: "applied", label: "Applied", empty: "No open applications." },
];

// ---------------------------------------------------------------------------
// Detail drawer
// ---------------------------------------------------------------------------

const DetailStat = ({ label, value, prefix, testid }) => (
    <div className="rounded-md border border-white/10 bg-card p-5 grain-surface">
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {label}
        </p>
        <div
            data-testid={testid}
            className="mt-3 flex items-baseline font-serif text-2xl leading-none"
        >
            {prefix && <IndianRupee className="h-4 w-4 text-ember-500" />}
            {value}
        </div>
    </div>
);

const CollabRow = ({ row }) => (
    <li
        data-testid={DETAIL_IDS.collabRow(row.id)}
        className="flex flex-col gap-2 py-4 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6"
    >
        <div className="min-w-0">
            <p className="truncate text-sm text-foreground">{row.campaign_title || "—"}</p>
            <p className="mt-1 text-xs text-muted-foreground">
                {row.brand_name || "Unknown brand"}
                {row.area ? ` · ${row.area}` : ""}
            </p>
        </div>
        <div className="flex flex-none items-center gap-3">
            <span className="inline-flex items-center text-xs text-muted-foreground">
                {row.agreed_amount != null ? (
                    <>
                        <IndianRupee className="h-3 w-3" />
                        {formatRupees(row.agreed_amount)}
                    </>
                ) : (
                    "Not agreed"
                )}
            </span>
            <StatePill state={row.state} />
        </div>
    </li>
);


// ---------------------------------------------------------------------------
// Roster
// ---------------------------------------------------------------------------

// A link, not a button. It used to open a drawer over the grid, which meant a
// creator had no address: you could not send one to a colleague, reload onto
// one, or use the back button to leave. The drawer is gone — this goes to
// /admin/creators/:id, which holds far more than a drawer ever could.
function CreatorTile({ creator }) {
    return (
        <Link
            to={`/admin/creators/${creator.user_id}`}
            data-testid={IDS.tile(creator.user_id)}
            className="group flex flex-col rounded-md border border-white/10 bg-card p-6 text-left transition-colors duration-200 hover:border-ember-500/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background grain-surface"
        >
            <div className="flex items-start gap-4">
                <CreatorAvatar
                    creator={creator}
                    testids={{
                        photo: IDS.tilePhoto(creator.user_id),
                        monogram: IDS.tileMonogram(creator.user_id),
                    }}
                />
                <div className="min-w-0 flex-1">
                    <p className="truncate font-serif text-xl leading-tight">
                        {creator.name || "Unnamed"}
                    </p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                        {creator.instagram_handle ? `@${creator.instagram_handle}` : "No handle yet"}
                        {typeof creator.follower_count === "number"
                            ? ` · ${formatCompact(creator.follower_count)}`
                            : ""}
                    </p>
                </div>
            </div>

            {creator.niches?.length > 0 && (
                <div className="mt-5 flex flex-wrap gap-1.5">
                    {creator.niches.slice(0, 3).map((n) => (
                        <span
                            key={n}
                            className="rounded-full bg-ember-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-ember-500"
                        >
                            {n}
                        </span>
                    ))}
                    {creator.niches.length > 3 && (
                        <span className="px-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                            +{creator.niches.length - 3}
                        </span>
                    )}
                </div>
            )}

            <div className="mt-6 flex items-end justify-between gap-4 border-t border-white/10 pt-4">
                <Pill meta={VERIFICATION_META} value={creator.verification_status} />
                <span
                    data-testid={IDS.tileEarned(creator.user_id)}
                    className="inline-flex items-baseline text-sm text-muted-foreground"
                >
                    <IndianRupee className="h-3 w-3" />
                    {formatRupees(creator.total_earned)}
                </span>
            </div>
        </Link>
    );
}

export default function AdminCreators() {
    const [data, setData] = useState(null);
    const [q, setQ] = useState("");
    const [search, setSearch] = useState("");
    const [status, setStatus] = useState("");
    const [niche, setNiche] = useState("");
    const [area, setArea] = useState("");
    const [page, setPage] = useState(1);

    // Typing shouldn't fire a request per keystroke.
    useEffect(() => {
        const t = setTimeout(() => {
            setSearch(q.trim());
            setPage(1);
        }, 300);
        return () => clearTimeout(t);
    }, [q]);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: d } = await api.get("/admin/creators", {
                params: {
                    page,
                    page_size: PAGE_SIZE,
                    ...(search ? { q: search } : {}),
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
    }, [page, search, status, niche, area]);

    useEffect(() => {
        load();
    }, [load]);

    const filtered = Boolean(search || status || niche || area);
    const rows = data?.creators || [];
    const pages = data?.pages || 0;


    const chips = [
        { key: "search", label: "Search", value: search, onRemove: () => { setQ(""); setSearch(""); setPage(1); } },
        { key: "status", label: "Status", value: status, onRemove: () => { setStatus(""); setPage(1); } },
        { key: "niche", label: "Niche", value: niche, onRemove: () => { setNiche(""); setPage(1); } },
        { key: "area", label: "Area", value: area, onRemove: () => { setArea(""); setPage(1); } },
    ];

    const clearFilters = () => {
        setQ("");
        setSearch("");
        setStatus("");
        setNiche("");
        setArea("");
        setPage(1);
    };

    const onFilter = (setter) => (v) => {
        setter(v);
        setPage(1);
    };

    const summary = useMemo(() => {
        if (!data) return "";
        const from = (page - 1) * PAGE_SIZE + 1;
        const to = Math.min(page * PAGE_SIZE, data.total);
        if (!data.total) return "No creators";
        return `${from}–${to} of ${data.total}`;
    }, [data, page]);

    return (
        <section data-testid={IDS.section}>
            <SectionHeader
                kicker="Creators"
                title="Creator roster"
                blurb="Everyone signed up, whatever their status. Open a creator to see what they've earned and everything they're on."
                onRefresh={load}
                refreshTestId={IDS.refresh}
            />

            <StickyBar level="headerFromMd" testid={STICKY_BAR.adminSection} className="mt-8">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                <div className="relative min-w-0 flex-1 sm:min-w-[16rem]">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        data-testid={IDS.search}
                        placeholder="Name, handle, phone or email"
                        aria-label="Search creators"
                        className="h-11 md:h-10 rounded-md border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                    />
                </div>
                <FilterSelect
                    label="Any status"
                    value={status}
                    onChange={onFilter(setStatus)}
                    options={STATUS_OPTIONS}
                    testid={IDS.filterStatus}
                />
                <FilterSelect
                    label="Any niche"
                    value={niche}
                    onChange={onFilter(setNiche)}
                    options={NICHE_OPTIONS}
                    testid={IDS.filterNiche}
                />
                <FilterSelect
                    label="Any area"
                    value={area}
                    onChange={onFilter(setArea)}
                    options={AREA_OPTIONS}
                    testid={IDS.filterArea}
                />
                {filtered && (
                    <button
                        type="button"
                        onClick={clearFilters}
                        data-testid={IDS.filterClear}
                        className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                    >
                        <X className="h-3.5 w-3.5" />
                        Clear
                    </button>
                )}
            </div>

            <FilterChips chips={chips} onClearAll={clearFilters} className="mt-3" />
            </StickyBar>

            <div className="mt-8">
                {!data ? (
                    <GridSkeleton tiles={6} testid={IDS.skeleton} />
                ) : rows.length === 0 ? (
                    <ListEmptyState
                        Icon={Users}
                        testid={IDS.empty}
                        filtered={filtered}
                        onClearFilters={clearFilters}
                        emptyTitle="No creators yet."
                        emptyBody="Everyone who signs up appears here, whether or not they have finished their profile. Approve them from Reviews once they submit."
                        filteredTitle="No creator matches those filters."
                        filteredBody="Widen the status, niche or area — or clear the search."
                    />
                ) : (
                    <>
                        <p
                            data-testid={IDS.count}
                            className="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                        >
                            {summary}
                        </p>
                        <div
                            data-testid={IDS.grid}
                            className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                        >
                            {rows.map((c) => (
                                <CreatorTile key={c.user_id} creator={c} />
                            ))}
                        </div>
                    </>
                )}
            </div>

            {pages > 1 && (
                <div
                    data-testid={IDS.pagination}
                    className="mt-8 flex items-center justify-center gap-6"
                >
                    <button
                        type="button"
                        disabled={page <= 1}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        data-testid={IDS.pagePrev}
                        className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 disabled:pointer-events-none disabled:opacity-40"
                    >
                        <ChevronLeft className="h-3.5 w-3.5" />
                        Previous
                    </button>
                    <span
                        data-testid={IDS.pageLabel}
                        className="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                    >
                        Page {page} of {pages}
                    </span>
                    <button
                        type="button"
                        disabled={page >= pages}
                        onClick={() => setPage((p) => Math.min(pages, p + 1))}
                        data-testid={IDS.pageNext}
                        className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 disabled:pointer-events-none disabled:opacity-40"
                    >
                        Next
                        <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                </div>
            )}

        </section>
    );
}
