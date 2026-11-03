/**
 * The app's visual primitives — "Option B · Warm".
 *
 * Every dashboard in the signed-in app is built from these: a white card on
 * the warm ground, a pill that names a state in one of five tones, a tinted
 * action card with one button, a stat tile, a sparkline that draws once, and
 * the cream AI card. They are layout and colour only — every word and every
 * number arrives as a prop, from an endpoint, and none of them computes a
 * figure.
 *
 * **No colour literal here.** Each tone is a token (`--state-*`, `--wash-*`,
 * `--shadow-card`), so the console's dark set reads correctly through the
 * same components, and the colour sweeps hold.
 */
import React from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { aiLive } from "@/content/marketing";

const cx = (...parts) => parts.filter(Boolean).join(" ");

/** A white card on the warm ground: 20px, no border, the card shadow. */
export function AppCard({ as: Tag = "section", className = "", children, ...rest }) {
    return (
        <Tag className={cx("rounded-lg bg-card p-5 shadow-card md:px-[22px]", className)} {...rest}>
            {children}
        </Tag>
    );
}

/** A card's heading: Manrope 800 16px, with an optional quiet aside. */
export function CardHeading({ children, aside, as: Tag = "h2", className = "" }) {
    return (
        <div className={cx("mb-3.5 flex items-baseline justify-between gap-3", className)}>
            <Tag className="text-body font-extrabold leading-snug text-heading">{children}</Tag>
            {aside ? <span className="shrink-0 text-meta font-semibold text-muted-foreground">{aside}</span> : null}
        </div>
    );
}

/** The five tones a pill can carry. `due` is amber — a clock that is running. */
export const PILL_TONE = {
    good: "bg-state-approved-wash text-state-approved",
    warn: "bg-state-rejected-wash text-state-rejected",
    info: "bg-state-info-wash text-state-info",
    due: "bg-state-due-wash text-state-due",
    neutral: "bg-wash-warm text-muted-foreground",
};

/** A state in words, on its own tint. Never colour alone. */
export function Pill({ tone = "neutral", children, className = "", ...rest }) {
    return (
        <span
            className={cx(
                "inline-flex items-center gap-1.5 whitespace-nowrap rounded-pill px-2.5 py-1 text-xs font-bold leading-none",
                PILL_TONE[tone] || PILL_TONE.neutral,
                className,
            )}
            {...rest}
        >
            {children}
        </span>
    );
}

/**
 * A thing somebody has to do, tinted by urgency, with exactly one button.
 *
 * `tone="red"` is the one item whose clock is running and its button is the
 * card's single `urgent` (red) action; `tone="navy"` is everything else and
 * its button is the navy `solid`. The button is whatever the caller passes as
 * `action` — a `Link`, usually — so the card never decides where it goes.
 */
export function ActionCard({ tone = "navy", title, detail, action, testid, className = "" }) {
    return (
        <div
            data-testid={testid}
            className={cx(
                "flex flex-col gap-3 rounded-[14px] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between",
                tone === "red" ? "bg-wash-red" : "bg-wash-navy",
                className,
            )}
        >
            <div className="min-w-0">
                <p className="text-body font-bold leading-snug text-heading">{title}</p>
                {detail ? <p className="mt-0.5 text-meta text-muted-foreground">{detail}</p> : null}
            </div>
            {action ? <div className="shrink-0">{action}</div> : null}
        </div>
    );
}

/** The button inside an action card: red when its card is red, navy otherwise. */
export function ActionButton({ tone = "navy", children, ...rest }) {
    return (
        <Button variant={tone === "red" ? "urgent" : "solid"} size="sm" {...rest}>
            {children}
        </Button>
    );
}

/**
 * A big number and a 13px label. `onNavy` is the translucent-white tile the
 * navy panels carry; otherwise it is a white tile (or a warm one, `quiet`).
 * The value is rendered as given — formatting is the caller's, from the
 * figure the endpoint served.
 */
export function StatTile({ value, label, onNavy = false, quiet = false, testid, className = "" }) {
    return (
        <div
            data-testid={testid}
            className={cx(
                "rounded-tile px-4 py-3.5",
                onNavy ? "bg-tint/[0.07]" : quiet ? "bg-wash-warm" : "bg-card shadow-card",
                className,
            )}
        >
            <div className="app-figure text-[1.75rem] leading-none text-heading md:text-[1.875rem]">{value}</div>
            <div className="mt-1.5 text-[13px] font-semibold text-muted-foreground">{label}</div>
        </div>
    );
}

/**
 * A line that draws once. `points` are the endpoint's own numbers in order;
 * nothing is interpolated, smoothed or invented between them. Fewer than two
 * points draws nothing — a line needs two ends.
 */
export function Sparkline({ points, width = 380, height = 70, className = "", label }) {
    const values = (points || []).filter((v) => typeof v === "number" && Number.isFinite(v));
    if (values.length < 2) return null;
    const max = Math.max(...values);
    const min = Math.min(...values);
    const span = max - min || 1;
    const pad = 4;
    const step = (width - pad * 2) / (values.length - 1);
    const xy = values.map((v, i) => [pad + i * step, height - pad - ((v - min) / span) * (height - pad * 2)]);
    const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
    const area = `${line} L${xy[xy.length - 1][0].toFixed(1)} ${height} L${xy[0][0].toFixed(1)} ${height} Z`;
    return (
        <svg
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="none"
            role={label ? "img" : undefined}
            aria-label={label}
            aria-hidden={label ? undefined : true}
            className={cx("block h-[70px] w-full", className)}
        >
            {/* The results page's own draw (`.dash-draw`, `.dash-after-line`
                in index.css): the line strokes in once, the fill follows,
                and reduced motion lands on both. `pathLength` makes the
                dash length 1 whatever the line's real length is. */}
            <path d={area} className="dash-after-line fill-accent/20" />
            <path
                d={line}
                pathLength="1"
                style={{ "--len": 1 }}
                className="dash-draw fill-none stroke-accent"
                strokeWidth="2.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
            />
        </svg>
    );
}

/**
 * What the AI wrote, on cream with a sparkle — and **nothing at all** unless
 * both halves are true: the public switch `aiLive("campaignSummary")` is on
 * and the endpoint actually returned a summary. An empty card saying the AI
 * has nothing to say is still the AI being advertised.
 */
export function AiSummaryCard({ text, title = "What stood out", footnote, testid, className = "" }) {
    if (!aiLive("campaignSummary")) return null;
    if (typeof text !== "string" || !text.trim()) return null;
    return (
        <section data-testid={testid} className={cx("rounded-lg bg-wash-cream p-5 md:px-[22px]", className)}>
            <div className="mb-2.5 flex items-center gap-2">
                <Sparkles aria-hidden="true" className="h-4 w-4 text-accent-ink" />
                <h2 className="text-body font-extrabold text-heading">{title}</h2>
            </div>
            <p className="text-body leading-relaxed text-foreground">{text}</p>
            {footnote ? <p className="mt-2.5 text-meta text-muted-foreground">{footnote}</p> : null}
        </section>
    );
}
