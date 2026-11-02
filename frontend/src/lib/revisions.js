// How many rounds of changes a brief includes. Mirrors
// `DEFAULT_REVISIONS_INCLUDED` / `REVISIONS_INCLUDED_MIN` / `_MAX` in
// server.py; `test_site_promises.py` fails if the two drift.
//
// A round is a send-back — a draft or live content returned for changes —
// and the number is frozen into the terms when a creator is taken on. Past
// it the reviewer can ask for one extra round, which the creator accepts or
// declines. See `_revision_allowance` on the server.
export const DEFAULT_REVISIONS_INCLUDED = 2;
export const REVISIONS_INCLUDED_MIN = 0;
export const REVISIONS_INCLUDED_MAX = 5;

/** "2 rounds of changes included", for the brief a creator reads. */
export function revisionsIncludedText(n) {
    const value = Number.isInteger(n) ? n : DEFAULT_REVISIONS_INCLUDED;
    if (value === 0) return "No rounds of changes included";
    return `${value} ${value === 1 ? "round" : "rounds"} of changes included`;
}
