// The creator roster: everyone on the platform, whatever their verification
// status. The verification queue upstairs is a to-do list; this is the address
// book — you come here to look someone up, not to act on them.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
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
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Sheet,
    SheetClose,
    SheetContent,
    SheetDescription,
    SheetTitle,
} from "@/components/ui/sheet";
import { ADMIN_CREATORS as IDS, ADMIN_CREATOR_DETAIL as DETAIL_IDS } from "@/constants/testIds";
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
    <div className="rounded-md border border-white/10 bg-card p-5">
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

function CreatorDetail({ creatorId, onClose }) {
    const [data, setData] = useState(null);

    useEffect(() => {
        let live = true;
        setData(null);
        if (!creatorId) return undefined;
        (async () => {
            try {
                const { data: d } = await api.get(`/admin/creators/${creatorId}`);
                if (live) setData(d);
            } catch (e) {
                toast.error(formatApiError(e));
                if (live) onClose();
            }
        })();
        return () => {
            live = false;
        };
    }, [creatorId, onClose]);

    const creator = data?.creator;
    const totals = data?.totals;

    return (
        <Sheet open={Boolean(creatorId)} onOpenChange={(v) => !v && onClose()}>
            <SheetContent
                side="right"
                data-testid={DETAIL_IDS.drawer}
                className="w-full overflow-y-auto border-l border-white/10 bg-background p-0 sm:max-w-xl"
            >
                {/* Radix needs a title and description on the panel; the visible
                    heading below is the same name, so these are screen-reader only. */}
                <SheetTitle className="sr-only">
                    {creator?.name || "Creator record"}
                </SheetTitle>
                <SheetDescription className="sr-only">
                    Earnings and collaboration history for this creator.
                </SheetDescription>

                {!data ? (
                    <div data-testid={DETAIL_IDS.skeleton} className="space-y-8 p-8">
                        <div className="flex items-center gap-4">
                            <Skeleton className="h-16 w-16 flex-none rounded-md" />
                            <div className="flex-1 space-y-2">
                                <Skeleton className="h-5 w-1/2" />
                                <Skeleton className="h-3 w-1/3" />
                            </div>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                            {[0, 1, 2].map((i) => (
                                <Skeleton key={i} className="h-24 rounded-md" />
                            ))}
                        </div>
                        <div className="space-y-3">
                            {[0, 1, 2, 3].map((i) => (
                                <Skeleton key={i} className="h-12 rounded-md" />
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="p-8">
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            Creator record
                        </p>

                        <div className="mt-6 flex items-start gap-4">
                            <CreatorAvatar creator={creator} size="h-16 w-16" />
                            <div className="min-w-0 flex-1">
                                <h3
                                    data-testid={DETAIL_IDS.name}
                                    className="font-serif text-3xl leading-none tracking-tight"
                                >
                                    {creator.name || "Unnamed creator"}
                                </h3>
                                <div className="mt-3 flex flex-wrap items-center gap-3">
                                    <Pill
                                        meta={VERIFICATION_META}
                                        value={creator.verification_status}
                                    />
                                    {creator.city && (
                                        <span className="text-xs text-muted-foreground">
                                            {creator.city}
                                        </span>
                                    )}
                                    <span className="text-xs text-muted-foreground">
                                        Joined {formatDate(creator.joined_at || creator.created_at)}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {creator.instagram_handle && (
                            <a
                                href={
                                    creator.instagram_profile_url ||
                                    `https://instagram.com/${creator.instagram_handle}`
                                }
                                target="_blank"
                                rel="noreferrer"
                                className="mt-6 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-card px-3 py-1.5 text-xs transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                            >
                                <Instagram className="h-3.5 w-3.5" />@{creator.instagram_handle}
                                {typeof creator.follower_count === "number" && (
                                    <span className="text-muted-foreground">
                                        · {formatCompact(creator.follower_count)} followers
                                    </span>
                                )}
                                <ExternalLink className="h-3 w-3" />
                            </a>
                        )}

                        <div className="mt-8 grid gap-3 sm:grid-cols-3">
                            <DetailStat
                                testid={DETAIL_IDS.lifetimeEarned}
                                label="Lifetime earned"
                                prefix
                                value={formatRupees(totals.lifetime_earned)}
                            />
                            <DetailStat
                                testid={DETAIL_IDS.committed}
                                label="Committed"
                                prefix
                                value={formatRupees(totals.committed)}
                            />
                            <DetailStat
                                testid={DETAIL_IDS.campaignsCompleted}
                                label="Campaigns done"
                                value={totals.campaigns_completed}
                            />
                        </div>
                        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                            Earned is money that has actually left the bank. Committed is
                            agreed on work still in flight.
                        </p>

                        <div className="mt-10 space-y-8">
                            {GROUPS.map((g) => {
                                const rows = data.collaborations[g.key] || [];
                                return (
                                    <div key={g.key} data-testid={DETAIL_IDS.group(g.key)}>
                                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                            {g.label} · {rows.length}
                                        </p>
                                        {rows.length === 0 ? (
                                            <p
                                                data-testid={DETAIL_IDS.groupEmpty(g.key)}
                                                className="mt-4 text-sm text-muted-foreground"
                                            >
                                                {g.empty}
                                            </p>
                                        ) : (
                                            <ul className="mt-2 divide-y divide-white/10">
                                                {rows.map((r) => (
                                                    <CollabRow key={r.id} row={r} />
                                                ))}
                                            </ul>
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        {/* The panel scrolls; this saves a trip back to the
                            corner X after reading a long history. */}
                        <SheetClose asChild>
                            <button
                                type="button"
                                data-testid={DETAIL_IDS.close}
                                className="mt-10 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                            >
                                Close
                            </button>
                        </SheetClose>
                    </div>
                )}
            </SheetContent>
        </Sheet>
    );
}

// ---------------------------------------------------------------------------
// Roster
// ---------------------------------------------------------------------------

function CreatorTile({ creator, onOpen }) {
    return (
        <button
            type="button"
            onClick={() => onOpen(creator.user_id)}
            data-testid={IDS.tile(creator.user_id)}
            className="group flex flex-col rounded-md border border-white/10 bg-card p-6 text-left transition-colors duration-200 hover:border-ember-500/40"
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
        </button>
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
    const [openId, setOpenId] = useState(null);

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
            toast.error(formatApiError(e));
            setData({ creators: [], total: 0, pages: 0 });
        }
    }, [page, search, status, niche, area]);

    useEffect(() => {
        load();
    }, [load]);

    const filtered = Boolean(search || status || niche || area);
    const rows = data?.creators || [];
    const pages = data?.pages || 0;

    const closeDetail = useCallback(() => setOpenId(null), []);

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

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                <div className="relative min-w-0 flex-1 sm:min-w-[16rem]">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        data-testid={IDS.search}
                        placeholder="Name, handle, phone or email"
                        aria-label="Search creators"
                        className="h-10 rounded-md border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
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

            <div className="mt-8">
                {!data ? (
                    <GridSkeleton tiles={6} testid={IDS.skeleton} />
                ) : rows.length === 0 ? (
                    <div
                        data-testid={IDS.empty}
                        className="flex items-center gap-4 rounded-md border border-white/10 bg-card px-6 py-10 text-sm text-muted-foreground"
                    >
                        <Users className="h-5 w-5 flex-none text-ember-500" />
                        <p>
                            {filtered
                                ? "No creator matches those filters."
                                : "Nobody has signed up yet."}
                        </p>
                    </div>
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
                                <CreatorTile key={c.user_id} creator={c} onOpen={setOpenId} />
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

            <CreatorDetail creatorId={openId} onClose={closeDetail} />
        </section>
    );
}
