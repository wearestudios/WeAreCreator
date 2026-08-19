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
	promise: 'landing-promise',
	howItWorksLink: 'landing-how-it-works-link',
};

export const LANDING_HERO = {
	section: 'hero-section',
	eyebrow: 'hero-eyebrow',
	heading: 'hero-heading',
	subheading: 'hero-subheading',
	kicker: 'hero-kicker',
	ctaBrand: 'hero-cta-brand',
	ctaCreator: 'hero-cta-creator',

	// The slider itself. Slides are addressed by index rather than by their
	// campaign type, so reordering the deck doesn't rewrite anyone's test.
	slides: 'hero-slides',
	slide: (i) => `hero-slide-${i}`,
	slideImage: (i) => `hero-slide-image-${i}`,
	dots: 'hero-dots',
	dot: (i) => `hero-dot-${i}`,
};

export const LANDING_CLOSING = {
	section: 'closing-cta',
};

export const LANDING_STUDIO = {
	// The endorsement line. Present beside the nav logo, in the mobile sheet,
	// in the footer and once at the foot of home — so each gets an id.
	nav: 'studio-endorsement-nav',
	navMobile: 'studio-endorsement-nav-mobile',
	footer: 'studio-endorsement-footer',
	landing: 'studio-endorsement-landing',
};
