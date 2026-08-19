// When a shoot may happen — the campaign's restricted days and shoot windows,
// on the form that sets them and on the surfaces that read them back.

export const SCHEDULING = {
	section: 'campaign-scheduling',
	day: (d) => `campaign-restricted-day-${d}`,
	window: (key) => `campaign-shoot-window-${key}`,
	customStart: 'campaign-shoot-window-custom-start',
	customEnd: 'campaign-shoot-window-custom-end',
	customAdd: 'campaign-shoot-window-custom-add',
	customRow: (i) => `campaign-shoot-window-custom-${i}`,
	customRemove: (i) => `campaign-shoot-window-custom-remove-${i}`,
	// Read-only, on the campaign page and in the slot picker.
	summary: 'campaign-scheduling-summary',
	openDays: 'campaign-scheduling-open-days',
	windows: 'campaign-scheduling-windows',
	// The manager's warning on a slot that predates a restriction.
	slotOutside: (id) => `slot-outside-preferences-${id}`,
};
