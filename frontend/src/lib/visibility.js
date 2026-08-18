// Campaign visibility, in words.
//
// The frontend half of `_campaign_visibility` in backend/server.py: the same
// two values, the same absent-means-public default, so a card drawn from a
// pre-field document says "Public" rather than nothing. The server enforces
// who sees what; this file only decides what the words are.

export const VISIBILITY_OPTIONS = [
    {
        value: "public",
        label: "Public",
        hint: "Every verified creator can find and pitch on this brief.",
    },
    {
        value: "private",
        label: "Invite-only",
        hint: "Hidden from browse and search. Only creators you invite can see it or apply.",
    },
];

export const campaignVisibility = (campaign) =>
    campaign?.visibility === "private" ? "private" : "public";

export const isPrivate = (campaign) => campaignVisibility(campaign) === "private";

export const visibilityLabel = (campaign) =>
    isPrivate(campaign) ? "Invite-only" : "Public";
