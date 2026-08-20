// How a creator gets paid, in one vocabulary.
//
// Mirrors `PayoutMethod` and `PAYOUT_METHOD_FIELDS` in `server.py`, the same
// arrangement `followerTiers.js` and `shootWindows.js` use — one copy each
// side and a unit test that fails if they drift.
//
// **The method is a stored answer, not something inferred from which boxes
// are full.** Inferring it would make a half-typed account number read as
// "they want UPI", and a creator who switched from one to the other would
// carry both sets of details with nothing saying which is current — so an
// accounts payable run would have to guess.

export const PAYOUT_METHODS = [
    {
        value: "upi",
        label: "UPI",
        hint: "Fastest. Usually the same day.",
    },
    {
        value: "bank",
        label: "Bank transfer",
        hint: "Account number and IFSC. One to two working days.",
    },
];

export const PAYOUT_METHOD_VALUES = PAYOUT_METHODS.map((m) => m.value);

/** The readable name, falling back to nothing rather than to a guess. */
export const payoutMethodLabel = (value) =>
    PAYOUT_METHODS.find((m) => m.value === value)?.label || "";

/**
 * What the creator still has to fill in, in the same words the server uses.
 *
 * The server is the authority — `payout_missing` rides on the profile
 * response — and this exists so a form can grey a button before a round trip
 * rather than instead of one.
 */
export const PAYOUT_REQUIRED = {
    upi: ["payout_upi"],
    bank: ["payout_account_name", "payout_account_number", "payout_ifsc"],
};

export const payoutReady = (profile) => {
    const method = profile?.payout_method || (profile?.payout_upi ? "upi" : null);
    if (!method) return false;
    return (
        (PAYOUT_REQUIRED[method] || []).every((f) => profile?.[f]) &&
        Boolean(profile?.pan)
    );
};
