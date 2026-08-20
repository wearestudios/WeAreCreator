// Test IDs for the creator's own read-only profile at /profile, and the
// avatar menu in the navbar that is the way into it.

export const NAV = {
	avatarButton: 'nav-avatar-button',
	avatarMenu: 'nav-avatar-menu',
	myProfile: 'nav-my-profile',
	avatarLogout: 'nav-avatar-logout',
};

export const CREATOR_PROFILE = {
	page: 'creator-profile-page',
	name: 'creator-profile-name',
	status: 'creator-profile-status',
	edit: 'creator-profile-edit',
	recheckNotice: 'creator-profile-recheck',
	recheckFields: 'creator-profile-recheck-fields',
	about: 'creator-profile-about',
	channels: 'creator-profile-channels',
	instagram: 'creator-profile-instagram',
	youtube: 'creator-profile-youtube',
	facebook: 'creator-profile-facebook',
	followers: 'creator-profile-followers',
	work: 'creator-profile-work',
	genres: 'creator-profile-genres',
	niches: 'creator-profile-niches',
	rate: 'creator-profile-rate',
	location: 'creator-profile-location',
	address: 'creator-profile-address',
	payout: 'creator-profile-payout',
	upi: 'creator-profile-upi',
};

// Asking to be forgotten — the DPDP Act's right to erasure, on the creator's
// and the brand's own profile screens.
export const ACCOUNT = {
	deletionSection: 'account-deletion-section',
	deletionOpen: 'account-deletion-open',
	deletionDialog: 'account-deletion-dialog',
	deletionReason: 'account-deletion-reason',
	deletionSubmit: 'account-deletion-submit',
	deletionCancel: 'account-deletion-cancel',
	deletionBlocked: 'account-deletion-blocked',
	deletionPending: 'account-deletion-pending',
	deletionWithdraw: 'account-deletion-withdraw',
};

// The admin's erasure queue.
export const ADMIN_DELETIONS = {
	page: 'admin-deletions-page',
	row: (id) => `admin-deletion-row-${id}`,
	erase: (id) => `admin-deletion-erase-${id}`,
	decline: (id) => `admin-deletion-decline-${id}`,
	blocked: (id) => `admin-deletion-blocked-${id}`,
	note: 'admin-deletion-note',
	confirm: 'admin-deletion-confirm',
	empty: 'admin-deletions-empty',
};
