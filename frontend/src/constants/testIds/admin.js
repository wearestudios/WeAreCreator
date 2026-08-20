// Test IDs for the admin console. Naming follows the directive in ./auth.js
// (keys camelCase, values kebab-case `<feature>-<element>[-<qualifier>]`).
//
// Ids that identify a specific row carry the record id, so they are exported as
// builder functions rather than strings — the value shape is the same either
// way, e.g. `admin-creator-tile-64b7f9a2c3d4e5f6a7b8c9d0`.

export const ADMIN_SHELL = {
	page: 'admin-console-page',
	heading: 'admin-heading',
	nav: 'admin-nav',
	navItem: (key) => `admin-nav-${key}`,
	navBadge: (key) => `admin-nav-badge-${key}`,
	mobileNavOpen: 'admin-nav-mobile-open',
	mobileNav: 'admin-nav-mobile',
	section: (key) => `admin-section-${key}`,
};

export const ADMIN_TABS = {
	nav: 'admin-tabs',
	tab: (key) => `admin-tab-${key}`,
	badge: (key) => `admin-tab-badge-${key}`,
};

// The four detail routes. Each is its own URL, so these identify a page rather
// than a panel that happens to be open.
export const COMMAND_PALETTE = {
	trigger: 'admin-search-trigger',
	dialog: 'admin-search-dialog',
	input: 'admin-search-input',
	hint: 'admin-search-hint',
	empty: 'admin-search-empty',
	group: (key) => `admin-search-group-${key}`,
	result: (id) => `admin-search-result-${id}`,
};

// The view-as banner lives above the router, so it is not an admin-only id in
// the routing sense — but it is only ever an admin who sees it.
export const IMPERSONATION = {
	banner: 'impersonation-banner',
	who: 'impersonation-who',
	stop: 'impersonation-stop',
	start: (id) => `impersonation-start-${id}`,
};

export const BREADCRUMBS = {
	nav: 'admin-breadcrumbs',
	crumb: (key) => `admin-breadcrumb-${key}`,
};

export const PERFORMANCE = {
	rollup: 'admin-performance-rollup',
	stat: (key) => `admin-performance-stat-${key}`,
	note: 'admin-performance-note',
	empty: 'admin-performance-empty',
	// One collaboration's reading.
	panel: 'admin-performance-panel',
	fetch: 'admin-performance-fetch',
	edit: 'admin-performance-edit',
	dialog: 'admin-performance-dialog',
	input: (metric) => `admin-performance-input-${metric}`,
	submit: 'admin-performance-submit',
	source: 'admin-performance-source',
	// Report + showcase.
	reportCsv: 'admin-report-csv',
	reportPrint: 'admin-report-print',
	showcase: 'admin-showcase-toggle',
	showcaseFilter: 'admin-campaigns-filter-showcase',
	showcaseBadge: (id) => `admin-campaign-showcase-${id}`,
};

export const ADMIN_HEALTH = {
	section: 'admin-health-section',
	skeleton: 'admin-health-skeleton',
	allClear: 'admin-health-all-clear',
	check: (key) => `admin-health-check-${key}`,
	checkCount: (key) => `admin-health-count-${key}`,
	item: (id) => `admin-health-item-${id}`,
	more: (key) => `admin-health-more-${key}`,
	// A row's shortfall figures, and the ways out of the problem it names.
	shortfall: (id) => `admin-health-short-${id}`,
	action: (id, label) =>
		`admin-health-action-${id}-${String(label).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
	total: 'admin-health-total',
};

export const ADMIN_INTEL = {
	section: 'admin-intel-section',
	skeleton: 'admin-intel-skeleton',
	chart: (key) => `admin-intel-chart-${key}`,
	stat: (key) => `admin-intel-stat-${key}`,
};

export const ADMIN_EXPORTS = {
	section: 'admin-exports-section',
	kind: (key) => `admin-export-${key}`,
	dateFrom: 'admin-export-date-from',
	dateTo: 'admin-export-date-to',
	clearDates: 'admin-export-clear-dates',
	note: 'admin-export-note',
};

export const ADMIN_DETAIL = {
	back: 'admin-detail-back',
	skeleton: 'admin-detail-skeleton',
	error: 'admin-detail-error',
	notFound: 'admin-detail-not-found',
	title: 'admin-detail-title',
	section: (key) => `admin-detail-section-${key}`,
	stat: (key) => `admin-detail-stat-${key}`,
	action: (key) => `admin-detail-action-${key}`,
	timeline: 'admin-detail-timeline',
	timelineEvent: (id) => `admin-detail-timeline-${id}`,
	timelineEmpty: 'admin-detail-timeline-empty',
	auditRow: (id) => `admin-detail-audit-${id}`,
};

export const ADMIN_CAMPAIGN_PAGE = {
	page: 'admin-campaign-page',
	status: 'admin-campaign-page-status',
	brandLink: 'admin-campaign-page-brand',
	managerName: 'admin-campaign-page-manager',
	compensation: 'admin-campaign-page-compensation',
	slot: (id) => `admin-campaign-page-slot-${id}`,
	slotBooking: (id) => `admin-campaign-page-booking-${id}`,
	slotsEmpty: 'admin-campaign-page-slots-empty',
	applicant: (id) => `admin-campaign-page-applicant-${id}`,
	applicantGroup: (key) => `admin-campaign-page-group-${key}`,
	applicantsEmpty: 'admin-campaign-page-applicants-empty',
	payment: (id) => `admin-campaign-page-payment-${id}`,
	paymentsEmpty: 'admin-campaign-page-payments-empty',
};

export const ADMIN_CREATOR_PAGE = {
	page: 'admin-creator-page',
	instagram: 'admin-creator-page-instagram',
	youtube: 'admin-creator-page-youtube',
	collab: (id) => `admin-creator-page-collab-${id}`,
	collabGroup: (key) => `admin-creator-page-group-${key}`,
	booking: (id) => `admin-creator-page-booking-${id}`,
	bookingsEmpty: 'admin-creator-page-bookings-empty',
};

export const ADMIN_BRAND_PAGE = {
	resubmissions: 'admin-brand-page-resubmissions',
	page: 'admin-brand-page',
	manager: 'admin-brand-page-manager',
	document: (id) => `admin-brand-page-document-${id}`,
	documentsEmpty: 'admin-brand-page-documents-empty',
	campaign: (id) => `admin-brand-page-campaign-${id}`,
	campaignsEmpty: 'admin-brand-page-campaigns-empty',
};

export const ADMIN_COLLAB_PAGE = {
	page: 'admin-collab-page',
	creatorLink: 'admin-collab-page-creator',
	campaignLink: 'admin-collab-page-campaign',
	step: (state) => `admin-collab-page-step-${state}`,
	slot: 'admin-collab-page-slot',
	content: 'admin-collab-page-content',
	payment: 'admin-collab-page-payment',
};

export const ADMIN_OVERVIEW = {
	section: 'admin-overview-section',
	refresh: 'admin-overview-refresh',
	statsSkeleton: 'admin-overview-stats-skeleton',
	stats: 'admin-overview-stats',
	stat: (key) => `admin-overview-stat-${key}`,
	statClear: 'admin-overview-stat-clear',
	tableSkeleton: 'admin-overview-table-skeleton',
	table: 'admin-overview-table',
	empty: 'admin-overview-empty',
	count: 'admin-overview-count',
	filterBrand: 'admin-overview-filter-brand',
	filterStatus: 'admin-overview-filter-status',
	filterType: 'admin-overview-filter-type',
	filterDateFrom: 'admin-overview-filter-date-from',
	filterDateTo: 'admin-overview-filter-date-to',
	filterClear: 'admin-overview-filter-clear',
	sort: (key) => `admin-overview-sort-${key}`,
	row: (id) => `admin-overview-row-${id}`,
	rowApplied: (id) => `admin-overview-applied-${id}`,
	rowApproved: (id) => `admin-overview-approved-${id}`,
	rowRejected: (id) => `admin-overview-rejected-${id}`,
};

export const ADMIN_CAMPAIGN_DETAIL = {
	panel: 'admin-campaign-detail',
	skeleton: 'admin-campaign-detail-skeleton',
	back: 'admin-campaign-detail-back',
	title: 'admin-campaign-detail-title',
	column: (key) => `admin-campaign-column-${key}`,
	columnEmpty: (key) => `admin-campaign-column-empty-${key}`,
	columnCount: (key) => `admin-campaign-column-count-${key}`,
	creator: (id) => `admin-campaign-creator-${id}`,
	creatorAdvance: (id) => `admin-campaign-advance-${id}`,
	creatorDecline: (id) => `admin-campaign-decline-${id}`,
	creatorCancel: (id) => `admin-campaign-cancel-${id}`,
};

export const ADMIN_REVIEWS = {
	section: (kind) => `admin-reviews-${kind}-section`,
	refresh: (kind) => `admin-reviews-${kind}-refresh`,
	skeleton: (kind) => `admin-reviews-${kind}-skeleton`,
	empty: (kind) => `admin-reviews-${kind}-empty`,
	list: (kind) => `admin-reviews-${kind}-list`,
	count: (kind) => `admin-reviews-${kind}-count`,
	row: (id) => `admin-review-row-${id}`,
	expand: (id) => `admin-review-expand-${id}`,
	detail: (id) => `admin-review-detail-${id}`,
	// The way to the whole record. A queue row is a summary and a peek is a
	// preview; the decision needs the page.
	open: (id) => `admin-review-open-${id}`,
	approve: (id) => `admin-review-approve-${id}`,
	reject: (id) => `admin-review-reject-${id}`,
	instagram: (id) => `admin-review-instagram-${id}`,
	blockedNote: 'admin-reviews-blocked-note',
};

export const ADMIN_QUEUE = {
	section: 'admin-queue-section',
	refresh: 'admin-queue-refresh',
	skeleton: 'admin-queue-skeleton',
	empty: 'admin-queue-empty',
	list: 'admin-queue-list',
	count: 'admin-queue-count',
	stats: 'admin-queue-stats',
	filter: (kind) => `admin-queue-filter-${kind}`,
	showWaiting: 'admin-queue-show-waiting',
	waitingList: 'admin-queue-waiting-list',
	row: (id) => `admin-queue-row-${id}`,
	rowKind: (id) => `admin-queue-kind-${id}`,
	rowAge: (id) => `admin-queue-age-${id}`,
	rowPrimary: (id) => `admin-queue-primary-${id}`,
	rowSecondary: (id) => `admin-queue-secondary-${id}`,
	// The two decisions on a row. The pair above are the two lines of text —
	// they were named before the row had buttons of its own.
	rowPrimaryAction: (id) => `admin-queue-action-${id}`,
	rowSecondaryAction: (id) => `admin-queue-reject-${id}`,
};

export const ADMIN_CREATORS = {
	// The link that opens the record's own page.
	open: (id) => `admin-creators-open-${id}`,
	section: 'admin-creators-section',
	refresh: 'admin-creators-refresh',
	search: 'admin-creators-search',
	filterStatus: 'admin-creators-filter-status',
	filterNiche: 'admin-creators-filter-niche',
	filterArea: 'admin-creators-filter-area',
	filterClear: 'admin-creators-filter-clear',
	// The grid became a table. `tile(id)` is deliberately kept as the row's id
	// rather than replaced with a fresh one: anything already written against
	// "the element for creator X on the creator list" keeps finding it, which
	// is the promise a test id makes.
	table: 'admin-creators-table',
	rowStatus: (id) => `admin-creator-status-${id}`,
	grid: 'admin-creators-grid',
	empty: 'admin-creators-empty',
	skeleton: 'admin-creators-skeleton',
	count: 'admin-creators-count',
	pagination: 'admin-creators-pagination',
	pagePrev: 'admin-creators-page-prev',
	pageNext: 'admin-creators-page-next',
	pageLabel: 'admin-creators-page-label',
	tile: (id) => `admin-creator-tile-${id}`,
	tilePhoto: (id) => `admin-creator-photo-${id}`,
	tileMonogram: (id) => `admin-creator-monogram-${id}`,
	tileEarned: (id) => `admin-creator-earned-${id}`,
};

export const ADMIN_CREATOR_DETAIL = {
	drawer: 'admin-creator-drawer',
	skeleton: 'admin-creator-drawer-skeleton',
	close: 'admin-creator-drawer-close',
	name: 'admin-creator-drawer-name',
	lifetimeEarned: 'admin-creator-lifetime-earned',
	committed: 'admin-creator-committed',
	campaignsCompleted: 'admin-creator-campaigns-completed',
	group: (group) => `admin-creator-group-${group}`,
	groupEmpty: (group) => `admin-creator-group-empty-${group}`,
	collabRow: (id) => `admin-creator-collab-${id}`,
};

export const ADMIN_CAMPAIGNS = {
	// The link that opens the record's own page.
	open: (id) => `admin-campaigns-open-${id}`,
	section: 'admin-campaigns-section',
	refresh: 'admin-campaigns-refresh',
	search: 'admin-campaigns-search',
	filterBrand: 'admin-campaigns-filter-brand',
	filterStatus: 'admin-campaigns-filter-status',
	filterDateFrom: 'admin-campaigns-filter-date-from',
	filterDateTo: 'admin-campaigns-filter-date-to',
	filterClear: 'admin-campaigns-filter-clear',
	list: 'admin-campaigns-list',
	empty: 'admin-campaigns-empty',
	skeleton: 'admin-campaigns-skeleton',
	count: 'admin-campaigns-count',
	pagination: 'admin-campaigns-pagination',
	pagePrev: 'admin-campaigns-page-prev',
	pageNext: 'admin-campaigns-page-next',
	pageLabel: 'admin-campaigns-page-label',
	row: (id) => `admin-campaign-row-${id}`,
	expand: (id) => `admin-campaign-expand-${id}`,
	creators: (id) => `admin-campaign-creators-${id}`,
	creatorRow: (id) => `admin-campaign-creator-${id}`,
	creatorsEmpty: (id) => `admin-campaign-creators-empty-${id}`,
	inviteOpen: (id) => `admin-campaign-invite-${id}`,
	approve: (id) => `admin-campaign-approve-${id}`,
	reject: (id) => `admin-campaign-reject-${id}`,
	pause: (id) => `admin-campaign-pause-${id}`,
	resume: (id) => `admin-campaign-resume-${id}`,
	close: (id) => `admin-campaign-close-${id}`,
	edit: (id) => `admin-campaign-edit-${id}`,
	reviewReason: (id) => `admin-campaign-review-reason-${id}`,
};

export const ADMIN_CAMPAIGN_EDIT = {
	dialog: 'admin-campaign-edit-dialog',
	title: 'admin-campaign-edit-title',
	budget: 'admin-campaign-edit-budget',
	// The only control in the product that can set a campaign to barter.
	compensation: 'admin-campaign-edit-compensation',
	compensationOption: (value) => `admin-campaign-edit-compensation-${value}`,
	creatorsNeeded: 'admin-campaign-edit-creators-needed',
	deliverables: 'admin-campaign-edit-deliverables',
	error: 'admin-campaign-edit-error',
	submit: 'admin-campaign-edit-submit',
	cancel: 'admin-campaign-edit-cancel',
};

export const ADMIN_BRANDS = {
	// The link that opens the record's own page.
	open: (id) => `admin-brands-open-${id}`,
	section: 'admin-brands-section',
	refresh: 'admin-brands-refresh',
	search: 'admin-brands-search',
	filterStatus: 'admin-brands-filter-status',
	list: 'admin-brands-list',
	empty: 'admin-brands-empty',
	skeleton: 'admin-brands-skeleton',
	count: 'admin-brands-count',
	row: (id) => `admin-brand-row-${id}`,
	rowSpend: (id) => `admin-brand-spend-${id}`,
	rowStatus: (id) => `admin-brand-status-${id}`,
	rowReason: (id) => `admin-brand-reason-${id}`,
	verify: (id) => `admin-brand-verify-${id}`,
	reject: (id) => `admin-brand-reject-${id}`,
	unverify: (id) => `admin-brand-unverify-${id}`,
	viewCampaigns: (id) => `admin-brand-campaigns-${id}`,
};

export const ADMIN_AUDIT = {
	section: 'admin-audit-section',
	refresh: 'admin-audit-refresh',
	filterAction: 'admin-audit-filter-action',
	filterActor: 'admin-audit-filter-actor',
	filterDateFrom: 'admin-audit-filter-date-from',
	filterDateTo: 'admin-audit-filter-date-to',
	filterClear: 'admin-audit-filter-clear',
	table: 'admin-audit-table',
	// The horizontal scroller around the table, so a test can assert the
	// log scrolls inside itself rather than widening the page.
	scroll: 'admin-audit-scroll',
	skeleton: 'admin-audit-skeleton',
	empty: 'admin-audit-empty',
	count: 'admin-audit-count',
	row: (id) => `admin-audit-row-${id}`,
	rowAction: (id) => `admin-audit-action-${id}`,
	rowActor: (id) => `admin-audit-actor-${id}`,
	rowReason: (id) => `admin-audit-reason-${id}`,
	rowChange: (id) => `admin-audit-change-${id}`,
};

export const ADMIN_CONFIRM = {
	extraField: (name) => `admin-confirm-extra-${name}`,
	dialog: 'admin-confirm-dialog',
	title: 'admin-confirm-title',
	reason: 'admin-confirm-reason',
	extra: 'admin-confirm-extra',
	error: 'admin-confirm-error',
	submit: 'admin-confirm-submit',
	cancel: 'admin-confirm-cancel',
};

export const ADMIN_ADVANCE = {
	dialog: 'admin-advance-dialog',
	amount: 'admin-advance-amount-input',
	slot: 'admin-advance-slot-input',
	location: 'admin-advance-location-input',
	fee: 'admin-advance-fee-input',
	feeOverride: 'admin-advance-fee-override',
	error: 'admin-advance-error',
	submit: 'admin-advance-submit',
	cancel: 'admin-advance-cancel',
};

export const ADMIN_INVITE = {
	dialog: 'admin-invite-dialog',
	search: 'admin-invite-search',
	skeleton: 'admin-invite-skeleton',
	list: 'admin-invite-list',
	empty: 'admin-invite-empty',
	option: (id) => `admin-invite-option-${id}`,
	selectedCount: 'admin-invite-selected-count',
	note: 'admin-invite-note',
	submit: 'admin-invite-submit',
	cancel: 'admin-invite-cancel',
	report: 'admin-invite-report',
	reportRow: (id) => `admin-invite-report-${id}`,
	reportDone: 'admin-invite-report-done',
};

// --- The console's working surface ------------------------------------------
//
// The rebuild's own controls. Existing ids elsewhere in this file are
// untouched: anything already written against `admin-tab-*`, a row id or a
// dialog keeps finding the same control.

export const ADMIN_SIDEBAR = {
	root: 'admin-sidebar',
	item: (key) => `admin-nav-${key}`,
	badge: (key) => `admin-nav-badge-${key}`,
	collapse: 'admin-sidebar-collapse',
	savedFilter: (section, name) =>
		`admin-saved-filter-${section}-${String(name).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`,
};

export const ADMIN_TABLE = {
	root: 'admin-table',
	header: (key) => `admin-th-${key}`,
	row: (id) => `admin-row-${id}`,
	toolbar: 'admin-table-toolbar',
	saveFilter: 'admin-save-filter',
	saveFilterName: 'admin-save-filter-name',
	saveFilterConfirm: 'admin-save-filter-confirm',
};

export const ADMIN_PEEK = {
	root: 'admin-peek',
	close: 'admin-peek-close',
	openFull: 'admin-peek-open-full',
	action: (key) => `admin-peek-action-${key}`,
};

export const ADMIN_SHORTCUTS = {
	root: 'admin-shortcuts',
	open: 'admin-shortcuts-open',
};

// --- Our own staff, and the brands they run ---------------------------------

export const ADMIN_TEAM = {
	page: 'admin-team-page',
	row: (id) => `admin-team-row-${id}`,
	create: 'admin-team-create',
	name: 'admin-team-name',
	email: 'admin-team-email',
	password: 'admin-team-password',
	phone: 'admin-team-phone',
	submit: 'admin-team-submit',
	empty: 'admin-team-empty',
};

// On the brand's own page: who at WeAre runs it.
export const ADMIN_BRAND_TEAM = {
	section: 'admin-brand-team',
	member: (id) => `admin-brand-team-member-${id}`,
	remove: (id) => `admin-brand-team-remove-${id}`,
	picker: 'admin-brand-team-picker',
	assign: 'admin-brand-team-assign',
	empty: 'admin-brand-team-empty',
};

// Creating a record from the console: a brand, a creator, or a brief of ours.
export const ADMIN_CREATE = {
	brandOpen: 'admin-create-brand-open',
	brandDialog: 'admin-create-brand-dialog',
	brandName: 'admin-create-brand-name',
	brandManager: 'admin-create-brand-manager',
	brandDesignation: 'admin-create-brand-designation',
	brandPhone: 'admin-create-brand-phone',
	brandEmail: 'admin-create-brand-email',
	brandCategory: 'admin-create-brand-category',
	brandCity: 'admin-create-brand-city',

	creatorOpen: 'admin-create-creator-open',
	creatorDialog: 'admin-create-creator-dialog',
	creatorName: 'admin-create-creator-name',
	creatorPhone: 'admin-create-creator-phone',
	creatorHandle: 'admin-create-creator-handle',
	creatorCity: 'admin-create-creator-city',

	campaignOpen: 'admin-create-campaign-open',
	campaignDialog: 'admin-create-campaign-dialog',
	campaignBrand: 'admin-create-campaign-brand',
	campaignTitle: 'admin-create-campaign-title',
	campaignBrief: 'admin-create-campaign-brief',
	campaignDeliverables: 'admin-create-campaign-deliverables',
	campaignCompensation: 'admin-create-campaign-compensation',
	campaignBudget: 'admin-create-campaign-budget',
	campaignExecution: 'admin-create-campaign-execution',
	campaignCreatorsNeeded: 'admin-create-campaign-creators-needed',
	campaignCategory: 'admin-create-campaign-category',
	campaignArea: 'admin-create-campaign-area',
	campaignType: 'admin-create-campaign-type',
	campaignStatus: 'admin-create-campaign-status',
	campaignEventDate: 'admin-create-campaign-event-date',
	campaignStart: 'admin-create-campaign-start',
	campaignEnd: 'admin-create-campaign-end',

	submit: 'admin-create-submit',
	cancel: 'admin-create-cancel',
	error: 'admin-create-error',
};

// The scoped console's own chrome: which of your brands you are looking at.
export const ADMIN_BRAND_FILTER = {
	root: 'admin-brand-filter',
	option: (id) => `admin-brand-filter-option-${id}`,
	clear: 'admin-brand-filter-clear',
};

// Work that fell over, on the creator's page and the brand's.
export const ADMIN_CANCELLATIONS = {
	list: 'admin-cancellations-list',
	row: (id) => `admin-cancellation-row-${id}`,
	fee: (id) => `admin-cancellation-fee-${id}`,
};

// Who has gone quiet, and the two re-engagement lists.
export const ADMIN_DORMANT = {
	page: 'admin-dormant-page',
	tab: (kind) => `admin-dormant-tab-${kind}`,
	row: (id) => `admin-dormant-row-${id}`,
	empty: 'admin-dormant-empty',
	count: (kind) => `admin-dormant-count-${kind}`,
};

// Reusable briefs, and duplicating a past one.
export const CAMPAIGN_TEMPLATES = {
	picker: 'campaign-template-picker',
	option: (id) => `campaign-template-${id}`,
	use: (id) => `campaign-template-use-${id}`,
	remove: (id) => `campaign-template-remove-${id}`,
	save: 'campaign-template-save',
	saveName: 'campaign-template-name',
	saveSubmit: 'campaign-template-save-submit',
	duplicate: (id) => `campaign-duplicate-${id}`,
	empty: 'campaign-template-empty',
};

// Saved creator lists.
export const CREATOR_LISTS = {
	panel: 'creator-lists-panel',
	row: (id) => `creator-list-${id}`,
	create: 'creator-list-create',
	name: 'creator-list-name',
	submit: 'creator-list-submit',
	invite: (id) => `creator-list-invite-${id}`,
	remove: (id) => `creator-list-remove-${id}`,
	add: (listId) => `creator-list-add-${listId}`,
	empty: 'creator-lists-empty',
};
