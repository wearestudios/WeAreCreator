// Every word the public pages render, and nothing else.
//
// **Components hold layout; this file holds copy.** A page that needs a
// sentence reads it from here, so the copy can be rewritten — by somebody who
// is not going to open a component — without a layout change riding along,
// and so the word budget and the claim checks in `test_marketing_pages.py`
// have one place to read rather than a JSX tree to walk.
//
// Two rules for whoever edits it:
//
//   - **Every claim has to be one the product keeps.** The tests read this
//     file against the server: a promise about money, verification or
//     contact details is pinned to the code that makes it true, and a claim
//     whose mechanism is not in the tree is refused rather than shipped.
//   - **Invented names only** in anything drawn as product UI. A real
//     company's name inside a mock screen on a public page reads as an
//     endorsement it never gave.

/**
 * The platform fee a brand pays on each agreed collaboration, as a percentage
 * of the creator's fee.
 *
 * **This is a pricing decision, not a layout value.** It is `null` because
 * nobody has decided the published figure, and a made-up percentage on a
 * pricing card is a promise somebody will be held to on an invoice. While it
 * is `null` the card says the fee is shown before the brand accepts — which
 * is true today: the rate applied to a campaign is on the brand's own
 * campaign before anybody is taken on. Set it here, once, when the figure is
 * agreed; every surface that quotes it reads this constant.
 */
export const PLATFORM_FEE_PERCENT = null;

/** What the pricing card says about the fee, decided in one place. */
export const FEE_PENDING_LABEL = "Shown before you accept";

export function platformFeeLabel(percent = PLATFORM_FEE_PERCENT) {
    if (percent === null || percent === undefined || Number.isNaN(Number(percent))) {
        return FEE_PENDING_LABEL;
    }
    return `${Number(percent)}% of the creator's fee`;
}
