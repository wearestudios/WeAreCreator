// The marketing site: home, the two audience pages, /how-it-works, /why-weare
// and the 404.

export const MARKETING = {
	// Page shells, one id each, so a test can assert it landed on the page it
	// asked for rather than on the SPA's catch-all.
	forBrands: 'for-brands-page',
	forCreators: 'for-creators-page',
	howItWorks: 'how-it-works-page',
	whyWeAre: 'why-weare-page',
	notFound: 'not-found-page',

	// Shared furniture.
	hero: 'marketing-hero',
	heroImage: 'marketing-hero-image',
	closing: 'marketing-closing',
	proof: 'marketing-proof',
	proofFigure: (key) => `marketing-proof-${key}`,

	// The one ask, stated twice per page.
	ctaTop: 'marketing-cta-top',
	ctaBottom: 'marketing-cta-bottom',

	// The two doors, on the pages that cannot know who arrived.
	twoPaths: 'marketing-two-paths',
	pathCreator: 'marketing-path-creator',
	pathBrand: 'marketing-path-brand',

	// Sections that a test names directly.
	valueProps: 'marketing-value-props',
	steps: 'marketing-steps',
	creatorTrack: 'how-it-works-creator-track',
	brandTrack: 'how-it-works-brand-track',
	trust: 'how-it-works-trust',
	pedigree: 'why-weare-pedigree',
	choice: 'why-weare-choice',
};
