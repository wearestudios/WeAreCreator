// Draft review — the stage between the shoot and publication.
//
// Two surfaces, so two blocks: the creator sending a cut up, and the reviewer
// looking at it on the application screen. They share nothing but the concept,
// which is why they don't share a prefix either.

export const CREATOR_DRAFT = {
	open: (id) => `draft-submit-btn-${id}`,
	dialog: 'draft-dialog',
	modeFile: 'draft-mode-file',
	modeLink: 'draft-mode-link',
	file: 'draft-file-input',
	url: 'draft-url-input',
	note: 'draft-note-input',
	error: 'draft-error',
	submit: 'draft-submit',
	cancel: 'draft-cancel',
	// The reviewer's note, shown back on the card that has to act on it.
	revisionNote: (id) => `draft-revision-note-${id}`,
};

export const DRAFT_REVIEW = {
	panel: 'draft-review-panel',
	state: 'draft-review-state',
	link: 'draft-review-link',
	file: 'draft-review-file',
	note: 'draft-review-note',
	revisions: 'draft-review-revisions',
	revisionNote: 'draft-review-revision-note',
	approve: 'draft-review-approve',
	requestChanges: 'draft-review-request-changes',
	changeNote: 'draft-review-change-note',
	changeSubmit: 'draft-review-change-submit',
	error: 'draft-review-error',
};
