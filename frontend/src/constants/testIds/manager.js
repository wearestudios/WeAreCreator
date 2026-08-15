// Test IDs for the campaign manager interface. Naming follows the directive in
// ./auth.js (keys camelCase, values kebab-case `<feature>-<element>`).
//
// Row-scoped ids are builder functions, so a test can target one creator on a
// roster of forty.

export const MANAGER_HOME = {
	page: 'manager-home-page',
	heading: 'manager-home-heading',
	refresh: 'manager-home-refresh',
	skeleton: 'manager-home-skeleton',
	empty: 'manager-home-empty',
	list: 'manager-home-list',
	card: (id) => `manager-campaign-card-${id}`,
	cardType: (id) => `manager-campaign-type-${id}`,
	cardWhen: (id) => `manager-campaign-when-${id}`,
	cardSlots: (id) => `manager-campaign-slots-${id}`,
	cardCreators: (id) => `manager-campaign-creators-${id}`,
};

export const MANAGER_CAMPAIGN = {
	page: 'manager-campaign-page',
	skeleton: 'manager-campaign-skeleton',
	back: 'manager-campaign-back',
	title: 'manager-campaign-title',
	refresh: 'manager-campaign-refresh',
	tab: (key) => `manager-tab-${key}`,
	dayOfToggle: 'manager-day-of-toggle',
	broadcastOpen: 'manager-broadcast-open',
	daysheet: 'manager-daysheet-download',
};

export const MANAGER_ROSTER = {
	section: 'manager-roster-section',
	skeleton: 'manager-roster-skeleton',
	empty: 'manager-roster-empty',
	list: 'manager-roster-list',
	counts: 'manager-roster-counts',
	row: (id) => `manager-roster-row-${id}`,
	rowName: (id) => `manager-roster-name-${id}`,
	rowHandle: (id) => `manager-roster-handle-${id}`,
	rowTime: (id) => `manager-roster-time-${id}`,
	rowCall: (id) => `manager-roster-call-${id}`,
	rowStatus: (id) => `manager-roster-status-${id}`,
};

export const MANAGER_SLOTS = {
	section: 'manager-slots-section',
	skeleton: 'manager-slots-skeleton',
	empty: 'manager-slots-empty',
	list: 'manager-slots-list',
	add: 'manager-slot-add',
	row: (id) => `manager-slot-row-${id}`,
	rowFill: (id) => `manager-slot-fill-${id}`,
	rowEdit: (id) => `manager-slot-edit-${id}`,
	rowDelete: (id) => `manager-slot-delete-${id}`,
};

export const MANAGER_SLOT_EDITOR = {
	dialog: 'manager-slot-dialog',
	date: 'manager-slot-date',
	startTime: 'manager-slot-start-time',
	endTime: 'manager-slot-end-time',
	capacity: 'manager-slot-capacity',
	capacityMinus: 'manager-slot-capacity-minus',
	capacityPlus: 'manager-slot-capacity-plus',
	error: 'manager-slot-error',
	submit: 'manager-slot-submit',
	cancel: 'manager-slot-cancel',
};

export const MANAGER_DAY_OF = {
	section: 'manager-day-of-section',
	skeleton: 'manager-day-of-skeleton',
	empty: 'manager-day-of-empty',
	progress: 'manager-day-of-progress',
	filter: (key) => `manager-day-of-filter-${key}`,
	row: (id) => `manager-day-of-row-${id}`,
	checkIn: (id) => `manager-day-of-check-in-${id}`,
	noShow: (id) => `manager-day-of-no-show-${id}`,
	reschedule: (id) => `manager-day-of-reschedule-${id}`,
	call: (id) => `manager-day-of-call-${id}`,
	done: (id) => `manager-day-of-done-${id}`,
};

export const MANAGER_NO_SHOW = {
	sheet: 'manager-no-show-sheet',
	note: 'manager-no-show-note',
	error: 'manager-no-show-error',
	submit: 'manager-no-show-submit',
	cancel: 'manager-no-show-cancel',
};

export const MANAGER_RESCHEDULE = {
	sheet: 'manager-reschedule-sheet',
	empty: 'manager-reschedule-empty',
	option: (id) => `manager-reschedule-option-${id}`,
	reason: 'manager-reschedule-reason',
	error: 'manager-reschedule-error',
	submit: 'manager-reschedule-submit',
	cancel: 'manager-reschedule-cancel',
};

export const MANAGER_BROADCAST = {
	sheet: 'manager-broadcast-sheet',
	message: 'manager-broadcast-message',
	count: 'manager-broadcast-count',
	review: 'manager-broadcast-review',
	confirm: 'manager-broadcast-confirm',
	back: 'manager-broadcast-back',
	cancel: 'manager-broadcast-cancel',
	error: 'manager-broadcast-error',
	report: 'manager-broadcast-report',
	reportRow: (id) => `manager-broadcast-report-${id}`,
	done: 'manager-broadcast-done',
};

export const MANAGER_VENUE = {
	section: 'manager-venue-section',
	address: 'manager-venue-address',
	map: 'manager-venue-map',
	instructions: 'manager-venue-instructions',
	contact: 'manager-venue-contact',
	contactCall: 'manager-venue-contact-call',
	empty: 'manager-venue-empty',
};
