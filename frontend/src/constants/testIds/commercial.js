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
