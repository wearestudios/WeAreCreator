// The dashboard's two charts, hand-written SVG.
//
// Two small shapes do not justify a charting dependency in the brand chunk —
// the arrangement `components/admin/Health.jsx` settled on. One navy series
// each (`currentColor` under `text-primary`, so the theme decides), tooltips
// on hover **and focus** so a keyboard reaches every value, and a "View as
// table" toggle beside each, because a chart nobody can read with a screen
// reader is a picture of numbers rather than the numbers.
import React, { useEffect, useMemo, useRef, useState } from "react";

import { formatIN, shortIN } from "@/lib/indianNumber";
import { formatDate } from "@/lib/time";
import { DASHBOARD as IDS } from "@/constants/testIds";

function TableToggle({ chart, shown, onToggle }) {
    return (
        <button
            type="button"
            onClick={onToggle}
            aria-pressed={shown}
            data-testid={IDS.asTable(chart)}
            className="text-meta text-muted-foreground underline-offset-4 transition-colors duration-200 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
            {shown ? "View as chart" : "View as table"}
        </button>
    );
}

export function ChartCard({ title, chart, table, children, className = "", style }) {
    const [asTable, setAsTable] = useState(false);
    return (
        <section
            className={`rounded-lg border border-border bg-card p-card-sm md:p-card ${className}`}
            style={style}
        >
            <div className="mb-4 flex items-baseline justify-between gap-3">
                <h2 className="font-serif text-h3">{title}</h2>
                <TableToggle chart={chart} shown={asTable} onToggle={() => setAsTable((v) => !v)} />
            </div>
            {asTable ? table : children}
        </section>
    );
}

function Tooltip({ tip }) {
    if (!tip) return null;
    return (
        <div
            role="status"
            data-testid={IDS.tooltip}
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border border-border bg-popover px-2.5 py-1.5 text-meta text-popover-foreground tabular-nums shadow-md"
            style={{ left: tip.x, top: tip.y - 8 }}
        >
            {tip.text}
        </div>
    );
}

/**
 * Cumulative views per day, with each reel's creator marked on the day it
 * went live. The line draws once; the area and the end label fade in after.
 */
export function ViewsOverTime({ series, markers, animate }) {
    const [tip, setTip] = useState(null);
    // **Drawn at the width it is shown**, measured, so 11px text is 11px on a
    // phone and on a laptop alike — a fixed viewBox scaled into a 330px column
    // shrinks every label to six pixels.
    const box = useRef(null);
    const [W, setW] = useState(520);
    useEffect(() => {
        const node = box.current;
        if (!node || typeof ResizeObserver === "undefined") return undefined;
        const ro = new ResizeObserver(([entry]) => {
            const width = Math.round(entry.contentRect.width);
            if (width > 0) setW(Math.max(280, width));
        });
        ro.observe(node);
        return () => ro.disconnect();
    }, []);
    const H = W < 420 ? 240 : 300;
    const PAD = { l: 44, r: 52, t: 44, b: 30 };
    const max = Math.max(1, ...series.map((d) => d.views));
    const x = (i) => PAD.l + (series.length <= 1 ? 0 : (i / (series.length - 1)) * (W - PAD.l - PAD.r));
    const index = useMemo(() => new Map(series.map((d, i) => [d.date, i])), [series]);
    // Markers take the first row with room for their name, so two reels a
    // day apart on a phone stack instead of printing over each other.
    const placed = [];
    const rowEnds = [];
    for (const m of markers) {
        const i = index.get(m.date);
        if (i === undefined) continue;
        const left = x(i) + 4;
        let row = rowEnds.findIndex((end) => end < left - 4);
        if (row === -1) {
            row = rowEnds.length;
            rowEnds.push(0);
        }
        rowEnds[row] = left + m.name.length * 6.2;
        placed.push({ ...m, i, row });
    }
    // Room above the plot for however many rows of names there are.
    PAD.t = 18 + Math.max(1, rowEnds.length) * 13;
    const y = (v) => H - PAD.b - (v / max) * (H - PAD.t - PAD.b);
    const points = series.map((d, i) => [x(i), y(d.views)]);
    const line = points.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`).join(" ");
    const area = points.length
        ? `${line} L${points[points.length - 1][0].toFixed(1)},${H - PAD.b} L${PAD.l},${H - PAD.b} Z`
        : "";
    const ticks = [0, 0.5, 1].map((f) => Math.round(max * f));
    const last = series[series.length - 1];
    const show = (i) =>
        setTip({
            x: `${(x(i) / W) * 100}%`,
            y: (y(series[i].views) / H) * 100,
            text: `${formatDate(series[i].date)} · ${formatIN(series[i].views)} views`,
        });

    return (
        <div ref={box} className="relative text-primary" data-testid={IDS.lineChart}>
            <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full overflow-visible" role="img"
                 aria-label={`Views building up to ${formatIN(last?.views)} over ${series.length} days`}>
                {ticks.map((t) => (
                    <g key={t}>
                        <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} className="stroke-border" strokeWidth="1" />
                        <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" className="fill-muted-foreground text-[11px] tabular-nums">
                            {shortIN(t)}
                        </text>
                    </g>
                ))}
                {/* `fillOpacity`, not `opacity`: the fade-in animates `opacity` to 1,
                    which would otherwise turn a 7% tint into solid navy. */}
                <path d={area} fill="currentColor" fillOpacity="0.08" className={animate ? "dash-after-line" : undefined} />
                <path
                    d={line}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    pathLength="1000"
                    className={animate ? "dash-draw" : undefined}
                    style={animate ? { "--len": 1000 } : undefined}
                />
                {placed.map((m) => (
                    <g key={`${m.date}-${m.name}`} className={animate ? "dash-after-line" : undefined}>
                        <line x1={x(m.i)} x2={x(m.i)} y1={H - PAD.b} y2={16 + m.row * 13}
                              className="stroke-border" strokeDasharray="2 3" />
                        <text x={x(m.i) + 4} y={13 + m.row * 13} className="fill-muted-foreground text-[11px]">
                            {m.name}
                        </text>
                    </g>
                ))}
                {last ? (
                    <text x={points[points.length - 1][0] + 8} y={points[points.length - 1][1] + 4}
                          className={`fill-current text-[13px] font-semibold tabular-nums ${animate ? "dash-after-line" : ""}`}>
                        {shortIN(last.views)}
                    </text>
                ) : null}
                {series.map((d, i) => (
                    <circle
                        key={d.date}
                        cx={x(i)}
                        cy={y(d.views)}
                        r="9"
                        fill="transparent"
                        tabIndex={0}
                        aria-label={`${formatDate(d.date)}: ${formatIN(d.views)} views`}
                        onMouseEnter={() => show(i)}
                        onFocus={() => show(i)}
                        onMouseLeave={() => setTip(null)}
                        onBlur={() => setTip(null)}
                        className="cursor-pointer focus:outline-none focus-visible:stroke-current focus-visible:[stroke-width:2]"
                    />
                ))}
                <text x={PAD.l} y={H - 8} className="fill-muted-foreground text-[11px]">{formatDate(series[0]?.date)}</text>
                <text x={W - PAD.r} y={H - 8} textAnchor="end" className="fill-muted-foreground text-[11px]">
                    {formatDate(last?.date)}
                </text>
            </svg>
            {tip ? <Tooltip tip={{ ...tip, y: `${tip.y}%` }} /> : null}
        </div>
    );
}

export function ViewsOverTimeTable({ series }) {
    return (
        <table className="w-full text-meta tabular-nums" data-testid={IDS.table("line")}>
            <caption className="sr-only">Views building up, by day</caption>
            <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 font-medium">Day</th>
                    <th className="py-2 text-right font-medium">Views so far</th>
                </tr>
            </thead>
            <tbody>
                {series.map((d) => (
                    <tr key={d.date} className="border-b border-divider">
                        <td className="py-1.5">{formatDate(d.date)}</td>
                        <td className="py-1.5 text-right">{formatIN(d.views)}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

/** Views by creator: horizontal bars, the value at the bar's end. */
export function ViewsByCreator({ rows, animate }) {
    const [focused, setFocused] = useState(null);
    const max = Math.max(1, ...rows.map((r) => r.views || 0));
    return (
        <ol className="space-y-2.5 text-primary" data-testid={IDS.barChart}>
            {rows.map((r, i) => {
                const pct = ((r.views || 0) / max) * 100;
                const label = `${r.name}: ${formatIN(r.views)} views from ${r.posts} ${r.posts === 1 ? "post" : "posts"}`;
                return (
                    <li
                        key={r.name}
                        tabIndex={0}
                        aria-label={label}
                        title={label}
                        onMouseEnter={() => setFocused(r.name)}
                        onMouseLeave={() => setFocused(null)}
                        onFocus={() => setFocused(r.name)}
                        onBlur={() => setFocused(null)}
                        className="grid grid-cols-[minmax(6rem,9rem)_1fr] items-center gap-3 rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    >
                        <span className="truncate text-meta text-foreground">{r.name}</span>
                        <span className="relative flex h-7 items-center">
                            <span
                                className={`block h-full rounded-r-sm bg-current ${animate ? "dash-grow" : ""} ${focused === r.name ? "opacity-80" : ""}`}
                                style={{ width: `${Math.max(pct, 0.5)}%`, "--i": i }}
                            />
                            <span className="ml-2 shrink-0 text-meta font-semibold tabular-nums text-foreground">
                                {formatIN(r.views)}
                            </span>
                        </span>
                    </li>
                );
            })}
        </ol>
    );
}

export function ViewsByCreatorTable({ rows }) {
    return (
        <table className="w-full text-meta tabular-nums" data-testid={IDS.table("bars")}>
            <caption className="sr-only">Views by creator</caption>
            <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 font-medium">Creator</th>
                    <th className="py-2 text-right font-medium">Posts</th>
                    <th className="py-2 text-right font-medium">Views</th>
                </tr>
            </thead>
            <tbody>
                {rows.map((r) => (
                    <tr key={r.name} className="border-b border-divider">
                        <td className="py-1.5">{r.name}</td>
                        <td className="py-1.5 text-right">{r.posts}</td>
                        <td className="py-1.5 text-right">{formatIN(r.views)}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}
