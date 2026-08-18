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

export const BRAND_LOGO = {
	image: (id) => `brand-logo-${id}`,
	monogram: (id) => `brand-logo-monogram-${id}`,
	input: "brand-logo-input",
	choose: "brand-logo-choose",
	remove: "brand-logo-remove",
	preview: "brand-logo-preview",
	error: "brand-logo-error",
};
