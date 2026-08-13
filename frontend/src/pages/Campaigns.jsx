import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
    Loader2,
    MapPin,
    IndianRupee,
    ArrowRight,
    Filter,
    Sparkles,
    Search,
    ArrowDownUp,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";
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
    lifestyle: "Lifestyle",
};

// Editorial budget buckets — always relevant regardless of live data.
const BUDGET_BUCKETS = [
    { value: ANY, label: "Any budget", min: null, max: null },
    { value: "u5", label: "Under ₹5,000", min: null, max: 4999 },
    { value: "5_15", label: "₹5k – ₹15k", min: 5000, max: 15000 },
    { value: "15_50", label: "₹15k – ₹50k", min: 15001, max: 50000 },
    { value: "50p", label: "₹50k+", min: 50001, max: null },
];

const SORT_OPTIONS = [
    { value: "newest", label: "Newest first" },
    { value: "budget_desc", label: "Budget: high to low" },
    { value: "budget_asc", label: "Budget: low to high" },
];

const formatMoney = (n) =>
    typeof n === "number"
        ? "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 })
        : "—";

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

const CampaignCard = ({ c, index }) => (
    <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: Math.min(index, 8) * 0.04, ease: [0.22, 1, 0.36, 1] }}
    >
        <Link
            to={`/campaigns/${c.id}`}
            data-testid={`campaign-card-${c.id}`}
            className="group relative flex h-full flex-col overflow-hidden rounded-lg border border-white/10 bg-card/60 p-7 transition-all duration-300 hover:-translate-y-0.5 hover:border-ember-500/50 hover:bg-card hover:shadow-[0_20px_60px_-30px_rgba(240,93,20,0.4)]"
        >
            {/* editorial accent line */}
            <span className="absolute inset-x-0 top-0 h-px origin-left scale-x-0 bg-gradient-to-r from-ember-500 via-ember-400 to-transparent transition-transform duration-500 group-hover:scale-x-100" />

            <div className="flex items-start justify-between gap-3">
                <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    {c.brand_name || "Brand"}
                </div>
                <TagBadge status={c.status} />
            </div>

            <h3 className="mt-5 font-serif text-[26px] leading-[1.05] tracking-tight text-foreground">
                {c.title}
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
            </div>

            <div className="mt-auto flex items-end justify-between border-t border-white/10 pt-6">
                <div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Budget / creator
                    </div>
                    <div className="mt-1 flex items-baseline gap-1 font-serif text-[32px] leading-none text-foreground">
                        <IndianRupee className="h-5 w-5 text-ember-500" />
                        {typeof c.budget_per_creator === "number"
                            ? c.budget_per_creator.toLocaleString("en-IN")
                            : "—"}
                    </div>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-hover:translate-x-1 group-hover:text-ember-500" />
            </div>
        </Link>
    </motion.div>
);

const EmptyState = ({ hasFilters, onReset }) => (
    <div
        data-testid="campaigns-empty"
        className="col-span-full rounded-lg border border-dashed border-white/15 bg-card/40 p-14 text-center"
    >
        <Sparkles className="mx-auto h-6 w-6 text-ember-500" />
        <p className="mt-5 font-serif text-3xl">Nothing matches yet.</p>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">
            {hasFilters
                ? "Try widening your filters. New briefs go live every week."
                : "We're onboarding brands right now. Check back in a day or two."}
        </p>
        {hasFilters && (
            <Button
                variant="outline"
                onClick={onReset}
                className="mt-6 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                data-testid="campaigns-reset-filters"
            >
                Reset filters
            </Button>
        )}
    </div>
);

export default function Campaigns() {
    const [items, setItems] = useState(null);
    const [error, setError] = useState("");
    const [area, setArea] = useState(ANY);
    const [category, setCategory] = useState(ANY);
    const [budget, setBudget] = useState(ANY);
    const [sort, setSort] = useState("newest");
    const [q, setQ] = useState("");
    const [debouncedQ, setDebouncedQ] = useState("");
    const [filters, setFilters] = useState({ areas: [], categories: [] });

    // Debounce keyword search input.
    useEffect(() => {
        const t = setTimeout(() => setDebouncedQ(q.trim()), 250);
        return () => clearTimeout(t);
    }, [q]);

    // Load filter options once.
    useEffect(() => {
        api.get("/campaigns/filters")
            .then(({ data }) => setFilters(data))
            .catch(() => setFilters({ areas: [], categories: [] }));
    }, []);

    // Load list whenever filters change.
    useEffect(() => {
        let cancelled = false;
        setItems(null);
        const params = {};
        if (area !== ANY) params.area = area;
        if (category !== ANY) params.category = category;
        const bucket = BUDGET_BUCKETS.find((b) => b.value === budget);
        if (bucket && bucket.min !== null) params.budget_min = bucket.min;
        if (bucket && bucket.max !== null) params.budget_max = bucket.max;
        if (sort && sort !== "newest") params.sort = sort;
        if (debouncedQ) params.q = debouncedQ;
        api.get("/campaigns", { params })
            .then(({ data }) => {
                if (!cancelled) setItems(data);
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
    }, [area, category, budget, sort, debouncedQ]);

    const hasFilters =
        area !== ANY ||
        category !== ANY ||
        budget !== ANY ||
        debouncedQ.length > 0 ||
        sort !== "newest";

    const totalBudget = useMemo(() => {
        if (!Array.isArray(items) || items.length === 0) return 0;
        return items.reduce(
            (acc, c) =>
                acc + (typeof c.budget_per_creator === "number" ? c.budget_per_creator : 0),
            0,
        );
    }, [items]);

    const resetAll = () => {
        setArea(ANY);
        setCategory(ANY);
        setBudget(ANY);
        setSort("newest");
        setQ("");
    };

    return (
        <div
            data-testid="campaigns-page"
            className="min-h-screen bg-background text-foreground"
        >
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-14 md:py-20">
                {/* Masthead */}
                <div className="grid gap-8 md:grid-cols-12 md:items-end">
                    <div className="md:col-span-8">
                        <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                            <span className="h-px w-8 bg-ember-500" />
                            Vol. 01 · Bengaluru
                        </p>
                        <h1
                            data-testid="campaigns-heading"
                            className="mt-5 font-serif text-5xl leading-[0.95] tracking-tight md:text-6xl"
                        >
                            Paid briefs, <span className="italic">open</span> to apply.
                        </h1>
                        <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground md:text-base">
                            Every campaign here comes from a vetted brand with a fixed
                            budget. Tap any card to see the full brief.
                        </p>
                    </div>
                    {Array.isArray(items) && items.length > 0 && (
                        <div className="md:col-span-4 md:text-right">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                Live pool
                            </div>
                            <div className="mt-1 font-serif text-5xl leading-none text-foreground">
                                {formatMoney(totalBudget)}
                            </div>
                            <div className="mt-2 text-xs text-muted-foreground">
                                across {items.length}{" "}
                                {items.length === 1 ? "campaign" : "campaigns"}
                            </div>
                        </div>
                    )}
                </div>

                {/* Filters bar */}
                <div
                    data-testid="campaigns-filters"
                    className="mt-12 flex flex-wrap items-center gap-3 rounded-lg border border-white/10 bg-card/50 p-3 backdrop-blur"
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
                            className="h-10 border-white/10 bg-background pl-8 focus-visible:ring-ember-500"
                        />
                    </div>

                    <Select value={area} onValueChange={setArea}>
                        <SelectTrigger
                            data-testid="filter-area-trigger"
                            className="h-10 w-full border-white/10 bg-background md:w-44"
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

                    <Select value={category} onValueChange={setCategory}>
                        <SelectTrigger
                            data-testid="filter-category-trigger"
                            className="h-10 w-full border-white/10 bg-background md:w-40"
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
                            className="h-10 w-full border-white/10 bg-background md:w-44"
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
                            className="h-10 w-full border-white/10 bg-background md:w-52"
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

                {/* Grid */}
                <section
                    data-testid="campaigns-grid"
                    className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3"
                >
                    {items === null && (
                        <div className="col-span-full flex justify-center py-16 text-muted-foreground">
                            <Loader2 className="h-5 w-5 animate-spin" />
                        </div>
                    )}
                    {Array.isArray(items) && items.length === 0 && (
                        <EmptyState hasFilters={hasFilters} onReset={resetAll} />
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
        </div>
    );
}
