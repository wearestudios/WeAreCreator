// Test IDs for campaign cover images and brand logos.
//
// The fallback is a separate id from the image on purpose: "did the cover
// render" and "did the cover render *the uploaded picture*" are different
// questions, and a check that cannot tell them apart passes on a brief whose
// image failed to load.

export const COVER = {
	frame: (id) => `campaign-cover-${id}`,
	image: (id) => `campaign-cover-image-${id}`,
	fallback: (id) => `campaign-cover-fallback-${id}`,
	// The upload control on the post-campaign form.
	input: "campaign-cover-input",
	choose: "campaign-cover-choose",
	remove: "campaign-cover-remove",
	preview: "campaign-cover-preview",
	progress: "campaign-cover-progress",
	error: "campaign-cover-error",
};

// The brand's public page, and the links into it.
export const BRAND_PAGE = {
	link: (id) => `brand-page-link-${id}`,
	name: (id) => `brand-name-${id}`,
	// The brand-facing half of the profile: what a creator reads.
	about: "brand-about-input",
	city: "brand-city-trigger",
	outletAdd: "brand-outlet-add",
	outlet: (i) => `brand-outlet-${i}`,
	outletName: (i) => `brand-outlet-name-${i}`,
	outletAddress: (i) => `brand-outlet-address-${i}`,
	outletRemove: (i) => `brand-outlet-remove-${i}`,
	preview: "brand-page-preview",
};

// Campaign visibility: the picker on the post form and the badge on rows.
export const VISIBILITY = {
	picker: "campaign-visibility-picker",
	option: (v) => `campaign-visibility-${v}`,
	badge: (id) => `campaign-visibility-badge-${id}`,
};

export const BRAND_LOGO = {
	image: (id) => `brand-logo-${id}`,
	monogram: (id) => `brand-logo-monogram-${id}`,
	input: "brand-logo-input",
	choose: "brand-logo-choose",
	remove: "brand-logo-remove",
	preview: "brand-logo-preview",
	error: "brand-logo-error",
};
