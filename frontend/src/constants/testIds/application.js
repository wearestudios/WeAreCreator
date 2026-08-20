// Test IDs for the single-application screen, which the admin and the brand
// both open at their own routes off one component. Naming follows the
// directive in ./auth.js.

export const APPLICATION = {
	// How long it has been in its current state, and whether that is too long.
	ageing: 'application-ageing',
	page: 'application-page',
	// The eight-stage process flow, on all three views of one application.
	process: 'application-process',
	processStage: (key) => `application-process-stage-${key}`,
	processToggle: 'application-process-toggle',
	processNext: 'application-process-next',
	processOwner: 'application-process-owner',
	processBanner: 'application-process-banner',

	// The booking handshake, offered to whoever runs the campaign.
	confirmSlot: 'application-confirm-slot',
	declineSlot: 'application-decline-slot',
	slotPending: 'application-slot-pending',
	declineSlotReason: 'application-decline-slot-reason',
	declineSlotSubmit: 'application-decline-slot-submit',

	// The record's readable name, on every view of it.
	reference: 'application-reference',

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
