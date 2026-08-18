// Test IDs for the brand-facing surfaces added with the brand manager.
//
// The older brand pages use inline string literals; these two features are new,
// so they start in the registry rather than being half-migrated into it. Ids
// that already shipped on the applicants page (`applicant-row-{id}` and the
// rest) are deliberately not moved here — anything already written against
// them would stop finding its control.
//
// Naming follows the directive in ./auth.js: keys camelCase, values kebab-case
// `<feature>-<element>[-<qualifier>]`.

export const WORK_NOTES = {
    section: (collabId) => `work-notes-${collabId}`,
    toggle: (collabId) => `work-notes-toggle-${collabId}`,
    // The agreed figure sits above the thread: the number and the conversation
    // that produced it are read together or not at all.
    agreed: (collabId) => `work-notes-agreed-${collabId}`,
    thread: (collabId) => `work-notes-thread-${collabId}`,
    empty: (collabId) => `work-notes-empty-${collabId}`,
    note: (noteId) => `work-note-${noteId}`,
    noteAuthor: (noteId) => `work-note-author-${noteId}`,
    noteBody: (noteId) => `work-note-body-${noteId}`,
    input: (collabId) => `work-notes-input-${collabId}`,
    submit: (collabId) => `work-notes-submit-${collabId}`,
    loading: (collabId) => `work-notes-loading-${collabId}`,
};

export const AGREED_AMOUNT = {
    open: (collabId) => `agreed-amount-open-${collabId}`,
    dialog: "agreed-amount-dialog",
    input: "agreed-amount-input",
    note: "agreed-amount-note",
    confirm: "agreed-amount-confirm",
};

export const SUGGESTED_CREATORS = {
    section: "suggested-creators",
    heading: "suggested-creators-heading",
    explainer: "suggested-creators-explainer",
    tier: "suggested-creators-tier",
    filters: "suggested-creators-filters",
    filterCity: "suggested-creators-filter-city",
    filterNiche: "suggested-creators-filter-niche",
    // Audience size is picked as a tier now, not typed as two numbers — one
    // vocabulary for the axis, the same one the band above the filter uses.
    filterTier: "suggested-creators-filter-tier",
    filterTierOption: (v) => `suggested-creators-filter-tier-${v}`,
    filterApply: "suggested-creators-filter-apply",
    filterClear: "suggested-creators-filter-clear",
    list: "suggested-creators-list",
    card: (userId) => `suggested-creator-${userId}`,
    reason: (userId) => `suggested-creator-reason-${userId}`,
    score: (userId) => `suggested-creator-score-${userId}`,
    breakdown: (userId) => `suggested-creator-breakdown-${userId}`,
    invite: (userId) => `suggested-creator-invite-${userId}`,
    empty: "suggested-creators-empty",
    loading: "suggested-creators-loading",
    more: "suggested-creators-more",
    error: "suggested-creators-error",
};

export const BRAND_CAMPAIGN_CONTROLS = {
    pause: (campaignId) => `brand-campaign-pause-${campaignId}`,
    resume: (campaignId) => `brand-campaign-resume-${campaignId}`,
    pauseDialog: "brand-campaign-pause-dialog",
    pauseReason: "brand-campaign-pause-reason",
    pauseConfirm: "brand-campaign-pause-confirm",
};

// The brand verification screen — the profile a reviewer reads, and the
// documents it is checked against. New surface, so it starts in the registry.
//
// The upload ids are keyed on the *queue* key rather than a document id,
// because a file that is still going up has no id yet and a file that failed
// the local type check never will. Stored documents key on the server's id.
export const BRAND_VERIFICATION = {
    page: "brand-verification-page",
    skeleton: "brand-verification-skeleton",
    stateBanner: "brand-verification-state",
    rejectionReason: "brand-verification-rejection-reason",
    missingList: "brand-verification-missing",
    missingField: (field) => `brand-verification-missing-${field}`,

    // Profile fields a reviewer needs before there is anything to review.
    field: (name) => `brand-verification-field-${name}`,
    fieldError: (name) => `brand-verification-field-error-${name}`,
    saveBtn: "brand-verification-save",
    saveError: "brand-verification-save-error",

    // Documents
    documentsSection: "brand-verification-documents",
    documentCount: "brand-verification-document-count",
    documentsEmpty: "brand-verification-documents-empty",
    documentsFull: "brand-verification-documents-full",
    documentList: "brand-verification-document-list",
    document: (id) => `brand-verification-document-${id}`,
    documentType: (id) => `brand-verification-document-type-${id}`,
    documentRemove: (id) => `brand-verification-document-remove-${id}`,
    documentConfirmRemove: (id) => `brand-verification-document-confirm-${id}`,
    documentCancelRemove: (id) => `brand-verification-document-keep-${id}`,
    documentError: (id) => `brand-verification-document-error-${id}`,
    docTypeTrigger: "brand-verification-doc-type",
    docTypeOption: (value) => `brand-verification-doc-type-${value}`,
    fileInput: "brand-verification-file-input",
    chooseBtn: "brand-verification-choose-file",

    // In-flight uploads
    queue: "brand-verification-upload-queue",
    queueItem: (key) => `brand-verification-upload-${key}`,
    queueProgress: (key) => `brand-verification-upload-progress-${key}`,
    queuePercent: (key) => `brand-verification-upload-percent-${key}`,
    queueError: (key) => `brand-verification-upload-error-${key}`,
    queueRetry: (key) => `brand-verification-upload-retry-${key}`,
    queueDismiss: (key) => `brand-verification-upload-dismiss-${key}`,

    submitBtn: "brand-verification-submit",
    submitBlocked: "brand-verification-submit-blocked",
    submitError: "brand-verification-submit-error",
};
