# WeAre Creators

Two-sided marketplace connecting verified creators with brands running paid
campaigns across India. Roles: `creator`, `brand`, `admin`, `campaign_manager`
(staff, assigned per campaign — sees only what they're assigned to).

- **Backend** — FastAPI + Motor (async MongoDB), entirely in `backend/server.py`.
  JWT in httpOnly cookies (`access_token` / `refresh_token`).
- **Frontend** — React 19 + CRA/craco, Tailwind, shadcn/ui in
  `frontend/src/components/ui/`, framer-motion, sonner. `@/` aliases `src/`.
- **Run it** — `docker compose up` (Mongo + API + frontend). See `PREVIEW.md`.

## Routers and auth

All routes mount under `/api` (`api_router`), with sub-routers by audience:
`/auth` and `/public` (unauthenticated), `/creator`, `/brand` (some endpoints also
allow `admin`), `/admin`, `/campaigns` (creator + admin; detail also the owning
brand), and `/notifications` (any signed-in user), and `/manager` (campaign_manager + admin,
scoped to assigned campaigns via `_managed_campaign_or_404`).

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
applied → verified → accepted → commercial_agreed → slot_booked
        → attended → content_submitted → content_approved → in_payment → closed
```

Plus two terminal exits that are **not** steps: `declined`, `cancelled`
(`TERMINAL_COLLAB_STATES`). Who moves each step matters:

- **Admin** — verification, fee, slot, attendance, payment (`/admin/collaborations/{id}/advance`)
- **Brand** — `accepted` and `content_approved` only (`_BRAND_OWNED_TRANSITIONS`).
  The admin `advance` endpoint refuses these with 409 by design.
- **Creator** — `slot_booked` (booking their own place, and cancelling it back to
  `commercial_agreed` up to 24h before) and `content_submitted`, and may resubmit
  until the brand approves.

Booking is atomic and lives in exactly one function, `_claim_slot`: a conditional
`$inc` on `booked_count` under `{"$expr": {"$lt": ["$booked_count", "$capacity"]}}`,
so two creators after the last place resolve inside the database. Both the
`/campaigns/slots/{id}/book` and `/creator/collaborations/{id}/book-slot` routes go
through it. **Do not add a second copy.** Releasing a seat always writes the
collaboration first and decrements after, so a place is never on sale while
somebody still holds it.

Rules to preserve when touching this:

- Every transition takes `from_state` as a write precondition and 409s on a
  mismatch — never write state with `{"_id": oid}` alone.
- Only verified creators can apply; `creators_needed` caps a campaign and flips it
  to `in_progress` when filled (`_sync_campaign_fill`).
- `in_payment` requires creator payout details (`payout_ready`: UPI + PAN).
- `verification_status` is `pending | verified | rejected`. This concept was
  previously called `approved` then `vetted`; **never reintroduce either word** —
  that mismatch once hid every approved creator from brands. Startup migrates
  both, and a unit test fails if a stray reference reappears.

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
The automated test agent locates elements this way; UI without them can't be checked.

`frontend/src/constants/testIds/` holds the registry (per-feature file, re-exported
from `index.js`). The admin console, the manager interface and the creator home
(`components/creator/`, `pages/Dashboard.jsx`) import from it; the older
brand-facing pages still use inline string literals, and `auth.js` doesn't match
the shipped OTP screens. Match the surrounding file — add to the registry when the
feature already uses it, inline otherwise, and don't half-migrate a page.

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
