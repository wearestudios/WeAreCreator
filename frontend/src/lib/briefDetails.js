// The structured half of a brief, mirrored from `BRIEF_LIST_FIELDS` /
// `BRIEF_TEXT_FIELDS` in server.py. A unit test fails if the two drift — the
// same arrangement `followerTiers.js`, `shootWindows.js` and
// `campaignTerms.js` use, for the same reason: two copies is how a field
// renders under the wrong heading.

// The list fields, in the order the checklist draws them. Do's before don'ts
// because a brief reads as what to make rather than what to avoid; the tags
// after both because they are the mechanical part.
export const BRIEF_LIST_FIELDS = {
	brief_dos: "Do",
	brief_donts: "Don't",
	mandatory_hashtags: 'Hashtags',
	mandatory_mentions: 'Accounts to tag',
};

export const BRIEF_TEXT_FIELDS = { caption_guidance: 'Caption' };

// A sentence under each heading, for the brand filling the form in. Absent
// from the checklist itself — a creator reading "Do" does not need it
// explained, and the explanations are what make a checklist unreadable.
export const BRIEF_FIELD_HINTS = {
	brief_dos: 'Things that have to be in the content.',
	brief_donts: 'Things that must not appear.',
	mandatory_hashtags: 'Typed with or without the #.',
	mandatory_mentions: 'Handles the post has to tag.',
	caption_guidance: 'What the caption should say, in a line or two.',
};

export const MAX_BRIEF_LIST_ITEMS = 12;
export const MAX_BRIEF_ASSETS = 8;

// The sigil each list is stored with, so what the form shows and what the
// server writes are the same string.
export const BRIEF_SIGILS = { mandatory_hashtags: '#', mandatory_mentions: '@' };

/** Every field the structured half carries, in render order. */
export const BRIEF_DETAIL_FIELDS = [
	...Object.keys(BRIEF_LIST_FIELDS),
	...Object.keys(BRIEF_TEXT_FIELDS),
	'brand_assets',
];

/**
 * How many checkable things a brief carries.
 *
 * **Zero means render nothing.** An empty "What to check" heading reads as a
 * brand that had nothing to say rather than as a question nobody was asked —
 * the same rule `ShootWindowNote` holds.
 */
export function briefChecklistCount(details) {
	if (!details) return 0;
	let n = 0;
	for (const key of Object.keys(BRIEF_LIST_FIELDS)) n += (details[key] || []).length;
	if (details.caption_guidance) n += 1;
	return n;
}

/** Whether there is anything at all to draw, assets included. */
export function hasBriefDetails(details) {
	return briefChecklistCount(details) > 0 || (details?.brand_assets || []).length > 0;
}

/** Normalise one typed line the way the server will, so the form shows the
 * value that gets stored rather than the one that was typed. */
export function normaliseBriefLine(field, value) {
	const line = String(value || '').replace(/\s+/g, ' ').trim();
	const sigil = BRIEF_SIGILS[field];
	if (!sigil) return line;
	const bare = line.replace(/^[#@\s]+/, '').trim();
	return bare ? `${sigil}${bare}` : '';
}
