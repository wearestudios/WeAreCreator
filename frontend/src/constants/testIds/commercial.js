// What we charge, and what comes back. Naming follows the directive in
// ./auth.js.

// The commission rate (on a brand and on a campaign), the flat campaign fee,
// and the refund decision. One component serves the brand page and the
// campaign page, so the ids do not vary by which record is being priced.
export const COMMERCIAL = {
	commission: 'commission-control',
	commissionEffective: 'commission-effective',
	commissionInput: 'commission-input',
	commissionReason: 'commission-reason',
	commissionSave: 'commission-save',

	fee: 'campaign-fee-panel',
	feeInput: 'campaign-fee-input',
	feeReason: 'campaign-fee-reason',
	feeSave: 'campaign-fee-save',

	// The refund reckoning, and the decision somebody makes against it.
	refund: 'campaign-refund',
	refundReason: 'campaign-refund-reason',
	refundReasonInput: 'campaign-refund-reason-input',
	refundConfirm: 'campaign-refund-confirm',
	refundDecline: 'campaign-refund-decline',
	refundDecided: 'campaign-refund-decided',
	refundOverridden: 'campaign-refund-overridden',
};

// Barter is opt-in for a creator's feed. The label is on every barter card and
// invitation; the switch lives on the feed, where the choice is made.
export const BARTER = {
	label: (id) => `barter-label-${id}`,
	feedToggle: 'barter-feed-toggle',
	feedToggleNote: 'barter-feed-toggle-note',
};

// The revision cap: "1 of 2 used" on both sides, the reviewer's request for an
// extra round past it, and the creator's answer.
export const REVISIONS = {
	block: (id) => `revisions-${id}`,
	used: (id) => `revisions-used-${id}`,
	none: (id) => `revisions-none-left-${id}`,
	askExtra: (id) => `revisions-ask-extra-${id}`,
	pending: (id) => `revisions-extra-pending-${id}`,
	accept: (id) => `revisions-extra-accept-${id}`,
	decline: (id) => `revisions-extra-decline-${id}`,
	briefField: 'brief-revisions-included',
	briefShown: 'campaign-revisions-included',
};
