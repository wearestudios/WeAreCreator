// The site footer, on every marketing page.

export const FOOTER = {
	root: 'site-footer',
	wordmark: 'footer-wordmark',
	studio: 'footer-studio-endorsement',
	// Keyed on the destination rather than an index, so a test names the page
	// it is looking for instead of a position that reorders.
	link: (to) => `footer-link-${to.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '')}`,
	contact: 'footer-contact',
	copyright: 'footer-copyright',
};
