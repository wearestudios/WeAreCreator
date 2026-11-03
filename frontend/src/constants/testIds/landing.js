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
	promises: 'landing-promises',
	// "What the AI does", while at least one AI switch is on.
	ai: 'landing-ai',
	aiCard: (key) => `landing-ai-card-${key}`,
	promise: (i) => `landing-promise-${i}`,
	clients: 'landing-clients',
	fill: 'landing-fill',
	creatorDoor: 'landing-creator-door',
	creatorDoorCta: 'landing-creator-door-cta',
};

export const LANDING_HERO = {
	section: 'hero-section',
	heading: 'hero-heading',
	accent: 'hero-accent',
	lead: 'hero-lead',
	note: 'hero-note',
	ctaBrand: 'hero-cta-brand',
	ctaTalk: 'hero-cta-talk',
	card: 'hero-card',
	cardRow: (i) => `hero-card-row-${i}`,
	// The step deck in the card's place. `hero-slides` carries
	// `data-mounted`, which is never more than two.
	slides: 'hero-slides',
	slide: (i) => `hero-slide-${i}`,
	rail: 'hero-rail',
	railStep: (i) => `hero-rail-step-${i}`,
	progress: 'hero-progress',
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
