# WeAre Creators

Two-sided marketplace connecting vetted creators with brands running paid
campaigns across India. Roles: `creator`, `brand`, `admin`.

- **Backend** — FastAPI + Motor (async MongoDB), entirely in `backend/server.py`.
  JWT in httpOnly cookies (`access_token` / `refresh_token`).
- **Frontend** — React 19 + CRA/craco, Tailwind, shadcn/ui in
  `frontend/src/components/ui/`, framer-motion, sonner. `@/` aliases `src/`.
- **Run it** — `docker compose up` (Mongo + API + frontend). See `PREVIEW.md`.

## Routers and auth

All routes mount under `/api` (`api_router`), with sub-routers by audience:
`/auth` and `/public` (unauthenticated), `/creator`, `/brand` (some endpoints also
allow `admin`), `/admin`, `/campaigns` (creator + admin; detail also the owning
brand), and `/notifications` (any signed-in user).

Guard every non-public endpoint with the `require_roles` dependency factory:

```python
@brand_router.get("/dashboard")
async def get_brand_dashboard(user: dict = Depends(require_roles("brand"))):
```

`get_current_user` decodes the cookie (or `Authorization: Bearer`) and returns the
user document with `password_hash` stripped. Admins sign in with email + password;
creators and brands use WhatsApp OTP only — `/auth/login` rejects non-admins.
Ownership is checked separately from role: `_own_campaign_or_404` and
`_brand_collab_or_404` return 404 (not 403) for another brand's records.

## Collaboration lifecycle

`COLLAB_STATE_ORDER` in `server.py` is the single source of truth:

```
applied → vetted → accepted → commercial_agreed → slot_booked
        → attended → content_submitted → content_approved → in_payment → closed
```

Plus two terminal exits that are **not** steps: `declined`, `cancelled`
(`TERMINAL_COLLAB_STATES`). Who moves each step matters:

- **Admin** — vetting, fee, slot, attendance, payment (`/admin/collaborations/{id}/advance`)
- **Brand** — `accepted` and `content_approved` only (`_BRAND_OWNED_TRANSITIONS`).
  The admin `advance` endpoint refuses these with 409 by design.
- **Creator** — `content_submitted`, and may resubmit until the brand approves.

Rules to preserve when touching this:

- Every transition takes `from_state` as a write precondition and 409s on a
  mismatch — never write state with `{"_id": oid}` alone.
- Only vetted creators can apply; `creators_needed` caps a campaign and flips it
  to `in_progress` when filled (`_sync_campaign_fill`).
- `in_payment` requires creator payout details (`payout_ready`: UPI + PAN).
- `vetting_status` is `pending | vetted | rejected`. **Never write `"approved"`** —
  that mismatch once hid every approved creator from brands.

Every state change calls `audit(...)` and usually `notify(...)`. Keep both.

## Design system

`design_guidelines.json` is the brief: burnt orange `#F05D14` as `ember-500`,
tinted near-black (never pure `#000`), max `rounded-lg`, generous padding, targeted
transitions (never `transition-all`), left-aligned dense content.

**The JSON is stale on typography.** It names Instrument Serif + DM Sans; the code
uses **Fraunces** (`font-serif`, headings) and **Inter Tight** (body) via
`tailwind.config.js` and `src/index.css`. Follow the code.

In practice: uppercase `tracking-[0.2em]` eyebrows, `font-serif` headings,
`border-white/10` on `bg-card` surfaces, ember for CTAs and accents only.

## data-testid convention

Every interactive or informational element carries a `data-testid`, kebab-case and
shaped `<feature>-<element>[-<qualifier>]` (e.g. `brand-campaign-publish-{id}`).
The automated test agent locates elements this way; UI without them can't be
verified.

`frontend/src/constants/testIds/` documents the registry pattern (per-feature file,
re-exported from `index.js`), **but nothing imports it** — all 252 usages are inline
string literals, and `auth.js` doesn't match the shipped OTP screens. Match the
surrounding file's inline style unless you're migrating the whole thing.

## Tests

```bash
cd backend
pytest tests/unit          # pure functions; runs anywhere, no services needed
pytest tests/              # full suite; needs a live backend + MongoDB
```

`tests/unit/` is the CI gate (`.github/workflows/ci.yml`) and covers the rules
above. `tests/` hits a running server over HTTP — it needs `REACT_APP_BACKEND_URL`,
`MONGO_URL`, `DB_NAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and reads OTP codes from
the backend log, so it can't gate a PR.

Build collaborations through `tests/pipeline.py` rather than by hand — it routes
each step to whoever owns it. Do not change `addopts` in `pytest.ini`; serialize
with `-n 0`.
