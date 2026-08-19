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

	// The marketing-only navbar. A variant of the shared one, so its ids are
	// its own — a test that asserts on `site-navbar` is asking about the
	// authenticated bar and must keep finding it.
	navbar: 'marketing-navbar',
	navLogo: 'marketing-nav-logo',
	navSignIn: 'marketing-nav-signin',
	navJoin: 'marketing-nav-join',
	navMenuButton: 'marketing-nav-menu-btn',
	navMenu: 'marketing-nav-menu',

	// The kinetic hero headline — the signature.
	kineticHeadline: 'marketing-kinetic-headline',
	kineticPhrase: 'marketing-kinetic-phrase',

	// Tilted photo cards floating behind the hero.
	floatingCards: 'marketing-floating-cards',
	floatingCard: (key) => `marketing-floating-card-${key}`,

	// The family handshake — the one place the studio palette appears.
	handshake: 'marketing-handshake',
	handshakeCta: 'marketing-handshake-cta',
	handshakeStudio: 'marketing-handshake-studio',

	// The scroll film — the campaign playing itself out.
	film: 'marketing-film',
	filmTrack: 'marketing-film-track',
	filmStage: 'marketing-film-stage',
	filmSteps: 'marketing-film-steps',
	filmPayout: 'marketing-film-payout',

	// Shared furniture.
	hero: 'marketing-hero',
	heroImage: 'marketing-hero-image',
	closing: 'marketing-closing',
	proof: 'marketing-proof',
	proofFigure: (key) => `marketing-proof-${key}`,
	proofReserve: 'marketing-proof-reserve',

	// The one ask, stated twice per page.
	ctaTop: 'marketing-cta-top',
	ctaBottom: 'marketing-cta-bottom',

	// The two doors, on the pages that cannot know who arrived.
	twoPaths: 'marketing-two-paths',
	pathCreator: 'marketing-path-creator',
	pathBrand: 'marketing-path-brand',

	// Sections that a test names directly.
	valueProps: 'marketing-value-props',
	point: 'marketing-point',
	steps: 'marketing-steps',
	creatorTrack: 'how-it-works-creator-track',
	brandTrack: 'how-it-works-brand-track',
	trust: 'how-it-works-trust',
	pedigree: 'why-weare-pedigree',
	choice: 'why-weare-choice',
};
