// Test IDs for the shared dense-view pieces — the sticky bars, filter chips,
// result counts, skeletons and empty states that the admin console, the
// campaigns lists, the creator directory, the applicant board and the audit log
// all now use.
//
// These are defaults. A surface that already ships an id for its empty state or
// its skeleton keeps it and passes it in, so nothing written against the old
// ids stops finding its element.
//
// Naming follows the directive in ./auth.js: keys camelCase, values kebab-case
// `<feature>-<element>[-<qualifier>]`.

export const DENSE = {
    count: 'dense-result-count',
    chips: 'dense-filter-chips',
    chip: (key) => `dense-filter-chip-${key}`,
    clearAll: 'dense-filter-clear-all',
    skeleton: 'dense-skeleton',
    emptyClear: 'dense-empty-clear',
};

// The sticky bars, one per surface. Named rather than generated so a test can
// assert that a specific view's context stays on screen.
export const STICKY_BAR = {
    adminSection: 'sticky-admin-section',
    campaigns: 'sticky-campaigns-filters',
    directory: 'sticky-directory-filters',
    applicants: 'sticky-applicants-tabs',
    audit: 'sticky-audit-filters',
    brandCampaigns: 'sticky-brand-campaigns',
};
