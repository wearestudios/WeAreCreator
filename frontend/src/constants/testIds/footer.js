// The site footer, on every marketing page.

export const FOOTER = {
	root: 'site-footer',
	wordmark: 'footer-wordmark',
	// Keyed on the destination rather than an index, so a test names the page
	// it is looking for instead of a position that reorders.
	link: (to) => `footer-link-${to.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '')}`,
	contact: 'footer-contact',
	copyright: 'footer-copyright',
	// The studio's name inside the copyright line. The credit used to be its
	// own endorsement component in six places; it is the owner named in the
	// copyright now, so the id goes where the words went.
	copyrightLink: 'footer-copyright-link',
};
