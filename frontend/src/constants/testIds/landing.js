// Test IDs for the public home page. Naming follows the directive in ./auth.js
// (keys camelCase, values kebab-case `<feature>-<element>[-<qualifier>]`).
//
// Ids that shipped before keep their exact values — `landing-page`,
// `hero-heading`, `hero-cta-brand` and the rest — so anything already written
// against them keeps finding the same control, even where the element around
// it has changed.

export const LANDING = {
	page: 'landing-page',
};

// The eight sections, in order. A section is addressed by what it is for,
// not by its position, so reordering the page doesn't rewrite anyone's test.
export const LANDING_PAGE = {
	page: 'landing-page',
	swap: 'compare-section',
	band: 'landing-band',
	steps: 'landing-steps',
	step: (i) => `landing-step-${i}`,
	stepTag: 'landing-step-tag',
	promises: 'landing-promises',
	promise: (i) => `landing-promise-${i}`,
	clients: 'landing-clients',
	client: (i) => `landing-client-${i}`,
	creatorDoor: 'landing-creator-door',
	creatorDoorCta: 'landing-creator-door-cta',
};

export const LANDING_HERO = {
	section: 'hero-section',
	eyebrow: 'hero-eyebrow',
	heading: 'hero-heading',
	line: 'hero-line',
	stepsList: 'hero-steps-list',
	ctaBrand: 'hero-cta-brand',
	ctaTalk: 'hero-cta-talk',

	// The deck. Slides are addressed by index rather than by their step, so
	// reordering the deck doesn't rewrite anyone's test.
	slides: 'hero-slides',
	slide: (i) => `hero-slide-${i}`,
	rail: 'hero-rail',
	railStep: (i) => `hero-rail-step-${i}`,
	railMarker: 'hero-rail-marker',
};

// "A campaign is not a spreadsheet and sixty DMs" — the band under the hero.
export const LANDING_COMPARE = {
	section: 'compare-section',
	title: 'compare-title',
	today: 'compare-today',
	here: 'compare-here',
};

export const LANDING_CLOSING = {
	section: 'closing-cta',
	ctaBrand: 'closing-cta-brand',
	ctaTalk: 'closing-cta-talk',
};
