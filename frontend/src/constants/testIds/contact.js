// The contact page and its form.

export const CONTACT = {
	page: 'contact-page',
	form: 'contact-form',
	name: 'contact-field-name',
	whatsapp: 'contact-field-whatsapp',
	email: 'contact-field-email',
	message: 'contact-field-message',
	// Keyed on the value rather than an index, so a test names the answer it
	// is picking instead of a position that reorders.
	role: (v) => `contact-role-${v}`,
	submit: 'contact-submit',
	// The error slot is reserved whether or not it has anything in it, so a
	// message appearing on blur cannot push the next field down.
	error: (field) => `contact-error-${field}`,
	refusal: 'contact-refusal',
	done: 'contact-done',
	doneEcho: 'contact-done-message',
	honeypot: 'contact-honeypot',
	// Keyed on the number, which is what `CONTACT_PEOPLE` is keyed on.
	person: (phone) => `contact-person-${phone.replace(/\D/g, '')}`,
	whatsappLink: (phone) => `contact-whatsapp-${phone.replace(/\D/g, '')}`,
	telLink: (phone) => `contact-tel-${phone.replace(/\D/g, '')}`,
	emailLink: 'contact-email-link',
};

// The admin console's enquiries section.
export const ENQUIRIES = {
	section: 'admin-enquiries',
	// Keyed on the row's id, which is what a test means by "that enquiry".
	row: (id) => `admin-enquiry-${id}`,
	rowRoot: (id) => `admin-enquiry-row-${id}`,
	handle: (id) => `admin-enquiry-handle-${id}`,
	peek: 'admin-enquiry-peek',
	confirm: 'admin-enquiry-confirm',
};
