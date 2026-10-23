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

export const LANDING_PAGE = {
	page: 'landing-page',
	swap: 'compare-section',
	band: 'landing-band',
	how: 'landing-how',
	step: (key) => `landing-step-${key}`,
	stepTag: 'landing-step-tag',
	promises: 'landing-promises',
	promise: (i) => `landing-promise-${i}`,
	clients: 'landing-clients',
	clientMarquee: 'landing-client-marquee',
	clientCard: (i) => `landing-client-card-${i}`,
	fill: 'landing-fill',
	creatorDoor: 'landing-creator-door',
	creatorDoorCta: 'landing-creator-door-cta',
};

export const LANDING_HERO = {
	section: 'hero-section',
	eyebrow: 'hero-eyebrow',
	heading: 'hero-heading',
	accent: 'hero-accent',
	lead: 'hero-lead',
	note: 'hero-note',
	builtFor: 'hero-built-for',
	ctaBrand: 'hero-cta-brand',
	ctaTalk: 'hero-cta-talk',
	rail: 'hero-rail',
	railStep: (key) => `hero-rail-${key}`,
	card: 'hero-card',
	cardRow: (i) => `hero-card-row-${i}`,
};

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
