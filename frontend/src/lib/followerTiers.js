// Audience size, in one vocabulary.
//
// There used to be two. The suggestion scorer had four bands named nano /
// micro / mid / macro with its own boundaries, while every screen a person
// reads described followers in raw numbers — so a brand seeing "micro" in the
// suggestions panel and picking "10k+" in the directory filter were talking
// about different people.
//
// Mirrors `FOLLOWER_TIERS`, `CONTENT_TYPES` and `BUDGET_BANDS` in
// `backend/server.py`; a unit test fails if they drift. The server is the
// authority — the brand-profile response ships these lists too, and a form
// that has them should prefer the server's copy. These exist for the surfaces
// that have no reason to fetch a brand profile just to label a dropdown.

export const FOLLOWER_TIERS = [
    { value: "micro", label: "Micro", range: "1K–10K", min: 1000, max: 10000 },
    { value: "mid", label: "Mid", range: "10K–100K", min: 10000, max: 100000 },
    { value: "macro", label: "Macro", range: "100K+", min: 100000, max: null },
];

export const ANY_TIER = { value: "any", label: "Any", range: "No preference" };

export const CONTENT_TYPES = [
    { value: "reels", label: "Reels" },
    { value: "stories", label: "Stories" },
    { value: "static_posts", label: "Static posts" },
    { value: "shorts", label: "YouTube Shorts" },
];

export const BUDGET_BANDS = [
    { value: "under_5k", label: "Under ₹5,000" },
    { value: "5k_15k", label: "₹5,000–15,000" },
    { value: "15k_40k", label: "₹15,000–40,000" },
    { value: "over_40k", label: "₹40,000+" },
];

/** Which tier an audience sits in. Null when we don't know the number. */
export function tierForFollowers(n) {
    if (typeof n !== "number" || n <= 0) return null;
    for (const t of FOLLOWER_TIERS) {
        if (n >= t.min && (t.max === null || n < t.max)) return t;
    }
    // Below the smallest floor is still the smallest tier: a 400-follower
    // account is a very small micro, not an unclassifiable one.
    return FOLLOWER_TIERS[0];
}

export function tierByValue(value) {
    return FOLLOWER_TIERS.find((t) => t.value === value) || null;
}

/**
 * "24k · Mid" — the number and the word together.
 *
 * Both, always: the number is what a brand negotiates against and the word is
 * what it filters on, and showing one without the other is how the two
 * vocabularies drifted apart in the first place.
 */
export function followerLabel(n, { compact = true } = {}) {
    if (typeof n !== "number" || n <= 0) return "—";
    const tier = tierForFollowers(n);
    const count = compact
        ? n >= 1_000_000
            ? `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`
            : n >= 1_000
              ? `${Math.round(n / 1_000)}k`
              : String(n)
        : n.toLocaleString("en-IN");
    return tier ? `${count} · ${tier.label}` : count;
}

export function contentTypeLabel(value) {
    return (CONTENT_TYPES.find((c) => c.value === value) || {}).label || value;
}

export function budgetBandLabel(value) {
    return (BUDGET_BANDS.find((b) => b.value === value) || {}).label || null;
}
