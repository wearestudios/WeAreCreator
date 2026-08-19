// Test IDs for the public home page. Naming follows the directive in ./auth.js
// (keys camelCase, values kebab-case `<feature>-<element>[-<qualifier>]`).
//
// Ids that shipped before this file existed keep their exact values —
// `landing-page`, `hero-heading`, `hero-cta-brand`, `brand-cta`,
// `closing-cta` and the rest — so anything already written against them keeps
// finding the same control, even where the element around it has changed.

export const LANDING = {
	page: 'landing-page',
};

export const LANDING_HERO = {
	section: 'hero-section',
	eyebrow: 'hero-eyebrow',
	heading: 'hero-heading',
	subheading: 'hero-subheading',
	kicker: 'hero-kicker',
	ctaBrand: 'hero-cta-brand',
	ctaCreator: 'hero-cta-creator',
	managedLink: 'hero-managed-link',
	stats: 'hero-stats',
	stat: (key) => `hero-stat-${key}`,

	// The slider itself. Slides are addressed by index rather than by their
	// campaign type, so reordering the deck doesn't rewrite anyone's test.
	slides: 'hero-slides',
	slide: (i) => `hero-slide-${i}`,
	slideImage: (i) => `hero-slide-image-${i}`,
	dots: 'hero-dots',
	dot: (i) => `hero-dot-${i}`,
};

export const LANDING_REACH = {
	section: 'reach-section',
	note: 'reach-note',
	// Was `cities`/`city`. The column lists the categories briefs are posted
	// in; a list of eight city names read as a footprint we do not have.
	categories: 'reach-categories',
	category: (name) =>
		`reach-category-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`,
};

export const LANDING_SECTIONS = {
	howItWorks: 'how-it-works-section',
	step: (n) => `step-${n}`,
	howCtaCreator: 'how-cta-creator',
	liveBriefs: 'live-briefs-section',
	liveBrief: (id) => `live-brief-${id}`,
	liveBriefsCta: 'live-briefs-cta',
	why: 'why-section',
	forBrands: 'for-brands-section',
};

export const LANDING_CLOSING = {
	section: 'closing-cta',
	toggle: 'closing-toggle',
	toggleOption: (role) => `closing-toggle-${role}`,
	eyebrow: 'closing-eyebrow',
	heading: 'closing-heading',
	support: 'closing-support',
	// `closing-cta-btn` is the button whatever the toggle says; `brand-cta`
	// and `creator-cta` additionally mark which side is showing, so a test can
	// assert the toggle actually swapped the destination.
	button: 'closing-cta-btn',
	buttonBrand: 'brand-cta',
	buttonCreator: 'creator-cta',
	managedLink: 'managed-cta',
};

export const LANDING_STUDIO = {
	// The endorsement line. Present twice — once beside the nav logo, once in
	// the footer — so both get an id.
	nav: 'studio-endorsement-nav',
	navMobile: 'studio-endorsement-nav-mobile',
	footer: 'studio-endorsement-footer',
};

export const LANDING_FOOTER = {
	section: 'landing-footer',
	wordmark: 'landing-footer-wordmark',
};
