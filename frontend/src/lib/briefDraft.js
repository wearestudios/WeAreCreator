// What the brief writer's draft does to the form, decided in one pure place.
//
// The server returns API-shaped fields (`budget_per_creator: 5000`); the form
// holds its own shapes (`"5000"` in a text box). `toFormValue` converts one
// into the other, and `planDraft` decides which fields a draft may write:
//
// - **A field the brand has edited is never overwritten silently.** "Edited"
//   means its value is neither what the page started with nor what the last
//   draft put there. Those fields come back as `conflicts`, and the form asks
//   before replacing them — which is what makes Regenerate safe to press.
// - **A field still holding the AI's value is the AI's to replace**, and is the
//   one that carries the "AI draft" marker. Typing in it makes it the brand's,
//   and the marker goes, with no handler needed: the value simply stops
//   matching.

// The fields a draft can fill, with the label the confirmation names.
export const DRAFT_FIELDS = {
    title: "Campaign title",
    brief: "Brief",
    campaign_type: "Kind of campaign",
    category: "Category",
    deliverable_items: "Deliverables",
    budget_per_creator: "Budget per creator",
    total_budget: "Total budget",
    creators_needed: "Creators needed",
    revisions_included: "Revisions included",
    event_date: "Which day",
    event_time: "Start time",
    start_date: "Start date",
    end_date: "End date",
    brief_dos: "Do's",
    brief_donts: "Don'ts",
    mandatory_hashtags: "Hashtags",
    mandatory_mentions: "Accounts to tag",
    caption_guidance: "Caption",
    required_disclosure: "Disclosure",
    compensation_type: "How it pays",
    venue_address: "Venue address",
    area: "Area",
};

const NUMBER_FIELDS = new Set(["budget_per_creator", "total_budget", "creators_needed", "revisions_included"]);

/** One API value in the form's own shape. */
export function toFormValue(key, value) {
    if (value === null || value === undefined) return value === null && key === "compensation_type" ? null : "";
    if (NUMBER_FIELDS.has(key)) return String(value);
    if (key === "deliverable_items") {
        return Object.fromEntries(value.map((i) => [i.type, i.quantity]));
    }
    return value;
}

export function sameValue(a, b) {
    return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/** Deliverables are an object of counts with zeros in it; compare only the
 * counts somebody asked for. */
function normalise(key, value) {
    if (key === "deliverable_items" && value && typeof value === "object") {
        return Object.fromEntries(Object.entries(value).filter(([, n]) => Number(n) > 0).sort());
    }
    return value;
}

export function isAiValue(key, current, aiValues) {
    return key in aiValues && sameValue(normalise(key, current[key]), normalise(key, aiValues[key]));
}

export function isEdited(key, current, baseline, aiValues) {
    const now = normalise(key, current[key]);
    if (sameValue(now, normalise(key, baseline?.[key]))) return false;
    if (key in aiValues && sameValue(now, normalise(key, aiValues[key]))) return false;
    return true;
}

/**
 * What a draft writes.
 *
 * @param fields   the server's `fields`, API-shaped
 * @param current  the form now, keyed like `DRAFT_FIELDS`, in form shapes
 * @param baseline the form as the page first rendered it
 * @param aiValues what the previous draft wrote, in form shapes
 * @param allowed  optional `{ key: (value) => boolean }` — e.g. an area the
 *                 select cannot show is skipped rather than set
 * @returns `{ apply, conflicts }`: `apply` is safe to write now; `conflicts`
 *          are edited fields the draft would change, to confirm first.
 */
export function planDraft({ fields, current, baseline, aiValues = {}, allowed = {} }) {
    const apply = {};
    const conflicts = [];
    for (const [key, raw] of Object.entries(fields || {})) {
        if (!(key in DRAFT_FIELDS)) continue;
        const value = toFormValue(key, raw);
        if (allowed[key] && !allowed[key](value)) continue;
        if (sameValue(normalise(key, current[key]), normalise(key, value))) {
            apply[key] = value;
            continue;
        }
        if (isEdited(key, current, baseline, aiValues)) conflicts.push(key);
        else apply[key] = value;
    }
    return { apply, conflicts };
}
