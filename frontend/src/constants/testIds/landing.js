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
	subheading: 'hero-subheading',
	kicker: 'hero-kicker',
	ctaBrand: 'hero-cta-brand',
	ctaCreator: 'hero-cta-creator',

	// The slider itself. Slides are addressed by index rather than by their
	// campaign type, so reordering the deck doesn't rewrite anyone's test.
	slides: 'hero-slides',
	slide: (i) => `hero-slide-${i}`,
	slideImage: (i) => `hero-slide-image-${i}`,
	// Below `md` only — three thumbnails and a counter on a 390px screen is
	// clutter over the one place the headline has to be read.
	dots: 'hero-dots',
	dot: (i) => `hero-dot-${i}`,

	// The rail of upcoming frames, and the counter beside it, which replaced
	// the dots at `md` and up. Frames are addressed by the slide index they
	// go to rather than by their position in the rail: the position changes
	// every six seconds and the destination is what a test means.
	rail: 'hero-rail',
	railTrack: 'hero-rail-track',
	railFrame: (i) => `hero-rail-frame-${i}`,
	index: 'hero-index',
	progress: 'hero-progress',
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
