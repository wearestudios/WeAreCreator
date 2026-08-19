import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
    MapPin,
    IndianRupee,
    ArrowRight,
    Filter,
    Lock,
    Sparkles,
    Search,
    ArrowDownUp,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import Footer from "@/components/Footer";
import {
    CardGridSkeleton,
    FilterChips,
    ListEmptyState,
    ResultCount,
    StickyBar,
} from "@/components/data/DenseView";
import { STICKY_BAR, VISIBILITY } from "@/constants/testIds";
import { api, formatApiError } from "@/lib/api";
import { formatCompensation, isBarter } from "@/lib/compensation";
import { isPrivate } from "@/lib/visibility";
import ExecutionBadge from "@/components/ExecutionBadge";
import ShareButton from "@/components/ShareButton";
import BrandName from "@/components/BrandName";
import CampaignCover from "@/components/CampaignCover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

const ANY = "__any__";
const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    real_estate: "Real Estate",
    fashion: "Fashion",
    travel: "Travel",
    wellness: "Wellness",
    lifestyle: "Lifestyle",
};

// Editorial budget buckets — always relevant regardless of live data.
// The words for the two enums the filters now cover. The API sends the raw
// value; a creator should not have to read "personal_table".
const TYPE_LABEL = {
    launch: "Launch",
    group_event: "Group event",
    personal_table: "Your own slot",
};
const COMPENSATION_LABEL = {
    fixed: "Fixed fee",
    negotiated: "Negotiable",
    barter: "Barter",
};

const BUDGET_BUCKETS = [
    { value: ANY, label: "Any budget", min: null, max: null },
    { value: "u5", label: "Under ₹5,000", min: null, max: 4999 },
    { value: "5_15", label: "₹5k – ₹15k", min: 5000, max: 15000 },
    { value: "15_50", label: "₹15k – ₹50k", min: 15001, max: 50000 },
    { value: "50p", label: "₹50k+", min: 50001, max: null },
];

// "Most relevant" is the server ranking briefs against this creator's own
// profile — niches, city, neighbourhood. For a profile that matches nothing it
// degrades to newest-first, so the option is never worse than the old default.
const SORT_OPTIONS = [
    { value: "relevant", label: "Most relevant first" },
    { value: "newest", label: "Newest first" },
    { value: "budget_desc", label: "Budget: high to low" },
    { value: "budget_asc", label: "Budget: low to high" },
];

const TagBadge = ({ status }) => {
    const isLive = status === "open";
    return (
        <span
            data-testid={`status-tag-${status}`}
            className={
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                (isLive
                    ? "bg-ember-500/15 text-ember-500"
                    : "border border-white/15 bg-white/5 text-muted-foreground")
            }
        >
            <span
                className={
                    "inline-block h-1.5 w-1.5 rounded-full " +
                    (isLive ? "bg-ember-500 animate-pulse" : "bg-muted-foreground")
                }
            />
            {isLive ? "Live" : "Upcoming"}
        </span>
    );
};

// Told only to people who can already see the brief — for a creator that
// means they were invited, which is worth saying out loud on the card.
const InviteOnlyPill = ({ campaign }) =>
    isPrivate(campaign) ? (
        <span
            data-testid={VISIBILITY.badge(campaign.id)}
            className="inline-flex items-center gap-1.5 rounded-full border border-ember-500/40 bg-ember-500/10 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-ember-500"
        >
            <Lock className="h-3 w-3" />
            Invite-only
        </span>
    ) : null;

const CampaignCard = ({ c, index }) => (
    <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: Math.min(index, 8) * 0.04, ease: [0.22, 1, 0.36, 1] }}
    >
        {/* An <article>, not a <Link>. The brand's name inside it is a link of
            its own now, and an anchor inside an anchor is invalid markup that
            browsers resolve however they like. The card stays clickable
            edge-to-edge through the stretched overlay on the title below —
            one hit area, two destinations, and valid HTML. */}
        <article
            data-testid={`campaign-card-${c.id}`}
            className="group relative flex h-full flex-col overflow-hidden rounded-lg border border-white/10 bg-card/60 transition-all duration-300 hover:-translate-y-0.5 hover:border-ember-500/50 hover:bg-card-elevated"
        >
            {/* editorial accent line */}
            <span className="absolute inset-x-0 top-0 z-10 h-px origin-left scale-x-0 bg-gradient-to-r from-ember-500 via-ember-400 to-transparent transition-transform duration-500 group-hover:scale-x-100" />

            {/* The box is reserved, so a list of twenty briefs does not reflow
                as their covers arrive. */}
            <CampaignCover
                campaign={c}
                rounded="rounded-none"
                className="border-0 border-b"
            />

            <div className="flex flex-1 flex-col p-7">
                <div className="flex items-start justify-between gap-3">
                    <BrandName
                        brand={c}
                        avatarSize="h-7 w-7"
                        lift
                        className="text-xs uppercase tracking-[0.2em] text-muted-foreground"
                    />
                    <span className="flex flex-none items-center gap-1.5">
                        <InviteOnlyPill campaign={c} />
                        <TagBadge status={c.status} />
                    </span>
                </div>

                {/* One line about the brand, under its name. A card carrying
                    only a name makes every unfamiliar business look the same,
                    which is most of them to most creators. Absent when the
                    brand hasn't written one — a blank line would be worse
                    than none. */}
                {c.brand_tagline && (
                    <p
                        data-testid={`campaign-card-tagline-${c.id}`}
                        className="mt-2 line-clamp-1 text-xs leading-relaxed text-muted-foreground/80"
                    >
                        {c.brand_tagline}
                    </p>
                )}

                <h3 className="mt-5 font-serif text-[26px] leading-[1.05] tracking-tight text-foreground">
                    {/* The stretched link: this is the card's click target, and
                        `after:absolute after:inset-0` is what makes it cover
                        the whole card without wrapping anything. */}
                    <Link
                        to={`/campaigns/${c.id}`}
                        data-testid={`campaign-card-open-${c.id}`}
                        className="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    >
                        {c.title}
                    </Link>
                </h3>

                <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                    {c.deliverables}
                </p>

                <div className="mt-6 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {c.area && (
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1">
                            <MapPin className="h-3 w-3" />
                            {c.area}
                        </span>
                    )}
                    {c.category && (
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 uppercase tracking-[0.15em]">
                            {CAT_LABEL[c.category] || c.category}
                        </span>
                    )}
                    {/* Who you'd be dealing with, on the card — it changes whose
                        WhatsApp answers on the day, which is worth knowing before
                        you open the brief, not after you apply. */}
                    <ExecutionBadge campaign={c} audience="creator" />
                </div>

                <div className="mt-auto flex items-end justify-between border-t border-white/10 pt-6">
                    <div>
                        <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            {isBarter(c) ? "What you get" : "Budget / creator"}
                        </div>
                        {/* A barter brief carries whatever budget it was posted
                          * with, so the rupee figure has to be suppressed rather
                          * than trusted — see lib/compensation.js. */}
                        <div className="mt-1 flex items-baseline gap-1 font-serif text-[32px] leading-none text-foreground">
                            {isBarter(c) ? (
                                "Barter"
                            ) : (
                                <>
                                    <IndianRupee className="h-5 w-5 text-ember-500" />
                                    {formatCompensation(c).amount ?? "—"}
                                </>
                            )}
                        </div>
                        {formatCompensation(c).suffix && (
                            <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-ember-500">
                                {formatCompensation(c).suffix}
                            </div>
                        )}
                    </div>
                    <div className="flex flex-none items-center gap-2">
                        {/* A private brief has no public page — /c/{id} 404s
                            by design — so a share button on it would copy a
                            dead link. Absent, not disabled. */}
                        {!isPrivate(c) && (
                            <ShareButton
                                campaignId={c.id}
                                title={c.title}
                                summary={c.deliverables}
                                variant="icon"
                                className="relative z-10"
                            />
                        )}
                        <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-hover:translate-x-1 group-hover:text-ember-500" />
                    </div>
                </div>
            </div>
        </article>
    </motion.div>
);

export default function Campaigns() {
    const [items, setItems] = useState(null);
    const [error, setError] = useState("");
    // Every filter starts at ANY: the page opens showing everything live and
    // the creator narrows from there, rather than being handed a slice
    // somebody else chose.
    const [city, setCity] = useState(ANY);
    const [area, setArea] = useState(ANY);
    const [category, setCategory] = useState(ANY);
    const [campaignType, setCampaignType] = useState(ANY);
    const [compensation, setCompensation] = useState(ANY);
    const [budget, setBudget] = useState(ANY);
    const [sort, setSort] = useState("relevant");
    const [q, setQ] = useState("");
    const [debouncedQ, setDebouncedQ] = useState("");
    const [filters, setFilters] = useState({
        cities: [],
        areas: [],
        categories: [],
        campaign_types: [],
        compensation_types: [],
    });
    const [total, setTotal] = useState(null);

    // Debounce keyword search input.
    useEffect(() => {
        const t = setTimeout(() => setDebouncedQ(q.trim()), 250);
        return () => clearTimeout(t);
    }, [q]);

    // Load filter options once.
    useEffect(() => {
        api.get("/campaigns/filters")
            .then(({ data }) => setFilters(data))
            .catch(() =>
                setFilters({
                    cities: [],
                    areas: [],
                    categories: [],
                    campaign_types: [],
                    compensation_types: [],
                }),
            );
    }, []);

    // Load list whenever filters change.
    useEffect(() => {
        let cancelled = false;
        setItems(null);
        const params = {};
        if (city !== ANY) params.city = city;
        if (area !== ANY) params.area = area;
        if (category !== ANY) params.category = category;
        if (campaignType !== ANY) params.campaign_type = campaignType;
        if (compensation !== ANY) params.compensation_type = compensation;
        const bucket = BUDGET_BUCKETS.find((b) => b.value === budget);
        if (bucket && bucket.min !== null) params.budget_min = bucket.min;
        if (bucket && bucket.max !== null) params.budget_max = bucket.max;
        // "relevant" is the server's default, so it travels as an absence.
        if (sort && sort !== "relevant") params.sort = sort;
        if (debouncedQ) params.q = debouncedQ;
        api.get("/campaigns", { params })
            .then(({ data, headers }) => {
                if (cancelled) return;
                setItems(data);
                // The server says how many matched, which is not the same as
                // how many came back — the list is capped.
                const seen = Number(headers?.["x-total-count"]);
                setTotal(Number.isFinite(seen) ? seen : data.length);
            })
            .catch((err) => {
                if (!cancelled) {
                    setError(formatApiError(err));
                    setItems([]);
                }
            });
        return () => {
            cancelled = true;
        };
    }, [city, area, category, campaignType, compensation, budget, sort, debouncedQ]);

    const hasFilters =
        city !== ANY ||
        campaignType !== ANY ||
        compensation !== ANY ||
        area !== ANY ||
        category !== ANY ||
        budget !== ANY ||
        debouncedQ.length > 0 ||
        sort !== "relevant";

    // One chip per filter that is actually doing something. `sort` is left out
    // on purpose: it changes the order, not the set, so calling it a filter
    // would misdescribe what removing it does.
    const chips = [
        {
            key: "search",
            label: "Search",
            value: debouncedQ,
            onRemove: () => setQ(""),
        },
        {
            key: "city",
            label: "City",
            value: city === ANY ? "" : city,
            onRemove: () => setCity(ANY),
        },
        {
            key: "area",
            label: "Area",
            value: area === ANY ? "" : area,
            onRemove: () => setArea(ANY),
        },
        {
            key: "campaign_type",
            label: "Type",
            value: campaignType === ANY ? "" : TYPE_LABEL[campaignType] || campaignType,
            onRemove: () => setCampaignType(ANY),
        },
        {
            key: "compensation",
            label: "Pays",
            value:
                compensation === ANY
                    ? ""
                    : COMPENSATION_LABEL[compensation] || compensation,
            onRemove: () => setCompensation(ANY),
        },
        {
            key: "category",
            label: "Category",
            value: category === ANY ? "" : CAT_LABEL[category] || category,
            onRemove: () => setCategory(ANY),
        },
        {
            key: "budget",
            label: "Budget",
            value:
                budget === ANY
                    ? ""
                    : (BUDGET_BUCKETS.find((b) => b.value === budget) || {}).label || "",
            onRemove: () => setBudget(ANY),
        },
    ];

    const resetAll = () => {
        setCity(ANY);
        setCampaignType(ANY);
        setCompensation(ANY);
        setArea(ANY);
        setCategory(ANY);
        setBudget(ANY);
        setSort("newest");
        setQ("");
    };

    return (
        <div
            data-testid="campaigns-page"
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-14 md:py-20">
                {/* Masthead */}
                <div className="grid gap-8 md:grid-cols-12 md:items-end">
                    <div className="md:col-span-8">
                        <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                            <span className="h-px w-8 bg-ember-500" />
                            Vol. 01 · Bengaluru · Influencer studio
                        </p>
                        <h1
                            data-testid="campaigns-heading"
                            className="mt-5 font-serif text-fluid-6xl leading-[0.95] tracking-tight"
                        >
                            Paid briefs, <span className="italic">open</span> to apply.
                        </h1>
                        <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground md:text-base">
                            Every campaign here comes from a verified brand with a fixed
                            budget — across F&amp;B, retail, real estate, fashion,
                            travel and hospitality. Tap any card to see the full brief.
                        </p>
                    </div>
                </div>

                {/* Filters bar. Sticky, so the thing you filtered by is still
                    on screen thirty cards down the list. */}
                <StickyBar level="headerFromMd"
                    testid={STICKY_BAR.campaigns}
                    bleed="-mx-6 px-6"
                    className="mt-12"
                >
                <div
                    data-testid="campaigns-filters"
                    className="flex flex-wrap items-center gap-3"
                >
                    <div className="flex items-center gap-2 pl-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        <Filter className="h-3.5 w-3.5" />
                        Filter
                    </div>

                    {/* Keyword search */}
                    <div className="relative w-full flex-1 md:min-w-[220px] md:max-w-[280px]">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            data-testid="filter-search-input"
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder="Search briefs…"
                            className="h-11 md:h-10 border-white/10 bg-background pl-8 focus-visible:ring-ember-500"
                        />
                    </div>

                    <Select value={city} onValueChange={setCity}>
                        <SelectTrigger
                            data-testid="filter-city-trigger"
                            className="h-11 md:h-10 w-full border-white/10 bg-background md:w-40"
                        >
                            <SelectValue placeholder="Any city" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ANY} data-testid="filter-city-any">
                                Any city
                            </SelectItem>
                            {(filters.cities || []).map((c) => (
                                <SelectItem value={c} key={c} data-testid={`filter-city-${c}`}>
                                    {c}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={area} onValueChange={setArea}>
                        <SelectTrigger
                            data-testid="filter-area-trigger"
                            className="h-11 md:h-10 w-full border-white/10 bg-background md:w-44"
                        >
                            <SelectValue placeholder="Any area" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ANY} data-testid="filter-area-any">
                                Any area
                            </SelectItem>
                            {filters.areas.map((a) => (
                                <SelectItem
                                    value={a}
                                    key={a}
                                    data-testid={`filter-area-${a}`}
                                >
                                    {a}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={campaignType} onValueChange={setCampaignType}>
                        <SelectTrigger
                            data-testid="filter-type-trigger"
                            className="h-11 md:h-10 w-full border-white/10 bg-background md:w-40"
                        >
                            <SelectValue placeholder="Any format" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ANY} data-testid="filter-type-any">
                                Any format
                            </SelectItem>
                            {(filters.campaign_types || []).map((t) => (
                                <SelectItem value={t} key={t} data-testid={`filter-type-${t}`}>
                                    {TYPE_LABEL[t] || t}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={compensation} onValueChange={setCompensation}>
                        <SelectTrigger
                            data-testid="filter-compensation-trigger"
                            className="h-11 md:h-10 w-full border-white/10 bg-background md:w-40"
                        >
                            <SelectValue placeholder="Any pay" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ANY} data-testid="filter-compensation-any">
                                Any pay
                            </SelectItem>
                            {(filters.compensation_types || []).map((t) => (
                                <SelectItem
                                    value={t}
                                    key={t}
                                    data-testid={`filter-compensation-${t}`}
                                >
                                    {COMPENSATION_LABEL[t] || t}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={category} onValueChange={setCategory}>
                        <SelectTrigger
                            data-testid="filter-category-trigger"
                            className="h-11 md:h-10 w-full border-white/10 bg-background md:w-40"
                        >
                            <SelectValue placeholder="Any category" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ANY} data-testid="filter-category-any">
                                Any category
                            </SelectItem>
                            {filters.categories.map((c) => (
                                <SelectItem
                                    value={c}
                                    key={c}
                                    data-testid={`filter-category-${c}`}
                                >
                                    {CAT_LABEL[c] || c}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={budget} onValueChange={setBudget}>
                        <SelectTrigger
                            data-testid="filter-budget-trigger"
                            className="h-11 md:h-10 w-full border-white/10 bg-background md:w-44"
                        >
                            <SelectValue placeholder="Any budget" />
                        </SelectTrigger>
                        <SelectContent>
                            {BUDGET_BUCKETS.map((b) => (
                                <SelectItem
                                    value={b.value}
                                    key={b.value}
                                    data-testid={`filter-budget-${b.value}`}
                                >
                                    {b.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={sort} onValueChange={setSort}>
                        <SelectTrigger
                            data-testid="filter-sort-trigger"
                            className="h-11 md:h-10 w-full border-white/10 bg-background md:w-52"
                        >
                            <ArrowDownUp className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {SORT_OPTIONS.map((s) => (
                                <SelectItem
                                    value={s.value}
                                    key={s.value}
                                    data-testid={`filter-sort-${s.value}`}
                                >
                                    {s.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {hasFilters && (
                        <button
                            type="button"
                            onClick={resetAll}
                            data-testid="clear-filters-btn"
                            className="ml-auto rounded-full border border-white/10 bg-transparent px-3 py-1 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                        >
                            Clear all
                        </button>
                    )}
                </div>

                {/* What you are looking at, and why. Both stay in the sticky
                    bar: a count you have to scroll up to read is a count you
                    stop reading. */}
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                    <FilterChips chips={chips} onClearAll={resetAll} />
                    {Array.isArray(items) && (
                        <ResultCount
                            shown={items.length}
                            // The server's count of what matched, which is not
                            // the same as what came back — the list is capped,
                            // and "40 of 137" is the honest way to say so.
                            total={total ?? undefined}
                            noun="campaign"
                            testid="campaigns-count"
                            className="ml-auto"
                        />
                    )}
                </div>
                </StickyBar>

                {/* Grid */}
                <section
                    data-testid="campaigns-grid"
                    className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3"
                >
                    {items === null && (
                        <div className="col-span-full">
                            <CardGridSkeleton
                                cards={6}
                                columns="md:grid-cols-2 lg:grid-cols-3"
                                // The cards carry covers now, and a skeleton
                                // without one shifts the whole grid by the
                                // height of a 16:9 box when they arrive.
                                cover
                                testid="campaigns-skeleton"
                            />
                        </div>
                    )}
                    {Array.isArray(items) && items.length === 0 && (
                        <div className="col-span-full">
                            <ListEmptyState
                                Icon={Sparkles}
                                testid="campaigns-empty"
                                filtered={hasFilters}
                                onClearFilters={resetAll}
                                emptyTitle="No briefs are open right now."
                                emptyBody="Live campaigns from verified brands appear here the moment they are approved. We are onboarding brands now — check back in a day or two."
                                filteredTitle="Nothing matches those filters."
                                filteredBody="Try a wider area, category or budget. New briefs go live every week."
                            />
                        </div>
                    )}
                    {Array.isArray(items) &&
                        items.map((c, i) => <CampaignCard c={c} key={c.id} index={i} />)}
                </section>

                {error && (
                    <p data-testid="campaigns-error" className="mt-6 text-sm text-destructive">
                        {error}
                    </p>
                )}
            </main>

            <Footer />
        </div>
    );
}
