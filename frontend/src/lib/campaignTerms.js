// The disclosure labels and usage grants, mirrored from the server.
//
// `DISCLOSURE_LABELS` and `USAGE_RIGHTS` in `backend/server.py` are the
// originals and a unit test fails if these drift — the same arrangement
// `followerTiers.js`, `shootWindows.js` and `deliverables.js` use, for the
// same reason: two copies of a vocabulary is how a form ends up offering an
// option the API rejects.

/** What the content has to carry. Keyed exactly as the server stores it. */
export const DISCLOSURE_LABELS = {
	paid_partnership: 'Paid partnership label (platform tag)',
	ad: '#ad',
	sponsored: '#sponsored',
	collab: '#collab',
	gifted: '#gifted',
};

/** The safe answer when nobody has decided — every brief here is a material
 *  connection, so absent means disclose rather than skip. */
export const DEFAULT_DISCLOSURE = 'paid_partnership';

/** What the brand may do with the content afterwards. */
export const USAGE_RIGHTS = {
	organic_only: 'Organic repost only',
	paid_usage: 'Paid usage for a set period',
	full_buyout: 'Full buyout',
};

/** The narrowest grant, which is what a brief that never said anything gave. */
export const DEFAULT_USAGE_RIGHTS = 'organic_only';

/** The only grant that means nothing without a clock on it: a repost is a
 *  moment and a buyout is forever, but open-ended paid usage is a buyout
 *  wearing a smaller name. */
export const USAGE_NEEDS_DURATION = ['paid_usage'];

/** Whether this grant has to carry a period. */
export const needsDuration = (kind) => USAGE_NEEDS_DURATION.includes(kind);
