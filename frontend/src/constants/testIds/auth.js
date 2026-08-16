// Test IDs for the auth feature (login, register, password reset, logout).
// Add new keys here as you wire up additional auth UI; see ./index.js for
// the recipe to add a new feature file.
//
// Directive:
//   - Keys are camelCase, values are kebab-case shaped as `<feature>-<element>`
//     (or `<feature>-<element>-<qualifier>` when an element repeats). Examples:
//     'login-submit-button', 'cart-quantity-input', 'product-card-image'.
//   - Reference them in JSX as `data-testid={LOGIN.submitButton}`.
//
// Why kebab-case values: required by qabot's CSS-attribute selector matcher
// and the lint rule `emergent(kebab-case-testid)`.

export const LOGIN = {
	emailInput: 'login-email-input',
	passwordInput: 'login-password-input',
	submitButton: 'login-submit-button',
	forgotPasswordLink: 'login-forgot-password-link',
	registerLink: 'login-register-link',
};

export const REGISTER = {
	nameInput: 'register-name-input',
	emailInput: 'register-email-input',
	passwordInput: 'register-password-input',
	passwordConfirmInput: 'register-password-confirm-input',
	submitButton: 'register-submit-button',
	loginLink: 'register-login-link',
};

export const LOGOUT = {
	button: 'logout-button',
};

// The OTP screens as actually shipped. LOGIN/REGISTER above describe an
// email+password flow this product does not have — they are kept only because
// removing them is a separate change, and nothing renders them.
//
// Values are the ones already in the DOM (`otp-*`), so moving the component
// onto the registry did not invalidate anything that referenced them.
export const AUTH = {
	phoneStep: 'otp-phone-step',
	phoneInput: 'otp-phone-input',
	phoneHint: 'otp-phone-hint',
	phoneError: 'otp-phone-error',
	sendBtn: 'otp-send-btn',
	blockedReason: 'otp-blocked-reason',

	codeStep: 'otp-code-step',
	codeInput: 'otp-code-input',
	sentTo: 'otp-sent-to',
	changePhone: 'otp-change-phone-btn',
	verifyBtn: 'otp-verify-btn',
	resendBtn: 'otp-resend-btn',
	notice: 'otp-notice',

	error: 'otp-error',
	// The resend offered inside the error itself, for the failures where that
	// is the actual next move.
	errorResend: 'otp-error-resend',
};

export const SIGNUP = {
	roleCreator: 'signup-role-creator',
	roleBrand: 'signup-role-brand',
	nameInput: 'signup-name-input',
	nameError: 'signup-name-error',
	managerNameInput: 'signup-manager-name-input',
	managerNameError: 'signup-manager-name-error',
	managerDesignationInput: 'signup-manager-designation-input',
	managerEmailInput: 'signup-manager-email-input',
	managerEmailError: 'signup-manager-email-error',
	terms: 'signup-terms-checkbox',
	termsError: 'signup-terms-error',
};
