// The structured half of a brief, and the proof that a story ran. Naming
// follows the directive in ./auth.js.

// The checklist: do's, don'ts, the tags that have to appear, what the caption
// should say, and where the assets are. One component on four surfaces — the
// campaign page, the creator's own row, the reviewer's screen and the
// manager's brief panel — so the ids do not vary by who is looking.
export const BRIEF = {
	checklist: 'brief-checklist',
	// One block per structured field, keyed by the stored field name so a
	// seventh field added to `BRIEF_LIST_FIELDS` needs no new id here.
	group: (key) => `brief-${key.replace(/_/g, '-')}`,
	line: (key, i) => `brief-${key.replace(/_/g, '-')}-${i}`,
	caption: 'brief-caption-guidance',
	assets: 'brief-brand-assets',
	asset: (i) => `brief-brand-asset-${i}`,
	count: 'brief-checklist-count',

	// The brand's editor, on the post form and the admin's edit dialog.
	editor: 'brief-details-editor',
	input: (key) => `brief-input-${key.replace(/_/g, '-')}`,
	add: (key) => `brief-add-${key.replace(/_/g, '-')}`,
	remove: (key, i) => `brief-remove-${key.replace(/_/g, '-')}-${i}`,
	captionInput: 'brief-input-caption-guidance',
	assetLabel: (i) => `brief-asset-label-${i}`,
	assetUrl: (i) => `brief-asset-url-${i}`,
	assetAdd: 'brief-asset-add',
	assetRemove: (i) => `brief-asset-remove-${i}`,
};

// A screenshot of a story that has since expired. The creator attaches them;
// whoever reviews the delivery reads them.
export const PROOF = {
	panel: 'story-proof',
	required: 'story-proof-required',
	pick: 'story-proof-pick',
	item: (id) => `story-proof-item-${id}`,
	remove: (id) => `story-proof-remove-${id}`,
	view: (id) => `story-proof-view-${id}`,
	empty: 'story-proof-empty',
	error: 'story-proof-error',
	busy: 'story-proof-busy',
};
