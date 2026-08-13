# WeAre Creators — PRD

## Original problem statement
Two-sided marketplace web app for Bengaluru connecting food & lifestyle content creators
with restaurants, cafés, and lifestyle brands for paid collaboration campaigns. Three user
roles: CREATOR, BRAND, ADMIN. Dark premium theme, burnt-orange accent, elegant serif +
clean sans, mobile-first. Foundation only for first build: auth + DB + role-based access +
placeholder home + login/signup. GitHub sync via Emergent UI.

## Stack (confirmed)
- Backend: FastAPI + Motor (MongoDB), JWT email/password auth, bcrypt
- Frontend: React 19 + Tailwind + Shadcn UI, framer-motion, sonner
- DB: MongoDB (managed)
- Fonts: Instrument Serif (headings) + DM Sans (body)
- Accent: Burnt Orange `#F05D14`
- Background: near-black tinted grey `hsl(20 8% 4%)`

## User personas
- Creator: Bengaluru food/lifestyle content creator applying to paid briefs.
- Brand: Restaurant/café/lifestyle brand posting briefs.
- Admin: WeAre Monk internal team curating both sides.

## Core requirements (static)
- Role-based access: creator | brand | admin
- Creators & brands: WhatsApp OTP login/signup (AiSensy delivery). Admin: email + password.
- Mobile-first, premium dark editorial UI
- All backend routes prefixed with `/api`

## Implemented (v0 — Feb 2026)
- JWT auth: register/login/logout/me/refresh, httpOnly cookies, bcrypt hashing
- Admin auto-seed from env on startup
- MongoDB unique indexes: partial-unique on `users.email` + `users.phone` (string-typed only)
- Role guard dependency (`require_roles`) + sample `/api/admin/ping`
- Frontend: Landing page, WhatsApp OTP Login (`/login`), Signup with role picker (`/signup`), Admin email login (`/admin/login`), role-aware Dashboard shell, ProtectedRoute, Navbar, AuthContext
- Design system: Instrument Serif + DM Sans, burnt-orange accent, dark tinted-grey base

## Implemented (v1.1 — WhatsApp OTP Auth, Feb 2026)
- New `otp_codes` collection (TTL 5 min, bcrypt-hashed codes, attempt counter)
- `POST /api/auth/otp/request` — 30s per-phone cooldown, 5/hour per-phone limit, purpose=login|signup
- `POST /api/auth/otp/verify` — 5-wrong-attempt lockout, issues JWT cookies on success
- AiSensy WhatsApp delivery with simulation mode when creds missing (logs OTP)
- `/auth/login` now admin-only (role=admin gate); creators/brands must use OTP
- Startup migration drops legacy single-field `email_1`/`phone_1` indexes before creating partial-unique variants

## Data model (v1 — Feb 2026)
Collections + indexes provisioned on startup. All linking IDs are `ObjectId`.

- `users` — id, email(unique), name, role(creator|brand|admin), phone?, status(pending|active|suspended), password_hash, created_at. Indexes: `email` unique, `role`, `status`.
- `creator_profiles` (1:1 users where role=creator) — user_id(unique), name, instagram_handle?, instagram_profile_url?, email?, address?, niches[], base_rate?, follower_count?, vetting_status(pending|vetted|rejected). Indexes: `user_id` unique, `vetting_status`, `niches`.
- `brand_profiles` (1:1 users where role=brand) — user_id(unique), business_name, category(fnb|hospitality|retail|lifestyle)?, areas[], verified. Indexes: `user_id` unique, `verified`, `category`.
- `campaigns` — brand_id → users._id, title, brief, deliverables, budget_per_creator, category?, area?, creators_needed, start_date?, end_date?, status(draft|upcoming|open|in_progress|completed|closed). Indexes: `brand_id`, `status`, `(status, created_at desc)`, `(area, category)`.
- `collaborations` — campaign_id → campaigns._id, creator_id → users._id, pitch?, quoted_rate?, agreed_amount?, content_url?, state(applied|vetted|accepted|commercial_agreed|slot_booked|attended|content_submitted|in_payment|closed). Indexes: `campaign_id`, `creator_id`, **unique `(campaign_id, creator_id)`** so a creator can apply only once, `state`.
- `payments` (1:1 collaborations) — collaboration_id(unique), agreed_amount, platform_fee, creator_payout, state(pending|paid), paid_at?. Indexes: `collaboration_id` unique, `state`.

On signup, a stub row is auto-created in `creator_profiles` or `brand_profiles` so downstream flows can rely on the profile existing.

## Implemented (v1.2 — Editorial refresh + campaign filters, Feb 2026)
- Font system upgraded: Fraunces (variable editorial serif) + Inter Tight — sitewide via `index.css` + `tailwind.config.js`
- Landing: Vol. 01 kicker, motion-in on step cards + trust cards, gradient accent line on hover
- Campaigns page: editorial masthead with italic accent, live-pool total, richer filter bar (keyword search + area + category + budget bucket + sort), Clear all pill, motion-in cards with hover lift + accent line
- OTP screens (`/login`, `/signup`): kicker + italicized heading treatment
- Backend: `GET /api/campaigns` now accepts `budget_min`, `budget_max`, `q`, `sort={newest|budget_desc|budget_asc}`; `GET /api/campaigns/filters` returns `budget_bounds`
- Regression tests: 17 new pytest cases (`test_campaign_filters.py`) + 13 existing OTP auth tests still green
- P1: YouTube stats integration for creators (parked earlier per user)
- P1: Rich creator profiles — avatar upload, portfolio grid, city/area, "About me"
- P1: Brand applicant board — side-by-side shortlist/reject on a campaign
- P1: Deliverable-type filter on campaigns (requires new schema field or heuristic)
- P2: Wire real AiSensy API key + campaign name (currently simulation mode)
- P2: WhatsApp notifications on collab state changes (accepted, commercial_agreed, slot_booked, day-before reminder, attended, closed) — parked until AiSensy templates provided
- P2: Payments (Razorpay/Stripe), invoices, ratings & reviews
- P2: Email/SMS notifications

## Next tasks
- User picks the next screen (creator profile, brief creation, or WhatsApp OTP)
