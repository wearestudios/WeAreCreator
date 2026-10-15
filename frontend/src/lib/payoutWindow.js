// When a creator gets paid, and whether getting there is covered.
//
// **Named `payoutWindow` rather than `payout` because `payout.js` is taken**,
// and the two are genuinely different subjects: that one is *how* money
// reaches a creator (UPI or bank, and what the form still needs), this one is
// *when* it does and what the brief promised about it.
//
// **Both blocks are server-decided and this file only renders them.** The
// campaign payload carries `payout` (`{days, promise}`) and `travel`
// (`{stated, covered, amount, text}`), built by `_payout_block` and
// `_travel_block` in server.py — so the brief, the `/c/{id}` share page and
// the manager's panel cannot word the same promise three ways. What lives
// here is the default they fall back to and the readers a surface uses,
// mirrored with a drift test the way `followerTiers.js` and `shootWindows.js`
// are.
//
// The payout window exists because the survey said so: late payment is what
// creators name most often, and the striking half is that creators who *were*
// paid within a week still name it. No brief had ever said when payment
// comes, and an unstated wait is assumed to be a long one.

/** Mirrors `CREATOR_PAYOUT_DAYS` in server.py. The platform promise, for the
 *  one case where a surface has no block to read — never used to overrule a
 *  block that did arrive. */
export const CREATOR_PAYOUT_DAYS = 7;

/**
 * The sentence for a brief. Mirrors `_payout_promise`.
 *
 * **Prefers the server's own wording.** A block that arrived carries the
 * sentence the server built; rebuilding it here would be a second definition
 * of the promise, which is how the brief and the share page come to disagree
 * about what we said.
 */
export function payoutPromise(payout) {
    if (payout?.promise) return payout.promise;
    const days = Number.isFinite(payout?.days) ? payout.days : CREATOR_PAYOUT_DAYS;
    if (days <= 0) return "Paid the same day your delivery is approved.";
    return `Paid within ${days} ${days === 1 ? "day" : "days"} of approved delivery.`;
}

/**
 * Whether to draw the travel line at all.
 *
 * **Three answers, not two.** `stated: false` is "nobody asked", which every
 * campaign written before the field carries — and rendering that as "travel
 * not covered" tells a creator something we never said. A surface draws
 * nothing in that case.
 */
export const travelStated = (travel) => Boolean(travel?.stated);

/** The line, or `null` where nothing was said. */
export const travelText = (travel) => (travelStated(travel) ? travel.text || null : null);
