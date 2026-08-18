// What the person registering a brand does there.
//
// Mirrors `CONTACT_ROLE_SUGGESTIONS` in `backend/server.py`; a unit test fails
// if they drift.
//
// **A suggestion list, not an enum.** `manager_designation` stays free text on
// the server, so every brand that signed up before this typed whatever they
// liked and their value still reads as a sentence in the console and in an
// export. The list exists to stop the next thousand being "mktg", "Mktg." and
// "marketing head" — narrowing what people type without invalidating what they
// already typed. That is also why "Other" opens a box rather than storing the
// word "Other", which tells a reviewer nothing.

export const CONTACT_ROLES = [
    "Owner",
    "Marketing Manager",
    "PR",
    "General Manager",
    "Operations",
    "Other",
];

export const OTHER_ROLE = "Other";

/** Which option a stored value should select. Anything unrecognised — every
 *  value typed before this list existed — lands on "Other" with the text
 *  intact, rather than silently resetting to blank. */
export function roleSelectionFor(value) {
    const text = (value || "").trim();
    if (!text) return { option: "", custom: "" };
    const known = CONTACT_ROLES.find(
        (r) => r !== OTHER_ROLE && r.toLowerCase() === text.toLowerCase(),
    );
    return known ? { option: known, custom: "" } : { option: OTHER_ROLE, custom: text };
}
