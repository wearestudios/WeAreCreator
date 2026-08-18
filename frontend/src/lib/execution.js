/**
 * Who runs a campaign — the one place the two words are spelled.
 *
 * `execution_owner` decides where applications are routed, so it is not
 * decoration: a creator reads it to know whose WhatsApp they will be on, a
 * brand reads it to know whether the applicant board is their work or ours,
 * and an admin filters on it. Three audiences, three different sentences about
 * the same field, so the copy lives here rather than being retyped per screen.
 *
 * Mirrors EXECUTION_OWNERS on the server, and like `_execution_owner` there,
 * anything unrecognised — including a campaign written before the field
 * existed — reads as "brand" rather than as an empty badge.
 */

export const EXECUTION_OWNERS = ["brand", "weare"];

export const DEFAULT_EXECUTION_OWNER = "brand";

export const EXECUTION_META = {
    brand: {
        label: "Brand-run",
        // Who the creator deals with, in the creator's own terms.
        creatorLabel: "Run by the brand",
        creatorNote:
            "You'll deal with the brand directly — they review applications and run the day.",
        brandNote: "You're running this one. Applications come to you.",
        adminNote: "The brand runs this. Applications go to their manager.",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    weare: {
        label: "WeAre-run",
        creatorLabel: "Run by WeAre",
        creatorNote:
            "WeAre runs this one. We review applications, book your slot and settle the payment.",
        brandNote: "WeAre is running this. Applications go to our team, and you're kept posted.",
        adminNote: "Ours to run. Applications come to the assigned manager.",
        tone: "bg-ember-500/15 text-ember-500 border-ember-500/40",
    },
};

/** The one reader. Never returns undefined, so a badge always has a word. */
export const executionOwner = (campaign) => {
    const value =
        typeof campaign === "string" ? campaign : campaign?.execution_owner;
    return EXECUTION_OWNERS.includes(value) ? value : DEFAULT_EXECUTION_OWNER;
};

export const executionMeta = (campaign) => EXECUTION_META[executionOwner(campaign)];

export const isWeareRun = (campaign) => executionOwner(campaign) === "weare";

/** Options for a picker, in the order a brand should read them. */
export const EXECUTION_OPTIONS = [
    {
        value: "brand",
        label: "We'll run it ourselves",
        hint: "Applications come to you. You accept creators, agree the fee and run the day.",
    },
    {
        value: "weare",
        label: "Hand it to the WeAre team",
        hint: "We review applications, book the creators and manage the shoot. You still see everything.",
    },
];

/** Filter options for the campaign lists, with the "no filter" entry first. */
export const EXECUTION_FILTERS = [
    { value: "all", label: "Anyone" },
    { value: "brand", label: "Brand-run" },
    { value: "weare", label: "WeAre-run" },
];
