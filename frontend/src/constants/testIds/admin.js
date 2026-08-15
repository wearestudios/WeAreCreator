// Test IDs for the admin console. Naming follows the directive in ./auth.js
// (keys camelCase, values kebab-case `<feature>-<element>[-<qualifier>]`).
//
// Ids that identify a specific row carry the record id, so they are exported as
// builder functions rather than strings — the value shape is the same either
// way, e.g. `admin-creator-tile-64b7f9a2c3d4e5f6a7b8c9d0`.
//
// The older sections of AdminConsole.jsx (verification queue, brand queue,
// collaborations board, audit trail) still use inline literals. Their ids are
// already wired into the automated test agent, so they were left alone rather
// than churned for consistency.

export const ADMIN_CREATORS = {
	section: 'admin-creators-section',
	refresh: 'admin-creators-refresh',
	search: 'admin-creators-search',
	filterStatus: 'admin-creators-filter-status',
	filterNiche: 'admin-creators-filter-niche',
	filterArea: 'admin-creators-filter-area',
	filterClear: 'admin-creators-filter-clear',
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
};

export const ADMIN_BRANDS_VIEW = {
	section: 'admin-brands-view-section',
	refresh: 'admin-brands-view-refresh',
	list: 'admin-brands-view-list',
	empty: 'admin-brands-view-empty',
	skeleton: 'admin-brands-view-skeleton',
	clear: 'admin-brands-view-clear',
	row: (id) => `admin-brand-card-${id}`,
	rowSpend: (id) => `admin-brand-spend-${id}`,
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
