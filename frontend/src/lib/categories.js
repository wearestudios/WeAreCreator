// The categories a campaign and a brand can be in.
//
// One list. It was written out twice — on the brand's onboarding form and on
// the campaign form — and a third copy was about to be typed for the admin's
// create dialog, which is the point at which two copies become a fact nobody
// can check. The values mirror `CATEGORY_LITERAL` in `server.py` and a unit
// test fails if the two drift, the same arrangement `followerTiers.js` and
// `shootWindows.js` use.
//
// The labels are ours: "fnb" is a database value and "F&B" is what a person
// reads, and the mapping between them is not something a formatter should be
// guessing at.
export const CATEGORY_OPTIONS = [
    { value: "fnb", label: "F&B" },
    { value: "hospitality", label: "Hospitality" },
    { value: "retail", label: "Retail" },
    { value: "real_estate", label: "Real Estate" },
    { value: "fashion", label: "Fashion" },
    { value: "travel", label: "Travel" },
    { value: "wellness", label: "Wellness" },
    { value: "lifestyle", label: "Lifestyle" },
];

export const CATEGORY_VALUES = CATEGORY_OPTIONS.map((c) => c.value);

/** The readable name, falling back to the stored value rather than to blank. */
export const categoryLabel = (value) =>
    CATEGORY_OPTIONS.find((c) => c.value === value)?.label || value || "";
