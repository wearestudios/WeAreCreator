// When a creator gets paid, what a barter brief is actually offering, and
// whether getting there is covered. Naming follows the directive in ./auth.js.
//
// One set for one renderer: the same `PayoutNote` is on the brief a creator
// reads before applying, the manager's brief panel and the brand's own form
// preview, so an id that varied by surface would be three ids for one fact.
export const PAYOUT = {
	note: 'payout-note',
	promise: 'payout-promise',
	due: 'payout-due',
	travel: 'payout-travel',
	barter: 'payout-barter',

	// The brand's own controls on the post form.
	barterInput: 'campaign-barter-description',
	travelToggle: 'campaign-travel-allowance',
	travelAmount: 'campaign-travel-allowance-amount',

	// The platform default, in the admin's settings section.
	setting: 'setting-creator-payout-days',

	// The prompt on a delivery brief for a creator with no address saved.
	addressPrompt: 'delivery-address-prompt',
};
