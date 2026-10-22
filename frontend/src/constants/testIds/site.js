// Test IDs for the two audience pages, /brands and /creators. Naming follows
// the directive in ./auth.js.

export const BRANDS_PAGE = {
	page: 'brands-page',
	hero: 'brands-hero',
	ctaTop: 'brands-cta-top',
	ctaBottom: 'brands-cta-bottom',
	shortlist: 'brands-shortlist',
	shortlistRow: (i) => `brands-shortlist-row-${i}`,
	pricing: 'brands-pricing',
	pricingCard: (i) => `brands-pricing-card-${i}`,
	fee: 'brands-pricing-fee',
	band: 'brands-band',
	promises: 'brands-promises',
	compare: 'brands-compare',
	faq: 'brands-faq',
	faqItem: (i) => `brands-faq-${i}`,
	close: 'brands-close',
};

export const CREATORS_PAGE = {
	page: 'creators-page',
	hero: 'creators-hero',
	ctaTop: 'creators-cta-top',
	ctaBottom: 'creators-cta-bottom',
	brief: 'creators-brief',
	money: 'creators-money',
	moneyAmount: 'creators-money-amount',
	moneyState: (i) => `creators-money-state-${i}`,
	protections: 'creators-protections',
	band: 'creators-band',
	payout: 'creators-payout',
	record: 'creators-record',
	close: 'creators-close',
};
