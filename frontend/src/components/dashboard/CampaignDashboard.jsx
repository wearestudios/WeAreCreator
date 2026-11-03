// A campaign's results, for the brand that ran it — and the same screen for
// an admin looking at any campaign.
//
// The order is the order a business owner asks in: how many people saw it
// (one very large number), who did the work and whether everybody posted,
// what people did with it, how it built up, who drove it, and every post.
// Everything is read from `GET /brand/campaigns/{id}/analytics`'s
// `dashboard` block; nothing here works out a total for itself.
//
// **Indian grouping everywhere** (`formatIN`), short forms only on the chart
// axes and end labels, tabular figures throughout. **Motion once per load**:
// the entrance classes go on the first render only, so the five-minute
// background refresh updates the numbers in place and never replays it.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDownRight, ArrowLeft, ArrowUpRight, Download, Layers, Play } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { downloadCsv } from "@/lib/download";
import { formatIN, formatPercent } from "@/lib/indianNumber";
import { formatDate, timeAgo } from "@/lib/time";
import { Button } from "@/components/ui/button";
import { DASHBOARD as IDS } from "@/constants/testIds";

import SummaryLine from "./SummaryLine";
import { useCountUp } from "./useCountUp";
import {
    ChartCard,
    ViewsByCreator,
    ViewsByCreatorTable,
    ViewsOverTime,
    ViewsOverTimeTable,
} from "./charts";

const REFRESH_MS = 5 * 60 * 1000;
const FORMAT_LABEL = { reel: "Reels", carousel: "Carousels", image: "Photos", story: "Stories", post: "Posts" };

const rise = (animate, i) =>
    animate ? { className: "dash-rise", style: { "--i": i } } : { className: "", style: undefined };

function Count({ value, format = formatIN, animate, className = "", testid }) {
    const ref = useCountUp(value, format, { animate });
    return (
        <span ref={ref} data-testid={testid} className={`tabular-nums ${className}`}>
            {format(value)}
        </span>
    );
}

function Card({ children, className = "", animate, index, testid }) {
    const r = rise(animate, index);
    return (
        <section
            data-testid={testid}
            className={`rounded-lg border border-border bg-card p-card-sm md:p-card ${r.className} ${className}`}
            style={r.style}
        >
            {children}
        </section>
    );
}

function Delta({ block }) {
    if (!block || block.change_percent === null || block.change_percent === undefined) return null;
    const up = block.change_percent >= 0;
    const Icon = up ? ArrowUpRight : ArrowDownRight;
    return (
        <p data-testid={IDS.delta} className="mt-3 inline-flex items-center gap-1.5 text-meta">
            <Icon className={`h-4 w-4 ${up ? "text-state-good" : "text-state-danger"}`} aria-hidden />
            <span className="tabular-nums font-medium">
                {up ? "+" : ""}
                {formatPercent(block.change_percent)}
            </span>
            <span className="text-muted-foreground">
                vs your last campaign{block.title ? `, ${block.title}` : ""}
            </span>
        </p>
    );
}

function FormatSplit({ formats, total }) {
    if (!formats?.length) return null;
    return (
        <div data-testid={IDS.split} className="mt-6">
            <div className="flex h-2 overflow-hidden rounded-pill bg-muted" aria-hidden>
                {formats.map((f, i) => (
                    <span
                        key={f.format}
                        className="block h-full bg-primary"
                        style={{ width: `${total ? ((f.views || 0) / total) * 100 : 0}%`, opacity: 1 - i * 0.35 }}
                    />
                ))}
            </div>
            <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-meta">
                {formats.map((f) => (
                    <div key={f.format} className="flex items-baseline gap-2">
                        <dt className="text-muted-foreground">
                            {FORMAT_LABEL[f.format] || f.format} · {f.posts}
                        </dt>
                        <dd className="font-medium tabular-nums">{formatIN(f.views)}</dd>
                    </div>
                ))}
            </dl>
        </div>
    );
}

function Tile({ id, label, sublabel, value, animate, index, wide = false }) {
    const r = rise(animate, index);
    return (
        <div
            data-testid={IDS.tile(id)}
            className={`rounded-lg border border-border bg-card p-card-sm ${wide ? "col-span-2 md:col-span-1" : ""} ${r.className}`}
            style={r.style}
        >
            <p className="text-meta text-muted-foreground">{label}</p>
            <p className="mt-1 app-figure text-h2 leading-none">
                <Count value={value} animate={animate} />
            </p>
            {sublabel ? <p className="mt-2 text-meta text-muted-foreground">{sublabel}</p> : null}
        </div>
    );
}

/** A tile on the wall of posts. A thumbnail that fails to load — Instagram's
 *  media URLs are signed and expire — becomes a plain tile, never a broken
 *  image. */
function PostTile({ post, index, animate }) {
    const [broken, setBroken] = useState(!post.thumbnail_url);
    const r = animate ? { className: "dash-thumb", style: { "--i": index } } : { className: "", style: undefined };
    const Tag = post.permalink ? "a" : "div";
    const linkProps = post.permalink
        ? { href: post.permalink, target: "_blank", rel: "noopener noreferrer" }
        : {};
    return (
        <li className={r.className} style={r.style}>
            <Tag
                {...linkProps}
                data-testid={IDS.post(post.key)}
                aria-label={`${post.creator_name}'s ${post.media_type}: ${formatIN(post.views)} views, ${formatIN(post.shares)} shares`}
                className="group block overflow-hidden rounded-md border border-border bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
                <div className="relative aspect-[4/5] bg-muted">
                    {broken ? (
                        <div
                            data-testid={IDS.postFallback(post.key)}
                            className="absolute inset-0 flex items-center justify-center bg-muted text-muted-foreground"
                            aria-hidden
                        >
                            {post.media_type === "carousel" ? <Layers className="h-6 w-6" /> : <Play className="h-6 w-6" />}
                        </div>
                    ) : (
                        <img
                            src={post.thumbnail_url}
                            alt=""
                            loading="lazy"
                            onError={() => setBroken(true)}
                            className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
                        />
                    )}
                    {post.media_type === "reel" ? (
                        <span className="absolute right-2 top-2 rounded-pill bg-brand-navy/80 p-1.5 text-brand-white">
                            <Play className="h-3 w-3 fill-current" aria-hidden />
                            <span className="sr-only">Reel</span>
                        </span>
                    ) : null}
                    {post.media_type === "carousel" && post.carousel_count ? (
                        <span className="absolute right-2 top-2 rounded-pill bg-brand-navy/80 px-2 py-0.5 text-xs font-medium tabular-nums text-brand-white">
                            1/{post.carousel_count}
                        </span>
                    ) : null}
                </div>
                <div className="px-2.5 py-2">
                    <p className="truncate text-meta font-medium">{post.creator_name}</p>
                    <p className="text-meta tabular-nums text-muted-foreground">
                        {formatIN(post.views)} views · {formatIN(post.shares)} shares
                    </p>
                    {post.source === "manual" ? (
                        <p className="text-xs text-muted-foreground">Entered by hand</p>
                    ) : null}
                </div>
            </Tag>
        </li>
    );
}

function EmptyState({ creators }) {
    return (
        <section data-testid={IDS.empty} className="rounded-lg border border-border bg-card p-card-sm md:p-card">
            <h2 className="font-bold text-h3">Nothing is live yet</h2>
            <p className="mt-2 max-w-measure text-body text-muted-foreground">
                Results appear here as each post goes live. This is where everybody is.
            </p>
            <ul className="mt-5 divide-y divide-divider">
                {creators.map((c, i) => (
                    <li key={`${c.name}-${i}`} data-testid={IDS.emptyCreator(i)} className="flex items-center justify-between py-3">
                        <span className="text-body">{c.name}</span>
                        <span className="text-meta text-muted-foreground">{c.status}</span>
                    </li>
                ))}
            </ul>
        </section>
    );
}

function Skeleton() {
    return (
        <div data-testid={IDS.loading} aria-hidden className="space-y-5">
            <div className="h-10 w-2/3 rounded-md bg-muted" />
            <div className="h-14 rounded-lg bg-muted" />
            <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
                <div className="h-64 rounded-lg bg-muted" />
                <div className="grid gap-5">
                    <div className="h-28 rounded-lg bg-muted" />
                    <div className="h-28 rounded-lg bg-muted" />
                </div>
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
                {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-28 rounded-lg bg-muted" />)}
            </div>
        </div>
    );
}

export default function CampaignDashboard({ campaignId, backTo, backLabel = "Back" }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState(false);
    // **The entrance plays on the first render that has data, and never
    // again.** Background refreshes render the same nodes without the
    // classes, so nothing replays.
    const [animate, setAnimate] = useState(true);
    const firstLoad = useRef(true);

    const load = useCallback(async () => {
        try {
            const res = await api.get(`/brand/campaigns/${campaignId}/analytics`);
            setData(res.data.dashboard);
            setError(false);
        } catch (e) {
            if (firstLoad.current) {
                setError(true);
                notifyError(e);
            }
        } finally {
            if (!firstLoad.current) setAnimate(false);
            firstLoad.current = false;
        }
    }, [campaignId]);

    useEffect(() => {
        load();
        const timer = setInterval(load, REFRESH_MS);
        return () => clearInterval(timer);
    }, [load, campaignId]);

    // Once the entrance has had time to finish, no later render carries it.
    useEffect(() => {
        if (!data || !animate) return undefined;
        const done = setTimeout(() => setAnimate(false), 3000);
        return () => clearTimeout(done);
    }, [data, animate]);

    if (error && !data) {
        return (
            <p data-testid={IDS.error} className="text-body text-muted-foreground">
                The results couldn't load. Try again in a moment.
            </p>
        );
    }
    if (!data) return <Skeleton />;

    const { campaign, totals, creators, posts, by_format: byFormat, by_creator: byCreator } = data;
    const live = posts.live;
    const liveLine =
        live === 0
            ? "No posts live yet"
            : live >= posts.total
                ? `All ${formatIN(live)} posts live`
                : `${formatIN(live)} of ${formatIN(posts.total)} posts live`;
    const exportCsv = () => {
        downloadCsv(`/brand/analytics/export?campaign_id=${campaignId}`, `${campaign.title || "campaign"}-results.csv`)
            .catch(notifyError);
    };

    return (
        <div data-testid={IDS.root} className="space-y-section">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div className="min-w-0">
                    {backTo ? (
                        <Link to={backTo} className="mb-3 inline-flex items-center gap-1.5 text-meta text-muted-foreground hover:text-foreground">
                            <ArrowLeft className="h-4 w-4" /> {backLabel}
                        </Link>
                    ) : null}
                    <h1 data-testid={IDS.title} className="app-title">
                        {campaign.title || "Campaign results"}
                    </h1>
                    <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-meta text-muted-foreground">
                        {campaign.start_date ? (
                            <span data-testid={IDS.dates}>
                                {formatDate(campaign.start_date)}
                                {campaign.end_date && campaign.end_date !== campaign.start_date
                                    ? ` – ${formatDate(campaign.end_date)}`
                                    : ""}
                            </span>
                        ) : null}
                        {data.updated_at ? (
                            <span data-testid={IDS.updated}>updated {timeAgo(data.updated_at)}</span>
                        ) : null}
                        <span data-testid={IDS.live} className="font-medium text-foreground">{liveLine}</span>
                    </p>
                </div>
                <Button variant="outline" onClick={exportCsv} data-testid={IDS.export} className="self-start md:self-auto">
                    <Download className="mr-2 h-4 w-4" /> Export
                </Button>
            </header>

            <SummaryLine campaignId={campaignId} />

            {live === 0 ? (
                <EmptyState creators={creators.list} />
            ) : (
                <>
                    <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
                        <Card animate={animate} index={0}>
                            <p className="text-meta text-muted-foreground">Total views</p>
                            <p className="mt-2 app-figure text-[clamp(3.25rem,9vw,6.5rem)] leading-none tracking-[-0.02em]">
                                <Count value={totals.views} animate={animate} testid={IDS.totalViews} />
                            </p>
                            <p data-testid={IDS.across} className="mt-3 text-body text-muted-foreground">
                                across {formatIN(live)} {live === 1 ? "post" : "posts"} from {formatIN(creators.posted)}{" "}
                                {creators.posted === 1 ? "creator" : "creators"}
                            </p>
                            <Delta block={data.versus_last_campaign} />
                            <FormatSplit formats={byFormat} total={totals.views} />
                        </Card>
                        <div className="grid gap-5">
                            <Card animate={animate} index={1} testid={IDS.creators}>
                                <p className="text-meta text-muted-foreground">Creators</p>
                                <p className="mt-1 app-figure text-h1 leading-none tabular-nums">
                                    <Count value={creators.posted} animate={animate} />
                                </p>
                                <p className="mt-2 text-meta text-muted-foreground">
                                    {creators.posted >= creators.total
                                        ? "all posted"
                                        : `${formatIN(creators.posted)} of ${formatIN(creators.total)} posted`}
                                </p>
                            </Card>
                            <Card animate={animate} index={2} testid={IDS.engagement}>
                                <p className="text-meta text-muted-foreground">Engagement rate</p>
                                <p className="mt-1 app-figure text-h1 leading-none">
                                    <Count value={totals.engagement_rate} format={formatPercent} animate={animate} />
                                </p>
                                <p className="mt-2 text-meta text-muted-foreground">interactions ÷ accounts reached</p>
                            </Card>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
                        <Tile id="reach" label="Accounts reached" sublabel="added across posts" value={totals.reach_sum} animate={animate} index={3} wide />
                        <Tile id="likes" label="Likes" value={totals.likes} animate={animate} index={4} />
                        <Tile id="shares" label="Shares" value={totals.shares} animate={animate} index={5} />
                        <Tile id="saves" label="Saves" value={totals.saves} animate={animate} index={6} />
                        <Tile id="comments" label="Comments" value={totals.comments} animate={animate} index={7} />
                    </div>

                    <div className="grid gap-5 lg:grid-cols-2">
                        {data.timeseries.length ? (
                            <ChartCard
                                title="Views, building up"
                                chart="line"
                                className={animate ? "dash-rise" : ""}
                                style={animate ? { "--i": 8 } : undefined}
                                table={<ViewsOverTimeTable series={data.timeseries} />}
                            >
                                <ViewsOverTime series={data.timeseries} markers={data.markers} animate={animate} />
                            </ChartCard>
                        ) : null}
                        <ChartCard
                            title="Views by creator"
                            chart="bars"
                            className={animate ? "dash-rise" : ""}
                            style={animate ? { "--i": 9 } : undefined}
                            table={<ViewsByCreatorTable rows={byCreator} />}
                        >
                            <ViewsByCreator rows={byCreator} animate={animate} />
                        </ChartCard>
                    </div>

                    <section>
                        <h2 className="mb-4 font-bold text-h3">Every post</h2>
                        <ul data-testid={IDS.wall} className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                            {posts.items.map((p, i) => (
                                <PostTile key={p.key} post={p} index={i} animate={animate} />
                            ))}
                        </ul>
                    </section>
                </>
            )}
        </div>
    );
}
