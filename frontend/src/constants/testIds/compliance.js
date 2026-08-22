// The unhappy paths: a dispute, a takedown, a verification that ran out, a
// suspension, and an invoice nobody paid. Naming follows the directive in
// ./auth.js.

// A dispute, read by all three parties and acted on by two of them. The panel
// is one component on every surface, so the ids do not vary by console.
export const DISPUTE = {
	panel: 'dispute-panel',
	open: 'dispute-open',
	reason: 'dispute-reason',
	submit: 'dispute-submit',
	cancel: 'dispute-cancel',
	withdraw: 'dispute-withdraw',
	// The mediator's half.
	resolve: 'dispute-resolve',
	resolution: (key) => `dispute-resolution-${key}`,
	resolveAmount: 'dispute-resolve-amount',
	resolveNote: 'dispute-resolve-note',
	resolveSubmit: 'dispute-resolve-submit',
	// The queue.
	queue: 'admin-disputes-page',
	row: (id) => `admin-dispute-row-${id}`,
	empty: 'admin-disputes-empty',
};

// Asking for a live post to come down, and the creator's answer.
export const TAKEDOWN = {
	panel: 'takedown-panel',
	open: 'takedown-open',
	reason: (code) => `takedown-reason-${code}`,
	detail: 'takedown-detail',
	submit: 'takedown-submit',
	cancel: 'takedown-cancel',
	// The creator's side.
	respond: 'takedown-respond',
	actioned: 'takedown-actioned',
	declined: 'takedown-declined',
	note: 'takedown-note',
	respondSubmit: 'takedown-respond-submit',
};

// "It has been a while since we checked" — the same prompt on both profiles.
export const REVALIDATE = {
	prompt: 'revalidate-prompt',
	confirm: 'revalidate-confirm',
	expiry: 'revalidate-expiry',
};

// Accounts worth a person's attention, and the decision that follows.
export const SUSPENSION = {
	panel: 'admin-suspension-prompts',
	row: (id) => `admin-suspension-row-${id}`,
	suspend: (id) => `admin-suspension-suspend-${id}`,
	empty: 'admin-suspension-empty',
};

// What we keep, for how long, and what is still with a lawyer.
export const RETENTION = {
	page: 'admin-retention-page',
	row: (key) => `admin-retention-row-${key}`,
	purge: 'admin-retention-purge',
	legal: 'admin-retention-legal',
};

// Money owed to us: the invoice's three states, and the way past the block.
export const INVOICE = {
	state: 'invoice-state',
	set: (state) => `invoice-set-${state}`,
	overdue: 'invoice-overdue',
	override: 'brand-invoice-override',
	overrideReason: 'brand-invoice-override-reason',
	overrideSubmit: 'brand-invoice-override-submit',
	overrideClear: 'brand-invoice-override-clear',
};

// The console's numeric operating settings that are not SLA targets.
export const ADMIN_SETTINGS = {
	page: 'admin-settings-page',
	group: (key) => `admin-setting-${key}`,
	input: (key) => `admin-setting-input-${key}`,
	save: (key) => `admin-setting-save-${key}`,
};

// Verification papers, on the page where the decision is made.
export const BRAND_DOCS = {
	list: 'brand-documents',
	empty: 'brand-documents-empty',
	row: (id) => `brand-document-${id}`,
	toggle: (id) => `brand-document-toggle-${id}`,
	viewer: (id) => `brand-document-viewer-${id}`,
	status: (id) => `brand-document-status-${id}`,
	download: (id) => `brand-document-download-${id}`,
	accept: (id) => `brand-document-accept-${id}`,
	rejectOpen: (id) => `brand-document-reject-${id}`,
	rejectNote: (id) => `brand-document-reject-note-${id}`,
	rejectSubmit: (id) => `brand-document-reject-submit-${id}`,
};

// A brand that has stopped needing us to read every brief.
export const TRUST = {
	panel: 'brand-trust',
	revoke: 'brand-trust-revoke',
	restore: 'brand-trust-restore',
	reason: 'brand-trust-reason',
	submit: 'brand-trust-submit',
	autoBadge: (id) => `campaign-auto-published-${id}`,
	spotCheck: (id) => `campaign-spot-check-${id}`,
};

// Working a queue fifty rows at a time.
export const BULK = {
	bar: 'bulk-bar',
	select: (id) => `bulk-select-${id}`,
	selectAll: 'bulk-select-all',
	approve: 'bulk-approve',
	reject: 'bulk-reject',
	dialog: 'bulk-dialog',
	reason: 'bulk-reason',
	confirm: 'bulk-confirm',
	summary: 'bulk-summary',
};

// A pitch taken before we had checked the creator.
export const HELD = {
	panel: 'held-applications',
	row: (id) => `held-application-${id}`,
	cancel: (id) => `held-application-cancel-${id}`,
	outstanding: 'held-outstanding',
	notice: 'apply-holds-notice',
};

// Why a brief cannot go out yet, and when it stops waiting on us at all.
export const BRAND_PUBLISH = {
	gate: 'brand-publish-gate',
	gateLink: 'brand-publish-gate-link',
	trusted: 'brand-publish-trusted',
	slotToggle: 'pc-slot-confirmation',
};
