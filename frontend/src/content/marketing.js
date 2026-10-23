// Every word the public pages render, and nothing else.
//
// **Components hold layout; this file holds copy.** A page reads every
// sentence from here, so copy can be rewritten by somebody who is not going to
// open a component, and the word budgets and the claim checks have one place
// to read rather than a JSX tree to walk.
//
// Three rules for whoever edits it:
//
//   - **A value nobody knows yet is `null`, and `null` hides its element in
//     production** — the line, the card, the FAQ item or the section. Never a
//     placeholder, never "TBC": a visitor who reads "TBC" on a pricing card
//     has learned that we have not decided what to charge them. `<Known>`
//     (components/marketing/Known.jsx) is the one way a page renders a
//     maybe-null value, so the rule is a component rather than a habit.
//   - **Every claim has to be one the product keeps.** The tests read this
//     file against the server: a promise about money, verification or contact
//     details is pinned to the code that makes it true, and a claim whose
//     mechanism is not in the tree is refused rather than shipped.
//   - **Invented names only** in anything drawn as product UI. Real client
//     names appear in exactly one place — `confirmedClients`, rendered only by
//     the home page's "who built it" section.

/**
 * Facts the pages depend on that are not copy. Each is either known or
 * `null`, and a `null` hides whatever would have shown it.
 */
export const FACTS = {
    /**
     * The platform fee a brand pays on each agreed collaboration, as a
     * percentage of the creator's fee.
     *
     * **A pricing decision, not a layout value.** `null` because nobody has
     * decided the published figure, and a made-up percentage on a pricing
     * card is a promise somebody will be held to on an invoice. While it is
     * `null` the percentage is simply not printed; the card's own sentence
     * ("shown before you accept") is true without it, because the rate applied
     * to a campaign is on the brand's own campaign before anybody is taken on.
     * Never invent a figure here.
     */
    platformFeePercent: null,

    /** "What should I budget?" — ranges per creator size. A pricing decision
     * too; the whole block is hidden until it is set. */
    budgetRangesByCreatorSize: null,

    /** A count of verified creators. A number on a public page is a claim a
     * stranger can check, so it is shown only once somebody sets it. */
    verifiedCreatorCount: null,

    /** `true` once it is confirmed brands receive a GST invoice; the FAQ item
     * that says so renders only then. Never `false` — unconfirmed is `null`. */
    gstInvoiceConfirmed: null,

    /**
     * Real clients we may name, in the order they appear. These three are
     * confirmed; anybody else is unconfirmed and therefore absent. Rendered
     * only in the home page's "who built it" section and its marquee.
     */
    confirmedClients: ["The Brew Factory", "9889", "The Rameshwaram Cafe"],
};

/** True for a value a page may show. `0` and `false` are values; `null` and
 * `undefined` are not. */
export function known(value) {
    return value !== null && value !== undefined;
}

/** The percentage, formatted, or `null` while undecided. */
export function platformFeeText(percent = FACTS.platformFeePercent) {
    if (!known(percent) || Number.isNaN(Number(percent))) return null;
    return `${Number(percent)}% of the creator's fee`;
}
