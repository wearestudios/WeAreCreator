// What a brief actually offers, and how to say it.
//
// Three kinds, and only two of them are a brand's to choose:
//
//   fixed       the budget is the fee
//   negotiated  the budget is a guide; the number is agreed offline
//   barter      no money — a meal, a stay, a product
//
// Barter is arranged by WeAre and refused on every brand write path
// (`_refuse_brand_barter` in server.py). This file is the frontend half of that
// rule: BRAND_COMPENSATION_OPTIONS is what the post-campaign form renders, and
// it does not contain barter, so there is no option to hide, disable or leak.
// The admin form uses ALL_COMPENSATION_OPTIONS.

/** The full set. Admin-facing only. */
export const ALL_COMPENSATION_OPTIONS = [
    {
        value: "fixed",
        label: "Fixed fee",
        blurb: "The budget below is what each creator is paid.",
    },
    {
        value: "negotiated",
        label: "Negotiated",
        blurb: "A guide price. You agree the real number with each creator.",
    },
    {
        value: "barter",
        label: "Barter",
        blurb: "No fee — a meal, a stay or a product. WeAre only.",
    },
];

/**
 * What a brand may post. Derived from the full list rather than written out
 * again, so a fourth kind added above cannot silently appear here — it has to
 * be named in BRAND_ALLOWED first, which is a decision about who can post it.
 */
const BRAND_ALLOWED = ["fixed", "negotiated"];
export const BRAND_COMPENSATION_OPTIONS = ALL_COMPENSATION_OPTIONS.filter((o) =>
    BRAND_ALLOWED.includes(o.value),
);

export const DEFAULT_COMPENSATION_TYPE = "fixed";

/** Campaigns written before the field existed were all paid, fixed-fee briefs. */
export const compensationType = (campaign) =>
    campaign?.compensation_type || DEFAULT_COMPENSATION_TYPE;

export const isBarter = (campaign) => compensationType(campaign) === "barter";

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : null;

/**
 * The fee as a creator should read it.
 *
 * A barter brief still carries whatever budget it was posted with — an admin
 * converting a paid campaign doesn't erase the figure, so that reverting isn't
 * lossy. That makes rendering `budget_per_creator` unconditionally a lie, which
 * is exactly the failure this whole feature exists to prevent. Every surface
 * that shows money goes through here.
 *
 * @returns {{ text: string, amount: string|null, suffix: string|null, isBarter: boolean }}
 *   `text` is the whole thing for a one-line slot. `amount`/`suffix` are for
 *   the places that set the rupee figure in a larger type size.
 */
export function formatCompensation(campaign, { per = null } = {}) {
    const kind = compensationType(campaign);
    const tail = per ? ` ${per}` : "";

    if (kind === "barter") {
        return { text: "Barter", amount: null, suffix: null, isBarter: true };
    }

    const rupees = formatRupees(campaign?.budget_per_creator);
    if (rupees == null) {
        return { text: "—", amount: null, suffix: null, isBarter: false };
    }
    // "up to" rather than a bare figure: on a negotiated brief the budget is a
    // ceiling somebody will argue about, and showing it as a fee sets up the
    // conversation to feel like a cut.
    const suffix = kind === "negotiated" ? "negotiable" : null;
    return {
        text: `₹${rupees}${tail}${suffix ? ` · ${suffix}` : ""}`,
        amount: rupees,
        suffix,
        isBarter: false,
    };
}

/** The short label for a chip or a meta row. */
export const compensationLabel = (campaign) =>
    ALL_COMPENSATION_OPTIONS.find((o) => o.value === compensationType(campaign))?.label ||
    "Fixed fee";
