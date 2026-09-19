/**
 * The one claim, and the three checkable facts under it.
 *
 * **It leads with what only we do.** Every competitor books a creator; we run
 * the campaign. The hero used to say "Your creator campaigns, handled
 * properly", which described the same thing and made the reader work out what
 * it meant — a headline that explains rather than lands, and one a brand
 * cannot repeat back. This one is sayable in a breath and is a claim about the
 * product rather than an adjective about it.
 *
 * **Every proof point is checkable**, which is the standard the marketing
 * pages are already held to: a brand can ask to see how a creator was
 * verified, ask for the rate in writing, and read the refund rule before it
 * signs anything. Nothing here is a feeling.
 *
 * Mirrored from `CAMPAIGN_CLAIM` / `CAMPAIGN_PROOF_POINTS` in
 * `backend/server.py`, with a drift test — the arrangement `followerTiers.js`,
 * `shootWindows.js` and `platformTerms.js` use. Two copies because the React
 * hero renders it before there is anything to fetch and the server-rendered
 * search pages render it with no bundle at all; two copies of a *promise*,
 * left unchecked, is how a company ends up with two promises.
 *
 * The positioning is unchanged: the thing we are against is disorganisation,
 * never agencies. `_FORBIDDEN_MARKETING_PHRASES` still governs every word.
 */

export const CAMPAIGN_CLAIM = "We run the campaign, not just the booking.";

export const CAMPAIGN_PROOF_POINTS = [
    {
        label: "Verified creators",
        line:
            "Every creator is checked before a brand ever sees them — the account, " +
            "the audience and the work.",
    },
    {
        label: "The rate, agreed in writing",
        line:
            "Settled before anyone shoots, so nothing is argued about three weeks " +
            "later.",
    },
    {
        label: "The campaign fee comes back",
        line:
            "If we cannot fill your brief, you get the fee back. The one exception " +
            "is creators you turn down.",
    },
];
