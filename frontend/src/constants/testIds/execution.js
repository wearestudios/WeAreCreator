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
};
