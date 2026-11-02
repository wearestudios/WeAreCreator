// The case-study console, and the marketing strips that link into it.
//
// A case study is the one public page in this product that names a person, so
// the ids here are what a check uses to assert the roster is what the server
// sent — and the editor's own ids are what a check uses to prove the screen
// exists at all, which is the half this feature would otherwise be missing.

export const CASE_STUDIES = {
	section: 'case-studies',
	table: 'case-studies-table',
	row: (id) => `case-study-row-${id}`,
	peek: 'case-study-peek',
	editor: 'case-study-editor',

	// Creating one. The first is the argument for the whole feature.
	fromCampaign: 'case-study-from-campaign',
	blank: 'case-study-blank',
	campaignList: 'case-study-campaign-list',
	campaignOption: (id) => `case-study-campaign-${id}`,

	// The fields. Only the narrative two are written by hand; everything else
	// arrives from the campaign and is here to be corrected.
	title: 'case-study-title',
	brand: 'case-study-brand',
	category: 'case-study-category',
	city: 'case-study-city',
	challenge: 'case-study-challenge',
	approach: 'case-study-approach',
	headline: 'case-study-headline',
	reach: 'case-study-reach',
	engagement: 'case-study-engagement',
	pieces: 'case-study-pieces',
	roster: 'case-study-roster',

	// The hero, which publish requires and the editor had no way to supply —
	// so a blank draft, and any draft from a campaign with no cover, was
	// permanently unpublishable with the reason listed and no control.
	hero: 'case-study-hero',
	heroInput: 'case-study-hero-input',
	heroChoose: 'case-study-hero-choose',
	heroRemove: 'case-study-hero-remove',
	heroError: 'case-study-hero-error',

	// The gallery, off the same endpoint. It renders as "The content" on the
	// public page and had no editor at all.
	gallery: 'case-study-gallery',
	galleryAdd: 'case-study-gallery-add',
	galleryAddInput: 'case-study-gallery-add-input',
	galleryItem: (i) => `case-study-gallery-item-${i}`,
	galleryCaption: (i) => `case-study-gallery-caption-${i}`,
	galleryRemove: (i) => `case-study-gallery-remove-${i}`,

	// What is in the way of publishing, named rather than counted.
	missing: 'case-study-missing',

	save: 'case-study-save',
	publish: 'case-study-publish',
	unpublish: 'case-study-unpublish',
	viewLive: 'case-study-view-live',
};
