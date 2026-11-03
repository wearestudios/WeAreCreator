// Numbers the way an Indian reader writes them.
//
// **`formatIN` everywhere a number is read**: 1,48,932, not 148,932 — the
// lakh grouping is what a restaurant owner in Bengaluru reads without
// stopping. **`shortIN` only where space forces it** — a chart axis or the
// label at the end of a line — because "4.27L" is a rounding, and a rounding
// in a headline figure reads as the figure.

const FULL = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const DECIMAL = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** 148932 → "1,48,932". `null` → the em dash every surface uses for unknown. */
export function formatIN(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
    return FULL.format(Math.round(Number(n)));
}

/** A percentage to two places at most: 4.37 → "4.37%". */
export function formatPercent(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
    return `${DECIMAL.format(Number(n))}%`;
}

const trim = (x, places) => String(Number(x.toFixed(places)));

/** 427000 → "4.27L", 38000 → "38K", 12000000 → "1.2Cr". Axes and end labels only. */
export function shortIN(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
    const v = Math.abs(Number(n));
    const sign = Number(n) < 0 ? "-" : "";
    if (v >= 1e7) return `${sign}${trim(v / 1e7, 2)}Cr`;
    if (v >= 1e5) return `${sign}${trim(v / 1e5, 2)}L`;
    if (v >= 1e3) return `${sign}${trim(v / 1e3, 1)}K`;
    return `${sign}${FULL.format(Math.round(v))}`;
}
