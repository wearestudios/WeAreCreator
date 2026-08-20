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
	// The drawers below the live work.
	tabs: 'creator-home-tabs',
	tab: (v) => `creator-home-tab-${v}`,
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
	followersVerified: 'stat-source-verified',
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
	withdraw: (id) => `creator-application-withdraw-${id}`,
	withdrawDialog: 'creator-withdraw-dialog',
	withdrawReason: 'creator-withdraw-reason',
	withdrawError: 'creator-withdraw-error',
	withdrawSubmit: 'creator-withdraw-submit',
	withdrawCancel: 'creator-withdraw-cancel',
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

	// Invitations. Being asked and asking are the same conversation, so they
	// live in the same view — an invitation that lives only in a WhatsApp
	// message is one a creator cannot find again.
	invitationList: 'creator-invitations-list',
	invitation: (id) => `creator-invitation-${id}`,
	invitationAccept: (id) => `creator-invitation-accept-${id}`,
	invitationDecline: (id) => `creator-invitation-decline-${id}`,
	invitationNote: (id) => `creator-invitation-note-${id}`,
	invitationDialog: 'creator-invitation-dialog',
	invitationRate: 'creator-invitation-rate',
	invitationPitch: 'creator-invitation-pitch',
	invitationSubmit: 'creator-invitation-submit',
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

// The profile builder. Signup asks for a name and a number, so everything else
// lives here — filled in over as many sittings as it takes. Ids that shipped
// with the old single-shot onboarding form keep their exact values, so tests
// written against them still find the same control.
export const CREATOR_ONBOARDING = {
	facebook: 'creator-onboarding-facebook',
	about: 'creator-onboarding-about',
	page: 'creator-onboarding-page',
	skeleton: 'onboarding-skeleton',
	error: 'onboarding-error',
	ring: 'onboarding-completeness-ring',
	percent: 'onboarding-completeness-percent',
	missing: 'onboarding-completeness-missing',
	missingItem: (field) => `onboarding-missing-${field}`,
	section: (key) => `onboarding-section-${key}`,

	name: 'onboarding-name-input',
	email: 'onboarding-email-input',
	city: 'onboarding-city-input',
	address: 'onboarding-address-input',
	fullAddress: 'onboarding-full-address-input',

	genres: 'onboarding-genres-editor',
	genresInput: 'onboarding-genres-input',
	genreChip: (value) => `genre-chip-${value}`,
	genreSuggest: (value) => `genre-suggest-${value}`,

	niches: 'onboarding-niches-editor',
	nichesInput: 'onboarding-niches-input',
	nicheChip: (value) => `niche-chip-${value}`,
	nicheSuggest: (value) => `niche-suggest-${value}`,

	platform: (value) => `onboarding-platform-${value}`,
	igHandle: 'onboarding-ig-handle-input',
	igUrl: 'onboarding-ig-url-input',
	youtube: 'onboarding-youtube-input',

	baseRate: 'onboarding-base-rate-input',
	followers: 'onboarding-followers-input',

	photoPreview: 'onboarding-photo-preview',
	photoInput: 'onboarding-photo-input',
	photoUpload: 'onboarding-photo-upload-btn',
	photoRemove: 'onboarding-photo-remove-btn',
	photoError: 'onboarding-photo-error',

	upi: 'onboarding-upi-input',
	payoutName: 'onboarding-payout-name-input',
	pan: 'onboarding-pan-input',
	payoutMethod: (value) => `onboarding-payout-method-${value}`,
	payoutAccount: 'onboarding-payout-account-input',
	payoutIfsc: 'onboarding-payout-ifsc-input',
	gstin: 'onboarding-gstin-input',

	save: 'onboarding-save-btn',
	submit: 'onboarding-submit-btn',
	submitBlocked: 'onboarding-submit-blocked',
	later: 'onboarding-later-link',
	statusNote: 'onboarding-status-note',
};

// The Instagram connection. Official stats via "Instagram API with Instagram
// Login" — the connect button, its disabled state while the Meta app is in
// review, and the guidance for creators still on a personal account.
export const CREATOR_INSTAGRAM = {
	card: 'creator-instagram-card',
	skeleton: 'creator-instagram-skeleton',
	status: 'creator-instagram-status',
	connect: 'creator-instagram-connect',
	unavailable: 'creator-instagram-unavailable',
	username: 'creator-instagram-username',
	badge: 'creator-instagram-verified-badge',
	stat: (key) => `creator-instagram-stat-${key}`,
	updated: 'creator-instagram-updated',
	refresh: 'creator-instagram-refresh',
	disconnect: 'creator-instagram-disconnect',
	stale: 'creator-instagram-stale',
	reconnect: 'creator-instagram-reconnect',
	error: 'creator-instagram-error',
	notProfessional: 'creator-instagram-not-professional',
	scopes: 'creator-instagram-scopes',
};

export const CREATOR_INSTAGRAM_CALLBACK = {
	page: 'creator-instagram-callback-page',
	working: 'creator-instagram-callback-working',
	success: 'creator-instagram-callback-success',
	error: 'creator-instagram-callback-error',
	notProfessional: 'creator-instagram-callback-not-professional',
	retry: 'creator-instagram-callback-retry',
	back: 'creator-instagram-callback-back',
};
