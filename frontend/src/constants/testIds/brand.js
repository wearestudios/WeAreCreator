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
    filterMinFollowers: "suggested-creators-filter-min-followers",
    filterMaxFollowers: "suggested-creators-filter-max-followers",
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
