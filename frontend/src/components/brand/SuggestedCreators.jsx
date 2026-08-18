// "Suggested creators" — the roster, ranked against this brief.
//
// Waiting for applicants means a brief is only seen by whoever happens to be
// browsing. This is the other direction: verified creators scored against the
// campaign, each with the reason in words, and an invite that goes through the
// platform. No contact details come back from the server, so there is nothing
// here to show even if we wanted to.
//
// The score's breakdown is one click away on every card. A brand that cannot
// see why somebody was suggested has been handed an oracle.
import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { notifyError, notifyInfo, notifySuccess } from "@/lib/feedback";
import {
    ChevronDown,
    ExternalLink,
    Instagram,
    Loader2,
    MapPin,
    Send,
    Sparkles,
    Users,
} from "lucide-react";

import { api, formatApiError, mediaUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SUGGESTED_CREATORS as T } from "@/constants/testIds";
import { tierByValue } from "@/lib/followerTiers";

const COMPONENT_LABEL = {
    niche: "Niche match",
    genre: "Genre match",
    city: "In the area",
    reach_fit: "Audience vs budget",
    engagement: "Engagement",
    delivery: "Delivered here before",
};

// The tier names come from `FOLLOWER_TIERS` now — there is no separate
// "nano", and no second spelling of "mid". A panel that labels a band
// differently from the filter that produces it is the split these tiers
// exist to end.
const tierName = (key) => (tierByValue(key) || {}).label || key;

const formatCompact = (n) => {
    if (typeof n !== "number") return null;
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
    if (n >= 1_000) return `${Math.round(n / 1_000)}k`;
    return String(n);
};

const PAGE_SIZE = 12;

function ScoreBreakdown({ row }) {
    const [open, setOpen] = useState(false);
    const entries = Object.entries(row.match_components || {});
    if (!entries.length) return null;

    return (
        <div className="mt-3">
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                className="-my-2 inline-flex min-h-[2.75rem] items-center gap-1 py-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:my-0 md:min-h-0 md:py-0"
            >
                Why this score
                <ChevronDown
                    className={`h-3 w-3 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
                />
            </button>
            {open && (
                <dl
                    data-testid={T.breakdown(row.user_id)}
                    className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 border-l-2 border-white/10 pl-3 text-xs"
                >
                    {entries.map(([key, value]) => (
                        <React.Fragment key={key}>
                            <dt className="text-muted-foreground">
                                {COMPONENT_LABEL[key] || key}
                                {row.unknown_signals?.includes(key) && (
                                    // Not measured is not the same as poor, and the
                                    // score treats them differently — so should the UI.
                                    <span className="ml-1.5 text-muted-foreground/60">
                                        not measured
                                    </span>
                                )}
                            </dt>
                            <dd className="text-right tabular-nums text-foreground/80">
                                {value}
                            </dd>
                        </React.Fragment>
                    ))}
                </dl>
            )}
        </div>
    );
}

export function SuggestedCreators({ campaignId, canInvite = true }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [inviting, setInviting] = useState(() => new Set());
    const [invited, setInvited] = useState(() => new Set());
    const [limit, setLimit] = useState(PAGE_SIZE);
    const [filters, setFilters] = useState({
        city: "",
        niche: "",
        min_followers: "",
        max_followers: "",
    });
    const [applied, setApplied] = useState(filters);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = { limit, offset: 0 };
            Object.entries(applied).forEach(([k, v]) => {
                if (String(v).trim() !== "") params[k] = v;
            });
            const { data: body } = await api.get(
                `/brand/campaigns/${campaignId}/suggested-creators`,
                { params },
            );
            setData(body);
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setLoading(false);
        }
    }, [campaignId, applied, limit]);

    useEffect(() => {
        load();
    }, [load]);

    const invite = async (row) => {
        if (inviting.has(row.user_id)) return;
        // A Set in state, not a ref: a ref doesn't re-render, so the button
        // would never show that it was working.
        setInviting((s) => new Set(s).add(row.user_id));
        try {
            const { data: result } = await api.post(
                `/brand/campaigns/${campaignId}/invite`,
                { creator_ids: [row.user_id] },
            );
            const outcome = result?.results?.[0];
            if (outcome?.status === "invited") {
                notifySuccess(`Invited ${row.name || "creator"}`);
            } else if (outcome?.status === "already_invited") {
                notifyInfo(outcome.reason);
            } else {
                // A partial send is reported, not swallowed: the invitation row
                // exists either way and can be retried.
                notifyError(outcome?.reason || "Couldn't send that invite.");
            }
            if (outcome?.status !== "failed") {
                setInvited((s) => new Set(s).add(row.user_id));
            }
        } catch (err) {
            notifyError(err);
        } finally {
            setInviting((s) => {
                const next = new Set(s);
                next.delete(row.user_id);
                return next;
            });
        }
    };

    const rows = data?.suggestions || [];
    const tier = data?.budget_tier;

    return (
        <section
            data-testid={T.section}
            className="border-t border-white/10 py-12 md:py-16"
        >
            <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Go and ask
                    </div>
                    <h2
                        data-testid={T.heading}
                        className="mt-2 font-serif text-fluid-4xl tracking-tight"
                    >
                        Suggested creators
                    </h2>
                    <p
                        data-testid={T.explainer}
                        className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground"
                    >
                        Verified creators ranked against this brief — what they cover, where
                        they are, how their audience fits the budget, and whether they've
                        delivered here before. Anyone who already applied or has been invited
                        is left out.
                    </p>
                </div>
                {tier?.label && (
                    <div
                        data-testid={T.tier}
                        className="rounded-md border border-white/10 bg-background/40 px-4 py-3 text-xs text-muted-foreground"
                    >
                        <div className="text-[10px] uppercase tracking-[0.2em]">
                            {/* Whether the brand told us, or we read it off
                                the fee. One of those is worth arguing with;
                                the other is worth correcting on the profile,
                                and a brand can only tell if we say which. */}
                            {tier.stated ? "You're looking for" : "This budget suits"}
                        </div>
                        <div className="mt-1 text-foreground/85">
                            {tierName(tier.label)} creators
                            {typeof tier.min_followers === "number" && (
                                <>
                                    {" "}
                                    · {formatCompact(tier.min_followers)}
                                    {tier.max_followers
                                        ? `–${formatCompact(tier.max_followers)}`
                                        : "+"}{" "}
                                    followers
                                </>
                            )}
                        </div>
                    </div>
                )}
            </div>

            <form
                data-testid={T.filters}
                onSubmit={(e) => {
                    e.preventDefault();
                    setLimit(PAGE_SIZE);
                    setApplied(filters);
                }}
                className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5"
            >
                <div className="flex flex-col gap-1.5">
                    <Label htmlFor="sc-city" className="text-[10px] uppercase tracking-[0.2em]">
                        City
                    </Label>
                    <Input
                        id="sc-city"
                        value={filters.city}
                        onChange={(e) => setFilters((f) => ({ ...f, city: e.target.value }))}
                        placeholder="Any"
                        data-testid={T.filterCity}
                    />
                </div>
                <div className="flex flex-col gap-1.5">
                    <Label htmlFor="sc-niche" className="text-[10px] uppercase tracking-[0.2em]">
                        Niche
                    </Label>
                    <Input
                        id="sc-niche"
                        value={filters.niche}
                        onChange={(e) => setFilters((f) => ({ ...f, niche: e.target.value }))}
                        placeholder="Any"
                        data-testid={T.filterNiche}
                    />
                </div>
                <div className="flex flex-col gap-1.5">
                    <Label htmlFor="sc-min" className="text-[10px] uppercase tracking-[0.2em]">
                        Followers from
                    </Label>
                    <Input
                        id="sc-min"
                        type="number"
                        min="0"
                        value={filters.min_followers}
                        onChange={(e) =>
                            setFilters((f) => ({ ...f, min_followers: e.target.value }))
                        }
                        placeholder="0"
                        data-testid={T.filterMinFollowers}
                    />
                </div>
                <div className="flex flex-col gap-1.5">
                    <Label htmlFor="sc-max" className="text-[10px] uppercase tracking-[0.2em]">
                        Followers to
                    </Label>
                    <Input
                        id="sc-max"
                        type="number"
                        min="0"
                        value={filters.max_followers}
                        onChange={(e) =>
                            setFilters((f) => ({ ...f, max_followers: e.target.value }))
                        }
                        placeholder="Any"
                        data-testid={T.filterMaxFollowers}
                    />
                </div>
                <div className="flex items-end gap-2">
                    <Button type="submit" data-testid={T.filterApply}>
                        Apply
                    </Button>
                    <Button
                        type="button"
                        variant="ghost"
                        data-testid={T.filterClear}
                        onClick={() => {
                            const cleared = {
                                city: "",
                                niche: "",
                                min_followers: "",
                                max_followers: "",
                            };
                            setFilters(cleared);
                            setApplied(cleared);
                            setLimit(PAGE_SIZE);
                        }}
                    >
                        Clear
                    </Button>
                </div>
            </form>

            {error ? (
                <p data-testid={T.error} className="mt-8 text-sm text-amber-300">
                    {error}
                </p>
            ) : loading && !data ? (
                <div
                    data-testid={T.loading}
                    className="mt-8 flex items-center gap-2 text-sm text-muted-foreground"
                >
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Ranking the roster…
                </div>
            ) : rows.length === 0 ? (
                <p
                    data-testid={T.empty}
                    className="mt-8 max-w-xl text-sm leading-relaxed text-muted-foreground"
                >
                    Nobody left to suggest for this brief. Either everyone who fits has
                    already applied or been invited, or the filters are narrower than the
                    roster.
                </p>
            ) : (
                <>
                    <ul
                        data-testid={T.list}
                        // items-start so opening one card's breakdown doesn't
                        // stretch its whole row into dead space.
                        className="mt-8 grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3"
                    >
                        {rows.map((row) => {
                            const busy = inviting.has(row.user_id);
                            const done = invited.has(row.user_id);
                            return (
                                <li
                                    key={row.user_id}
                                    data-testid={T.card(row.user_id)}
                                    className="flex flex-col gap-4 rounded-lg border border-white/10 bg-card p-5 grain-surface"
                                >
                                    <div className="flex items-start gap-3">
                                        {row.profile_image_url ? (
                                            <img
                                                src={mediaUrl(row.profile_image_url)}
                                                alt=""
                                                loading="lazy"
                                                className="aspect-square h-11 w-11 flex-none rounded-full border border-white/10 object-cover"
                                            />
                                        ) : (
                                            <span className="h-11 w-11 flex-none rounded-full border border-white/10 bg-white/5" />
                                        )}
                                        <div className="min-w-0 flex-1">
                                            <div className="font-serif text-xl leading-tight">
                                                {row.name || "Creator"}
                                            </div>
                                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                                {row.instagram_handle && (
                                                    <a
                                                        href={
                                                            row.instagram_profile_url ||
                                                            `https://instagram.com/${row.instagram_handle}`
                                                        }
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        className="inline-flex items-center gap-1 transition-colors duration-200 hover:text-ember-500"
                                                    >
                                                        <Instagram className="h-3 w-3" />@
                                                        {row.instagram_handle}
                                                        <ExternalLink className="h-2.5 w-2.5" />
                                                    </a>
                                                )}
                                                {typeof row.follower_count === "number" && (
                                                    <span className="inline-flex items-center gap-1">
                                                        <Users className="h-3 w-3" />
                                                        {formatCompact(row.follower_count)}
                                                        {row.follower_count_verified && (
                                                            <span
                                                                className="text-ember-500"
                                                                title="Verified via Instagram"
                                                            >
                                                                ✓
                                                            </span>
                                                        )}
                                                    </span>
                                                )}
                                                {row.city && (
                                                    <span className="inline-flex items-center gap-1">
                                                        <MapPin className="h-3 w-3" />
                                                        {row.city}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div
                                            data-testid={T.score(row.user_id)}
                                            className="flex-none text-right"
                                            title="Match score out of 100"
                                        >
                                            <div className="inline-flex items-baseline gap-0.5 font-serif text-2xl text-ember-500">
                                                <Sparkles className="h-3.5 w-3.5" />
                                                {Math.round(row.match_score)}
                                            </div>
                                        </div>
                                    </div>

                                    <p
                                        data-testid={T.reason(row.user_id)}
                                        className="text-sm leading-relaxed text-foreground/85"
                                    >
                                        {row.match_reason}
                                    </p>

                                    <ScoreBreakdown row={row} />

                                    {canInvite && (
                                        <div className="mt-auto pt-2">
                                            <Button
                                                type="button"
                                                size="sm"
                                                variant={done ? "ghost" : "default"}
                                                disabled={busy || done}
                                                onClick={() => invite(row)}
                                                data-testid={T.invite(row.user_id)}
                                                className="w-full"
                                            >
                                                {busy ? (
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                ) : (
                                                    <Send className="h-4 w-4" />
                                                )}
                                                {done ? "Invited" : "Invite"}
                                            </Button>
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ul>

                    {data?.has_more && (
                        <div className="mt-8 flex justify-center">
                            <Button
                                type="button"
                                variant="outline"
                                data-testid={T.more}
                                disabled={loading}
                                onClick={() => setLimit((n) => n + PAGE_SIZE)}
                            >
                                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                                Show more
                            </Button>
                        </div>
                    )}
                </>
            )}
        </section>
    );
}

export default SuggestedCreators;
