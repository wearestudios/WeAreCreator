// Which date fields each campaign type carries.
//
// Mirrored from `_SCHEDULING_BY_TYPE` in server.py, and a unit test fails if
// the two drift — the same arrangement `followerTiers.js`, `shootWindows.js`,
// `deliverables.js` and `campaignTerms.js` use. Two copies is how a form asks
// for a field the server refuses, which is a 422 the person filling it in
// cannot do anything about.
//
// **Only the date fields.** `restricted_days` and `shoot_windows` also live in
// the server's table, and the post form already branches on them by hand; this
// exists for the surfaces that need to edit *dates* on an existing brief —
// today the admin's edit dialog, which is where the health panel's "extend the
// dates" has to land.

export const SCHEDULING_DATE_FIELDS = {
	// One evening. `event_date` carries the hour as well as the day, because
	// the day and the time are one arrangement.
	launch: ['event_date'],
	// A day, and a timetable of sittings on it.
	group_event: ['event_date'],
	// A window the creator picks a time inside.
	personal_table: ['start_date', 'end_date'],
};

export const SCHEDULING_DATE_LABELS = {
	event_date: 'Date',
	start_date: 'Runs from',
	end_date: 'Runs until',
};

/**
 * The date fields this campaign carries.
 *
 * **An unknown type gets both shapes rather than none.** Campaigns predate
 * types, and returning `[]` would make every historical brief un-editable on
 * exactly the screen support uses to fix one — the same absent-reads-safe rule
 * `_scheduling_refusal` holds when it declines to check an unknown type.
 */
export function schedulingDateFields(campaign) {
	const type = campaign?.campaign_type;
	if (type && SCHEDULING_DATE_FIELDS[type]) return SCHEDULING_DATE_FIELDS[type];
	return ['event_date', 'start_date', 'end_date'];
}
