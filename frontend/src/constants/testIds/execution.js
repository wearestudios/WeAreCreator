// Test IDs for the execution-owner badge, note and filters — the same field
// shown to three audiences, so the ids are keyed on the owner rather than on
// the screen.

export const EXECUTION = {
	badge: (owner) => `execution-badge-${owner}`,
	note: (owner) => `execution-note-${owner}`,
	filter: 'execution-filter',
	filterOption: (value) => `execution-filter-${value}`,
	picker: 'execution-picker',
	pickerOption: (value) => `execution-picker-${value}`,
	// What stands where the picker would be on a brief that is ours by rule —
	// a launch, or one for more than the threshold. It replaces the picker
	// rather than sitting beside it: a choice the server is about to override
	// is not a choice.
	weareRun: 'execution-weare-run',
};
