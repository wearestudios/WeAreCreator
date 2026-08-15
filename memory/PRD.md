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

- `users` — id, email(unique), name, role(creator|brand|admin|campaign_manager), phone?, status(pending|active|suspended), password_hash, created_at. Indexes: `email` unique, `role`, `status`.
- `creator_profiles` (1:1 users where role=creator) — user_id(unique), name, instagram_handle?, instagram_profile_url?, profile_image_url?, email?, address?, niches[], base_rate?, follower_count? (self-reported), verification_status(pending|verified|rejected), pending_review, payout_upi?, payout_account_name?, pan?, gstin?. Indexes: `user_id` unique, `verification_status`, `niches`.
- `brand_profiles` (1:1 users where role=brand) — user_id(unique), business_name, category(fnb|hospitality|retail|lifestyle)?, areas[], verified, verified_at?, verification_reason? (why we refused), rejected_at?. Unverified brands may draft campaigns but not submit them. Indexes: `user_id` unique, `verified`, `category`.
- `campaigns` — brand_id → users._id, title, brief, deliverables, budget_per_creator, category?, area?, creators_needed, start_date?, end_date?, campaign_type(launch|group_event|personal_table), event_date? (launch/group_event only), venue_address?, venue_instructions?, on_site_contact?, manager_id? → users._id, manager_name?, manager_phone?, manager_email?, status(draft|pending_review|upcoming|open|in_progress|paused|completed|closed), submitted_for_review_at?, reviewed_at?, reviewed_by?, review_reason?, paused_at?, paused_from_status?, pause_reason?, closed_at?, closed_by_admin?. The type decides the dates: launch/group_event carry event_date and no window; personal_table carries start_date+end_date and no event_date — enforced in PostCampaignPayload. Manager fields are a snapshot taken at assignment. A brand may only set draft or pending_review; only an admin approval reaches open/upcoming. Indexes: `brand_id`, `status`, `(status, created_at desc)`, `(area, category)`.
- `collaborations` — campaign_id → campaigns._id, creator_id → users._id, pitch?, quoted_rate?, agreed_amount?, content_url?, state(applied|verified|accepted|commercial_agreed|slot_booked|attended|content_submitted|content_approved|in_payment|closed) plus terminal exits (declined|cancelled), active, slot_id? → campaign_slots._id, checked_in_at?, no_show_reported?, no_show_note? (raised by the manager, actioned by an admin), rescheduled_at?, scheduled_at?, agreed_at?, exit_reason?, cancellation_type(creator_no_show|brand_cancelled|admin_cancelled)?, cancelled_from_state?, agreed_amount_at_cancellation?, settlement_review_needed?, reverted_from?, revert_reason?. Indexes: `campaign_id`, `creator_id`, **partial-unique `(campaign_id, creator_id)` where active=true** so a declined creator may re-apply, `state`.
- `campaign_invitations` — campaign_id → campaigns._id, creator_id → users._id, brand_id, invited_by → users._id, note?, state(sent|send_failed), delivered_on_whatsapp, whatsapp_mode?, error?. Indexes: **unique `(campaign_id, creator_id)`** so nobody is invited twice, `(creator_id, created_at desc)`.
- `campaign_slots` — campaign_id → campaigns._id, starts_at, ends_at? (required for personal_table windows), capacity, booked_count, created_by → users._id. Editable by the assigned manager: capacity never below booked_count, and moving the time re-stamps the collaborations on it. Booking increments booked_count under a `$expr` capacity check, so the last place resolves inside the database. Indexes: `(campaign_id, starts_at)`.
- `payments` (1:1 collaborations) — collaboration_id(unique), agreed_amount, platform_fee, creator_payout, state(pending|paid|cancelled|refunded), paid_at?, payment_reference?, refunded_at?, refund_reason?, refund_reference?, brand_invoice_state(pending|sent|settled|void), brand_refund_due?. `cancelled` is a payout that never happened; `refunded` is one that did and came back. Indexes: `collaboration_id` unique, `state`.
- `audit_log` — actor_id → users._id, actor_role, actor_name, action (`<subject>.<verb>`, e.g. `payment.refund`), subject_type, subject_id, before, after, note, created_at. Written by every admin mutation. Indexes: `created_at desc`, `(subject_type, subject_id)`, `(actor_id, created_at desc)`, `(action, created_at desc)`.

On signup, a stub row is auto-created in `creator_profiles` or `brand_profiles` so downstream flows can rely on the profile existing.

## Admin console aggregation (Aug 2026)
- `GET /api/admin/dashboard` — one call for the landing view: campaign counts by status (zero-filled, with `live` aliasing `open`), the five review queues plus a headline that is their sum, totals (GMV, paid out, active creators, active brands), and a per-campaign summary with applied/approved/rejected/completed counts. Optional `campaign_id` scopes every number to one brief; the platform-wide vetting queues read zero when scoped, since they are not that campaign's business. Four aggregations (`$facet`/`$group`), a fixed number of round trips whatever the data looks like.
- `GET /api/admin/campaigns/{id}/applicants` — one pipeline with three `$lookup`s, bucketed into applied / approved (accepted and beyond, including finished) / rejected (declined + cancelled). Distinct from the brand's own board, which is a decision screen scoped to that brand's campaigns.

## Implemented (v1.4 — Brand-facing creator directory, Feb 2026)
- New endpoint `GET /api/brand/creators` — public projection (no PII) with `city`, `niche`, `min_followers`, `q`, `sort` filters
- New endpoint `GET /api/brand/creators/filters` — distinct cities + case-deduped niches + total count
- New page `/brand/creators` with one-tap city chips (aria-pressed), filter bar (niche/followers/sort/search), animated cards, empty state, `Clear all`
- Navbar: brand-only "Creators" link; Brand Dashboard header: "Browse creators" outline button
- Idempotent seed of 8 verified demo creators across 7 cities (Bengaluru, Mumbai, Delhi NCR, Hyderabad, Chennai, Pune, Goa) so the directory has content on fresh installs
- Regression tests: 19 new pytest cases (`test_brand_directory.py`) + 52 previous ones — all green

## Implemented (v1.3 — All-India pivot + Landing rewrite, Feb 2026)
- Positioning shift: no longer Bengaluru-only. Now framed as an all-India influencer studio across F&B, hospitality, retail, real estate, fashion, travel, wellness and lifestyle. Agency angle woven in ("Self-serve, or hand it to our team").
- Backend category enum expanded to 8 values: fnb, hospitality, retail, real_estate, fashion, travel, wellness, lifestyle
- Creator profile: new optional `city` field (persisted, returned on GET, surfaced in admin console + applicant lists)
- Landing rewrite: rotating hero vertical (cafés → restaurants → retail → real estate → fashion → travel → hotels), infinite cities marquee, animated number counters, scroll-parallax hero, dedicated 'For brands' section, mailto managed-service CTA
- Signup role subtitles + Login + Signup taglines + Campaigns kicker + brand/creator onboarding copy all reworked for pan-India + all-verticals
- 22 new pytest cases in `test_pivot_city_categories.py`; OTP + filter regressions still green

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
