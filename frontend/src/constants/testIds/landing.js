// Test IDs for the public home page. Naming follows the directive in ./auth.js
// (keys camelCase, values kebab-case `<feature>-<element>[-<qualifier>]`).
//
// Ids that shipped before this file existed keep their exact values —
// `landing-page`, `hero-heading`, `hero-cta-brand` and the rest — so anything
// already written against them keeps finding the same control, even where the
// element around it has changed.
//
// Home is a router now rather than the whole pitch, so several groups here
// describe sections that moved to their own pages. Their ids live in
// `marketing.js` with the pages that own them; what is left is what home
// still renders.

export const LANDING = {
	page: 'landing-page',
};

export const LANDING_PAGE = {
	page: 'landing-page',
	problem: 'landing-problem-section',
	// The two image slots. Home was the only marketing page with none — the
	// audience pages carry two each and /why-weare four — so the strongest
	// claim on the site was three lines of type with nothing beside them.
	problemImage: 'landing-problem-image',
	bandImage: 'landing-band-image',
	promise: 'landing-promise',
	howItWorksLink: 'landing-how-it-works-link',
};

export const LANDING_HERO = {
	section: 'hero-section',
	eyebrow: 'hero-eyebrow',
	heading: 'hero-heading',
	// The active step's support line. The rotating line above it is `line`.
	subheading: 'hero-subheading',
	line: 'hero-line',
	// The four lines as a static, visually-hidden list — what a screen reader
	// gets instead of copy that changes every six seconds.
	stepsList: 'hero-steps-list',
	kicker: 'hero-kicker',
	ctaBrand: 'hero-cta-brand',
	ctaCreator: 'hero-cta-creator',

	// The deck. Slides are addressed by step index, and at most two are ever
	// mounted — `hero-slides` carries `data-mounted` with the count.
	slides: 'hero-slides',
	slide: (i) => `hero-slide-${i}`,
	// 01 Offer · 02 Agree · 03 Deliver · 04 Get paid.
	rail: 'hero-rail',
	railStep: (i) => `hero-rail-step-${i}`,
	progress: 'hero-progress',
	// The three-claim strip at the foot of the hero.
	claims: 'hero-claims',
	claim: (i) => `hero-claim-${i}`,
};

// "A campaign is not a spreadsheet and sixty DMs", directly under the hero.
export const LANDING_COMPARE = {
	section: 'compare-section',
	title: 'compare-title',
	today: 'compare-today',
	here: 'compare-here',
	link: 'compare-link',
};

export const LANDING_CLOSING = {
	section: 'closing-cta',
};

