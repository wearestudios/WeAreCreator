// Test IDs for the single-application screen, which the admin and the brand
// both open at their own routes off one component. Naming follows the
// directive in ./auth.js.

export const APPLICATION = {
	page: 'application-page',
	lifecycle: 'application-lifecycle',
	lifecycleStep: (state) => `application-lifecycle-step-${state}`,
	lifecycleExit: 'application-lifecycle-exit',
	nextAction: 'application-next-action',
	nextOwner: 'application-next-owner',

	creator: 'application-creator',
	campaign: 'application-campaign',
	// The way out to the two things this application is about. Both are
	// present on every console; only the destination differs.
	campaignLink: 'application-campaign-link',
	brandLink: 'application-brand-link',

	commercial: 'application-commercial',
	commercialQuoted: 'application-commercial-quoted',
	commercialAgreed: 'application-commercial-agreed',
	commercialType: 'application-commercial-type',
	amountInput: 'application-amount-input',
	amountLocked: 'application-amount-locked',
	amountBarter: 'application-amount-barter',
	amountError: 'application-amount-error',

	actions: 'application-actions',
	approveProfile: 'application-approve-profile',
	accept: 'application-accept',
	decline: 'application-decline',
	agreeCommercial: 'application-agree-commercial',
	advance: 'application-advance',
};
