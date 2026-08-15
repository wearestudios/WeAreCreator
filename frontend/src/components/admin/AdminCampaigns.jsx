// Brands and their campaigns. Two sections that share one piece of state:
// picking a brand filters the campaign list below it, which is the question an
// admin actually asks ("what has this brand been running?").
//
// The creator-facing feed still only shows open and upcoming briefs. This view
// deliberately does not — an admin has to be able to see a draft or a closed
// campaign, which is the whole point of the endpoint behind it.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
    Building2,
    CalendarDays,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    IndianRupee,
    Search,
    Send,
    Sparkles,
    X,
} from "lucide-react";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ADMIN_BRANDS_VIEW as BRAND_IDS, ADMIN_CAMPAIGNS as IDS } from "@/constants/testIds";
import InviteCreatorsDialog from "./InviteCreatorsDialog";
import {
    CAMPAIGN_STATUS_META,
    FilterSelect,
    GridSkeleton,
    INVITABLE_STATUSES,
    ListSkeleton,
    Pill,
    SectionHeader,
    StatePill,
    formatDate,
    formatRupees,
} from "./shared";

const PAGE_SIZE = 10;

const STATUS_OPTIONS = Object.entries(CAMPAIGN_STATUS_META).map(([value, m]) => ({
    value,
    label: m.label,
}));

// Dates go through the shadcn calendar — the brief rules out raw date inputs.
function DateFilter({ value, onChange, label, testid }) {
    const [open, setOpen] = useState(false);
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
            <PopoverContent
                align="start"
                className="w-auto rounded-md border-white/10 bg-card p-0"
            >
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
}

// ---------------------------------------------------------------------------
// Brands
// ---------------------------------------------------------------------------

function BrandsView({ selectedId, onSelect }) {
    const [rows, setRows] = useState(null);

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get("/admin/brands");
            setRows(data);
        } catch (e) {
            toast.error(formatApiError(e));
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    return (
        <section data-testid={BRAND_IDS.section} className="mt-16">
            <SectionHeader
                kicker="Section 5"
                title="Brands"
                blurb="What each brand has run and what they've actually paid. Pick one to filter the campaigns below."
                onRefresh={load}
                refreshTestId={BRAND_IDS.refresh}
            />

            <div className="mt-8">
                {!rows ? (
                    <GridSkeleton tiles={3} testid={BRAND_IDS.skeleton} />
                ) : rows.length === 0 ? (
                    <div
                        data-testid={BRAND_IDS.empty}
                        className="flex items-center gap-4 rounded-md border border-white/10 bg-card px-6 py-10 text-sm text-muted-foreground"
                    >
                        <Building2 className="h-5 w-5 flex-none text-ember-500" />
                        <p>No brand has signed up yet.</p>
                    </div>
                ) : (
                    <div
                        data-testid={BRAND_IDS.list}
                        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                    >
                        {rows.map((b) => {
                            const isOn = selectedId === b.user_id;
                            return (
                                <button
                                    key={b.user_id}
                                    type="button"
                                    aria-pressed={isOn}
                                    onClick={() => onSelect(isOn ? "" : b.user_id)}
                                    data-testid={BRAND_IDS.row(b.user_id)}
                                    className={
                                        "flex flex-col rounded-md border bg-card p-6 text-left transition-colors duration-200 " +
                                        (isOn
                                            ? "border-ember-500/60"
                                            : "border-white/10 hover:border-ember-500/40")
                                    }
                                >
                                    <p className="truncate font-serif text-xl leading-tight">
                                        {b.business_name || "Unnamed brand"}
                                    </p>
                                    <p className="mt-1 truncate text-xs text-muted-foreground">
                                        {b.category || "—"}
                                        {b.areas?.length ? ` · ${b.areas.join(", ")}` : ""}
                                    </p>

                                    <div className="mt-6 flex items-end justify-between gap-4 border-t border-white/10 pt-4">
                                        <span className="text-xs text-muted-foreground">
                                            {b.campaign_count}{" "}
                                            {b.campaign_count === 1 ? "campaign" : "campaigns"}
                                            {b.active_campaign_count > 0
                                                ? ` · ${b.active_campaign_count} active`
                                                : ""}
                                        </span>
                                        <span
                                            data-testid={BRAND_IDS.rowSpend(b.user_id)}
                                            className="inline-flex items-baseline text-sm"
                                        >
                                            <IndianRupee className="h-3 w-3 text-ember-500" />
                                            {formatRupees(b.total_spend)}
                                        </span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        </section>
    );
}

// ---------------------------------------------------------------------------
// Campaigns
// ---------------------------------------------------------------------------

function CampaignRow({ campaign, expanded, onToggle, onInvite }) {
    const canInvite = INVITABLE_STATUSES.includes(campaign.status);
    return (
        <li data-testid={IDS.row(campaign.id)} className="px-6 py-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:gap-6">
                <button
                    type="button"
                    onClick={onToggle}
                    aria-expanded={expanded}
                    data-testid={IDS.expand(campaign.id)}
                    className="group flex min-w-0 flex-1 items-start gap-3 text-left"
                >
                    <ChevronDown
                        className={
                            "mt-1 h-4 w-4 flex-none text-muted-foreground transition-transform duration-200 " +
                            (expanded ? "rotate-180" : "")
                        }
                    />
                    <div className="min-w-0">
                        <p className="truncate font-serif text-xl leading-tight transition-colors duration-200 group-hover:text-ember-500">
                            {campaign.title}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {campaign.brand_name || "Unknown brand"}
                            {campaign.area ? ` · ${campaign.area}` : ""} · created{" "}
                            {formatDate(campaign.created_at)}
                        </p>
                    </div>
                </button>

                <div className="flex flex-none flex-wrap items-center gap-3 md:justify-end">
                    <span className="inline-flex items-baseline text-sm text-muted-foreground">
                        <IndianRupee className="h-3 w-3" />
                        {formatRupees(campaign.budget_per_creator)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                        {campaign.filled_slots}/{campaign.creators_needed} filled
                    </span>
                    <Pill meta={CAMPAIGN_STATUS_META} value={campaign.status} />
                    {canInvite && (
                        <Button
                            type="button"
                            onClick={() => onInvite(campaign)}
                            data-testid={IDS.inviteOpen(campaign.id)}
                            className="h-8 rounded-full bg-ember-500 px-4 text-xs text-black hover:bg-ember-400"
                        >
                            <Send className="mr-1.5 h-3.5 w-3.5" />
                            Invite creators
                        </Button>
                    )}
                </div>
            </div>

            {expanded && (
                <div
                    data-testid={IDS.creators(campaign.id)}
                    className="mt-5 rounded-md border border-white/10 bg-background/40 px-5 py-2"
                >
                    {campaign.creators.length === 0 ? (
                        <p
                            data-testid={IDS.creatorsEmpty(campaign.id)}
                            className="py-4 text-sm text-muted-foreground"
                        >
                            Nobody has applied to this brief yet.
                        </p>
                    ) : (
                        <ul className="divide-y divide-white/10">
                            {campaign.creators.map((c) => (
                                <li
                                    key={c.collaboration_id}
                                    data-testid={IDS.creatorRow(c.collaboration_id)}
                                    className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6"
                                >
                                    <div className="min-w-0">
                                        <p className="truncate text-sm">{c.name || "Unnamed"}</p>
                                        {c.instagram_handle && (
                                            <p className="truncate text-xs text-muted-foreground">
                                                @{c.instagram_handle}
                                            </p>
                                        )}
                                    </div>
                                    <div className="flex flex-none items-center gap-3">
                                        <span className="inline-flex items-baseline text-xs text-muted-foreground">
                                            {c.agreed_amount != null ? (
                                                <>
                                                    <IndianRupee className="h-3 w-3" />
                                                    {formatRupees(c.agreed_amount)}
                                                </>
                                            ) : (
                                                "Not agreed"
                                            )}
                                        </span>
                                        <StatePill state={c.state} />
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </li>
    );
}

export default function AdminCampaigns() {
    const [brandId, setBrandId] = useState("");
    const [data, setData] = useState(null);
    const [q, setQ] = useState("");
    const [search, setSearch] = useState("");
    const [status, setStatus] = useState("");
    const [from, setFrom] = useState(null);
    const [to, setTo] = useState(null);
    const [page, setPage] = useState(1);
    const [expanded, setExpanded] = useState({});
    const [inviteFor, setInviteFor] = useState(null);

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
            const { data: d } = await api.get("/admin/campaigns", {
                params: {
                    page,
                    page_size: PAGE_SIZE,
                    ...(search ? { q: search } : {}),
                    ...(status ? { status } : {}),
                    ...(brandId ? { brand_id: brandId } : {}),
                    ...(from ? { date_from: from.toISOString() } : {}),
                    // Through the end of the chosen day, not its first second.
                    ...(to
                        ? {
                              date_to: new Date(
                                  to.getFullYear(),
                                  to.getMonth(),
                                  to.getDate(),
                                  23,
                                  59,
                                  59,
                              ).toISOString(),
                          }
                        : {}),
                },
            });
            setData(d);
        } catch (e) {
            toast.error(formatApiError(e));
            setData({ campaigns: [], total: 0, pages: 0 });
        }
    }, [page, search, status, brandId, from, to]);

    useEffect(() => {
        load();
    }, [load]);

    const selectBrand = (id) => {
        setBrandId(id);
        setPage(1);
    };

    const filtered = Boolean(search || status || brandId || from || to);
    // Memoised because the brand-name lookup below depends on it; a fresh array
    // each render would re-run that on every keystroke.
    const rows = useMemo(() => data?.campaigns || [], [data]);
    const pages = data?.pages || 0;

    const selectedBrandName = useMemo(
        () => rows.find((c) => c.brand_id === brandId)?.brand_name,
        [rows, brandId],
    );

    const clearFilters = () => {
        setQ("");
        setSearch("");
        setStatus("");
        setBrandId("");
        setFrom(null);
        setTo(null);
        setPage(1);
    };

    const summary = data
        ? data.total
            ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, data.total)} of ${
                  data.total
              }`
            : "No campaigns"
        : "";

    return (
        <>
            <BrandsView selectedId={brandId} onSelect={selectBrand} />

            <section data-testid={IDS.section} className="mt-16">
                <SectionHeader
                    kicker="Section 6"
                    title="Campaigns"
                    blurb="Every brief in every state, drafts and closed ones included. Expand one to see who is on it."
                    onRefresh={load}
                    refreshTestId={IDS.refresh}
                />

                {brandId && (
                    <button
                        type="button"
                        onClick={() => selectBrand("")}
                        data-testid={BRAND_IDS.clear}
                        className="mt-6 inline-flex items-center gap-2 rounded-full border border-ember-500/40 bg-ember-500/10 px-3 py-1.5 text-xs uppercase tracking-[0.15em] text-ember-500 transition-colors duration-200 hover:bg-ember-500/20"
                    >
                        {selectedBrandName || "Filtered to one brand"}
                        <X className="h-3.5 w-3.5" />
                    </button>
                )}

                <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                    <div className="relative min-w-0 flex-1 sm:min-w-[16rem]">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            data-testid={IDS.search}
                            placeholder="Campaign title"
                            aria-label="Search campaigns"
                            className="h-10 rounded-md border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                        />
                    </div>
                    <FilterSelect
                        label="Any status"
                        value={status}
                        onChange={(v) => {
                            setStatus(v);
                            setPage(1);
                        }}
                        options={STATUS_OPTIONS}
                        testid={IDS.filterStatus}
                    />
                    <DateFilter
                        label="From"
                        value={from}
                        onChange={(d) => {
                            setFrom(d);
                            setPage(1);
                        }}
                        testid={IDS.filterDateFrom}
                    />
                    <DateFilter
                        label="To"
                        value={to}
                        onChange={(d) => {
                            setTo(d);
                            setPage(1);
                        }}
                        testid={IDS.filterDateTo}
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

                <div className="mt-8 rounded-md border border-white/10 bg-card">
                    {!data ? (
                        <ListSkeleton rows={4} testid={IDS.skeleton} />
                    ) : rows.length === 0 ? (
                        <div
                            data-testid={IDS.empty}
                            className="flex items-center gap-4 px-6 py-10 text-sm text-muted-foreground"
                        >
                            <Sparkles className="h-5 w-5 flex-none text-ember-500" />
                            <p>
                                {filtered
                                    ? "No campaign matches those filters."
                                    : "No campaign has been posted yet."}
                            </p>
                        </div>
                    ) : (
                        <ul data-testid={IDS.list} className="divide-y divide-white/10">
                            {rows.map((c) => (
                                <CampaignRow
                                    key={c.id}
                                    campaign={c}
                                    expanded={Boolean(expanded[c.id])}
                                    onToggle={() =>
                                        setExpanded((e) => ({ ...e, [c.id]: !e[c.id] }))
                                    }
                                    onInvite={setInviteFor}
                                />
                            ))}
                        </ul>
                    )}
                </div>

                {data && rows.length > 0 && (
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
                        <p
                            data-testid={IDS.count}
                            className="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                        >
                            {summary}
                        </p>
                        {pages > 1 && (
                            <div
                                data-testid={IDS.pagination}
                                className="flex items-center gap-6"
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
                    </div>
                )}
            </section>

            <InviteCreatorsDialog
                campaign={inviteFor}
                open={Boolean(inviteFor)}
                onOpenChange={(v) => !v && setInviteFor(null)}
                onSent={load}
            />
        </>
    );
}
