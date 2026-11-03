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
};

export const LANDING_HERO = {
	section: 'hero-section',
	// The slider's region, which carries aria-roledescription="carousel".
	carousel: 'hero-carousel',
	badge: 'hero-ai-badge',
	heading: 'hero-heading',
	accent: 'hero-accent',
	lead: 'hero-lead',
	note: 'hero-note',
	ctaBrand: 'hero-cta-brand',
	ctaTalk: 'hero-cta-talk',
	// Slide A's deal card, and its rows.
	card: 'hero-card',
	cardRow: (i) => `hero-card-row-${i}`,
	// The stage carries `data-mounted`, which is never more than two.
	slides: 'hero-slides',
	slide: (i) => `hero-slide-${i}`,
	visual: (i) => `hero-visual-${i}`,
	tabs: 'hero-tabs',
	tab: (i) => `hero-tab-${i}`,
	progress: 'hero-progress',
};
