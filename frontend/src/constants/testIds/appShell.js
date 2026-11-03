// The signed-in app's shell: the navy sidebar, the phone's top bar and sheet,
// and the content column they frame.
export const APP_SHELL = {
	root: 'app-shell',
	sidebar: 'app-sidebar',
	logo: 'app-sidebar-logo',
	account: 'app-sidebar-account',
	logout: 'app-sidebar-logout',
	topBar: 'app-top-bar',
	menuOpen: 'app-menu-open',
	sheet: 'app-nav-sheet',
	content: 'app-content',
	loading: 'app-content-loading',
	item: (key) => `app-nav-${key}`,
	itemMobile: (key) => `app-nav-${key}-mobile`,
	badge: (key) => `app-nav-${key}-badge`,
};
