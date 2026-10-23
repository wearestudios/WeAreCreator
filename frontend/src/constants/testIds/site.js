// Test IDs for the two audience pages, /for-brands and /for-creators, and the
// parts they share. Naming follows
// the directive in ./auth.js.

export const BRANDS_PAGE = {
	page: 'brands-page',
	hero: 'brands-hero',
	ctaTop: 'brands-cta-top',
	ctaTalkTop: 'brands-cta-talk-top',
	ctaBottom: 'brands-cta-bottom',
	ctaTalkBottom: 'brands-cta-talk-bottom',
	shortlist: 'brands-shortlist',
	shortlistRow: (i) => `brands-shortlist-row-${i}`,
	pricing: 'brands-pricing',
	pricingCard: (key) => `brands-pricing-${key}`,
	fee: 'brands-pricing-fee',
	budget: 'brands-budget',
	report: 'brands-report',
	band: 'brands-band',
	promises: 'brands-promises',
	compare: 'brands-compare',
	compareCards: 'brands-compare-cards',
	faq: 'brands-faq',
	faqItem: (i) => `brands-faq-${i}`,
	close: 'brands-close',
};

export const CREATORS_PAGE = {
	page: 'creators-page',
	hero: 'creators-hero',
	chips: 'creators-chips',
	ctaTop: 'creators-cta-top',
	ctaHow: 'creators-cta-how',
	ctaBottom: 'creators-cta-bottom',
	briefs: 'creators-briefs',
	money: 'creators-money',
	moneyAmount: 'creators-money-amount',
	moneyState: (i) => `creators-money-state-${i}`,
	protections: 'creators-protections',
	band: 'creators-band',
	payouts: 'creators-payouts',
	record: 'creators-record',
	close: 'creators-close',
};

export const SITE_PARTS = {
	sectionRule: (n) => `section-rule-${n}`,
	stickyCta: 'sticky-cta',
	stickyCtaButton: 'sticky-cta-button',
};
