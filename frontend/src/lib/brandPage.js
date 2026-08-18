// Where the brand's public page lives.
//
// Same shape and the same reasoning as `shareUrlFor` in ShareButton: the page
// is server-rendered by the backend and reached at `/brands/{id}` on the
// product's own origin, because a crawler does not run JavaScript and a link
// somebody pastes has to preview as the brand rather than as the generic site
// card. `/brands/*` is proxied to the API host the same way `/c/*` is — see
// PREVIEW.md.
//
// So these are real navigations, not router pushes. That is the point: one
// page, the same one a stranger opens, rather than a second in-app copy that
// would immediately start disagreeing with it.

export function brandPageUrl(brandId) {
    if (!brandId) return null;
    const base = (process.env.REACT_APP_SHARE_BASE_URL || "").trim().replace(/\/$/, "");
    return `${base || window.location.origin}/brands/${brandId}`;
}
