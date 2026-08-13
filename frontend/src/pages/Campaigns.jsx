import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
    Loader2,
    MapPin,
    IndianRupee,
    ArrowRight,
    Filter,
    Sparkles,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
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

const CampaignCard = ({ c }) => (
    <Link
        to={`/campaigns/${c.id}`}
        data-testid={`campaign-card-${c.id}`}
        className="group relative flex flex-col overflow-hidden rounded-md border border-white/10 bg-card p-6 transition-colors duration-200 hover:border-ember-500/50"
    >
        <div className="flex items-start justify-between gap-3">
            <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {c.brand_name || "Brand"}
            </div>
            <TagBadge status={c.status} />
        </div>

        <h3 className="mt-4 font-serif text-2xl leading-tight tracking-tight text-foreground">
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

        <div className="mt-6 flex items-end justify-between border-t border-white/10 pt-5">
            <div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    Budget per creator
                </div>
                <div className="mt-1 flex items-baseline gap-1 font-serif text-3xl text-foreground">
                    <IndianRupee className="h-5 w-5 text-ember-500" />
                    {typeof c.budget_per_creator === "number"
                        ? c.budget_per_creator.toLocaleString("en-IN")
                        : "—"}
                </div>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-hover:translate-x-1 group-hover:text-ember-500" />
        </div>
    </Link>
);

const EmptyState = ({ hasFilters, onReset }) => (
    <div
        data-testid="campaigns-empty"
        className="col-span-full rounded-md border border-dashed border-white/15 bg-card/40 p-14 text-center"
    >
        <Sparkles className="mx-auto h-6 w-6 text-ember-500" />
        <p className="mt-4 font-serif text-2xl">Nothing matches yet.</p>
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
    const [filters, setFilters] = useState({ areas: [], categories: [] });

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
    }, [area, category]);

    const hasFilters = area !== ANY || category !== ANY;
    const totalBudget = useMemo(() => {
        if (!Array.isArray(items) || items.length === 0) return 0;
        return items.reduce(
            (acc, c) =>
                acc + (typeof c.budget_per_creator === "number" ? c.budget_per_creator : 0),
            0,
        );
    }, [items]);

    return (
        <div
            data-testid="campaigns-page"
            className="min-h-screen bg-background text-foreground"
        >
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-14 md:py-20">
                <div className="grid gap-8 md:grid-cols-12 md:items-end">
                    <div className="md:col-span-8">
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            Live campaigns · Bengaluru
                        </p>
                        <h1
                            data-testid="campaigns-heading"
                            className="mt-4 font-serif text-4xl leading-none tracking-tight md:text-5xl"
                        >
                            Paid briefs, open to apply.
                        </h1>
                        <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground">
                            Every campaign here comes from a vetted brand with a fixed
                            budget. Tap any card to see the full brief.
                        </p>
                    </div>
                    {Array.isArray(items) && items.length > 0 && (
                        <div className="md:col-span-4 md:text-right">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                Live pool
                            </div>
                            <div className="mt-1 font-serif text-4xl text-foreground">
                                {formatMoney(totalBudget)}
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                                across {items.length}{" "}
                                {items.length === 1 ? "campaign" : "campaigns"}
                            </div>
                        </div>
                    )}
                </div>

                {/* Filters */}
                <div
                    data-testid="campaigns-filters"
                    className="mt-10 flex flex-wrap items-center gap-3 rounded-md border border-white/10 bg-card/50 p-3"
                >
                    <div className="flex items-center gap-2 pl-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        <Filter className="h-3.5 w-3.5" />
                        Filter
                    </div>
                    <Select value={area} onValueChange={setArea}>
                        <SelectTrigger
                            data-testid="filter-area-trigger"
                            className="h-10 w-full border-white/10 bg-background md:w-56"
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
                            className="h-10 w-full border-white/10 bg-background md:w-56"
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

                    {hasFilters && (
                        <button
                            type="button"
                            onClick={() => {
                                setArea(ANY);
                                setCategory(ANY);
                            }}
                            data-testid="clear-filters-btn"
                            className="ml-auto rounded-full border border-white/10 bg-transparent px-3 py-1 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                        >
                            Clear
                        </button>
                    )}
                </div>

                {/* Grid */}
                <section
                    data-testid="campaigns-grid"
                    className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3"
                >
                    {items === null && (
                        <div className="col-span-full flex justify-center py-16 text-muted-foreground">
                            <Loader2 className="h-5 w-5 animate-spin" />
                        </div>
                    )}
                    {Array.isArray(items) && items.length === 0 && (
                        <EmptyState
                            hasFilters={hasFilters}
                            onReset={() => {
                                setArea(ANY);
                                setCategory(ANY);
                            }}
                        />
                    )}
                    {Array.isArray(items) &&
                        items.map((c) => <CampaignCard c={c} key={c.id} />)}
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
