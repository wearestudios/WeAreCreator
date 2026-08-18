# WeAre Creators

Two-sided marketplace connecting verified creators with brands running paid
campaigns in Bengaluru. The product is Bengaluru-first — user-facing copy says
Bengaluru, not "every city in India". The city field and the category list are
deliberately open for later expansion, but don't write claims the operation
can't back. Roles: `creator`, `brand_manager`, `admin`, `campaign_manager`
(staff, assigned per campaign — sees only what they're assigned to). `brand` is
the old name for `brand_manager` and both are still accepted — see below.

- **Backend** — FastAPI + Motor (async MongoDB), entirely in `backend/server.py`.
  JWT in httpOnly cookies (`access_token` / `refresh_token`).
- **Frontend** — React 19 + CRA/craco, Tailwind, shadcn/ui in
  `frontend/src/components/ui/`, framer-motion, sonner. `@/` aliases `src/`.
- **Run it** — `docker compose up` (Mongo + API + frontend). See `PREVIEW.md`.

## Routers and auth

All routes mount under `/api` (`api_router`), with sub-routers by audience:
`/auth` and `/public` (unauthenticated), `/creator`, `/brand` (some endpoints also
allow `admin`), `/admin`, `/campaigns` (creator + admin; detail also the owning
brand), `/collaborations` (work notes — brand, admin and the assigned manager),
`/notifications` (any signed-in user), and `/manager` (campaign_manager + admin,
scoped to assigned campaigns via `_managed_campaign_or_404`).

Guard every non-public endpoint with the `require_roles` dependency factory:

```python
@brand_router.get("/dashboard")
async def get_brand_dashboard(user: dict = Depends(require_roles(*BRAND_ROLES))):
```

`get_current_user` decodes the cookie (or `Authorization: Bearer`) and returns the
user document with `password_hash` stripped. Admins sign in with email + password;
creators and brands use WhatsApp OTP only — `/auth/login` rejects non-admins.

Ownership is checked separately from role: `_own_campaign_or_404` and
`_brand_collab_or_404` return 404 (not 403) for another brand's records.

## The OTP front door

Login and signup are the same two steps — a number, then a code — and share
one component, `frontend/src/components/OtpForm.jsx`. `Login.jsx` is that
component and nothing else; `Signup.jsx` wraps it with the fields a new account
needs and blocks the send until they are valid, passing `blockedReason` so the
disabled button says why.

**Every OTP refusal carries a `code`, and the form dispatches on the code, not
on the prose.** `_otp_error(status, code, message, **extra)` builds them —
`{"detail": {"message", "code", ...}}`, the same shape the Instagram and
impersonation refusals use, read by `formatApiError` / `apiErrorCode` in
`lib/api.js`. Eleven codes, listed in `tests/unit/test_otp_errors.py`, which
fails if the set changes.

The codes exist because the form has to *decide something*, and deciding it by
matching English means a copy edit breaks a login screen:

- `FAILURES` in `OtpForm.jsx` maps each code to some of `coolsDown`,
  `offerResend`, `clearCode`, `backToPhone`. An unrecognised code falls through
  `|| {}` to "show the message and do nothing", so a code deployed on the
  server before the form catches up degrades rather than throwing.
- **`cooldown` carries `retry_after` and the countdown is seeded from it**,
  never from a local constant. The form used to set a flat 30s while the
  message said "wait 23s", so the button stayed dead after the server would
  have accepted it — and the two 429s are not the same thing: `hourly_limit`
  has no countdown that will clear inside the session, so it sends the user
  back to the number field instead of ticking down to nothing.
- **`wrong_code` carries `remaining` and must not offer a resend.** They got
  the code; they mistyped it. Resending invalidates the one they are holding,
  so "didn't get it? resend" — which used to be appended to *every* failure —
  is advice that makes it worse.
- `locked_out` is raised at two sites, before the comparison and after the
  decrement, or the fifth wrong code reads as a sixth.

### The fixed test code

`OTP_TEST_CODE` issues one fixed six-digit code for every request, so testing
signup doesn't mean reading a code out of the deploy log each time. It is a
login bypass for anyone who knows a phone number, so it is fenced on four
sides and **all four must be open**: the value is six digits, `APP_ENV`/`ENV`
is not `production|prod|live`, no AiSensy credential is set, and
`_simulation_allowed()`. Refusal is logged as an error, use is logged as a
warning on *every* code, and `warn_about_fixed_test_otp()` announces the state
at boot — the failure this guards against is a staging setting riding quietly
into production.

- **The production check is independent of `_simulation_allowed()`**, which
  returns true for `ALLOW_OTP_SIMULATION=true` whatever `APP_ENV` says. Leaning
  on it alone would let `APP_ENV=production ALLOW_OTP_SIMULATION=true` hand out
  a fixed code; a unit test pins exactly that combination.
- It is deliberately **not** `_is_production()`, which reads an unset `APP_ENV`
  as production. That is right for warning about a missing admin account and
  wrong here — it would refuse the code on a box labelled `APP_ENV=staging`,
  which is where this is meant to work.
- **Only the value is fixed, never the safeguards.** The code is hashed,
  stored, expired, counted and locked out exactly like a random one, and
  `verify_otp` has no branch for it — it is accepted there because it is the
  code that was issued. TTL, resend cooldown, hourly limit and attempt lockout
  all stay on and stay testable; unit tests assert the absence of a shortcut.
- The response carries `test_mode` as a **boolean and never the code** — a
  response body is the one place a live code must not appear. `OtpForm` reads
  it before the plain simulation notice, which is less specific and would
  otherwise send somebody to the log for a code they already know.

Validation is inline and fires on blur, not on submit: `validatePhone` names
the three distinct problems (no country code, too short, not an Indian mobile)
rather than answering all of them with "invalid". A plain-string `detail` still
renders — the two signup-integrity refusals have no code because the client
already prevents them.

## The brand manager

A brand has exactly **one login**, and it belongs to a named person captured at
registration: full name, designation, WhatsApp number (which *is* the login),
work email. That person is the `brand_manager`.

- `BRAND_ROLES = ("brand", "brand_manager")` — spread into `require_roles` on
  every brand endpoint. `brand` is what the role used to be called; startup
  migrates real accounts over (demo feed rows, which have no phone and nobody
  signs into, are left alone). Never name either string directly; use the tuple,
  or `is_brand_side(user)`.
- **`_brand_scope(user)` is how every brand-scoped query finds its brand.**
  Reaching for `user["_id"]` is correct only while the login and the brand are
  the same row — a unit test fails any brand endpoint that does. The actor's own
  id is still right for `agreed_by` and `checked_in_by`.
- One login per brand is a database constraint (`one_manager_per_brand`, partial
  unique on `users.brand_id`), not a rule to remember. There is no endpoint that
  mints a second manager. Don't add one.
- **Campaigns default their manager to the brand's own person** — `manager_id`,
  `manager_name`, `manager_phone`, `manager_email` from `_brand_manager_contact`.
  An admin can still reassign to a WeAre manager.
- That default means `_managed_campaign_or_404` would pass a brand manager into
  the `/manager` router on ownership alone. **The role guard is the only thing
  keeping them out**, and out of the daysheet CSV, which carries creators' phone
  numbers by design. Every `/manager` route stays `require_roles("campaign_manager",
  "admin")`; a unit test enforces it.
- What the brand manager can do on their own campaigns: pause, resume, close,
  edit while draft, accept/decline, invite (verified brands only), record the
  agreed fee, approve content or request changes, mark attendance, and read a
  phone-free roster. **Going live is not theirs** — that stays with admin review.
  Pause/resume/invite/check-in share one implementation with the admin routes
  (`_pause_campaign`, `_resume_campaign`, `_invite_creators`,
  `_check_in_collaboration`) so the two can't diverge.
- `notify_brand_manager` tells them what happened; `_tell_brand_manager_unless_managed`
  skips the message when the campaign's manager *is* them and
  `notify_campaign_manager` already sent one. Two WhatsApps for one booking is
  how a channel stops being read.
- Every brand-manager action audits with `**_campaign_audit_context(campaign)`,
  which attaches `brand_id` and `campaign_id`. "Everything this brand did" and
  "everything that happened on this brief" are the questions the log is asked.

## Creator data a brand may see

`_brand_visible_creator` is the **only** projection of a creator on any
brand-facing surface — the directory, the applicant board, the suggestions panel
and the notes header all go through it. It is an allow-list
(`_BRAND_VISIBLE_CREATOR_FIELDS`): name, photo, Instagram and YouTube handles
with their public stats, follower count and its provenance, engagement rate,
city, niches, genres, platforms, base rate, verification status.

**A brand never receives a phone number, WhatsApp number, email or full
address** — not at any collaboration state, not in the invite flow, not in an
export. This is a change: the applicant board used to reveal an email and a
phone once a collaboration reached `accepted`, so taking somebody onto a
campaign handed over a contact they never offered. Brands reach creators through
the platform — the invite endpoint reads the number and never returns it.

`BRAND_FORBIDDEN_CREATOR_FIELDS` lists what must never appear; a unit test walks
every brand response shape looking for both the keys and the values, and an
integration test does the same against live HTTP. The WeAre manager's roster and
daysheet still carry phone numbers — that is the job of the person at the door —
and stay behind the staff role. The brand's roster passes
`reveal_contact=False`, which omits the key rather than nulling it.

## Work notes

`collaboration_notes`, reached at `POST`/`GET /collaborations/{id}/notes`.
Offline negotiation is the model, so this is where the paper trail lives: who
said what, when, against the application it was about, with the agreed amount
returned alongside the thread.

Visible to the brand manager on their own campaigns, to admins, and to the
assigned campaign manager (`_note_readable_collab_or_404` — three doors, a 404
behind all of them, so whether a thread exists on somebody else's collaboration
is itself not answered). **Creators never see them**, and the route doesn't
accept the role at all. Append-only: no edit, no delete — a record that can be
quietly rewritten is not a record. Every note is audited.

## Creator questions on a campaign

`campaign_questions`: one thread per (campaign, creator), asked from the
campaign page, answered by whoever runs the campaign. **It is not the work
notes** — those stay the internal paper trail creators never see; this thread
has the creator as a party, and both are append-only for the same reason.

- **One creator's thread is invisible to every other creator.** The creator
  routes (`GET`/`POST /questions/campaign/{id}`) take no creator id at all:
  the thread is the session's. Asking respects campaign visibility (the same
  404 as the page), and a creator already on a campaign can keep asking after
  it leaves the live statuses — mid-shoot is when the questions come — while
  bystanders get a 409.
- **Who answers follows `execution_owner`** (`_question_staff_may_see`):
  admins always, the assigned WeAre manager on their campaigns, the owning
  brand **only when the campaign is brand-run**. On a weare-run campaign the
  brand does not see the thread at all — a creator asking "our team" a
  question has not agreed to the brand reading it — and the application
  page's `questions_enabled` flag says so, decided server-side like every
  other action there. The staff thread payloads run the creator through
  `_brand_visible_creator`; a leak test plants contact values and searches
  the output.
- Notifications route exactly like a new application: weare-run →
  `notify_weare_team` (assigned manager, or every admin when unstaffed),
  brand-run → the brand's manager. Answers notify the creator with a link
  back to the campaign. Events `campaign_question` / `question_answered`.
- Replying where nobody asked is refused — that would start a thread the
  creator never opened, which is outreach, and outreach is the invite flow.
- "Unanswered" = the thread's last word is the creator's, computed with
  **`_id` as the timestamp tiebreak** — a question and its answer can land in
  the same clock tick, and the flake that taught this is why every thread
  read sorts on `(created_at, _id)`. `GET /questions/unanswered` feeds the
  admin action queue, whose question rows link to the campaign page's
  threads panel rather than growing their own reply box.
- Surfaces: `CampaignQuestions` (the creator's ask box on CampaignDetail,
  mounted by the page for creators only — the component itself never asks the
  role), `QuestionThread` (one thread, on the application page),
  `QuestionThreadsPanel` (all threads, admin campaign page and the brand
  applicant board; hides itself on the staff routes' 404 and renders nothing
  until somebody has asked).

## Suggesting creators

`GET /brand/campaigns/{id}/suggested-creators` ranks verified creators against a
brief. The whole score is `score_creator_for_campaign` — one pure function, no
database, no hidden term; `CREATOR_MATCH_WEIGHTS` sums to 100 and is the only
tuning knob. The components ship with every result, so a brand can see why
somebody was suggested.

- Signals: niche and genre overlap with the brief, city match, follower count
  against the budget tier (`CREATOR_REACH_TIERS`), engagement rate, past on-time
  delivery here. `CAMPAIGN_CATEGORY_SYNONYMS` bridges the category enum to the
  words creators actually use — nobody writes "fnb" about themselves.
- **An unmeasured signal scores at the midpoint, never zero.** A creator with no
  connected Instagram has an unknown engagement rate, not a bad one, and scoring
  unknowns at zero would bury everyone who has never worked here — which is
  everyone, at the start. `unknown_signals` names them so the UI can say so.
- Anyone who already applied or was invited is excluded. Filters for niche, city
  and follower range; paginated. Admins can call it on any campaign.

## Creator onboarding

Signup takes a **name and a WhatsApp number**, nothing else. Everything a brand
shortlists on is built afterwards in the profile builder, over as many sittings as
it takes:

- `PUT /creator/profile` writes **only the keys present in the body**
  (`payload.model_fields_set`) — every field is optional, an omitted key means
  "leave it alone", an explicit `null` means "clear it". Saving never puts anyone
  in a queue.
- `POST /creator/profile/submit-for-review` is the only thing that does, and it
  409s below 100%, naming the missing fields. It stamps `submitted_for_review_at`,
  which is what `/admin/creators/pending` filters on (`_AWAITING_REVIEW_QUERY`) —
  not a stray Instagram handle, which is what it used to guess with.
- `_profile_completeness` is the single definition of "done" and rides along on
  `GET /creator/profile` and the dashboard. It asks for a channel **per platform
  the creator picked** (`_PLATFORM_COMPLETENESS_FIELDS`): an Instagram-only creator
  is never asked for a YouTube link, because otherwise they could never reach 100%
  and so could never submit at all. Payout details are deliberately not counted —
  a PAN must not be the price of being looked at.
- Browsing campaigns is open to everyone; `POST /campaigns/{id}/apply` 403s anyone
  not `verified` and says which of the three states they're in
  (`_why_you_cannot_apply`).
- `nudge_stale_creator_profiles` WhatsApps creators who stalled, once each ever —
  the `onboarding_nudge_sent_at` stamp is claimed under a filter that only matches
  while it's absent, before the send. Driven by a startup asyncio loop
  (`PROFILE_NUDGE_INTERVAL_SECONDS`, `0` disables) and by
  `POST /admin/jobs/creator-nudges`.

## The creator's home

`pages/Dashboard.jsx` + `components/creator/`. The rule the layout answers to:
**status, active work and the next action are visible without scrolling.**

- The header opens with the photo at portrait size (`h-28` → `md:h-40`, the
  monogram holding the same box), the verification badge, the handle, and the
  three headline stats — lifetime earned (a one-shot `CountUp`), campaigns
  completed, pending. Status banners and the completeness nudge sit directly
  under it, outside any tab: a blocked account is not a section, it is the
  situation.
- **The live work never goes behind a tab.** Each active card leads with a
  16:5 slice of the campaign's cover (`md:max-h-44` — aspect-ratio yields to
  max-height, which is what stops a full-width card growing a 350px wall of
  tint), the animated lifecycle tracker, the next action in plain words with
  whose move it is, and **one** primary button — every action variant fills
  the same `IDS.primary` slot.
- Everything a creator consults rather than acts on — suggestions, past
  pitches, the ledger — lives in Radix tabs below, each drawer keeping its own
  `SafeSection`, the strip `overflow-x-auto` so three labels don't wrap and
  eat the fold at 390px.
- Motion is entrance-only (`Reveal` staggers by index, the tracker fills as
  one stroke, nothing loops) and everything checks `prefers-reduced-motion` —
  verified by emulation: under `reduce` the money's first paint is its final
  value. `HomeSkeleton` mirrors the new arrangement (photo box, cover strip,
  tab strip); CLS measured 0.0000 at 390 and 1280 with the payload delayed.

## What a creator says about themselves

The suggestion lists were food and nothing but food — cafe, brunch, bakery,
brewery, home chef — on a platform that accepts every category. That list told
a fashion or gaming creator they were in the wrong place before they had typed
anything. `CREATOR_TAXONOMY` is fifteen groups spanning every category, with
the food terms kept *inside* the food group; `lib/taxonomy.js` mirrors it and a
unit test fails if the two drift. `niches` and `genres` are still free text —
this is a starting point, not an enum.

**City is a closed list** (`INDIAN_CITIES`), because free text cannot be
reconciled: "Bangalore", "bangalore", "Bengaluru " and "BLR" are four rows in a
filter and one city in reality, so a brand filtering the directory found a
fraction of the people in it. `_canonical_city` folds the aliases and 422s on
anything else, naming what is allowed; an empty city is still allowed, because
the profile is built over sittings and refusing it would block partial saves.
The **neighbourhood stays free text and stays optional** — it is not in
`_PROFILE_COMPLETENESS_FIELDS`, and neither is YouTube unless the creator says
they post there.

`about` is the one field on the form whose shape the creator chose. It is
optional on purpose: putting it in completeness would drop every existing
creator below 100% and silently un-submit them. `facebook_url` is optional for
the same reason and is deliberately **not** in `CREATOR_PLATFORMS`, which would
make it a completeness question for anyone who ticked it.

### Seeing your own profile, and re-approval

`/profile` is the creator's own profile, read-only, reached from an avatar menu
in the navbar (`CreatorAvatarMenu`, creator-only — an admin's navigation is the
console and a brand's is its dashboard, neither of which this would open onto).
Editing is a separate state at `/onboarding/creator`, reached from there. It
used to be the only way to see your own details at all, so checking what a
brand sees meant opening a builder and reading it out of input boxes.

**`MATERIAL_PROFILE_FIELDS` is the one definition of a change worth re-checking**
— name, both Instagram fields, YouTube, Facebook, city, and every payout detail.
It was three fields inline in the update handler, which missed YouTube, Facebook
and all of the payout ones. Everything else is theirs to change freely: putting
a creator back in a queue for fixing their bio is how a profile stops being kept
up to date.

- **A re-check is not a downgrade.** `verification_status` stays `verified` and
  `pending_review` goes true. Sending them back to `pending` would erase the
  record that they were ever approved — the same reason suspension is separate
  from rejection — and would empty the admin's "edited since approval" queue,
  which keys on exactly that pair. A unit test pins that the handler never
  writes `verification_status`.
- `_awaiting_recheck` is the reader, and it gates **new applications only** —
  the apply route, the `can_apply` flag so the button agrees with the API, and
  the invite path, where an invite they could not accept goes nowhere. Work
  already accepted is untouched, which is a matter of where the check is *not*:
  a profile edit never reaches into `collaborations`.
- `pending_review_fields` records what triggered it, so the notice names the
  change rather than saying "something". The creator is told **once**, on the
  way in — saving again while already pending must not send it again. An admin
  decision clears both the flag and the labels.

### The address, and the pin

Two things that look like one. `full_address` is what gets printed on a
delivery label; `location_lat`/`location_lng`/`location_place_id` are what
somebody navigates to. Places autocomplete lands on the street about as often
as the building, so the pin is **draggable** — a precise-looking coordinate
that is precisely wrong is worse than none.

- Dragging moves **only the coordinates**. Reverse-geocoding the drag would
  replace "2nd floor, above the pharmacy" with a street name, which is exactly
  what a courier needed.
- `REACT_APP_GOOGLE_MAPS_API_KEY` is read from the environment and never
  hardcoded; a test greps the whole frontend for an `AIza…` literal. It is a
  browser key, so referrer restrictions in the Google console are the actual
  protection.
- **Absent is a supported state**, the same shape as Instagram: `mapsConfigured()`
  is false, no script is injected, the field is a plain textarea, and a saved
  pin still shows as a static image and a Maps link. Verified by rendering with
  no key — every field present, zero requests to Google.
- **The pin is never brand-visible.** A coordinate on somebody's front door is
  their home address to five decimal places. It is off the allow-list and named
  in `BRAND_FORBIDDEN_CREATOR_FIELDS` so the leak test looks for it. `about` and
  `facebook_url` *are* brand-visible — they were written to be read.

## Instagram stats

Official numbers come from **"Instagram API with Instagram Login"**, never the
Facebook-Login flow — that one requires every creator to link a Facebook Page.
`graph.facebook.com` must not appear in this codebase; a unit test enforces it.
The Apify scraper this replaces breached Instagram's terms; **don't bring back
any scraped source.**

- Two read scopes only (`INSTAGRAM_SCOPES`): `instagram_business_basic` and
  `instagram_business_manage_insights`. Nothing here can post or change anything.
- Tokens live in their own collection, `instagram_connections`, encrypted with
  Fernet over `INSTAGRAM_TOKEN_KEY`. A separate collection means no creator-profile
  serializer can leak one by accident. **No route may return a decrypted token.**
- Absent credentials is a supported state (the app is in review): `instagram_configured()`
  is false, the connect routes 503 with an explanation, the jobs no-op, and follower
  counts stay self-reported. Never make anything else depend on it being on.
- Stats are cached for `INSTAGRAM_STATS_TTL_HOURS` (12) and refreshed by
  `refresh_instagram_stats`. **Never fetch on a dashboard load** — the ceiling is
  200 calls per user per hour and a reading costs three.
- `refresh_instagram_tokens` renews the 60-day token a week before expiry. A
  revoked or expired token (`_is_revoked`) sets the connection `stale`, drops the
  token and asks the creator to reconnect; a transient Graph error is deferred, not
  treated as revocation.
- `_follower_provenance` travels with every follower count on every surface.
  `follower_count_self_reported` is kept so disconnecting falls back to it, and a
  typed number can't overwrite a verified one.
- Only a Professional (Business/Creator) account can authorise. A personal one gets
  a 409 whose detail is `{"code": "not_professional", ...}` so the UI can show the
  switching steps and a retry.

## The brand behind the brief

A creator could see a campaign and learn nothing about who was posting it.
`GET /brands/{id}` is the public brand page — server-rendered by the backend
like `/c/{id}`, for the same reason, and only for **verified** brands. Vercel
proxies `/brands/:id` and `/sitemap.xml` alongside `/c/:id`; they are one
feature, and shipping one without the others is a link into a page that does
not exist.

- **`_public_brand` is the only projection of a brand on any unauthenticated
  surface**, an allow-list like `_brand_visible_creator`. The manager's phone,
  email and name, the `registered_address` (frequently a director's home), the
  GST number and the rejection reason are all named in
  `PUBLIC_BRAND_FORBIDDEN_FIELDS`; a unit test renders the page with those
  values planted and searches the output.
- **An outlet is not a registered address.** `outlets` on the profile are
  shopfronts a creator turns up to — name, address, area, canonical city, and
  an optional pin (both coordinates or neither, `_clean_outlets`). The pin
  links out as a plain Google Maps URL built from the coordinate, never the
  text, and the page embeds **no API key** — it is unauthenticated, so a
  static map would publish one for decoration. `about` and `city` round out
  the creator-facing half; none of it is in `_BRAND_REQUIRED_FIELDS`, because
  it is what a creator reads, not evidence of anything.
- The page lists the brand's **live** briefs, each linking to its `/c/{id}`
  page, and the brief page links back — the only edges between public pages,
  which with `/sitemap.xml` (verified brands + their live briefs) is what
  makes "indexable" true rather than aspirational. `robots.txt` disallows
  `/brand/` (the console — trailing slash, so `/brands/{id}` stays allowed).
- `BrandName` is the one component naming a brand in the app — avatar, name,
  and a real `<a>` to the public page, plain text when there is no id. The
  campaign card became an `<article>` with a stretched link on the title,
  because an anchor inside an anchor is invalid markup; anything interactive
  above the overlay carries `relative z-10`. On the application page both
  links ride `APPLICATION.campaignLink` / `APPLICATION.brandLink`, and the
  admin route swaps in console links via `entityLinks` — the component still
  never asks what role is looking.
- The brand edits its own half in onboarding: `about`, a canonical-city
  dropdown, and an outlet repeater that reuses `AddressPicker` (now in
  `components/`, not `components/creator/`). The picker's privacy note is a
  prop — the creator's address is team-only, an outlet is public, and the
  default text saying "only the WeAre team sees it" would have been a lie on
  this form. A verified brand gets a "View your public page" link.

## Brand verification

Anyone can sign up and claim to be any business, so a brand is a claim until we
have checked it. `verification_state` says where it stands —
`unsubmitted | pending_verification | verified | rejected` — alongside the older
`verified` boolean, which a great deal of code still gates on and which stays
authoritative. `_brand_verification_state` derives the state for rows written
before the field existed, and startup backfills it.

- Required before we'll look (`_BRAND_REQUIRED_FIELDS`): business name, legal
  entity name, business type, category, registered address, contact person,
  their designation, a work email. GST number, website and the official social
  handles are optional — plenty of real small businesses have none of them.
  `PUT /brand/profile` is a partial save like the creator's, and stays open to a
  rejected brand so it can fix itself.
- Documents (`brand_documents`) prove the business exists; the fields say which
  business and who is asking on its behalf. Any one of GST certificate, business
  registration, FSSAI licence or shop & establishment licence is enough. Several
  are allowed and nothing is deleted on upload, so a clearer scan after a
  rejection doesn't cost the rest.
- **They are never publicly served.** Files land in `PRIVATE_UPLOAD_DIR`,
  deliberately *not* `UPLOAD_DIR` — that one is `app.mount`ed as `StaticFiles`,
  so anything in it is fetchable by anyone who guesses the name, and these carry
  registered addresses and directors' names. The only way out is
  `GET /admin/brands/{user_id}/documents/{id}`, admin-only, audited,
  `Cache-Control: no-store`, filtered on both ids. `_serialize_brand_document`
  returns no path and no URL. Don't add one.
- `_store_private_upload` sniffs magic bytes exactly like the creator profile
  image (`sniff_document_type` = the image signatures plus `%PDF-`); the stored
  name is ours and random, the uploader's filename is kept only as a label.
- `POST /brand/verification/submit` needs every required field and at least one
  document, and 409s naming what's absent. `POST /admin/brands/{id}/verify` and
  `/reject` (reason required) decide, notify on WhatsApp either way, and the
  rejection quotes the reason so the brand knows what to fix.
- The queue is `verified: false` **and** `verification_state` in
  `pending_verification | rejected` — a bare signup is not a queue item.

The brand's half of this is `pages/BrandOnboarding.jsx` plus
`components/brand/VerificationDocuments.jsx`. For a long time it did not exist:
the four endpoints above shipped with no caller anywhere in the frontend, so a
brand could sign up, draft, and then hit `_verified_brand_or_403` forever with
no route to the thing that would clear it. If a backend flow has no UI it is not
shipped, whatever the tests say.

- Onboarding and verification are **one page in two halves**, because the second
  is invisible otherwise — an unverified brand drafts happily and only meets the
  wall at publish. The top is the thirty-second setup; below it are the fields a
  reviewer needs, the documents, and the submit.
- Saving is partial and submitting is not, mirroring the server exactly: `Save`
  writes whatever is filled in, `Send for verification` demands the set. The
  button is disabled when it would 409, and **`missing_fields` is rendered as a
  list** — a grey button with no explanation is how a form becomes a support
  ticket.
- The upload's limits come from the server (`max_document_bytes`,
  `accepted_mime_types`, `max_documents` on the verification block) and are
  checked in the browser before a byte moves, so a 6MB scan fails instantly
  instead of after a minute on mobile data. `ACCEPTED_DOCUMENT_MIMES` is derived
  from the signature tables `sniff_document_type` actually uses, so the `accept=`
  attribute cannot offer a format the sniffer will reject.
- **Uploads are sequential, one progress bar each, and the picker is closed
  while any is in flight.** Parallel uploads on a phone make every bar crawl and
  none finish; a silent disabled button gets pressed again, and the second press
  is a second document in the reviewer's queue.
- A file that fails the local check is **queued as already-failed rather than
  dropped**, with the error on that file's own row. Dropping it silently is how
  somebody submits believing four documents went up.

The gate is `_verified_brand_or_403`. An unverified brand may draft campaigns
and edit its own profile; anything that *reaches a creator* is behind it —
publish, the creator directory and its filters, the applicant list, accept,
decline, approve content, request changes. `_why_brand_is_blocked` gives the
three states three different next steps; "not verified" on its own just
generates a support email.

**Ownership is checked before verification**, always:

```python
    campaign = await _own_campaign_or_404(campaign_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
```

The other order turns another brand's campaign from a 404 into a 403, which
leaks which ids exist. A unit test pins the order for every gated endpoint.

## Finding a brief, and sending one on

`GET /campaigns` lists everything live — `open` and `upcoming` — with **no
filter applied by default**, and narrows on `city`, `area`, `category`,
`campaign_type` and `compensation_type`. It is paginated with the matched total
in `X-Total-Count`; it used to be a bare array capped at 200 with no way to know
anything had been cut off.

**The default order is "most relevant first."** `score_campaign_for_creator` is
the mirror of `score_creator_for_campaign` — same vocabulary (`_campaign_terms`,
the category synonyms), pointed the other way: niche/genre overlap saturating at
three matched terms, city, neighbourhood. Pure and DB-free, so the ranking runs
in Python over the newest `_RELEVANCE_SCAN_CAP` matches and then slices, keeping
pagination and the count header honest. An empty profile scores everything 0 and
the sort falls through to recency — the old order, and the right one for
somebody we know nothing about. **It deliberately knows nothing about money**:
a barter brief ranks on fit exactly like a paid one, or "most relevant" quietly
becomes "paid first". Explicit `sort=newest|budget_desc|budget_asc` still mean
what they say. The "Live pool" masthead figure is gone — it summed
`budget_per_creator` across the feed, a number barter made a lie.

- **A money filter says nothing about barter.** A barter brief keeps its
  vestigial budget, so `budget_min/max` used to surface a barter stay whose
  leftover number happened to land in the range. The filter now ANDs in
  `{"compensation_type": {"$ne": "barter"}}`; combined with an explicit
  `compensation_type=barter` it returns the empty set, which is the honest
  answer to "barter briefs priced ₹5k–15k".
- **`city` on a campaign is new.** Campaigns carried only `area`, the free-text
  neighbourhood, so "briefs in my city" was unanswerable even though a creator's
  city is a canonical dropdown. It goes through `_canonical_city`, the same
  function the creator's does, or the two could never be compared.
- Filtering for the default city or `fixed` matches documents with **no field at
  all** — campaigns predate both, and a filter that only works after a migration
  has run returns nothing on a box that has not restarted. Same trap as
  `execution_owner` and `showcase`.
- Every clause that wants `$and` — the default-city filter, the keyword
  search, the barter exclusion, the visibility cut — **appends via
  `setdefault`, never assigns**: an assignment among the appends silently
  drops whatever came before it, and a unit test greps the handler for the
  bare form.
- `/campaigns/filters` returns distinct values, not the full enums: offering a
  category with no live brief in it is a filter whose only outcome is an empty
  list.

### Public and invite-only briefs

`visibility` on a campaign, `public` or `private` (`CampaignVisibility`).
Public is the shop window; private is invite-only and **enforced server-side on
every campaign read and on apply** — the pickers and pills are a courtesy on
top. `_campaign_visibility(doc)` is the one reader (absent reads `public`,
campaigns predate the field) and `PUBLIC_CAMPAIGN_QUERY` is the one filter,
`$ne: "private"` for the usual pre-migration reason.

- **Two doors into a private brief, in `_creator_may_see` /
  `_visible_campaign_ids_for_creator`**: an invitation row in
  `campaign_invitations`, or an active collaboration — a brand flipping a live
  brief private must not vanish it from the people already on it. Everyone
  else gets a **404, not a 403**: whether the campaign exists is itself what
  the privacy protects.
- The cut applies to browse (folded into the same query as the filters, so
  pagination and the count stay right), the detail read, apply, the `/c/{id}`
  share page, the sitemap, the landing preview, the brand page's shelf, the
  suggestions panel, and `/campaigns/filters` — a private brief's
  neighbourhood showing up as a dropdown option would announce its existence.
  Admins see everything; the owning brand reaches its own through the
  ownership checks it already had.
- The brand picks at post time (`PostCampaignPayload`, defaulting to public)
  and may change it on edit; the edit round-trip in `PostCampaign` re-seeds
  the picker so fixing a typo doesn't silently flip a private brief public.
  Every owner-facing row prints one of the two words — a brand reading
  nothing would have to guess the default — and a creator who can see a
  private brief gets an "Invite-only" pill, which for them is true and
  flattering. **No Share button on a private brief**: its public page 404s by
  design, so the button would copy a dead link. Absent, not disabled.
- `lib/visibility.js` mirrors the reader (absent means public) and holds the
  two options' wording.

### The shareable page

`GET /c/{id}` — a public brief, outside the `/api` prefix, no account needed.

**Server-rendered by the backend, deliberately.** The app is a static SPA and
the crawlers that build a WhatsApp or Instagram preview do not run JavaScript,
so Open Graph tags injected by React are tags no crawler ever sees. It is the
page a *person* lands on too, not a crawler-only shim that redirects — one page,
so what the preview promised is what opens.

- Only live briefs from **verified** brands, the same rule as the shop window:
  an unverified brand can post and be seen by verified creators in-app, but is
  not promoted to the open internet under our name. Everything else 404s,
  including a malformed id.
- Every field is `html_escape`d — a campaign title is brand-supplied text on a
  public page — and barter never renders as a rupee figure.
- `PUBLIC_SHARE_BASE_URL` sets the origin links are built from, defaulting to
  the frontend's. **Vercel must proxy `/c/*` to the backend** or a shared link
  opens the SPA and previews as the generic site card; see PREVIEW.md.
- `ShareButton` uses `navigator.share` where it exists — on a phone that is
  WhatsApp and Instagram in one tap — and copies otherwise. Dismissing the sheet
  rejects with `AbortError` and must not raise a toast: that is a decision, not
  a failure. It `stopPropagation`s because the card it sits on is a link.
- `og:image` is the brief's **own cover**, absolute, with the site card as the
  fallback — a link that previews the same as every other link is a link nobody
  taps. `_absolute_media_url` builds it against `request.base_url`, the backend,
  which is the host that mounts `/uploads`; `_share_base()` would be wrong, as
  only `/c/*` is proxied to the frontend. The declared `og:image:width/height`
  are emitted **only for the site card**, whose size we know — a wrong one is
  worse than none, because some crawlers lay the card out from it.

## A picture on the brief, a mark on the brand

`cover_image_url` on a campaign and `logo_url` on a brand profile. Before them
every listing was the same grey rectangle, which is the strongest argument
against reading any of them.

- **The value is a path we issued.** Both are set by uploading a file to their
  own route — `POST`/`DELETE /brand/campaigns/{id}/cover` and
  `/brand/profile/logo` — never by a field on an edit payload, so there is no
  way to point a campaign at somebody else's server. Both go through
  `_replace_image` → `_store_upload`, the same function the creator's profile
  photo uses: the type comes from the leading bytes, the stored name is ours and
  random, the ceiling is enforced while streaming.
- They land in `UPLOAD_DIR`, which is `app.mount`ed — the exact opposite of the
  brand's verification documents. A cover is meant to be seen by strangers.
- `_replace_image` writes the new file, points the record at it, and **only then**
  deletes the old one. The other order leaves a record pointing at nothing when
  the write fails, and a broken image is worse than an out-of-date one.
- The cover is the brand's **or an admin's**, via `_own_campaign_or_404`, and
  audited both ways. It is deliberately **not** behind `_verified_brand_or_403`:
  a cover on a draft reaches nobody, and publish already has the gate.
- Neither is behind verification, and the logo is **not locked when a brand is
  verified** — it is how a business is recognised, not evidence of who it is.
- `ACCEPTED_IMAGE_MIMES` is derived from `_IMAGE_SIGNATURES` for the same reason
  `ACCEPTED_DOCUMENT_MIMES` is, and rides on `GET /brand/profile` as
  `uploads.accepted_image_mime_types` / `max_image_bytes`, so the browser
  pre-check uses the server's numbers rather than a copy that drifts.

`components/ImageUploadField.jsx` is the one control for both, in two modes: it
uploads on pick when given an `endpoint`, and holds the `File` behind an object
URL when not — because a cover has to be pickable on a brief that does not exist
yet. `PostCampaign` sends the held file the moment the campaign is created, and
if *that* fails it says so and keeps the brief; losing a filled-in form over a
picture would be the wrong trade.

### No picture is a state, not a hole

`CampaignCover` draws either the image or a generated fallback — the brand's
initial on a tint derived from the campaign's id — inside an `aspect-[16/9]`
container. `BrandAvatar` is the same idea at avatar size, and mirrors
`CreatorAvatar` exactly: the two appear on the same screens, so two fallback
treatments there would read as two kinds of account. A logo is `object-contain`
where a photo is `object-cover`, because cropping a mark to fill a square cuts
it in half.

- `_cover_hue` and `coverHue` in `frontend/src/lib/cover.js` **must agree** —
  the card in the app and the server-rendered share page of the same brief are
  the same colour. Both are FNV-1a; the first version summed character codes and
  was measured to be useless, putting ids that differ in their last byte (which
  is what consecutive ObjectIds are) two degrees apart.
- **The ratio is on the container, never on the `<img>`**, so an image that
  never arrives still occupies the space it claimed.
- **The generated branch carries no `.media-frame`.** Both it and the gradient
  set `background-image` and one would silently win — the same rule the design
  foundations state for grain.
- On CampaignDetail the cover sits **below** the title and the share row, not
  above them: a 16:9 band at the column's width pushes the eyebrow, the title
  and the brand off a phone screen, and those are what a creator is deciding on.
- Every skeleton standing in for a card or a detail page reserves the same box:
  `CardSkeleton({cover})`, `DetailPageSkeleton({cover})` and Landing's
  `BriefCardSkeleton`. Measured with the API delayed 700ms and the images 500ms,
  and with the skeletons confirmed to have actually rendered — otherwise the
  measurement is vacuous. **When measuring with Playwright here, the context
  option is `viewport`, not `viewportSize`** — this project's playwright-core
  silently ignores the latter, so every "375px" number taken with it was really
  1280 and mobile-only shifts passed unseen. At real widths: CampaignDetail
  0.0000 with and without a cover; landing 0.0042/0.0011 (375/1280); campaigns
  0.0000/0.0047 — the 0.0718 at 375 was the Live pool aside mounting only
  after the fetch and pushing the filter bar down ~120px; the aside has since
  been removed outright, which is also why the number improved again.


## What a brief pays

`compensation_type` on a campaign, one of three (`CompensationType`):

- `fixed` — `budget_per_creator` is the fee.
- `negotiated` — the budget is a guide; the real number is agreed offline and
  recorded against the collaboration (see work notes).
- `barter` — no money. A meal, a stay, a product.

**Barter is admin-only.** A brand posts paid work or it posts nothing:
`BRAND_COMPENSATION_TYPES = ("fixed", "negotiated")`, and `_refuse_brand_barter`
422s on both brand write paths — `create_brand_campaign` and
`update_brand_campaign`, the second because its update loop copies the payload
generically and `compensation_type` would otherwise ride along with everything
else. `PATCH /admin/campaigns/{id}` is the **only** route that accepts it, and
deliberately does not call the guard; a unit test pins both halves. There is no
admin campaign-*create* route, so in practice a barter brief is one an admin
converted, which means somebody read it first.

The guard refuses two different things: writing `barter`, and rewriting the
compensation of a campaign that already *is* barter — otherwise a brand could
undo a WeAre arrangement into a cash liability. The rest of such a brief stays
theirs to edit.

`compensation_type` is typed as the full enum on `PostCampaignPayload` on
purpose. Narrowing it to the brand subset would answer with pydantic's "Input
should be 'fixed' or 'negotiated'", which reads like a typo; the handler
refuses it with the actual reason instead.

- `_compensation_type(doc)` is the only reader. Campaigns predate the field and
  a bare `.get()` returns `None`, which is not a third kind of money — they
  were all brand briefs against a cash budget, so they read as `fixed`. Startup
  backfills them.
- **A barter campaign keeps whatever budget it was posted with**, so that an
  admin switching it back is not lossy. That makes rendering
  `budget_per_creator` unconditionally a lie, so every response carrying a fee
  carries the type beside it and every surface that shows money goes through
  `formatCompensation` / `isBarter` in `frontend/src/lib/compensation.js`. A
  unit test walks `server.py` for a fee emitted without its type.
- The brand form imports `BRAND_COMPENSATION_OPTIONS`, which has no barter in
  it — the option is *absent*, not present and disabled, so there is nothing to
  re-enable from devtools. `ALL_COMPENSATION_OPTIONS` is admin-only and is used
  by exactly one control, `CampaignEditDialog`.

## Collaboration lifecycle

`COLLAB_STATE_ORDER` in `server.py` is the single source of truth:

```
applied → verified → accepted → commercial_agreed → slot_booked → attended
        → [draft_submitted → draft_approved] → content_submitted
        → content_approved → in_payment → closed
```

Plus two terminal exits that are **not** steps: `declined`, `cancelled`
(`TERMINAL_COLLAB_STATES`). The bracketed pair is optional per campaign — see
"The draft gate" below. Who moves each step matters:

- **Admin** — verification, fee, slot, attendance, payment (`/admin/collaborations/{id}/advance`)
- **Brand** — `accepted` and `content_approved` only (`_BRAND_OWNED_TRANSITIONS`).
  The admin `advance` endpoint refuses these with 409 by design.
- **Reviewer** (brand or WeAre, per `execution_owner`) — `draft_approved`, and
  sending it back to `attended`. `advance` refuses both
  (`_DRAFT_OWNED_TRANSITIONS`) for a different reason: they are not decisions to
  fabricate.
- **Creator** — `slot_booked` (booking their own place, and cancelling it back to
  `commercial_agreed` up to 24h before), `draft_submitted` and
  `content_submitted`, and may resubmit either until it is approved.

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

### The draft gate

`content_submitted` carried a link to something already live, so the brand's
first sight of the content was after the creator's followers had had theirs and
"can we change the caption" was a request to delete a post.
`draft_submitted → draft_approved` sit between `attended` and
`content_submitted`, and the routes are `/drafts/{collab_id}/…`.

- **Optional per campaign, and absent reads off.** `_requires_draft_approval`
  returns False for a campaign with no such field, which is every campaign
  written before it existed. **There is no backfill, deliberately** — that is
  the whole migration guarantee: anything already past `attended` keeps the path
  it started on, because the two states are simply not on its ladder. New
  brand-run campaigns default it *on* at creation; the creation default and the
  reader default differ on purpose, because one is a policy for new work and the
  other is a promise to old work.
- **`_collab_ladder(campaign)` is the one reader of "which states does this
  campaign walk"**, and `_next_collab_state` / `_previous_collab_state` /
  `_lifecycle_for` all take the campaign. A collaboration *standing* on a draft
  state falls back to the full ladder whatever the campaign now says — a toggle
  flipped mid-flight must not strand somebody on a state with no way forward.
- **A live link is refused before the draft is approved.** `submit_collab_content`
  accepts from `draft_approved` on a reviewing campaign and from `attended`
  otherwise; accepting `attended` on both would be the route around the gate.
  `can_submit_content` on the creator's row mirrors it exactly.
- **Two ways in, because one of them fails on the phone this runs on.** A
  finished reel is often several hundred megabytes and a creator on mobile data
  would publish it rather than watch a bar crawl, so an unlisted link is a
  first-class option. Both routes go through `_record_draft`, so the file and the
  link cannot diverge in state, audit or notification.
- **The file lands in `PRIVATE_UPLOAD_DIR`** — the same reasoning as the brand's
  verification documents, and the opposite of a cover image. An unpublished draft
  is the one thing here that must not be one guessed URL away from the internet.
  `_serialize_draft` returns no path; the only way out is
  `GET /drafts/{id}/file`, audited. `sniff_draft_type` reads the leading bytes
  (ISO-BMFF `ftyp` at offset 4, EBML for WebM, the image signatures) and refuses
  a PDF, which is a valid *document* and not a draft.
- **The reviewer follows `execution_owner`**, through `_question_staff_may_see` —
  the same reader the question threads use, not a second copy. 404 behind all
  three doors.
- **A send-back requires a note** and `$inc`s `draft_revision_count`. Two
  revisions is a conversation; five is a brief that was never clear, and only a
  counter shows the difference. The note rides back to the creator's card as
  their next action, and a new draft clears it while the count survives.
- A draft is **not** in `DELIVERED_COLLAB_STATES` — performance is measured on
  published content, and a draft has no reach — but both states are in
  `COLLAB_GROUP_ONGOING`, and `_roster_rows` counts them as having turned up.

## Who runs a campaign

`execution_owner` on a campaign, `brand` or `weare`. It is what applications
are **routed on**, which is the job it exists to do: before it, every new
application went to the brand's manager whether or not the brand had asked us
to run the campaign, so a brand that handed one over still got paged for every
applicant and no WeAre manager was told at all.

- `_execution_owner(campaign)` is the only reader — pure, DB-free, and an
  absent or unrecognised value reads as `brand`. Every surface showing this has
  to print one of two words, so it never travels as `None`. A brand picks at
  post time (`PostCampaignPayload`, defaulting to `brand`: posting a brief means
  running it unless you say otherwise).
- **It never disagrees with `manager_id`.** Assigning a WeAre manager sets
  `execution_owner: "weare"` in the same write — there is no such thing as one
  of our managers running a campaign the console calls brand-run. Going the
  other way, a `weare` campaign is created with `_NO_CAMPAIGN_MANAGER` rather
  than the brand's own person, which would route applications straight back to
  the brand that asked us to take it on.
- Routing, in `apply_to_campaign`: `weare` tells `notify_weare_team` (the
  assigned manager, or **every admin** when nobody is assigned — otherwise a
  campaign we have taken on but not staffed is the one arrangement where an
  application reaches nobody) and still tells the brand through
  `_tell_brand_manager_unless_managed`, which is being informed rather than
  being asked to act. `brand` tells the brand's manager, as before. Admins see
  and act on everything either way; none of the admin endpoints are scoped by it.
- A brand may change it **only while the brief is a draft or in review**
  (`_refuse_late_execution_handover`). After that, creators have applied knowing
  who they would be dealing with, and switching would silently stop telling
  whoever has been working it. An admin can still move it; `PATCH
  /admin/campaigns/{id}` deliberately does not call the guard — the same shape
  as `_refuse_brand_barter`, and for the same reason: the brand edit loop copies
  the payload generically, so an unguarded field rides along with everything else.
- Filtering for `brand` is `{"$ne": "weare"}`, not an equality test — campaigns
  predate the field. The startup backfill fills them in (deriving `weare` from a
  WeAre `manager_id`), but a filter that only works after a migration has run
  returns nothing on a box that has not restarted. Same reasoning as `showcase`.

`lib/execution.js` is the frontend half — the two words, the three audiences'
wording, and the reader with the same default. `ExecutionBadge` / `ExecutionNote`
are one component rather than a pill per console, because the point of the field
is that the admin, the brand and the creator agree about it.

## One application, on its own screen

`components/application/ApplicationDetail.jsx`, rendered at **two routes off one
component**: `/admin/applications/:id` and `/brand/applications/:id`. Sharing it
is the point — the admin and the brand used to read the same collaboration
through different endpoints and describe it differently, which is how an
approved application went on showing as pending in one console and approved in
the other.

- `GET /applications/{id}` serves both. Access is `_note_readable_collab_or_404`
  — the same three doors as the work notes the screen embeds, a 404 behind all
  of them — and the creator block goes through `_brand_visible_creator`, so the
  shared payload carries no contact detail for either role.
- **The client never asks "am I an admin".** Every action arrives in `actions`,
  decided server-side, so neither console offers a button the API will refuse.
  A unit test greps the component for role checks.
- `_NEXT_ACTION` is one table saying who is waited on at each state, and
  `_lifecycle_for` ships the whole ladder with the response. The status bar
  draws what it is given; rebuilding `COLLAB_STATE_ORDER` in the client would be
  a second copy of the state machine to keep in step.
- An exit (`declined`, `cancelled`) is **the bar stopping, not an eleventh
  step** — it is said in words rather than drawn as a box.

### What a brief pays, at the fee step

`_resolve_agreed_amount(campaign, supplied)` is the only place that decides, and
**both writers go through it** — the admin's `advance_collaboration` and the
brand's `brand_record_agreed_amount`. Two paths to one state is how two states
drift apart.

- `negotiated` — an amount is **required**; there is no fee until somebody
  agrees one. The UI disables the button rather than producing a 422.
- `fixed` — prefilled from `budget_per_creator` and **locked**. A supplied
  figure is accepted only if it matches, so a stale form cannot rewrite a
  commercial per creator.
- `barter` — **no amount, and `None` rather than `0`**. Zero reads as "agreed,
  nothing" on every surface that shows money.

This step used to demand a figure whatever the campaign was, so a **barter
collaboration could never leave `accepted`** — and `AgreedAmountPayload.agreed_amount`
is now optional for that reason: the model cannot see the campaign, so it must
not decide.

After the fee, **the next action is the creator's** — they book, or on a
`personal_table` they pick a time inside the window. Both notifications say so;
neither quotes a rupee figure on a barter brief.

## Content performance

`content_url` was collected on every delivery and read by nobody. It is the
only evidence that the work we arranged did anything, which makes it the answer
to the question a brand asks at renewal.

One record per collaboration in `content_performance`, upserted on
`collaboration_id`: a post keeps accruing reach, so a second reading is a
correction of the first, and `captured_at` says which moment the numbers
describe. Written by `_record_performance`, which both the admin and the
`/manager` route delegate to (the manager's is scoped by
`_managed_campaign_or_404`) — the audit-coverage tests name it as a delegating
helper, so it must keep auditing.

- **An unknown metric is `None`, never `0`.** A post with no saves and a post
  whose saves we could not read are different, and averaging the second as a
  zero makes a campaign look worse than it was. Every surface draws unknown as
  an em dash.
- `engagement_rate` is **derived, never stored or typed** — `_engagement_rate_from`
  computes engagements over **reach**, recomputed on read so an old record
  reports the current formula and can never contradict its own inputs. Against
  reach rather than followers: a rate against followers flatters a post that
  reached nobody.
- The rollup's headline rate is total engagements over total reach, **not the
  mean of the per-post rates** — the mean lets one tiny post with a freak rate
  move the number.

### Barter and cost

`_rollup_performance` takes the paid set **and** the barter set, and they are
not each other's inverse. Excluding barter's *spend* would be meaningless (it
is already zero); the damage is on the other side of the division, where its
reach would inflate the denominator and report a cost per thousand we never
achieved. So cost metrics use `paid_reach` on both sides, and `paid_reach`,
`barter_reach` and `awaiting_payment_deliveries` all come back so the figure
can be checked by hand.

A delivery on a *paid* campaign whose payment hasn't gone out is **neither**
paid nor barter. Deriving barter as "everything unpaid" would put a line in a
client report claiming we got work free that we simply haven't settled —
`_barter_collab_ids` reads `compensation_type`, never a missing payment.

### Instagram, and never depending on it

`_fetch_instagram_performance` returns `(metrics, reason)` and **never raises**.
It matches the submitted permalink's shortcode against the creator's *own*
`/me/media`, so there is no path that reads insights for a link we were merely
handed. Every failure returns a sentence, and the fetch endpoint answers 200
either way — a creator who hasn't connected Instagram is the ordinary case, not
a fault, and manual entry is always on screen beside it.

### The report

`GET /admin/campaigns/{id}/report?format=json|csv|html`, all three off one
builder so the spreadsheet and the printable page cannot disagree. It goes to a
brand, so it carries what a brand may see: handles and follower counts, **never
a phone number, email or address** — a unit test walks the builder for those
keys. CSV goes through `csv.writer`; the HTML escapes everything typed and is
light-on-white because it gets printed. Both are `no-store`.

Authenticated deliberately — "shareable" means an admin prints it to a PDF and
sends that. A public link would be a new unauthenticated surface carrying
creator data, which is a decision to take on purpose rather than as a side
effect of adding an export.

`showcase` is admin-only and its own endpoint, not a field on
`UpdateCampaignPayload` — that payload is the brand's edit route too, and which
campaigns we put in front of a prospect is not theirs to decide. The list filter
uses `{"$ne": True}` for "not showcased" so campaigns predating the field match.

## Health, activity and exports

The overview leads with **what is going wrong**, then what the business is
doing, then its own numbers, then the exports. A campaign quietly underfilling
four days before the shoot generates no notification and sits in no queue — it
is discovered when the brand rings up, unless something looks for it.

`GET /admin/health` runs seven checks: underfilling campaigns near their day,
accepted creators with no slot, content overdue after attendance, drafts nobody
has reviewed, payments sitting unpaid, brands waiting on our verification, and
profiles that stalled. The draft one has the shortest fuse
(`DRAFT_REVIEW_OVERDUE_DAYS`, 2) because it is the only row where the delay is
*ours*: the creator has done the work and cannot publish until somebody looks.
Every threshold is a named constant (`FILL_WARNING_RATIO`, `PAYMENT_OVERDUE_DAYS`
…) because each is a judgement about how much slack the operation has, and they
travel back in the response so the panel quotes the server's numbers rather than
a copy that drifts. **Every row carries an `href`** — a count tells you there is
a problem and then makes you go and find it.

`GET /admin/intelligence` is four shapes and no more: campaigns posted per week
by current status, fill-rate trend, repeat versus one-off brands, active versus
dormant creators over `DORMANT_AFTER_DAYS` (60). Charts are hand-written SVG in
`components/admin/Health.jsx` — four small shapes do not justify a charting
dependency. A week with no data is `None` and **breaks the sparkline** rather
than being drawn as zero; a line that runs straight through a gap asserts
something we do not know.

### Exports and the contact line

`GET /admin/exports/{kind}` — creators, brands, campaigns, collaborations,
payments, audit — honouring the caller's filters and a date range. One route,
because six copies of the date window, the CSV framing and the `no-store` header
is six places to forget one. `kind` is checked against `EXPORT_KINDS` **before**
the `globals()` lookup that resolves the builder. Every download is audited,
including whether it carried contact details.

**This is the only family of responses where creator contact details are
allowed.** An admin export is an internal document — a payout row without a
number to chase is useless to whoever is reconciling a bank statement — and
`EXPORTS_WITH_CONTACT` names which ones carry them. Nothing brand-facing may,
including the campaign report.

`tests/unit/test_exports.py` holds that line by **running the brand-facing
builders with recognisable contact values planted in the input and searching the
real output**, not by reading the source for a key name. Source-reading catches
the mistake somebody makes on purpose; running it catches the one where a phone
number arrives through a `**spread` from a document nobody remembered had one.
Planting a leak in `_build_campaign_report` fails the suite — checked.

## The admin console

`/admin` is a **layout**, not a page (`pages/AdminConsole.jsx`): it owns the tab
strip and the badge counts and renders the matched route into an `<Outlet>`. The
URL is the state. It used to be one route with a `useState` tab, which made every
screen unaddressable — no deep link, no back button, and a reload always landed
on Overview.

- Nine list routes off the tab strip (`""` index, `creator-reviews`,
  `campaign-reviews`, `brand-reviews`, `queue`, `creators`, `campaigns`,
  `brands`, `audit`) and four detail routes: `/admin/campaigns/:id`,
  `/creators/:id`, `/brands/:id`, `/collaborations/:id`. `ADMIN_TABS` in
  `AdminConsole.jsx` is both the strip and the route table.
- `/admin/login` is declared **outside** the layout — it is the one `/admin`
  path that must not require an admin.
- Filters that are worth sharing live in the query string, not in state:
  `/admin/campaigns?brand=<id>` is what the Brands list links to.
- `useAdminConsole()` is how a screen reads `reloadCounts` and `feePercent` off
  the outlet context; it throws rather than destructuring undefined.
- `components/admin/routes.jsx` holds thin adapters between the router and the
  section components. Nothing there holds state — if a wrapper wants some, it
  belongs in the section or in the URL.
- `components/admin/DetailPage.jsx` is the shared scaffold: `DetailShell`
  (back link, title, loading/error/404), `Section`, `Field`, `Stat`, `Panel`
  and `AuditTrail`. Four pages solving loading and failure four ways is how a
  console starts feeling like four consoles.
- Rows **link**. A creator tile used to open a drawer, so a creator had no
  address at all; the drawer is gone. Campaign rows keep the chevron as a
  peek-inline affordance, with the title as the link — two affordances, kept
  separate.

Backed by three detail endpoints — `GET /admin/campaigns/{id}`,
`/admin/brands/{user_id}`, `/admin/collaborations/{id}` — each **declared after
its fixed-path siblings**, or `pending` gets read as an id and the fixed route
never matches again. A unit test checks this structurally for every prefix.
Applicants, notes and the audit trail stay on their own endpoints so one action
doesn't refetch the page.

The collaboration timeline is read out of the audit log rather than kept as a
`state_history` on the record: the log is already written on every transition and
is append-only, so a timeline built from it cannot disagree with the record.

`POST /admin/creators/{id}/suspend` and `/reinstate` are separate from
verification and must stay that way — a unit test fails either if it touches
`verification_status`. Rejecting a verified creator to remove them would erase
the record that they were ever approved.

**Cmd+K** (`components/admin/CommandPalette.jsx`) is mounted in the shell, so it
works on every screen under `/admin`. It calls `GET /admin/search`, which spans
creators, brands, campaigns **and phone numbers** — a number arrives as a
WhatsApp message, so `_phone_tail` matches on the last ten digits and a number
typed with or without `+91` finds the same person. Results are grouped, walked
with the arrows and opened with Enter.

Every entity name in the console is a link, through `components/admin/links.jsx`
(`CreatorLink`, `BrandLink`, `CampaignLink`, `CollaborationLink`). They render
plain text when the id is missing rather than a link to nowhere. Detail pages
carry `crumbs` into `DetailShell`, which draws breadcrumbs above the back link —
the crumbs say what you are inside, the back link is the one-tap way out.

## View-as (impersonation)

An admin sees the app exactly as one creator, brand manager or campaign manager
sees it, so "I can't see the button" is answered by looking. `POST
/admin/impersonate/{user_id}` starts it, `POST /auth/impersonate/stop` ends it.

**It is read-only, and `_reject_impersonated_writes` is what makes that true.**
The banner and the hidden buttons are a courtesy. The middleware refuses every
method outside `SAFE_METHODS` while an impersonation cookie is present, before
routing — so a route added tomorrow is covered by having been written at all.
It keys on the *method*, never on a list of endpoints: an allow-list would have
to be maintained, and the endpoint added after it is forgotten is unprotected.
`tests/unit/test_impersonation.py` holds this line over real HTTP, including
against paths that do not exist; 38 of its 62 tests fail if the middleware is
disabled.

- A **third cookie**, never a swap of the admin's own. Stopping is deleting one
  cookie, the admin's real session is never destroyed, and an impersonated
  request cannot be confused for a real one. `IMPERSONATION_MIN` is 30 — it
  expires on its own, and an expired token reads as "not impersonating" so the
  admin is simply themselves again.
- One exemption from the middleware, and it must stay one: the stop route,
  which clears a cookie and writes an audit line and touches no business data.
  It deliberately has **no role guard** — the caller *is* the impersonated
  creator to every guard, so `require_roles("admin")` would lock the admin
  inside the session it exists to leave.
- **Admins are not impersonatable** (`IMPERSONATABLE_ROLES`). An admin already
  sees what an admin sees; the only thing admin→admin would add is acting as a
  named colleague.
- Both ends audit with the target's name and role. The start audits **before**
  the cookie is set, or a failed write would leave a live session with no
  record. The stop recovers the admin from the token's `act` claim, so the line
  is not credited to the creator.
- A session that simply expires writes no closing line — there is no request to
  write it on. The start line carries `expires_in_minutes`, so the window is
  reconstructible.
- `/auth/me` reports the session; the banner is drawn from that rather than
  from anything stored at start, so a second tab and an expired session both
  show the truth. The banner is mounted **above the router** in `App.js`, so no
  route can fail to render it.

Admins get **admin navigation only**. `linksFor()` in `Navbar.jsx` returns from
one branch per role; admin used to share the creator branch, which put the
creator brief feed in staff navigation. The marketing strip renders only when
nobody is signed in.

## Design system

`design_guidelines.json` is the brief: burnt orange `#F05D14` as `ember-500`,
tinted near-black (never pure `#000`), max `rounded-lg`, generous padding, targeted
transitions (never `transition-all`), left-aligned dense content.

Typography is **Fraunces** (`font-serif`, headings) and **Inter Tight** (body),
defined in `tailwind.config.js` and `src/index.css`. `design_guidelines.json` now
matches; if the two ever disagree again, the code wins. Exactly one font
stylesheet loads — the `@import` at the top of `src/index.css`. Don't add a
second one to `public/index.html`.

In practice: uppercase `tracking-[0.2em]` eyebrows, `font-serif` headings,
`border-white/10` on `bg-card` surfaces, ember for CTAs and accents only.

### The four foundations

All four live in `src/index.css` and `tailwind.config.js` rather than at call
sites, so a new component gets them by using the ordinary classes.

- **Grain.** One texture, `--grain-texture`, applied three ways: `.grain-page`
  (the ground, `background-attachment: fixed`, so it reads as paper rather than
  a pattern scrolling behind the text), `.grain-surface` (an extra background
  layer on the element, inheriting its radius) and `.media-frame`. All blend
  `overlay`, measured: the page ground lifts sRGB 11 → 12.8, a card 17 → 18.7.
  `soft-light` was tried and took the ground to 15.6, which reads as a different
  colour rather than a texture.
  - **Never on a gradient** — both set `background-image` and one silently wins.
  - **Never on a translucent surface** (`bg-card/40`). The blend runs against
    the element's own colour before it composites over the page, so at 40% alpha
    there is nothing to attenuate the noise against and the panel lifts to
    nearly 40. Those panels sit on a grained ground already.
- **Fluid type.** Eight `text-fluid-*` steps, each a `clamp()` whose minimum and
  maximum are the two Tailwind sizes the responsive pair it replaced used, so
  nothing is bigger or smaller at either end — it just stops jumping. The
  preferred term interpolates over 375px→1280px, so the whole phone range is
  fluid rather than pinned at the minimum. **No heading uses a flat `text-*`
  size.** An explicit `leading-*` still wins over the step's own line-height
  (Tailwind emits lineHeight after fontSize), so a converted heading keeps its
  leading.
- **Media frames.** `.media-frame` reserves the box and tints it, so an empty
  frame reads as a surface that has not filled rather than a hole. Every `<img>`
  in the app is inside one, out of flow, or carries an aspect ratio.
  - When checking this, do **not** ask whether `getComputedStyle(img).height` is
    non-zero. Computed style resolves `height: auto` to the used pixel value
    once layout has run, so that test passes for a completely unreserved image
    and the whole check silently becomes vacuous. Ask for an aspect ratio, out-
    of-flow positioning, `width`+`height` attributes, or a framed ancestor.
- **Elevation.** Hairline border plus surface tint on anything that sits in the
  page; `box-shadow` only on things that genuinely float — dialogs, dropdowns,
  popovers, toasts. Zero shadows outside `components/ui/`, checked by walking
  every element on a rendered page rather than by grepping for `shadow-`.

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

## Dense views

The admin console, the campaigns lists, the creator directory, the applicant
board and the audit log share `frontend/src/components/data/DenseView.jsx`.
Anything new that lists data uses it rather than solving these again:

- `STICKY` is the only place the sticky offsets and z-indexes live. The navbar
  is `sticky top-0 z-40 h-16`, so everything under it clears 4rem and stays
  below z-40. A bar whose controls stack on a phone takes
  `level="headerFromMd"` — a 400px column of filters pinned under the navbar
  leaves a third of an 844px screen for the list it exists to help you read.
- `FilterChips` + `ResultCount` on every filtered list: one chip per active
  filter, each removable on its own. Sort gets no chip — it changes the order,
  not the set.
- `ListEmptyState` draws the distinction that matters: "nothing here yet"
  (say what would appear) versus "nothing matches your filters" (offer the
  clear). Never a bare blank area.
- Loading is a skeleton shaped like the content, never a spinner, and sized so
  the swap costs nothing — measured at 0.0000 CLS on both widths.
- `ScrollTable` for tables: header sticky to the container, first column
  pinned. `overflow-x: auto` computes `overflow-y` to `auto` too, so the
  container is the scroller and has to own a max-height; a sticky header with
  nothing to stick against does nothing at all.

### Page skeletons

`components/data/PageSkeleton.jsx` is the same idea one level up, for detail and
form *pages* rather than lists: `DetailPageSkeleton`, `FormPageSkeleton`,
`PageHeaderSkeleton`, `FieldSkeleton`, `LoadingAnnouncement`. Separate from
DenseView because the problem is different — a list skeleton stands in for rows
whose count is unknown and whose height is uniform, so sketching them is free,
while a page skeleton stands in for one arrangement that will land in a known
place and has to be measured against it.

- **The skeleton renders inside the real page's chrome** — same `Navbar`, same
  `<main>`, same `max-w-*`. The centred spinners these replaced sat in their own
  full-viewport box, so the page did not arrive so much as replace a different
  one.
- Heights are **measured against a rendered element, not derived from the type
  scale** — line-height is what occupies space, and `text-fluid-*` is a clamp, so
  a headline is a different height at 375 and 1280. Where content decides the
  height, reserve both.
- The footer action bar is part of the shape. It is the tallest single element on
  a phone (`flex-col-reverse` stacks full-width buttons), so leaving it out is
  what makes a skeleton shift by 100px on mobile and 0 on a laptop.
- Skeletons are `aria-hidden`; `LoadingAnnouncement` is the `role="status"` that
  is not, so a screen reader hears "loading" rather than silence.
- Verified by measurement, not by eye: CLS is **0.0000** on CampaignDetail,
  PostCampaign (new and edit) and BrandOnboarding at 375 and 1280, and 0.0048 on
  Landing's below-fold brief grid. When checking this, confirm the skeleton
  actually rendered — a page that redirects to `/login` also scores zero.

## The campaign manager, and the venue

A manager reads `ManagerHome` either the night before a shoot or standing in the
venue on the day, and those two moments want opposite things. So the day's work
is a section of its own, at full size, with a direct route into day-of mode
(`/manager/campaigns/:id?mode=day-of`); everything else is smaller below it and
anything already finished is folded shut but kept, because performance still
gets recorded days later.

- `isToday` compares at **local midnight**, not on the ISO string — a 19:00
  event reads as tomorrow in UTC for everybody using this. It answers for both
  shapes: an event's single date, and a personal table's window that *contains*
  today.
- `attentionFor` only speaks about today and the next two days. Every signal it
  raises is otherwise silent — no notification, no queue — and each is a thing
  the manager finds out about from a phone call: no slots, unbooked places,
  fewer creators than the brief asked for, no venue address on the day. It stays
  short deliberately; a list of eleven warnings is a list nobody reads standing
  up.

### Check-ins survive the venue's wifi

`lib/offlineQueue.js`. A manager checking twenty people into a basement is the
worst network in the product and the least forgiving moment to be in it: there
is a person in front of them, and a check-in that silently failed surfaces days
later as an attendance record that disagrees with the room.

- **A network failure queues rather than rolls back.** The row stays checked in
  and gets a "waiting" marker; the request goes to `localStorage` and replays
  itself. The old behaviour — revert and raise a Retry toast — asks somebody
  mid-queue to notice a toast and tap it, which is asking them to do the
  network's job.
- **A 4xx drops the item; only no-response, 408, 429 and 5xx retry.** The
  check-in route answers **409 "They're already checked in"**, so on a replay a
  409 means the work landed. Treating it as retryable would loop forever on
  something that already succeeded — a unit of this is pinned by a test that
  queues a check-in for an already-attended collaboration.
- **Backoff is for timers, not for people.** `flush({ force: true })` ignores
  both the backoff and `navigator.onLine`, and is what "Try now", the `online`
  event and returning to the tab all use. Honouring a two-minute wait after an
  explicit tap makes the button look broken — and `onLine` is a hint that lies
  on captive portals.
- `enqueue` keys on the action (`check-in:<id>`), so a second tap replaces
  rather than stacks.
- `QueueBanner` shows nothing when online and empty. A permanent "connected"
  badge trains the manager to stop looking at the corner of the screen that will
  one day say four check-ins have not gone through.

Verified against a stub that fails check-ins on demand: the queue survives a
full page reload, drains when the server recovers, and both check-ins reach the
server. Breaking either rule — persistence, or 409-as-retryable — fails the
suite.

## Local test accounts

`backend/seed_personas.py` seeds one signed-in-able account per persona —
verified creator, half-finished creator, creator awaiting review, verified
brand manager, unverified brand manager, campaign manager — plus a campaign for
the manager to manage. Idempotent, keyed on phone. See `PREVIEW.md` for the
numbers.

**A script, not an endpoint.** A route that mints pre-verified accounts with
known phone numbers is a backdoor whether or not it is guarded, and it would sit
in the route table in production one misconfiguration from reachable. A script
cannot be called over the network.

It refuses to run unless `_simulation_allowed()` — the same gate the OTP log
uses. That is not an extra precaution but the honest condition: without
simulation you cannot read the login code, so the accounts would be unusable
anyway. Numbers are `+9199000000NN`, patterned so one in a production database
is a self-announcing bug.

## When something breaks

Three layers, in `components/ErrorBoundary.jsx`, `lib/errorLog.js` and
`lib/globalErrors.js`. Before them a render error anywhere unmounted the whole
tree, and the user's evidence was a white page — indistinguishable from a
network failure, a bad deploy, or the app not existing.

- **Root boundary**, mounted in `App.js` *outside* `AuthProvider` and
  `BrowserRouter`. Those can throw too, so a boundary inside them goes down with
  them. Its fallback therefore uses a plain `<a href="/">` and
  `location.reload()` and touches no router — a `<Link>` in a fallback that may
  be standing in for a broken router is a fallback that breaks.
- **Route boundary** (`RouteBoundary`) inside the router, `resetOn={pathname}`.
  The root one would also catch a page crash but could never un-catch it: the
  fallback would survive navigating somewhere that works. It also sits *below*
  `ImpersonationBanner`, so a page crash never leaves an admin acting as
  somebody else with nothing on screen saying so.
- **Section boundaries** (`SafeSection`) around independent panels: the four
  admin overview panels, the `<Outlet>` and the ⌘K palette in the console shell,
  the creator dashboard's six sections, the applicant board and the suggestions
  panel. Named `SafeSection` because `admin/DetailPage.jsx` already exports a
  `Section` that means a titled block.
  - Every panel on every admin **detail** page is covered by one change:
    `DetailPage`'s `Section` wraps its own children. Doing it in the shared
    primitive rather than at twenty call sites is the only version that stays
    true — a panel added next month is covered by using `Section` at all. The
    heading stays outside the boundary, so a broken panel still says which one.
  - `Try again` bumps a key and remounts, so a component that threw on bad state
    gets a fresh one rather than the state that broke it.

### What a crash report may contain

`logError` records the component, the route, the **role**, the error and the
component stack. It must never record a name, phone number, email, address, UPI
id or PAN — this product handles all of them, and a log line is a data store
nobody audits because logs feel like plumbing.

- `redact()` scrubs message, stack and component stack. The patterns are blunt
  on purpose: personal data reaches a log by somebody interpolating a record
  into an error, and that can be any shape.
- **The query string is dropped whole, not filtered.** ⌘K searches on phone
  numbers, so `?q=%2B919876543210` is a URL this app really produces. Path
  segments stay — an ObjectId is opaque and "which creator's page crashed" is
  most of the debugging value.
- The role is published to a module by `AuthContext`, **inside `fetchMe` before
  `setUser`**, not only in an effect. React runs effects after a commit, and a
  child that throws during the render a state change causes never reaches one —
  so an effect-only version filed every first-render crash against `anonymous`,
  which is exactly the crash you most want the role for.
- The sink is the console plus a bounded ring at `window.__weareErrors()`.
  Everything in the ring went through `redact` on the way in, so pointing it at
  a real collector cannot become a privacy change by accident.

### Failures nobody was listening for

`installGlobalErrorHandlers()` in `App.js` at module load. `unhandledrejection`
covers a request whose `.then()` chain had no `.catch()` — the spinner that
spins forever; `error` covers a throw in a callback or timer, which no boundary
can see.

**Deliberately not an axios interceptor.** Around sixty call sites already catch
their own failures and say something better than a generic message ("Accept the
creator first"). An interceptor cannot know whether a caller is about to handle
the rejection, so it would double-toast every one of them. The browser knows
exactly that, and only fires `unhandledrejection` when nothing handled it — so
the deliberate `.catch(() => {})` sites stay correctly quiet.

Toasts carry a stable id derived from the message, so a session expiring
mid-screen produces one toast rather than six. A non-request crash gets
"Something went wrong" and never a type name or a stack — the person reading it
cannot act on either.

## Configuration, and refusing to start

Three variables have no default and nothing sensible to fall back to:
`MONGO_URL`, `DB_NAME`, `JWT_SECRET`. `validate_environment()` checks all three
at import, **before** the `os.environ["MONGO_URL"]` a few lines below it, and
exits 1 with every missing one named at once. The order matters — the other way
round, a raw `KeyError` wins the race and the useful message is never printed;
a unit test pins it structurally.

- The list is one boot, not one variable per restart. Reporting only the first
  costs three deploys to fix three blanks.
- `JWT_SECRET` is why this exists at all. The other two were already read at
  import so a missing one crashed the boot, loudly if unhelpfully. `_jwt_secret()`
  read its own per call, so a deploy without it **started cleanly**, served the
  marketing page, and 500'd the first person who tried to sign in. It is still
  a lookup rather than a frozen constant — a test can set it — but a blank now
  raises a `RuntimeError` naming the variable.
- A blank string counts as missing. `JWT_SECRET=` in a `.env` file is an empty
  value, not an absent key, and it is the shape a half-filled `.env.example`
  copy actually takes.
- `_ENV_PRODUCTION` (`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS`) **warns
  rather than exits**: each has a default that lets the process run, and a
  laptop and the unit suite legitimately have no admin account. Refusing to boot
  over CORS would be worse than saying so loudly, since a proxy may be setting
  the header instead.
- **Unset reads as production.** `_is_production()` treats only
  `dev|development|local|test` as not — the same signal `_simulation_allowed()`
  uses, read the same way. Guessing the other way would silently permit OTP
  simulation on a real deployment. `ENV` is a fallback for hosts that set that
  name; `APP_ENV` wins where both are present.

`backend/.env.example` documents **every** variable the app reads, defaults
included, and `tests/unit/test_environment.py` holds it to that by AST-walking
the backend for `os.environ` reads and diffing against the file. The
notification templates are the half that drifts: they are resolved dynamically
as `AISENSY_TEMPLATE_{event.upper()}`, so no static analysis of the source can
find them and nothing but that test notices when a new `NOTIFY_EVENTS` entry
ships with no line documenting its template. It checks both directions — an
undocumented event, and a documented template for an event that no longer
exists.

## Tests

Dependencies are split in two. `requirements.txt` is the **runtime** set —
what a production build installs and nothing else — and `requirements-dev.txt`
pulls it in and adds pytest, xdist, `requests` (the integration suite drives
the API over real HTTP) and the linters. Install the second one on any machine
you develop or run tests on; CI and `docker compose` both use it, and the
container the app runs in does not.

Three runtime entries are never imported and must not be dropped for looking
unused: `uvicorn` runs the process, `email-validator` is what lets pydantic
build an `EmailStr`, and `python-multipart` is what lets FastAPI parse
`Form()`/`UploadFile` — the brand documents and the profile image. `runtime.txt`
pins **python-3.11**, matching `python:3.11-slim` in `docker-compose.yml`;
without it a host picks its own default and 3.13 makes `pymongo==4.6.3` compile
from source.

```bash
cd backend
pip install -r requirements-dev.txt
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
