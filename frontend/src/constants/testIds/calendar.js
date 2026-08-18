// The shoot calendar, and self check-in.

export const CALENDAR = {
	page: 'calendar-page',
	skeleton: 'calendar-skeleton',
	error: 'calendar-error',
	empty: 'calendar-empty',
	monthLabel: 'calendar-month-label',
	prev: 'calendar-prev-month',
	next: 'calendar-next-month',
	today: 'calendar-today',
	campaignFilter: 'calendar-campaign-filter',
	// The month grid, desktop only.
	grid: 'calendar-grid',
	day: (iso) => `calendar-day-${iso}`,
	dayCount: (iso) => `calendar-day-count-${iso}`,
	// The agenda, which is the whole view on a phone.
	agenda: 'calendar-agenda',
	agendaDay: (iso) => `calendar-agenda-day-${iso}`,
	entry: (id) => `calendar-entry-${id}`,
};

export const CHECKIN = {
	// The manager's day-of screen.
	panel: 'checkin-qr-panel',
	open: (slotId) => `checkin-qr-open-${slotId}`,
	qr: 'checkin-qr',
	link: 'checkin-qr-link',
	expiry: 'checkin-qr-expiry',
	refresh: 'checkin-qr-refresh',
	// The creator's page.
	page: 'checkin-page',
	pending: 'checkin-pending',
	success: 'checkin-success',
	failure: 'checkin-failure',
	retry: 'checkin-retry',
};
