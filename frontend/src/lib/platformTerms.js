// Keeping the work on the platform, and what a creator gets for it.
//
// Mirrors `CIRCUMVENTION_TERMS`, `CIRCUMVENTION_REASONS`,
// `CIRCUMVENTION_REASON_LABELS` and `PLATFORM_PROTECTIONS` in
// `backend/server.py`; a unit test fails if they drift — the same arrangement
// `followerTiers.js` and `shootWindows.js` use, for the same reason: the
// clause appears on the signup screen *before* any account exists to fetch a
// profile for, so it cannot be served, and two copies with nothing holding
// them together is how a rule ends up worded one way in the thing somebody
// agreed to and another way in the thing they are held to.
//
// `PLATFORM_PROTECTIONS` is here as a fallback only — the creator dashboard
// receives it from the server, which is the authority.

export const CIRCUMVENTION_TERMS =
    "Work introduced through WeAre Creators stays on WeAre Creators. If a " +
    "brand you met through a brief here asks you to arrange payment or " +
    "scheduling directly with them, outside the platform, say no and tell us. " +
    "Taking a collaboration off-platform means losing your account — and with " +
    "it the paid briefs, the fee agreed in writing before you shoot, the " +
    "payment protection, the dispute cover and the delivery record you have " +
    "built up. This is the one rule here that ends an account.";

// What somebody flagging a suspected off-platform deal is reporting. A short
// list rather than free text, because the reason is what the review queue
// sorts on; the evidence note beside it is where the detail goes.
export const CIRCUMVENTION_REASONS = [
    { value: "direct_payment", label: "Payment arranged directly with the brand" },
    { value: "direct_scheduling", label: "Shoot arranged directly with the brand" },
    { value: "asked_to_go_offline", label: "Asked the brand to take it off the platform" },
    { value: "brand_reports_it", label: "The brand told us it went off-platform" },
    { value: "other", label: "Something else" },
];

export const PLATFORM_PROTECTIONS = [
    {
        key: "fee_in_writing",
        title: "Your fee, agreed before you shoot",
        detail:
            "The number is recorded against the collaboration with a name and " +
            "a date on it, so there is nothing to argue about afterwards.",
    },
    {
        key: "payment_protection",
        title: "Payment follows approved delivery",
        detail:
            "Once your content is approved the payment is ours to chase, not " +
            "yours. You keep 100% of the fee — it sits on the brand.",
    },
    {
        key: "dispute_cover",
        title: "Somebody neutral if it goes wrong",
        detail:
            "If a brand refuses delivered work or the money stalls, you can " +
            "raise a dispute and a person here decides it. The record — every " +
            "note, every date — is what it gets decided on.",
    },
    {
        key: "reliability_record",
        title: "A delivery record that travels",
        detail:
            "Every brief you finish on time builds a record brands can see. " +
            "It is why the next brief comes, and it only exists here.",
    },
    {
        key: "brief_flow",
        title: "Briefs that keep arriving",
        detail:
            "Paid work from checked brands, ranked against your profile, " +
            "without you chasing any of it.",
    },
];

export function circumventionReasonLabel(value) {
    return (CIRCUMVENTION_REASONS.find((r) => r.value === value) || {}).label || value;
}
