// Test IDs for the creator's home. Naming follows the directive in ./auth.js
// (keys camelCase, values kebab-case `<feature>-<element>[-<qualifier>]`).
//
// Anything that identifies one collaboration, campaign or slot carries its id,
// so these are exported as builder functions rather than strings — a creator
// with six live collaborations needs six addressable cards.

export const CREATOR_HOME = {
	page: 'dashboard-page',
	error: 'dashboard-error',
	skeleton: 'creator-home-skeleton',
	refresh: 'creator-home-refresh',
};

export const CREATOR_HERO = {
	section: 'creator-header',
	photo: 'creator-profile-image',
	monogram: 'creator-profile-monogram',
	name: 'creator-name-heading',
	handle: 'creator-ig-handle',
	handleEmpty: 'creator-ig-handle-empty',
	badge: (status) => `verification-badge-${status}`,
	followers: 'stat-followers',
	followersNote: 'stat-source-note',
	lifetime: 'creator-stat-lifetime',
	completed: 'creator-stat-completed',
	pending: 'creator-stat-pending',
	editProfile: 'header-edit-profile',
	browse: 'header-browse-campaigns',
};

export const CREATOR_COMPLETENESS = {
	section: 'creator-completeness-section',
	ring: 'creator-completeness-ring',
	percent: 'creator-completeness-percent',
	list: 'creator-completeness-list',
	item: (field) => `creator-completeness-missing-${field}`,
	cta: 'creator-completeness-cta',
};

export const CREATOR_ACTIVE = {
	section: 'creator-active-section',
	empty: 'creator-active-empty',
	list: 'creator-active-list',
	count: 'creator-active-count',
	card: (id) => `creator-active-card-${id}`,
	title: (id) => `creator-active-title-${id}`,
	amount: (id) => `creator-active-amount-${id}`,
	tracker: (id) => `creator-active-tracker-${id}`,
	stage: (id, key) => `creator-active-stage-${id}-${key}`,
	nextAction: (id) => `creator-active-next-${id}`,
	manager: (id) => `creator-active-manager-${id}`,
	call: (id) => `creator-active-call-${id}`,
	venue: (id) => `creator-active-venue-${id}`,
	slotTime: (id) => `creator-active-slot-${id}`,
	primary: (id) => `creator-active-action-${id}`,
	cancelSlot: (id) => `creator-active-cancel-slot-${id}`,
};

export const CREATOR_SLOT_PICKER = {
	dialog: 'creator-slot-dialog',
	skeleton: 'creator-slot-skeleton',
	error: 'creator-slot-error',
	empty: 'creator-slot-empty',
	window: 'creator-slot-window',
	list: 'creator-slot-list',
	option: (id) => `creator-slot-option-${id}`,
	spots: (id) => `creator-slot-spots-${id}`,
	calendar: 'creator-slot-calendar',
	timeList: 'creator-slot-times',
	// Keyed by epoch milliseconds — an ISO string would put colons and
	// dots in the id and break the kebab-case rule.
	time: (epochMs) => `creator-slot-time-${epochMs}`,
	review: 'creator-slot-review',
	summary: 'creator-slot-summary',
	back: 'creator-slot-back',
	confirm: 'creator-slot-confirm',
	cancel: 'creator-slot-cancel',
};

export const CREATOR_SUGGESTED = {
	section: 'creator-suggested-section',
	grid: 'creator-suggested-grid',
	empty: 'creator-suggested-empty',
	count: 'creator-suggested-count',
	tile: (id) => `creator-suggested-tile-${id}`,
	reason: (id) => `creator-suggested-reason-${id}`,
	budget: (id) => `creator-suggested-budget-${id}`,
	apply: (id) => `creator-suggested-apply-${id}`,
};

export const CREATOR_APPLICATIONS = {
	section: 'applications-section',
	empty: 'applications-empty',
	browse: 'applications-browse-link',
	list: 'creator-applications-list',
	count: 'creator-applications-count',
	row: (id) => `application-row-${id}`,
	state: (id) => `creator-application-state-${id}`,
	note: (id) => `creator-application-note-${id}`,
	declinedList: 'creator-declined-list',
	declinedRow: (id) => `creator-declined-row-${id}`,
	declinedBrowse: 'creator-declined-browse',
};

export const CREATOR_EARNINGS = {
	section: 'payments-section',
	empty: 'payments-empty',
	list: 'creator-earnings-list',
	paidTotal: 'creator-earnings-paid-total',
	pendingTotal: 'creator-earnings-pending-total',
	row: (id) => `payment-row-${id}`,
	rowAmount: (id) => `creator-earnings-amount-${id}`,
	rowState: (id) => `creator-earnings-state-${id}`,
};

export const CREATOR_SUBMIT_CONTENT = {
	open: (id) => `submit-content-btn-${id}`,
	dialog: 'submit-content-dialog',
	url: 'submit-content-url-input',
	urlAt: (i) => `submit-content-url-input-${i}`,
	remove: (i) => `submit-content-remove-${i}`,
	add: 'submit-content-add-url',
	error: 'submit-content-error',
	submit: 'submit-content-submit',
	cancel: 'submit-content-cancel',
};
