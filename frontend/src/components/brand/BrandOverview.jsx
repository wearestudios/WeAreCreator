/**
 * The top of the brand's dashboard — board 24, "Option B · Warm".
 *
 * The navy panel is the campaign that is live right now, and under it three
 * columns: what needs the brand, the creators on that campaign, and a stack
 * of the AI summary, the budget and the brand's other briefs. With nothing
 * live, a navy "post a brief" panel takes the same footprint.
 *
 * **Every number is one an endpoint served.** The dashboard row (fill, the
 * budget block, the brand's totals), the campaign's analytics (views,
 * shares, engagement, the cumulative views the sparkline draws, each
 * creator's views and status), the applicant board (each creator's photo and
 * agreed fee) and the AI summary. Nothing here adds, divides or estimates:
 * the boards' "paid" budget segment is not served and is not drawn, and a
 * figure the API returned as unknown is left out rather than shown as a
 * zero. `loadBrandOverview` is the one place those requests are made, so the
 * page can draw everything in one commit.
 *
 * **What a brand sees of a creator** is what `_brand_visible_creator` sent:
 * a name, a photo and the fee they agreed. This file reads nothing else off
 * a creator.
 */
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { api } from "@/lib/api";
import { aiLive } from "@/content/marketing";
import {
    ActionButton,
    ActionCard,
    AiSummaryCard,
    AppCard,
    CardHeading,
    Pill,
    Sparkline,
    StatTile,
} from "@/components/app/ui";
import { daysFromToday, formatDate } from "@/lib/time";
import { formatPercent, formatIN, shortIN } from "@/lib/indianNumber";
import { formatCollabMoney, formatInr } from "@/lib/compensation";
import { BRAND_OVERVIEW as IDS } from "@/constants/testIds";

/** Statuses during which a brief is on the feed and work is happening. */
const LIVE = ["open", "in_progress"];

/**
 * The campaign the panel is about: live, and **already under way** before
 * merely open — a brief that starts next week has nothing to show yet, and
 * one in its second week is what the brand opened the dashboard to see.
 * Within each, the one that started (or starts) most recently.
 */
export function pickLiveCampaign(campaigns = []) {
    const start = (c) => c.start_date || c.event_date || c.created_at || "";
    const begun = (c) => {
        const d = daysFromToday(c.start_date || c.event_date);
        return d === null || d <= 0;
    };
    const live = campaigns.filter((c) => LIVE.includes(c.status));
    return (
        live.sort(
            (a, b) =>
                Number(begun(b)) - Number(begun(a)) || String(start(b)).localeCompare(String(start(a))),
        )[0] || null
    );
}

/**
 * The live campaign's three reads, in parallel and each allowed to fail on
 * its own: a missing summary or applicant list is a smaller panel, not an
 * error page. The summary is asked for only while the switch is on.
 */
export async function loadBrandOverview(campaigns) {
    const live = pickLiveCampaign(campaigns);
    if (!live) return { live: null };
    const ask = (p) => p.then((r) => r.data).catch(() => null);
    const [analytics, board, summary] = await Promise.all([
        ask(api.get(`/brand/campaigns/${live.id}/analytics`)),
        ask(api.get(`/brand/campaigns/${live.id}/applicants`)),
        aiLive("campaignSummary") ? ask(api.get(`/brand/campaigns/${live.id}/summary`)) : Promise.resolve(null),
    ]);
    return { live, analytics, board, summary };
}

// ---------------------------------------------------------------------------
// The navy panel
// ---------------------------------------------------------------------------

function liveChip(c) {
    const day = daysFromToday(c.start_date || c.event_date);
    if (day === null) return "Live";
    if (day > 0) return `Live · starts ${formatDate(c.start_date || c.event_date, { day: "numeric", month: "short" })}`;
    return `Live · day ${1 - day}`;
}

function bookedLine(c) {
    const parts = [`${c.filled_slots ?? 0} of ${c.creators_needed ?? 0} creators booked`];
    const budget = c.budget;
    if (c.compensation_type !== "barter" && budget && typeof budget.committed === "number") {
        parts.push(
            typeof budget.total === "number"
                ? `${formatInr(budget.committed)} of ${formatInr(budget.total)} committed`
                : `${formatInr(budget.committed)} committed`,
        );
    }
    return parts.join(" · ");
}

/** The panel's stat tiles — only the ones the analytics measured. */
function heroTiles(totals) {
    if (!totals) return [];
    return [
        totals.views != null && { key: "views", value: shortIN(totals.views), label: "Views" },
        totals.shares != null && { key: "shares", value: formatIN(totals.shares), label: "Shares" },
        totals.engagement_rate != null && {
            key: "engagement",
            value: formatPercent(totals.engagement_rate),
            label: "Engagement",
        },
    ].filter(Boolean);
}

export function LiveCampaignPanel({ campaign, analytics, hasHistory }) {
    if (!campaign) {
        return (
            <section
                data-testid={IDS.emptyPanel}
                data-surface="inverse"
                className="app-hero-glow relative overflow-hidden rounded-[24px] bg-card px-6 py-7 text-foreground md:min-h-[17rem] md:px-[30px]"
            >
                <div className="relative z-10 max-w-xl">
                    <span className="inline-flex items-center gap-2 rounded-pill bg-tint/10 px-3 py-1 text-[13px] font-bold">
                        Nothing live right now
                    </span>
                    <h1 className="app-title mt-3.5">{hasHistory ? "Post your next brief" : "Post your first brief"}</h1>
                    <p className="mt-2 text-body text-muted-foreground">
                        Tell us what you want made. We shortlist creators against it, and you see the numbers
                        here as the posts go live.
                    </p>
                    {/* A link, not a second red button: "Post a brief" is
                        already the screen's one red action, at the top. */}
                    <Link
                        to="/campaigns/new"
                        data-testid={IDS.emptyPost}
                        className="mt-5 inline-flex min-h-[2.75rem] items-center gap-1.5 rounded-button text-body font-bold text-foreground underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                        Start writing it <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>
            </section>
        );
    }
    const dash = analytics?.dashboard;
    const tiles = heroTiles(dash?.totals);
    const points = (dash?.timeseries || []).map((p) => p.views);
    return (
        <section
            data-testid={IDS.panel}
            data-surface="inverse"
            className="app-hero-glow relative grid gap-6 overflow-hidden rounded-[24px] bg-card px-6 py-7 text-foreground md:min-h-[17rem] md:grid-cols-[1.1fr_1fr] md:gap-[26px] md:px-[30px]"
        >
            <div className="relative z-10 min-w-0">
                <span className="inline-flex items-center gap-2 rounded-pill bg-tint/10 px-3 py-1 text-[13px] font-bold">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full bg-state-live" />
                    {liveChip(campaign)}
                </span>
                <h1 className="app-title mt-3.5">
                    <Link
                        to={`/brand/campaigns/${campaign.id}/applicants`}
                        data-testid={IDS.title}
                        className="rounded-button hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                        {campaign.title}
                    </Link>
                </h1>
                <p data-testid={IDS.booked} className="mt-1.5 text-body text-muted-foreground">
                    {bookedLine(campaign)}
                </p>
                <div className="mt-4 h-[70px]">
                    {points.length >= 2 ? (
                        <Sparkline points={points} label="Views so far, day by day" />
                    ) : null}
                </div>
            </div>
            <div className="relative z-10 grid content-end">
                {tiles.length ? (
                    <div data-testid={IDS.tiles} className="grid grid-cols-3 gap-3">
                        {tiles.map((t) => (
                            <StatTile key={t.key} onNavy value={t.value} label={t.label} testid={IDS.tile(t.key)} />
                        ))}
                    </div>
                ) : (
                    <p data-testid={IDS.noNumbers} className="text-meta text-muted-foreground md:text-right">
                        Views, shares and engagement arrive once the first post is live.
                    </p>
                )}
            </div>
        </section>
    );
}

// ---------------------------------------------------------------------------
// Needs you
// ---------------------------------------------------------------------------

/**
 * What is waiting on the brand, from the dashboard's own counts. **One red
 * card at most**: deliveries waiting on the brand's approval, because a
 * creator who has done the work is waiting on it to be paid — that is the
 * clock running. Everything else is navy.
 */
export function needsYouItems(data, live, board) {
    const items = [];
    const totals = data?.totals || {};
    if (totals.content_to_review > 0) {
        const row = (board?.applicants || []).find((r) => r.can_review_content);
        items.push({
            key: "content",
            tone: "red",
            title: `${totals.content_to_review} ${totals.content_to_review === 1 ? "delivery" : "deliveries"} to review`,
            detail: "The creator is waiting on your approval to be paid.",
            to: row ? `/brand/applications/${row.id}` : live ? `/brand/campaigns/${live.id}/applicants` : "#brand-campaigns",
            cta: "Review",
        });
    }
    for (const c of data?.campaigns || []) {
        if (c.awaiting_decision > 0) {
            items.push({
                key: `decide-${c.id}`,
                tone: "navy",
                title: `${c.awaiting_decision} ${c.awaiting_decision === 1 ? "applicant" : "applicants"} to look at`,
                detail: c.title,
                to: `/brand/campaigns/${c.id}/applicants`,
                cta: "Open shortlist",
            });
        }
    }
    // The gate's own reason, when there is something on this app to do about
    // it. An overdue invoice is settled outside the app, and the standing
    // notice above already says so — a card with a button that goes nowhere
    // useful would be the one thing here that is not an action.
    const block = data?.publish_block;
    const BLOCK_ACTION = {
        no_profile: ["Tell us about your brand", "Finish your profile"],
        unverified: ["Finish verification to publish", "Finish it"],
        verification_lapsed: ["Confirm your details are current", "Confirm"],
    };
    if (block && BLOCK_ACTION[block.code]) {
        const [title, cta] = BLOCK_ACTION[block.code];
        items.push({
            key: "verify",
            tone: "navy",
            title,
            detail: block.message,
            to: "/onboarding/brand",
            cta,
        });
    }
    for (const c of (data?.campaigns || []).filter((c) => c.status === "draft").slice(0, 2)) {
        items.push({
            key: `draft-${c.id}`,
            tone: "navy",
            title: "Finish your draft",
            detail: c.title || "Untitled brief",
            to: `/campaigns/${c.id}/edit`,
            cta: "Finish",
        });
    }
    return items;
}

export function NeedsYou({ items }) {
    return (
        <AppCard data-testid={IDS.needs}>
            <CardHeading aside={items.length ? String(items.length) : null}>Needs you</CardHeading>
            {items.length ? (
                <div className="space-y-2.5">
                    {items.map((it) => (
                        <ActionCard
                            key={it.key}
                            tone={it.tone}
                            title={it.title}
                            detail={it.detail}
                            testid={IDS.need(it.key)}
                            action={
                                <ActionButton tone={it.tone} asChild>
                                    <Link to={it.to}>{it.cta}</Link>
                                </ActionButton>
                            }
                        />
                    ))}
                </div>
            ) : (
                <p data-testid={IDS.needsEmpty} className="text-meta text-muted-foreground">
                    Nothing is waiting on you. We'll put it here when something is.
                </p>
            )}
        </AppCard>
    );
}

// ---------------------------------------------------------------------------
// Creators
// ---------------------------------------------------------------------------

/** The status the analytics named, in a tone. */
function creatorTone(row) {
    if (row.posted) return "good";
    if (/review/i.test(row.status || "")) return "warn";
    if (/booked|done|received|way/i.test(row.status || "")) return "info";
    return "neutral";
}

const initials = (name) =>
    (name || "?")
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((p) => p[0])
        .join("")
        .toUpperCase();

export function CampaignCreators({ live, analytics, board, max = 5 }) {
    const dash = analytics?.dashboard;
    const list = dash?.creators?.list || [];
    const views = new Map((dash?.by_creator || []).map((r) => [r.name, r.views]));
    // The applicant board's rows carry the photo and the agreed fee; the
    // analytics carries the status and the views. Matched on the name both
    // read off the same profile.
    const rows = new Map((board?.applicants || []).map((r) => [r.creator?.name, r]));
    const kind = board?.campaign?.compensation_type || live?.compensation_type;
    return (
        <AppCard data-testid={IDS.creators}>
            <CardHeading
                aside={
                    live && list.length ? (
                        <Link to={`/brand/campaigns/${live.id}/applicants`} className="hover:text-foreground">
                            View all
                        </Link>
                    ) : null
                }
            >
                Creators
            </CardHeading>
            {list.length ? (
                <ul>
                    {list.slice(0, max).map((c) => {
                        const row = rows.get(c.name);
                        const photo = row?.creator?.profile_image_url;
                        const fee = row ? formatCollabMoney({ compensationType: kind, agreed: row.agreed_amount }).text : null;
                        const v = views.get(c.name);
                        return (
                            <li
                                key={c.name}
                                data-testid={IDS.creatorRow}
                                className="flex items-center gap-3 border-b border-wash-warm py-2.5 last:border-b-0"
                            >
                                <span className="grid h-9 w-9 flex-none place-items-center overflow-hidden rounded-[12px] bg-wash-navy text-[13px] font-extrabold text-heading">
                                    {photo ? (
                                        <img src={photo} alt="" className="h-full w-full object-cover" loading="lazy" />
                                    ) : (
                                        initials(c.name)
                                    )}
                                </span>
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-body font-bold text-heading">{c.name}</p>
                                    <p className="truncate text-meta tabular-nums text-muted-foreground">
                                        {[fee, v != null ? `${formatIN(v)} views` : null].filter(Boolean).join(" · ") || "No post yet"}
                                    </p>
                                </div>
                                <Pill tone={creatorTone(c)}>{c.posted ? "Posted" : c.status}</Pill>
                            </li>
                        );
                    })}
                </ul>
            ) : (
                <p data-testid={IDS.creatorsEmpty} className="text-meta text-muted-foreground">
                    {live
                        ? "Nobody is booked on this brief yet. Creators appear here once they're taken on."
                        : "Creators appear here once a brief is live and they're taken on."}
                </p>
            )}
        </AppCard>
    );
}

// ---------------------------------------------------------------------------
// The right-hand stack
// ---------------------------------------------------------------------------

/**
 * What the brief has left to spend, from the campaign's own budget block:
 * committed (agreed fees) against what is left. **No "paid" segment** — the
 * block does not serve one, and summing payments here would be a second
 * definition of a figure the server owns.
 */
export function BudgetCard({ campaign }) {
    const b = campaign?.budget;
    if (!campaign || campaign.compensation_type === "barter" || !b || typeof b.total !== "number") return null;
    const ratio = Math.max(0, Math.min(1, b.ratio ?? 0));
    return (
        <AppCard data-testid={IDS.budget}>
            <CardHeading>Budget</CardHeading>
            <p className="app-figure text-[2.125rem] leading-none text-heading">
                {formatInr(Math.max(0, b.remaining))}{" "}
                <span className="text-body font-semibold tracking-normal text-muted-foreground">left</span>
            </p>
            <div
                className="mt-3 flex h-3 overflow-hidden rounded-pill bg-wash-warm"
                role="img"
                aria-label={`${formatInr(b.committed)} agreed of ${formatInr(b.total)}`}
            >
                <span className="dash-grow h-full bg-primary" style={{ width: `${ratio * 100}%` }} />
            </div>
            <div className="mt-2.5 flex flex-wrap justify-between gap-2 text-meta font-semibold text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                    <span aria-hidden="true" className="h-2.5 w-2.5 rounded-[3px] bg-primary" /> Agreed {formatInr(b.committed)}
                </span>
                <span>of {formatInr(b.total)}</span>
            </div>
            {b.warning || b.exhausted ? (
                <Pill tone={b.exhausted ? "warn" : "due"} className="mt-3">
                    {b.exhausted ? "Fully spoken for" : "Nearly spent"}
                </Pill>
            ) : null}
        </AppCard>
    );
}

const STATUS_PILL = {
    draft: ["neutral", "Draft"],
    pending_review: ["info", "In review"],
    rejected: ["warn", "Sent back"],
    upcoming: ["info", "Upcoming"],
    open: ["good", "Live"],
    in_progress: ["good", "Filled"],
    paused: ["due", "Paused"],
    completed: ["neutral", "Completed"],
    closed: ["neutral", "Closed"],
};

export function OtherCampaigns({ campaigns, live, max = 4 }) {
    const others = (campaigns || []).filter((c) => c.id !== live?.id);
    if (!others.length) return null;
    return (
        <AppCard data-testid={IDS.others}>
            <CardHeading
                aside={
                    others.length > max ? (
                        <a href="#brand-campaigns" className="hover:text-foreground">
                            All {others.length}
                        </a>
                    ) : null
                }
            >
                Other campaigns
            </CardHeading>
            <ul>
                {others.slice(0, max).map((c) => {
                    const [tone, label] = STATUS_PILL[c.status] || ["neutral", c.status];
                    return (
                        <li key={c.id} className="flex items-center justify-between gap-3 border-b border-wash-warm py-2.5 last:border-b-0">
                            <Link
                                to={c.status === "draft" ? `/campaigns/${c.id}/edit` : `/brand/campaigns/${c.id}/applicants`}
                                className="min-w-0 truncate text-body font-semibold text-heading hover:underline"
                            >
                                {c.title || "Untitled brief"}
                            </Link>
                            <Pill tone={tone}>{label}</Pill>
                        </li>
                    );
                })}
            </ul>
        </AppCard>
    );
}

// ---------------------------------------------------------------------------
// The whole top
// ---------------------------------------------------------------------------

export default function BrandOverview({ data, overview }) {
    const live = overview?.live || null;
    const summary = overview?.summary?.available ? overview.summary.summary : null;
    const items = needsYouItems(data, live, overview?.board);
    return (
        <div data-testid={IDS.root}>
            <LiveCampaignPanel
                campaign={live}
                analytics={overview?.analytics}
                hasHistory={(data?.campaigns || []).length > 0}
            />
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
                <NeedsYou items={items} />
                <CampaignCreators live={live} analytics={overview?.analytics} board={overview?.board} />
                <div className="space-y-4">
                    <AiSummaryCard
                        testid={IDS.ai}
                        text={summary?.headline}
                        title="AI summary"
                        footnote={
                            live ? (
                                <Link to={`/brand/campaigns/${live.id}/results`} className="inline-flex items-center gap-1 font-semibold text-foreground hover:underline">
                                    The full results <ArrowRight className="h-3.5 w-3.5" />
                                </Link>
                            ) : null
                        }
                    />
                    <BudgetCard campaign={live} />
                    <OtherCampaigns campaigns={data?.campaigns} live={live} />
                </div>
            </div>
        </div>
    );
}
