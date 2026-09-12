// The campaign budget cap, and the off-platform rule. Naming follows the
// directive in ./auth.js.

// Total, committed and remaining on a brief. One component on four surfaces —
// the brand's applicant board, the admin campaign page, the manager's
// campaign page and the shared application screen — so the ids do not vary by
// who is looking.
export const BUDGET = {
	meter: 'campaign-budget-meter',
	total: 'campaign-budget-total',
	committed: 'campaign-budget-committed',
	remaining: 'campaign-budget-remaining',
	bar: 'campaign-budget-bar',
	warning: 'campaign-budget-warning',
	exhausted: 'campaign-budget-exhausted',

	// The cap on the post form and the admin's edit dialog.
	input: 'campaign-total-budget-input',
	// The override an admin types when going past the cap deliberately.
	overrideOpen: 'campaign-budget-override-open',
	overrideReason: 'campaign-budget-override-reason',
	overrideSubmit: 'campaign-budget-override-submit',
};

// Work that went off-platform: the rule, the flag, and the review queue.
export const CIRCUMVENTION = {
	// The clause itself, wherever it is read — signup, and the terms card.
	terms: 'circumvention-terms',
	// What a creator gets by staying, on their own dashboard.
	protections: 'platform-protections',
	protection: (key) => `platform-protection-${key.replace(/_/g, '-')}`,

	// Flagging a collaboration, from the shared application screen.
	report: 'circumvention-report',
	reportOpen: 'circumvention-report-open',
	reportReason: 'circumvention-report-reason',
	reportEvidence: 'circumvention-report-evidence',
	reportSubmit: 'circumvention-report-submit',
	reportPending: 'circumvention-report-pending',

	// The admin queue.
	queue: 'circumvention-queue',
	row: (id) => `circumvention-row-${id}`,
	confirm: (id) => `circumvention-confirm-${id}`,
	dismiss: (id) => `circumvention-dismiss-${id}`,
	empty: 'circumvention-empty',
};
