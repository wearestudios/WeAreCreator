// What a brief asks for, in counted pieces.
//
// **This was free text on the form**, and free text is what made it
// unanswerable. "1 reel + 3 stories", "one reel, three stories", "reel x1,
// stories x3" and "a reel and a few stories" are four spellings of one brief:
// nothing could count what a campaign asked for, a creator comparing two
// briefs was comparing prose, and "a few" is not a number anybody agreed to.
//
// Mirrors `DELIVERABLE_TYPES` in `server.py`, the same arrangement
// `followerTiers.js` and `shootWindows.js` use and for the same reason — a
// unit test fails if the two drift. The keys are the wire values; nothing here
// invents one.
//
// **A campaign posted before this field existed has a sentence and no
// structure.** `deliverableItems()` returns `[]` for it, and every surface
// falls back to `campaign.deliverables` — which is also what the structured
// ask derives into on the server, so old and new briefs read the same way.

/** Wire value → what a person calls it. The order is the order they render. */
export const DELIVERABLE_TYPES = {
    reel: "Reel",
    story: "Story",
    static_post: "Static post",
    youtube_short: "YouTube Short",
    video: "Video",
};

/** Spelled out rather than lowercased: "youtube short" is not the name. */
export const DELIVERABLE_SINGULARS = {
    reel: "reel",
    story: "story",
    static_post: "static post",
    youtube_short: "YouTube Short",
    video: "video",
};

export const DELIVERABLE_PLURALS = {
    reel: "reels",
    story: "stories",
    static_post: "static posts",
    youtube_short: "YouTube Shorts",
    video: "videos",
};

/** One brief asking for forty of anything is a brief somebody mistyped. */
export const MAX_DELIVERABLE_QUANTITY = 50;

/** The keys, in render order. */
export const DELIVERABLE_KEYS = Object.keys(DELIVERABLE_TYPES);

/**
 * The structured ask on a campaign, normalised — known types only, merged,
 * in the vocabulary's order. `[]` means "there is no structure here", which
 * is what every campaign posted before this field looks like.
 */
export function deliverableItems(campaign) {
    const raw = campaign?.deliverable_items;
    if (!Array.isArray(raw)) return [];
    const totals = {};
    for (const row of raw) {
        const key = row?.type;
        if (!(key in DELIVERABLE_TYPES)) continue;
        const qty = Number(row?.quantity);
        if (!Number.isFinite(qty) || qty <= 0) continue;
        totals[key] = Math.min(MAX_DELIVERABLE_QUANTITY, (totals[key] || 0) + Math.floor(qty));
    }
    return DELIVERABLE_KEYS.filter((k) => k in totals).map((k) => ({
        type: k,
        quantity: totals[k],
    }));
}

/** "3 reels", "1 YouTube Short" — one item, said the way a person would. */
export function deliverableLabel(item) {
    const words =
        item.quantity === 1
            ? DELIVERABLE_SINGULARS[item.type]
            : DELIVERABLE_PLURALS[item.type];
    return `${item.quantity} ${words}`;
}

/**
 * The whole ask as one sentence — the same one the server derives and stores,
 * so a surface that has the items and a surface that only has the text agree.
 */
export function deliverablesText(campaign) {
    const items = deliverableItems(campaign);
    if (items.length > 0) return items.map(deliverableLabel).join(" · ");
    return (campaign?.deliverables || "").trim();
}
