import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
    Loader2,
    Users,
    MapPin,
    Instagram,
    Filter,
    Search,
    ArrowDownUp,
    IndianRupee,
    Sparkles,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError, mediaUrl } from "@/lib/api";
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

const FOLLOWER_BUCKETS = [
    { value: ANY, label: "Any following", min: null },
    { value: "10k", label: "10k+ followers", min: 10000 },
    { value: "50k", label: "50k+ followers", min: 50000 },
    { value: "100k", label: "100k+ followers", min: 100000 },
    { value: "500k", label: "500k+ followers", min: 500000 },
];

const SORT_OPTIONS = [
    { value: "newest", label: "Newest first" },
    { value: "followers_desc", label: "Followers: high to low" },
    { value: "rate_asc", label: "Base rate: low to high" },
];

const compactCount = (n) => {
    if (typeof n !== "number") return "—";
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}k`;
    return String(n);
};

const formatMoney = (n) =>
    typeof n === "number"
        ? "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 })
        : "—";

const CreatorCard = ({ c, index }) => {
    const handle = c.instagram_handle
        ? c.instagram_handle.startsWith("@")
            ? c.instagram_handle
            : `@${c.instagram_handle}`
        : null;
    return (
        <motion.article
            data-testid={`creator-card-${c.id}`}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
                duration: 0.5,
                delay: Math.min(index, 10) * 0.03,
                ease: [0.22, 1, 0.36, 1],
            }}
            className="group relative flex h-full flex-col overflow-hidden rounded-lg border border-white/10 bg-card/60 p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-ember-500/50 hover:bg-card hover:shadow-[0_20px_60px_-30px_rgba(240,93,20,0.4)]"
        >
            <span className="absolute inset-x-0 top-0 h-px origin-left scale-x-0 bg-gradient-to-r from-ember-500 via-ember-400 to-transparent transition-transform duration-500 group-hover:scale-x-100" />

            <div className="flex items-start gap-4">
                {/* The initial is the fallback, not the default — a real photo
                    is what a brand actually wants to see here. */}
                <div className="grid h-14 w-14 flex-none place-items-center overflow-hidden rounded-full border border-white/10 bg-ember-500/10 font-serif text-2xl text-ember-500">
                    {c.profile_image_url ? (
                        <img
                            src={mediaUrl(c.profile_image_url)}
                            alt=""
                            data-testid={`creator-photo-${c.id}`}
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        (c.name || "?").slice(0, 1).toUpperCase()
                    )}
                </div>
                <div className="min-w-0 flex-1">
                    <h3 className="truncate font-serif text-[22px] leading-tight tracking-tight">
                        {c.name || "Unnamed creator"}
                    </h3>
                    {handle && (
                        <a
                            href={
                                c.instagram_profile_url ||
                                `https://instagram.com/${handle.replace("@", "")}`
                            }
                            target="_blank"
                            rel="noreferrer"
                            data-testid={`creator-ig-${c.id}`}
                            className="mt-1 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-ember-500"
                        >
                            <Instagram className="h-3.5 w-3.5" />
                            {handle}
                        </a>
                    )}
                </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
                {c.city && (
                    <span
                        data-testid={`creator-city-${c.id}`}
                        className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-muted-foreground"
                    >
                        <MapPin className="h-3 w-3" />
                        {c.city}
                    </span>
                )}
                {(c.niches || []).slice(0, 3).map((n) => (
                    <span
                        key={n}
                        className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs uppercase tracking-[0.14em] text-muted-foreground"
                    >
                        {n}
                    </span>
                ))}
                {(c.niches || []).length > 3 && (
                    <span className="text-xs text-muted-foreground">
                        +{c.niches.length - 3}
                    </span>
                )}
            </div>

            <div className="mt-6 grid grid-cols-2 gap-4 border-t border-white/10 pt-5">
                <div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Followers
                    </div>
                    <div className="mt-1 font-serif text-2xl text-foreground">
                        {compactCount(c.follower_count)}
                    </div>
                </div>
                <div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Base rate
                    </div>
                    <div className="mt-1 flex items-baseline gap-1 font-serif text-2xl text-foreground">
                        {typeof c.base_rate === "number" ? (
                            <>
                                <IndianRupee className="h-4 w-4 text-ember-500" />
                                {c.base_rate.toLocaleString("en-IN")}
                            </>
                        ) : (
                            <span className="text-muted-foreground">—</span>
                        )}
                    </div>
                </div>
            </div>
        </motion.article>
    );
};

const EmptyState = ({ hasFilters, onReset }) => (
    <div
        data-testid="directory-empty"
        className="col-span-full rounded-lg border border-dashed border-white/15 bg-card/40 p-14 text-center"
    >
        <Sparkles className="mx-auto h-6 w-6 text-ember-500" />
        <p className="mt-5 font-serif text-3xl">
            No creators match that yet.
        </p>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">
            {hasFilters
                ? "Try widening your filters. We're verifying new creators across every city every week."
                : "Our team is onboarding creators right now. Please check back soon."}
        </p>
        {hasFilters && (
            <Button
                variant="outline"
                onClick={onReset}
                data-testid="directory-reset-btn"
                className="mt-6 rounded-full border-white/15 bg-transparent hover:bg-white/5"
            >
                Reset filters
            </Button>
        )}
    </div>
);

export default function BrandCreatorDirectory() {
    const [items, setItems] = useState(null);
    const [error, setError] = useState("");
    const [filters, setFilters] = useState({ cities: [], niches: [], total: 0 });
    const [city, setCity] = useState(ANY);
    const [niche, setNiche] = useState(ANY);
    const [followers, setFollowers] = useState(ANY);
    const [sort, setSort] = useState("newest");
    const [q, setQ] = useState("");
    const [debouncedQ, setDebouncedQ] = useState("");

    useEffect(() => {
        const t = setTimeout(() => setDebouncedQ(q.trim()), 250);
        return () => clearTimeout(t);
    }, [q]);

    useEffect(() => {
        api.get("/brand/creators/filters")
            .then(({ data }) => setFilters(data))
            .catch(() => setFilters({ cities: [], niches: [], total: 0 }));
    }, []);

    useEffect(() => {
        let cancelled = false;
        setItems(null);
        const params = {};
        if (city !== ANY) params.city = city;
        if (niche !== ANY) params.niche = niche;
        const bucket = FOLLOWER_BUCKETS.find((b) => b.value === followers);
        if (bucket && bucket.min !== null) params.min_followers = bucket.min;
        if (sort && sort !== "newest") params.sort = sort;
        if (debouncedQ) params.q = debouncedQ;
        api.get("/brand/creators", { params })
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
    }, [city, niche, followers, sort, debouncedQ]);

    const hasFilters =
        city !== ANY ||
        niche !== ANY ||
        followers !== ANY ||
        sort !== "newest" ||
        debouncedQ.length > 0;

    const totalReach = useMemo(() => {
        if (!Array.isArray(items) || items.length === 0) return 0;
        return items.reduce(
            (acc, c) =>
                acc + (typeof c.follower_count === "number" ? c.follower_count : 0),
            0,
        );
    }, [items]);

    const resetAll = () => {
        setCity(ANY);
        setNiche(ANY);
        setFollowers(ANY);
        setSort("newest");
        setQ("");
    };

    return (
        <div
            data-testid="brand-directory-page"
            className="min-h-screen bg-background text-foreground"
        >
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-14 md:py-20">
                {/* Masthead */}
                <div className="grid gap-8 md:grid-cols-12 md:items-end">
                    <div className="md:col-span-8">
                        <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                            <span className="h-px w-8 bg-ember-500" />
                            Creator directory · India
                        </p>
                        <h1
                            data-testid="directory-heading"
                            className="mt-5 font-serif text-5xl leading-[0.95] tracking-tight md:text-6xl"
                        >
                            Every verified creator,{" "}
                            <span className="italic">by city</span>.
                        </h1>
                        <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground md:text-base">
                            Filter by city, niche or following to shortlist creators
                            for your next campaign. Launching in Mumbai? Filter Mumbai.
                            Opening in Goa? Filter Goa.
                        </p>
                    </div>
                    {Array.isArray(items) && items.length > 0 && (
                        <div className="md:col-span-4 md:text-right">
                            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                Reach on this list
                            </div>
                            <div className="mt-1 font-serif text-5xl leading-none text-foreground">
                                {compactCount(totalReach)}
                            </div>
                            <div className="mt-2 text-xs text-muted-foreground">
                                across {items.length}{" "}
                                {items.length === 1 ? "creator" : "creators"}
                            </div>
                        </div>
                    )}
                </div>

                {/* Cities strip — one-tap city filter */}
                {filters.cities.length > 0 && (
                    <div
                        data-testid="directory-cities-strip"
                        className="mt-10 flex flex-wrap items-center gap-2"
                    >
                        <span className="mr-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            <Users className="mr-1.5 inline h-3.5 w-3.5" />
                            Popular
                        </span>
                        <button
                            data-testid="city-chip-any"
                            onClick={() => setCity(ANY)}
                            aria-pressed={city === ANY}
                            className={
                                "rounded-full border px-3 py-1.5 text-xs uppercase tracking-[0.14em] transition-colors duration-200 " +
                                (city === ANY
                                    ? "border-ember-500 bg-ember-500/15 text-ember-500"
                                    : "border-white/10 bg-white/[0.02] text-muted-foreground hover:border-ember-500/40 hover:text-foreground")
                            }
                        >
                            All cities
                        </button>
                        {filters.cities.map((cty) => (
                            <button
                                key={cty}
                                data-testid={`city-chip-${cty}`}
                                onClick={() => setCity(cty)}
                                aria-pressed={city === cty}
                                className={
                                    "rounded-full border px-3 py-1.5 text-xs uppercase tracking-[0.14em] transition-colors duration-200 " +
                                    (city === cty
                                        ? "border-ember-500 bg-ember-500/15 text-ember-500"
                                        : "border-white/10 bg-white/[0.02] text-muted-foreground hover:border-ember-500/40 hover:text-foreground")
                                }
                            >
                                {cty}
                            </button>
                        ))}
                    </div>
                )}

                {/* Filters bar */}
                <div
                    data-testid="directory-filters"
                    className="mt-6 flex flex-wrap items-center gap-3 rounded-lg border border-white/10 bg-card/50 p-3 backdrop-blur"
                >
                    <div className="flex items-center gap-2 pl-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        <Filter className="h-3.5 w-3.5" />
                        Refine
                    </div>

                    <div className="relative w-full flex-1 md:min-w-[220px] md:max-w-[280px]">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            data-testid="directory-search-input"
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder="Search name, handle, niche…"
                            className="h-10 border-white/10 bg-background pl-8 focus-visible:ring-ember-500"
                        />
                    </div>

                    <Select value={niche} onValueChange={setNiche}>
                        <SelectTrigger
                            data-testid="directory-niche-trigger"
                            className="h-10 w-full border-white/10 bg-background md:w-44"
                        >
                            <SelectValue placeholder="Any niche" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ANY}>Any niche</SelectItem>
                            {filters.niches.map((n) => (
                                <SelectItem
                                    key={n}
                                    value={n}
                                    data-testid={`directory-niche-${n}`}
                                >
                                    {n}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={followers} onValueChange={setFollowers}>
                        <SelectTrigger
                            data-testid="directory-followers-trigger"
                            className="h-10 w-full border-white/10 bg-background md:w-48"
                        >
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {FOLLOWER_BUCKETS.map((b) => (
                                <SelectItem
                                    key={b.value}
                                    value={b.value}
                                    data-testid={`directory-followers-${b.value}`}
                                >
                                    {b.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={sort} onValueChange={setSort}>
                        <SelectTrigger
                            data-testid="directory-sort-trigger"
                            className="h-10 w-full border-white/10 bg-background md:w-52"
                        >
                            <ArrowDownUp className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {SORT_OPTIONS.map((s) => (
                                <SelectItem
                                    key={s.value}
                                    value={s.value}
                                    data-testid={`directory-sort-${s.value}`}
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
                            data-testid="directory-clear-btn"
                            className="ml-auto rounded-full border border-white/10 bg-transparent px-3 py-1 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                        >
                            Clear all
                        </button>
                    )}
                </div>

                {/* Grid */}
                <section
                    data-testid="directory-grid"
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
                        items.map((c, i) => <CreatorCard c={c} key={c.id} index={i} />)}
                </section>

                {error && (
                    <p
                        data-testid="directory-error"
                        className="mt-6 text-sm text-destructive"
                    >
                        {error}
                    </p>
                )}
            </main>
        </div>
    );
}
