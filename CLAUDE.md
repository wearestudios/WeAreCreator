# WeAre Creators

Two-sided marketplace connecting verified creators with brands running paid
campaigns in Bengaluru. The product is Bengaluru-first — user-facing copy says
Bengaluru, not "every city in India". The city field and the category list are
deliberately open for later expansion, but don't write claims the operation
can't back. Roles: `creator`, `brand_manager`, `admin`, `weare_team` (staff,
the admin console scoped to assigned brands), `campaign_manager` (staff,
assigned per campaign — sees only what they're assigned to). `brand` is the old
name for `brand_manager` and both are still accepted — see below.

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
user document with `password_hash` stripped. **Staff sign in with email +
password** — admin, `campaign_manager` and `weare_team`, which `/auth/login`
holds as an allow-list; creators and brands use WhatsApp OTP only.

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

## Being asked

An invitation used to exist only as a WhatsApp message and a row in
`campaign_invitations`. **Every "who is on this campaign" view read
`collaborations`**, and an invitation is not one until the creator pitches — so
somebody who missed the message had no way to find out they had been asked, and
a campaign we had invited six people to looked empty on both applicant boards.

- `INVITATION_OPEN_STATES = ("sent", "send_failed")`; `_invitation_state` and
  `_serialize_invitation` are the readers. **`open` is decided server-side** —
  open state *and* a live campaign — so an invitation to a brief that has since
  closed reads as history rather than offering an Accept that would 404.
- `GET /creator/invitations` and the dashboard both call `_creator_invitations`;
  the dashboard's `totals.invitations` counts only the open ones.
- **Accepting goes through `apply_to_campaign`** — same verification gate, same
  re-check gate, same capacity check, same duplicate refusal, same routing of
  the notification. A second implementation would be a second definition of
  what an application is. Declining writes no collaboration and is **not** a bar
  on applying later. Either way it can only be answered once (409), and
  somebody else's invitation is a 404, never a 403.
- `_pending_invitations_for(campaign_oid, applied_creator_ids)` feeds both
  boards — `groups["invited"]` on the admin's, `invited` + `totals.invited` on
  the brand's — and excludes anyone who has since applied, who is on the board
  under their own application. One of those boards is brand-facing, so the
  creator half comes through `_brand_visible_creator` like every other brand
  surface and the flat keys are read back off it.
- The rows are **not applicants and are not counted as such**: `invited` is not
  a collaboration state, is in no `_APPLICANT_BUCKETS` entry, and the admin
  page's "Applicants" count skips it. `collaboration_id` is `None` — a made-up
  id is an id somebody tries to act on.
- Surfaces: `components/creator/Invitations.jsx` (above the pitches in the
  applications view, carrying both answers on the row — Accept opens the same
  short rate-and-pitch form the campaign page does, because an application with
  no rate is one the brand cannot act on), the admin campaign page's "Invited,
  not answered" group, and `InvitedStrip` on the brand's applicant board. Open
  invitations count toward the dashboard's Applications tab badge.

## Suggesting creators

`GET /brand/campaigns/{id}/suggested-creators` ranks verified creators against a
brief. The whole score is `score_creator_for_campaign` — one pure function, no
database, no hidden term; `CREATOR_MATCH_WEIGHTS` sums to 100 and is the only
tuning knob. The components ship with every result, so a brand can see why
somebody was suggested.

- Signals: niche and genre overlap with the brief, whether the creator can post
  the formats the brand asked for, city match, follower count against the wanted
  tier, engagement rate, past on-time delivery here. `CAMPAIGN_CATEGORY_SYNONYMS`
  bridges the category enum to the words creators actually use — nobody writes
  "fnb" about themselves.
- **An unmeasured signal scores at the midpoint, never zero.** A creator with no
  connected Instagram has an unknown engagement rate, not a bad one, and scoring
  unknowns at zero would bury everyone who has never worked here — which is
  everyone, at the start. `unknown_signals` names them so the UI can say so. The
  same applies to a *brand* that skipped a question: an unstated content
  preference is an unknown, not a zero for everybody.
- Anyone who already applied or was invited is excluded. Filters for niche, city
  and follower range; paginated. Admins can call it on any campaign.

### Audience size, in one vocabulary

There used to be two. The scorer had four bands named nano / micro / mid /
macro with its own boundaries, while every screen a person reads described
followers in raw numbers and the directory filter offered "10k+ / 50k+ / 100k+
/ 500k+". A brand seeing "micro" in one place and picking "10k+" in another
were talking about different people.

**`FOLLOWER_TIERS` is the only vocabulary** — micro 1K–10K, mid 10K–100K, macro
100K+ — and `CREATOR_REACH_TIERS` (budget → expected audience) returns one of
its keys rather than a fourth name. `lib/followerTiers.js` mirrors it and a
test fails if they drift. **The budget boundaries moved when the vocabulary
did**, picked so the same fee buys roughly the same audience it did before:
keeping the old numbers against the new bands would have made ₹8,000 buy a
1k–10k creator where it used to buy 10k–50k, which is a re-tuning smuggled in
under a renaming.

### What a brand is looking for

`content_types`, `preferred_follower_tier` and `typical_budget_band` on the
brand profile, captured in onboarding and editable after. Standing preferences,
not lines on one brief: a café that works with micro food creators wants that
on every campaign it posts, and re-deriving it from each fee was a guess where
an answer was available. None of them are in `_BRAND_REQUIRED_FIELDS` — this is
what we rank on, not evidence of anything.

- **A stated preference beats an inferred one.** `_wanted_reach_tier` takes the
  brand's tier when it set one and falls back to the budget map otherwise; the
  typical band stands in when a brief has no fee of its own (barter, or a
  draft). `budget_tier.stated` travels with the response so the panel can say
  "you're looking for" rather than "this budget suits" — one of those is worth
  arguing with and the other is worth correcting on the profile.
- `"any"` is a real answer, stored as one, and does **not** steer the ranking.
  It means "we don't mind", which is different from never reaching the question.
- `content_fit` is a new weight worth 10, and it came out of `niche` (30→25) and
  `genre` (15→10) rather than out of city or reliability: it measures the same
  thing they do at a finer, factual grain — which formats somebody actually
  posts is a fact, a niche is a description. Read off `platforms`, so an empty
  profile is an unknown rather than a zero. The reason line names **only the
  gap** ("no YouTube"), because a match is not something to act on.
- The brand's own half of its identity: a `tagline` (90 characters, on every
  campaign card it posts and first in the share preview — it was written to be
  one line) beside `about` (a paragraph, on the public page). And
  `CONTACT_ROLE_SUGGESTIONS` at signup, which is **a suggestion list, not an
  enum** — the designation stays free text so every value typed before it still
  reads as a sentence, and "Other" opens a box rather than storing the word.

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
- **The counter says "1 document uploaded", not "1 of 12".** `max_documents` is
  a ceiling, not a target, and the copy two lines above says any one of the four
  kinds is enough — so a fraction reads as eleven more to find. The limit
  appears only on the last couple of slots, which is when it is a fact somebody
  needs.
- **The "still needed" checklist filters the server's list by what is on
  screen.** It used to be pure server state: it named what the *stored* profile
  was missing and never looked at the form under it, so a brand filled every
  box — Category included, two sections up the same page — and was told the
  boxes were empty, with `Send for verification` greyed out and the Save button
  that would have made the list agree 200px away in a different section. The
  labels stay the server's, so there is still one vocabulary. And **`Send for
  verification` saves first**, because the route judges the stored profile and
  noticing a distant Save button is not the price of submitting.
  `test_brand_checklist.py` drives the real `PUT` handler with the body the real
  form sends, so a field renamed on one side and not the other fails there
  rather than in somebody's onboarding.

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

### When a shoot may happen

A venue's Monday is not its Saturday and its 11am is not its 8pm. Two fields on
a campaign say so: `restricted_days` (weekday indexes the venue is out) and
`shoot_windows` (the hours that work). Before them the only place a brand could
say "not during service" was the brief, which nothing reads.

- **Every weekday and hour comparison happens in IST** (`SHOOT_TZ`). Slots are
  stored in UTC and a 19:00 Bengaluru sitting is the *next day* in UTC, so
  reading `.weekday()` off the stored value puts a Friday evening on Saturday
  for everybody. Same trap as `isToday` on the manager's screen, same fix.
  Fixed rather than per-campaign because the operation is Bengaluru-first.
- **`_shoot_time_refusal(campaign, starts, ends)` is the only decider** —
  slot creation and editing (both through `_validate_slot_times`), and every
  booking (through `_claim_slot`, the single function behind both booking
  routes), so they cannot disagree about what the brand asked for. It
  **returns the sentence rather than raising**, because one caller labels
  instead of refusing.
- **Creating and booking are separate checks.** A slot can predate a
  restriction, or an admin can have written one past it on purpose, so the
  booking is checked again — before the seat is incremented, or a refusal
  quietly shrinks the slot. On a fixed slot the refusal points at the manager,
  because the creator only chose which of the manager's slots to take; on a
  personal table they named the time, so they get the plain sentence.
- **A preset's times come from `SHOOT_WINDOW_PRESETS` at write time**, never
  from the client: a "lunch" window running 2am–4am is a window whose label
  lies, and resolving at write time means retuning a preset later cannot move
  a brief somebody already agreed to. Only `custom` carries times.
- A slot must sit **inside one window**, not straddle two — a sitting running
  from lunch into the afternoon is one the venue never agreed to, however each
  half looks alone. Absent reads as unrestricted, the usual pre-migration rule.
- `_clean_restricted_days` **refuses all seven**: that is not a restriction,
  it is a campaign nobody can ever book, discovered by a creator with a dead
  picker. The frontend control holds the same line at six.
- **Nobody who already holds a seat loses it.** The check is on the act of
  booking, never on an existing collaboration — a brand restricting Mondays
  does not evict the creator already booked on one, the same shape as a brief
  going private. `outside_preferences` on the manager's slot rows flags such a
  slot so they can ring the venue rather than finding out through a creator's
  failed booking. The admin `advance` path writes `scheduled_at` directly and
  is deliberately not checked: it is the escape hatch for when the rule is
  wrong.
- `lib/shootWindows.js` mirrors the presets, the weekday names and the offset;
  a unit test fails if they drift. **Weekday indexes follow Python's
  `datetime.weekday()` (Monday 0), not JavaScript's `getDay()` (Sunday 0)** —
  `dayIndex` is the only place that conversion happens. `SlotPicker` cuts the
  disallowed days and times out rather than offering and then refusing them,
  and `ShootWindowNote` renders the same rule on the campaign page, in the
  picker and above the manager's slot list — it renders nothing when nothing
  was set, because an empty box headed "When it shoots" reads as a fact about
  the venue rather than a question nobody answered.

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

## The marketing site

Five pages and a designed 404, **all React routes**. `/` routes, `/for-brands`
and `/for-creators` sell to one reader each, `/how-it-works` is the journey
from both sides, `/why-weare` is the standalone case. Registered in `App.js`
and linked with `<Link>` — see "Why they are not server-rendered" below, which
is a reversal worth reading before reinstating anything.

**The positioning governs every word, and it is not "against agencies".** WeAre
Studios is one, and the managed service is a real offering somebody chooses —
"without an agency" or "cut out the middleman" would be a page arguing against
our own product. **The enemy named is disorganisation**: campaigns run over DMs
and spreadsheets, nobody checked, no rate in writing, no proof of what it
achieved. `_FORBIDDEN_MARKETING_PHRASES` in `server.py` holds the line and
`test_marketing_pages.py` fails any page for any of them.

**Bengaluru is evidence of network depth, never identity.** "The network runs
deepest in Bengaluru, and creators sign up from anywhere in India" is the
sentence; "every city", "pan-India" and "nationwide" are banned on every page,
including the login and signup screens, which sat outside these tests long
enough to keep "Every city that matters" months after it was removed elsewhere.

What each audience must come away knowing is pinned there too — for creators,
that briefs are real and paid, the rate is agreed in writing before they shoot,
they keep 100% of it because the fee sits on the brand, payment follows
approved delivery, brands are checked, and joining is free; for brands, real
audience stats, every creator and every rate visible, no retainer and no markup
on creator fees, approval before publication, a report at the end, and the
self-serve/managed choice **as an option, never as a fee they are locked into**.

- **An audience page asks once, in the same words, twice.** Hero and close, both
  spread from one `ASK` constant so "the same words" is structural. Two
  differently-worded CTAs is a choice of doors.
- **A both-sides page routes instead of asking.** Home and `/how-it-works` are
  read by both, so they end with `TwoPaths` — the one place competing buttons
  are right, because picking for the visitor is the mistake. `TwoPaths` must
  not appear on an audience page; a test enforces both halves.
- **Home was at most two screens, and the film is the deliberate exception.**
  Hero, the counted proof strip, the scroll film, one problem-and-promise
  section, the close. Everything except the film still answers the old rule —
  it was 1,780px of content before the film was added — and the film's own
  length is scroll it spends telling the story rather than page a reader has to
  get past. Everything else that used to be below home has its own page, and
  the live brief feed went to `/campaigns`, which is a better version of it.
- **Every proof figure is counted, never written down.** `_platform_proof`
  queries verified creators, campaigns that reached `in_progress` or beyond,
  verified brands and distinct cities; `GET /public/proof` serves them and
  `ProofStrip` draws them. Each appears only above a floor — 10, 5, 5 and 3 —
  and the strip renders nothing when there is nothing worth saying, because "3
  creators" is not proof, it is a reason to close the tab. Home carried a
  hardcoded "500+" until this replaced it.

### Why they are not server-rendered

`/for-brands` and `/for-creators` **were** FastAPI handlers rendering
hand-written HTML, for the same reason `/c/{id}` and `/brands/{id}` still are:
a WhatsApp crawler does not run JavaScript, so Open Graph tags React injects
are tags nobody sees. Three things made that the wrong trade here:

- a page the backend renders cannot be reached with a `<Link>`, so
  `/how-it-works` and `/why-weare` could not exist beside them at all;
- the Vercel rewrites that would have pointed at them were never repointed, so
  in production both answered with the SPA's catch-all — every nav and footer
  link to them went nowhere;
- the copy lived only there, so no page in the app could reuse a word of it.

**What it cost:** non-JS crawlers read `public/index.html`'s static tags, so a
marketing link pasted into a chat previews with the site-wide card.
`components/marketing/PageMeta.jsx` states that at the top of the file and says
how to buy it back — point the rewrites at a prerender service, or add a Vercel
`has` condition on crawler user-agents. A test keeps that note present.
**`/c/{id}` and `/brands/{id}` stay server-rendered**: there the shared link
*is* the preview, and the trade would not be worth making.

`PageMeta` writes title, description, canonical and the OG/Twitter tags per
page. No two pages share a title — one title for two pages makes two links
preview identically, which is the whole reason for separate pages.

### The copy budget

**One idea per screen-height, and a word count per page**: home under 120,
`/for-brands` and `/for-creators` under 250 each, `/how-it-works` and
`/why-weare` under 300. Headlines to eight words, supporting lines to twenty.
`test_marketing_pages.py` enforces all of it.

Every page keeps its words in one `COPY` object so the budget can be read
rather than reconstructed by walking JSX — and so a section that wants to say
more has to argue with a number.

**The shape is what holds the rule.** No primitive in `Sections.jsx` takes a
`body`; they take a label and one `line`. A four-word label plus a sentence
carries the same point as the fifty-word paragraph it replaced and is read
rather than skipped, and a section that wants to make two points has to become
two sections. The detail that came out lives in onboarding and in the product,
which is where somebody who has clicked actually needs it.

This was a compression, not a repositioning: every claim survived, and the
tests that pin what each audience must come away knowing were rewritten to
look for the idea rather than the sentence it used to sit in.

### The motion layer

`components/marketing/motion.js` — one easing curve (`EASE`), durations
between 200 and 400ms, transforms and opacity only. Entrances are `Reveal`
(rise and fade, staggered by index); the proof figures use `CountUp`; cards
lift 2px and warm their border toward ember on hover; images ease to 1.02x
inside frames that clip.

- **`prefers-reduced-motion` is handled in `Reveal` and `CountUp`, once.**
  Under `reduce` the element renders at its final state and the number's first
  paint is its final value — not a shorter animation. Verified by emulation:
  at 50ms the hero heading is opacity 0 / y+14 normally, and opacity 1 /
  `transform: none` under `reduce`.
- **A hover transform must not sit on the element Framer animates.** Framer
  writes `transform` as an inline style, so `hover:-translate-y-*` on the same
  node is dead once the entrance settles at `transform: none`. Measured: the
  border warmed and the card did not move. `Point` puts the hover on a child,
  and a test pins it.
- The image zoom scales a layer inside the frame, never the frame — scaling
  the container would grow the hole it reserves.
- `duration-[400ms]` is written `[transition-duration:400ms]`: the arbitrary
  `duration-*` form matches both transition- and animation-duration, and
  Tailwind warns on every build. It warns for the string anywhere, including
  inside a comment.

### The kinetic hero, and the imagery

**The signature is the headline.** `KineticHeadline` morphs at letterform
level between four kinds of campaign — launch night, fashion drop, travel
stay, menu tasting — each resolving against a line that never moves. The
motion *is* the message: what changes is the kind of work, what does not is
how it is run.

- **"Your" and "handled properly." are outside the morph.** Animating the
  whole line would say four unrelated headlines are cycling rather than one
  sentence being re-pointed.
- **Per letter, on a stagger, moving as well as fading.** A single opacity
  tween on the phrase is the thing this is specified not to be. ~4s a phrase;
  the swap itself is under a second, so the phrase is still for most of its
  life.
- **The tallest phrase reserves the box.** A line that changes height moves
  the page every four seconds — a CLS event per cycle.
- One `aria-label` on the `h1`, with the animated spans hidden. A screen
  reader reading four letters at a time as they arrive is gibberish.
- Under `prefers-reduced-motion` the first phrase renders and no timer starts.

**`FloatingCards`** are tilted photo cards drifting on scroll, in two clusters:
four behind the hero (the four categories, said at once rather than one at a
time) and two hanging past the edges of a proof strip. Rotation is static;
the drift is `y` off the scroll position, so nothing touches layout. **Two
cards below `md`, four above** — four overlapping compositing layers on a
390px screen sit behind text nobody can read through them.

**This is the only `box-shadow` on the marketing site**, and a deliberate
exception to the elevation rule: a card drifting at a different rate from the
page behind it is the one inline element that really is floating, and without
the shadow the tilt reads as a mistake. Soft, and in black rather than the
default grey. A test fails any other marketing file that grows one.

The hero's full-bleed photo slider is gone. Its job was to say "we do all of
these", which the cards now do better — and it cost a full-viewport layer
cross-fading every seven seconds on the page most likely to be opened on
mobile data.

### The scroll film

`CampaignFilm` — the centrepiece on home. Seven beats of a campaign playing
itself out: a brief goes up, creators apply, one is accepted, they hear on
WhatsApp, a slot is booked, the draft is approved, the creator is paid. The
product demonstrating itself, which is the one thing a paragraph cannot do.

- **The pin is `position: sticky` and nothing else.** No wheel listener, no
  `scrollTo`, no `preventDefault` — the page scrolls at the rate the reader's
  finger says and they can leave at any point. A test greps for all four.
- **Every beat derives from `scrollYProgress`, never from state.** That is what
  makes it reverse: scrolling up is the same function at smaller numbers. A
  `useState` beat-tracker looks identical going down and is wrong going up, and
  nobody sees it until they scroll back. The only `useState` in the file is the
  media query.
- **The payout counts with scroll and writes `textContent` on a ref.** A
  `setState` per frame re-renders the whole stage sixty times a second to change
  four characters. Measured unwinding: ₹2,722 at 87% → ₹12,000 at 97% → ₹2,722
  back at 87%.
- Elements persist once they arrive, so the campaign accumulates rather than
  each beat replacing the last — one story instead of seven slides.

**The fallback is a first-class design, not a degraded mode.** Below `md` and
under `prefers-reduced-motion` the same seven beats render as a numbered
stepped list: every UI piece drawn, every caption present, nothing pinned and
nothing scroll-driven. `wide` starts `false`, so a phone never mounts the
pinned version even for a frame — the other way round, five screens of scroll
would appear and vanish on the device least able to afford it.

**The interfaces are drawn, never screenshotted** (`filmUI.jsx`). A screenshot
dates the moment somebody moves a button, and a real component would drag the
app's data shapes, API calls and auth context onto a page that has none of
them. They borrow the design language — `bg-card`, `grain-surface`, ember on
the one thing that matters in each — and are simplified past literal: a real
applicant row carries eight fields, this one carries three. The WhatsApp beat
names the channel and borrows none of its marks.

Measured on the mid-range Android profile: **zero long tasks over 50ms during
a full scroll through the film**, on both the pinned and stepped paths. CLS
0.0001. The four long tasks on the page are React bootstrapping, and the
control page without a film has the same four.

### The family handshake

The closing band on every marketing page: full-bleed studio coral, white
poster type, a black CTA block. **The only place the studio palette appears
on the site** — a colour used twice is a co-brand rather than an endorsement,
and Creators has its own identity to keep.

- `lib/studioPalette.js` holds it, once, and a test fails any second importer.
  **It is deliberately not a Tailwind token**: adding one would put the
  studio's colour within reach of every authenticated screen, which is exactly
  what "the only place" prevents.
- The hex is a considered stand-in and says so in the file — nothing in this
  repository carries the studio's registered brand colour, and inventing
  precision would be worse than flagging it.
- What is inherited is the confidence and the motion, never the assets: no
  studio copy, no studio photography, no studio logo treatment.
- `TwoPaths` takes a `tone`, because the dark card reads as a hole punched in
  the coral. Same two doors, same words, inverted for the field.

### Measured, not assumed

Mid-range Android profile — 4× CPU throttle, Fast-3G, 390px:

- **CLS was 0.0798 and is 0.0002.** The whole of it was the proof strip: it
  rendered nothing until the figures landed and then appeared, pushing every
  section below it down. It reserves its height now, at **both** widths — the
  figures wrap below `md`, so a single value was right on desktop and 52px
  wrong on a phone. Neither the headline nor the cards contributed anything.
- **The flourishes cost no blocking time.** Home (kinetic headline + four
  cards) blocks 969ms; `/for-brands`, which has neither, blocks 1012ms. The
  cost on both is React and the CRA bundle. FCP and LCP are within 60ms of
  each other.
- Lighthouse itself is not installed here; these are its metrics measured
  directly through the Performance Observer API, which is the same numbers by
  a different route.

### The marketing chrome

`MarketingNavbar` and `MarketingFooter` are **variants, not edits**. The shared
`Navbar` is on nineteen surfaces — every dashboard, the console, the manager
screens, onboarding — where it carries role links, the bell and the avatar
menu; the shared `Footer` stays on Legal, Campaigns and CampaignDetail. Neither
was touched.

The marketing bar takes no session: it has one audience, and a second mode is
how a variant drifts back into being the component it was created to avoid
editing. Logged out it carries the four pages, Sign in, Join, and the studio
endorsement. `lib/siteNav.js` holds `MARKETING_LINKS` and `FOOTER_COLUMNS`; the
shared navbar keeps its own copy of the four links because editing it was out
of scope, and a drift test compares the two.

### The shared furniture

`components/marketing/Sections.jsx` — `MarketingPage` (meta, navbar, footer),
`MarketingHero`, `TextImageSection`, `ValueProps`, `Steps`, `ClosingSection`,
`TwoPaths`, `Cta`, `Eyebrow`. Five bespoke pages would be five design systems
inside a fortnight, which is what the hand-written HTML was already becoming.

`TextImageSection` alternates sides on a `flip` prop rather than by hand:
doing it by hand means somebody eventually ships two in a row on the same side
and the page reads as a column with pictures next to it.

### Image slots

Every page has deliberate placements — hero, alternating text-and-image
sections, proof areas — and **nothing on the marketing site fetches a third
party**. The hero hotlinked four stock photographs and the auth screens one
each; a test now walks every source file for `images.unsplash.com`.

`components/marketing/PlaceholderImage.jsx` is the slot: a tint from the warm
palette with the site's grain over it, in a container that already occupies the
space the photograph will.

- **The ratio is on the container, never on the `<img>`** — the whole point is
  that filling the slot moves nothing. `fill` drops the ratio for a slot whose
  height something else decided, such as a section background.
- **The grain is the overlay variant, never `.grain-surface`.** This element
  sets `background-image` for the gradient and the surface variant would set it
  too; one of the two silently wins. Same rule the design foundations state.
- **Every slot carries a `note`** — a sentence somebody could hand to a
  photographer — rendered as a `PLACEHOLDER IMAGE:` comment in the source and
  as `data-placeholder` on the element. A slot nobody can brief is a slot that
  stays empty. Tests require both, and that the note is longer than a label.
- The tint's hue is derived from the note, in a 14°–40° band around ember, so
  neighbouring slots differ without any of them leaving the palette.

### The navbar, and the 404

Logged out, the bar carries the four pages — For brands, For creators, How it
works, Why WeAre — plus Log in and **Join**. It said "Sign up as a creator"
until the site started addressing two audiences by name beside it; `/signup`
carries a role picker and defaults to creator, so nobody loses a step. One
`MARKETING_LINKS` list feeds the desktop bar and the mobile sheet, because the
sheet is the only navigation below `md` and anything missing there is
unreachable on a phone. Signed-in users keep their role navigation; the
marketing strip renders only when nobody is signed in.

`pages/NotFound.jsx` replaced `<Navigate to="/" replace />`. A mistyped URL, a
link from an old post and a brief that has since closed all landed silently on
the front page, which is indistinguishable from the link having worked. It says
what happened, offers three ways on, and keeps the footer.

### The footer

There wasn't one. Every marketing page ended at its closing CTA, so the only
way to reach terms, privacy or a human was to already know the URL — and a
consent checkbox pointing at pages nothing links to is a consent record that is
hard to defend.

`components/Footer.jsx`, and **`lib/siteNav.js` is the one link list**,
mirrored by `FOOTER_COLUMNS` in `server.py` with a drift test — the same
arrangement `followerTiers.js` and `shootWindows.js` use, for the same reason:
two copies is how a footer advertises a page that moved. The backend's copy is
no longer a second renderer; it is what **builds the sitemap**, alongside
`MARKETING_PATHS`, so a page added to the site cannot quietly be left out of
either. `FooterLink` picks `<a>` over `<Link>` on `link.external`, which today
marks only the mailto — the audience pages were marked too while the backend
rendered them.

Four columns now rather than three: "Why WeAre" and "How it works" used to be
the audience pages under borrowed names, because those were the only two pages
that existed. Each is its own page, and the audience columns point at the
audience pages.

It is on **every page a signed-out person can land on** — Landing, Legal,
Campaigns, CampaignDetail, the four marketing pages and the 404. Deliberately not the admin
console, the manager screens or the dashboards: those are dense working
surfaces under a sticky header, and a marketing footer under a data table is
noise rather than navigation. The OTP screens are the other exception — one
focused task, and `Signup` already links both documents inline, at the moment
consent is actually recorded.

The copyright names **WeAre Monk**, the entity that was already in that line.
Who owns the thing is a fact, not a copy decision, so it is carried over rather
than re-branded to match the product name. The year is read at render.

### Terms and privacy

`pages/Legal.jsx`, and the rule is that they describe **what the product
actually does**, checked against the code rather than against a list somebody
typed. A privacy page that describes a data flow we removed is worse than a
placeholder, because somebody reads it and believes it — and that is not
hypothetical: this page said, months after it stopped being true, that a brand
received a creator's contact details on acceptance, which is the strongest
promise the product now makes, described backwards.

`test_legal_pages.py` walks the classes of data the product really handles and
fails if the page does not name them: the WhatsApp number, the delivery address
*and* the map pin as two different things, the business documents and what is
inside them, Instagram as official-API-and-read-only with an encrypted token,
UPI and PAN, and the records a collaboration leaves — including the draft,
which is content that is not public yet. The terms carry the draft gate, the
24-hour slot window, `execution_owner`, invite-only briefs, barter, and
re-review after a material profile edit. "Vets"/"vetted" are banned in the copy
too, not just in the code.

**What needs a lawyer is flagged, never invented.** A `NEEDS A LAWYER` block in
the file header lists the DPDP Act 2023 duties, retention periods, how long
business documents may be held after a decision, unpublished drafts, whether a
coordinate is sensitive personal data, content licensing and Meta's platform
terms. A test keeps that block present — deleting it is how "this needs review"
quietly becomes "this looks finished".

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
else. The **two** routes that accept it are `PATCH /admin/campaigns/{id}` and
`POST /admin/campaigns`, both of which deliberately do not call the guard; a
unit test pins every half. So a barter brief is one an admin either posted or
converted — either way somebody at WeAre typed it, which is the property the
restriction is actually about.

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

## What a brief asks for

`deliverable_items` on a campaign: `[{type, quantity}]` over five formats
(`DELIVERABLE_TYPES` — reel, story, static post, YouTube Short, video). It was
a free-text box, and free text is what made it unanswerable: "1 reel + 3
stories", "one reel, three stories", "reel x1, stories x3" and "a reel and a
few stories" are four spellings of one brief, so nothing could count what a
campaign asked for, a creator comparing two briefs was comparing prose, and "a
few" is not a number anybody agreed to.

- **`deliverables` stays, and is now derived rather than typed.**
  `_deliverables_text` renders the items as "1 reel · 3 stories" and that is
  what gets stored — because the campaign keyword search regexes it, the CSV
  and the printable report print it, and `/c/{id}` renders it. Deriving means
  one answer in two shapes that cannot disagree, and means **no campaign
  written before this field has to be migrated to keep working**.
- **`_deliverable_items(doc)` is the one reader and absent is `[]`** — not
  "asked for nothing". An empty list is what tells every surface to fall back
  to the sentence, which is all a pre-field brief has.
- **`_resolve_deliverables(items, text, required)` is the only writer**, shared
  by `create_brand_campaign`, `update_brand_campaign` and
  `admin_update_campaign` — the same rule `_resolve_agreed_amount` holds for
  the fee. Items win and the sentence is derived from them; a bare sentence is
  accepted only when no items came with it (the shape a pre-field campaign
  takes coming back through an edit) and **clears the structure**, so a brief's
  words and its counted pieces can never describe different asks. The edit
  handlers pop both keys out of the generic copy loop before resolving, for the
  same reason `_refuse_brand_barter` exists.
- `_clean_deliverables` merges duplicate rows (two "reel" rows are one ask with
  a quantity) and orders by the vocabulary, so two campaigns wanting the same
  thing read the same way round. Singulars and plurals are spelled out —
  lowercasing "YouTube Short" to fit mid-sentence gives "youtube short", and a
  proper noun is not a word a formatter gets to recase.
- `lib/deliverables.js` mirrors the vocabulary and a unit test fails if they
  drift. `components/Deliverables.jsx` is the one renderer — `DeliverableList`
  (counted chips, falling back to the sentence) and `DeliverableSummary` (one
  line, for a card) — and a test fails any surface still printing
  `campaign.deliverables` directly.
- `DeliverablePicker` is the one control, on the brand form and in the admin's
  edit dialog. **Zero is how it says no**: there is no checkbox beside the
  number, so a ticked row asking for nothing is a state it cannot reach. It
  shows the sentence the campaign will carry as it is being built, which is
  exactly the string the server derives.

## Reference ids

**An ObjectId is not something a person says out loud**, and every record here
was addressed by one — in a URL, in a support thread, on a call with a brand —
so "the campaign ending 4f2a" is what that turned into. `BRD-0012`, `CMP-0034`,
`CRT-0108`, `COL-0456`: short, ordered, pronounceable, and narrow enough for a
table column.

- **A label, never a key.** Nothing looks a record up by one except search, and
  every route still takes the ObjectId — a second identifier that can address a
  record is a second thing to check permissions on.
- `_next_reference(kind)` allocates from a counter document per kind under an
  `$inc` upsert, so the sequence is decided inside the database. Counting rows
  would hand out a duplicate the moment anything was deleted.
- `_reference_of(doc)` is the one reader and **absent is `None`** — a record the
  backfill has not reached has no number, and an invented one is worse than a
  blank column because somebody would quote it. Every entity serializer emits
  it; the creator's is on `_BRAND_VISIBLE_CREATOR_FIELDS` because it carries
  nothing about the person and is what a brand and an admin quote at each other.
- Startup migration 11 numbers everything **in `_id` order**, so `CMP-0001` is
  the first brief this operation ever posted rather than whichever row the
  migration reached first, then adds a unique sparse index.
- `parse_reference` reads `"BRD-0012"`, `"brd12"` and `"crt 108"` alike — one
  somebody has to spell exactly is one they retype three times. A typed
  reference is answered **exactly** by `admin_global_search`, returning the one
  record, and it is the only way to reach a *collaboration* from the palette:
  nothing about one is a name, so there is nothing else to type.

## The application process flow

**Eight friendly stages over twelve internal states, and the states did not
change.** `COLLAB_STATE_ORDER` is the machine — what transitions are checked
against, what audit lines name, what a 409 is about — and it is unreadable:
"commercial agreed", "draft approved" and "in payment" are twelve boxes
describing our bookkeeping, and nobody can tell which one means "nearly done".

Submitted → Verified → Negotiated → Scheduled → Attended → Content review →
Content delivery → Payment. `_process_flow` groups; it decides nothing.

- **A state missing from the mapping fails a test** rather than silently
  rendering nothing. `_stage_of` is the one reader.
- **Without a draft gate the two content stages shift by one**, and that is not
  a fudge to keep the count at eight: with no gate the live link *is* the thing
  being reviewed and approving it is the delivery being accepted, while with
  the gate the draft is the review and the live post is the delivery. Both are
  true of their own campaign; what would be false is drawing a "Content review"
  stage on a campaign that reviews nothing.
- **The picture is identical for all three and only the voice changes.** The
  party who has to act reads an instruction ("Pick your slot"), everybody else
  reads the wait ("Waiting for the creator to pick a slot"). The server knows
  who called, so `ProcessFlow` never asks what role is looking — the same rule
  the shared application screen holds, and a test greps for role checks in it.
- `_process_owner` maps the table's `brand` steps through `execution_owner`: on
  a weare-run brief they are ours, and telling a creator the brand is reviewing
  their draft when our manager is would be a lie the screen tells twice a day.
- **An exit is a banner, not a ninth box**, and a send-back is *this* stage
  again with a reason — drawing it as a step backwards would lose the fact that
  the work exists.
- Below `md` the flow collapses to "Stage 4 of 8 · Scheduled", expandable.
  Eight boxes on a 390px screen are eight illegible boxes. `useWide` moved to
  `lib/useWide.js` for this — a component on the creator's dashboard importing
  a hook out of the console kit is a dependency in the wrong direction.
- **It replaced three disagreeing bars.** The creator's `LIFECYCLE` (six
  stages), the console's raw ladder and the brand's state pill were three
  answers to "where has this got to". The first is deleted, not left beside the
  new one.

## A booking is a request until somebody says yes

Booking used to be one move: a creator picked a time and that was the
arrangement, with nobody at the venue having agreed to it — so a creator turned
up to a shoot nobody had planned for.

- **It is not a new state.** The ladder still reads `commercial_agreed →
  slot_booked`; what changed is that `slot_booked` carries `slot_confirmed_at`.
  Absent means booked and waiting, set means agreed. Nothing mid-flight is
  stranded and no transition check moved.
- **`_slot_confirmed` reads absent as confirmed on a booking made before the
  handshake existed** — those were agreed by the only mechanism there was,
  nobody objecting, and reopening them all on deploy would put a decision in
  front of every manager for shoots that already happened. `slot_booked_at` is
  what tells the two apart.
- **The seat is held from the moment of booking**, either way: a place somebody
  is waiting on an answer for is not a place to sell twice.
- **Nobody books on a creator's behalf.** `advance_collaboration` refuses
  `slot_booked` outright now — it used to write the state and a time straight
  onto the collaboration, which is an admin deciding when somebody else's day
  is. `_CREATOR_OWNED_TRANSITIONS` names it, and `commercial_agreed` left
  `ADMIN_ACTION_STATES` because there is nothing an admin can do there.
- **`_answer_slot_request` is the one implementation** behind the brand's two
  routes and the WeAre manager's two, because which of them answers depends on
  `execution_owner` and a booking that meant different things depending on who
  confirmed it would not be a confirmation. Confirming writes no state — only
  the timestamp. Declining moves the collaboration back to `commercial_agreed`
  **first** and releases the seat after, or a place is on sale while somebody
  still holds it.
- The creator is told either way (`slot_requested` on booking, then
  `slot_confirmed` or `slot_declined`), and **the reason is required on a
  decline** — without it they pick the same impossible time again.

## What a brand sees on a campaign it handed to us

**Handing a campaign to WeAre is handing over the shortlisting too.** That is
what the brand is buying. The board used to show every application anyway, so
the brand watched thirty unchecked pitches arrive, formed opinions about
creators we had not checked, and was paged about each one.

- **`agreed_at` is the line**, not a state: it is the moment somebody at WeAre
  finished the job, it survives everything afterwards including a later
  decline, and it is exactly what "with the agreed amount" means. Barter sets
  it with no figure, which is right — the work was done, there is no money in
  it. `_brand_sees_collab` and `_brand_visible_collab_query` are the readers.
- **Every door carries it**, not just the board: `_brand_collab_or_404` *and*
  `_note_readable_collab_or_404`. A shield on one of two doors is a shield on
  neither — the board could hide a raw application while its id, pasted from
  anywhere, opened the pitch and the creator. A 404, like every other ownership
  refusal here.
- Applications on a weare-run brief notify `notify_weare_team` and **not the
  brand**. The brand hears once, at `_tell_brand_about_shortlist`, from both
  fee routes — so which of the two settled the number cannot change whether the
  brand finds out. `_awaiting_brand_counts` skips weare-run campaigns for the
  same reason: a badge for work they cannot do.
- **`advance_collaboration` allows the brand-owned transitions on a weare-run
  campaign**, because the brand cannot reach the application to make them.
  Refusing both would leave it stuck at `verified` with nobody able to move it.

## Every review opens a full page

A review queue row is a summary and its peek is a preview; neither carries what
a decision needs. An admin verifying a brand could not see its GST number, its
registered address or its documents from the screen where they decide it.

- Every config in `Reviews.jsx` has an `href` to the entity's own page, the row
  name is a link to it, and the peek carries "Open full page".
- **The approval actions live on the page too** — otherwise "open the full
  page" means losing the queue to read the record and going back to act on it.
  All three pages already had them; what was missing was the way there.

## Collaboration lifecycle

`COLLAB_STATE_ORDER` in `server.py` is the single source of truth:

```
applied → verified → accepted → commercial_agreed → slot_booked → attended
        → [draft_submitted → draft_approved] → content_submitted
        → content_approved → in_payment → closed
```

Plus four terminal exits that are **not** steps: `declined`, `cancelled`,
`withdrawn` and `expired` (`TERMINAL_COLLAB_STATES`) — see "Taking it back, and
calling it off" and "Expiry". The bracketed pair is optional per campaign — see "The draft gate" below.
Who moves each step matters:

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
- An exit (`declined`, `cancelled`, `withdrawn`) is **the bar stopping, not an eleventh
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

## How a creator actually gets paid

There was nowhere to record it, so every payment meant chasing an account
number over WhatsApp and typing it into a bank portal from a chat window.
`payout_method` is `upi` or `bank`, with `payout_upi` or the three bank fields
(`payout_account_name`, `payout_account_number`, `payout_ifsc`) beside it.

- **`_payout_method(profile)` reads absent-with-a-UPI-id as `"upi"`.** The
  field is new and the UPI id is not, so the other reading would make every
  currently payable creator unpayable the moment this deployed. Same
  absent-reads-safe rule as `_compensation_type` and `_execution_owner`.
- **`payout_missing` is the one definition of what is still needed and
  `payout_ready` is `not payout_missing`** — one function, so the gate at
  `in_payment`, the creator's own progress panel and the admin's payment row
  cannot disagree about whether somebody can be paid. It names the fields in
  words a person would use ("an IFSC code"), because "payout_ifsc" is not a
  thing anybody can go and find.
- **It is not part of completeness and not asked at signup.** A PAN must not be
  the price of being looked at — the same reason `_profile_completeness` leaves
  payout out — and this is required to reach `in_payment`, which is the moment
  it is actually true.
- `IFSC_RE` and `ACCOUNT_RE` refuse a shape that cannot be an IFSC or an
  account number. A typo caught here is a form field; caught later it is a
  failed transfer somebody has to unpick with a bank.
- **Changing any of it re-triggers review.** Every payout field is in
  `MATERIAL_PROFILE_FIELDS` — the account money goes to is exactly the kind of
  change worth looking at again — and re-review is the existing
  `pending_review` flag, never a downgrade.

### Masked, and never brand-facing

`mask_tail(value, keep=4)` is the only thing that shortens one of these, and
`_masked_payout(profile)` is what an admin surface receives. `None` stays
`None`: a masked blank would read as a number nobody can see rather than a
number nobody has.

- **Brands receive none of it, at any state.** The fields are in
  `BRAND_FORBIDDEN_CREATOR_FIELDS` and off `_BRAND_VISIBLE_CREATOR_FIELDS`, so
  the leak test that plants values and searches every brand response shape
  covers them the way it covers the phone number and the map pin.
- The UPI mask keeps the `@handle`, because that half is what tells two ids
  apart when somebody is checking they are paying the right person, and it is
  not the secret half.
- The **payments export is the one place the real values may go** — the same
  exception `EXPORTS_WITH_CONTACT` already carves out, for the same reason:
  somebody is reconciling a bank statement, and a masked account number is
  useless to them. `_payout_columns(snapshot, profile)` builds them, and **the
  snapshot on the payment wins over the live profile**: what matters for
  accounting is where the money actually went, not where it would go today.

### PAN and withholding

`pan` sits with the payout fields — admin-only, masked the same way, required
before a first payout for the same tax reason it is collected at all.

**Nothing here computes a tax rate.** `MarkPaidPayload` carries
`tds_applicable` and `tds_amount` and records what the admin typed;
`mark_payment_paid` stores both plus `net_paid`. A withholding rate depends on
the payee's status and the section it falls under, and a rate hardcoded here
would be wrong for somebody and silently wrong for everybody after the next
budget.

- **Three states, not two.** `None` is "nobody has said", `False` is "no
  withholding", `True` carries an amount. The export prints blank, "no" and
  "yes" — a `None` rendered as "no" is a claim we never made.
- A `model_validator` refuses the incoherent pairs: `False` with an amount, and
  `True` with none. Either one produces a payment record that contradicts
  itself, which is the shape an accountant finds a year later.
- **There are two mark-paid doors and both carry the fields.** The
  collaboration page and the action queue, and the queue is the one most
  payouts go through — working the queue is the fast path — so a withholding
  field on the detail page alone is TDS recordable in theory and unrecorded in
  practice. A test walks every `/mark_paid` caller under `components/admin/`.
- `ConfirmDialog` takes `extra` (one field) or `extras` (several). A call site
  that builds its config into state must forward **both**: the queue forwarded
  only `extra`, so moving its payout config to the multi-field shape dropped
  every field including the required reference, leaving a correct POST body
  and an empty form. The `/mark_paid` test could not see that — the fields and
  the submit handler are wired in different places — so a second test checks
  the forwarding, and the browser is what caught it.

## Taking it back, and calling it off

Two exits that did not exist. Before them a creator who had changed their mind
could only go quiet — and a brand then shortlisted somebody who was never going
to turn up — while a cancellation after acceptance had no defined handling at
all, so it happened over WhatsApp and left no record of who called it or how
much notice anybody had.

- **Withdrawal is the creator's, up to acceptance.**
  `WITHDRAWABLE_COLLAB_STATES` is `("applied", "verified")`: after `accepted`
  somebody has committed to them and taking it back unilaterally is a
  cancellation, which is a different event with a different name. It writes the
  terminal state `withdrawn`, captures the reason — required, because "one of
  your three applicants is gone" is not something anybody can act on — and
  notifies whoever runs the campaign through the same `execution_owner`
  routing an application uses.
- **`withdrawn` is a fourth terminal state, not a variant of `cancelled`.**
  It is in `TERMINAL_COLLAB_STATES` and `COLLAB_GROUP_ENDED`, has its own
  `_PROCESS_BANNERS` and `_NEXT_ACTION` entries, and the history panel prints
  the two words differently: a withdrawal happens before anybody is committed
  and is the creator's to make, so drawing it as a cancellation puts a black
  mark where there is none.
- **Cancellation records the notice, not a verdict on it.**
  `_days_of_notice(campaign, collab)` is whole days in IST and **can be
  negative** — a shoot cancelled after the fact is a real thing that happens
  and rounding it to zero would hide it. Whether four days is enough is a
  commercial judgement that differs by brand and by venue, so the panel reports
  the number and leaves the judgement to whoever is reading.
- `cancelled_by_id`/`_name`/`_role` are on the record because "the brand
  cancelled" and "we cancelled" are different facts about the same row, and the
  audit line alone does not travel with the collaboration.
- **A kill fee keeps the payment row `pending`** rather than closing it — money
  is owed, and a cancelled collaboration whose payment vanished is money nobody
  chases. Where there is no payment row yet one is inserted, flagged
  `is_kill_fee` and carrying the payout snapshot like any other. The creator is
  told immediately and the message names the amount.
- `_cancellation_history(creator_id=…| brand_ids=…)` feeds **one component on
  two pages** (`CancellationHistory`). The same event is two questions — a
  brand's page asks how often we pull out on people, a creator's asks how often
  this happens around them — and two panels would answer them differently the
  first time one was changed.

## Rejection is not a dead end

A rejected brand could read a WhatsApp message and then had nowhere to go: the
profile stayed open to edit, and nothing turned a fixed profile back into a
queue item.

- The rejection reason is **on the brand's own onboarding page**, quoted, above
  the fields it is about. Telling somebody they failed and not what to fix is
  how a verification queue turns into a support thread.
- Resubmitting goes through the **same** `POST /brand/verification/submit` —
  same required set, same 409 naming what is absent. A second route would be a
  second definition of what a submission is.
- `verification_resubmissions` counts them and rides on the admin's brand page
  and the review queue row. It is context, not a threshold: a third attempt
  might be somebody who cannot read the form, and knowing that is what lets a
  reviewer pick up the phone instead of rejecting again.

## Being forgotten

`deletion_router` at `/account`, and the admin half at
`/admin/deletion-requests`. The DPDP Act 2023 gives a person the right to
erasure and until this existed the only way to exercise it was to email
somebody and hope — in a product that holds a WhatsApp number, a home address,
a map pin, a PAN and a bank account.

- **A request, reviewed by a person.** `DELETION_STATES` is
  `("requested", "erased", "declined", "withdrawn")` — deliberately **not**
  "approved", both because the guard test bans that legacy word and because
  "erased" is the accurate one: what the admin does is not grant permission,
  it is carry it out.
- **Blocked while work is in flight, and the block names the work.**
  `_blocking_collaborations(user)` returns the live rows and the 409 carries
  them as `work_in_flight`; "you have three collaborations open" is not
  something anybody can act on, "the Toit tasting, waiting on your draft" is.
  The list is **re-read at the moment of erasure**, never trusted from when the
  request was made — work can start in between, and erasing then leaves a brand
  with a booking against nobody.
- **Erasing removes the person and keeps the arithmetic.** Every write is
  `$unset` plus a tombstone, never a document delete, so collaborations,
  amounts and audit lines still resolve their joins — they simply have nobody
  in them. `_ERASE_CREATOR_PROFILE` / `_ERASE_BRAND_PROFILE` / `_ERASE_ACCOUNT`
  are the field lists, the private uploads are removed from disk, and the
  Instagram connection and its encrypted token go with them.
- **Payments are reached through the collaborations, not by a `creator_id` on
  the payment.** There isn't one — the first version of this queried for it,
  matched nothing, and would have left every bank account and PAN sitting in
  `payments` after an erasure that reported success.
- The screen says what "deleted" actually means **before** anybody agrees to
  it, because it does not mean everything vanishes. Somebody who finds that out
  afterwards has met exactly the surprise the right exists to prevent.
- A refusal **closes the dialog**, because the blocking list renders in the
  panel behind it — leaving it up shows an unchanged form and a button that
  did nothing, which is the one reading of a refusal worse than the refusal.
- The reason is **optional**. Nobody has to justify leaving, and a required box
  there is a toll on a right.

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

## The clock

**Nothing in this system had one.** Every state waited indefinitely for a
human: an application sat at `applied` until somebody read it, a draft at
`draft_submitted` until somebody looked, a brand in the verification queue
until somebody decided. None of that is wrong — these *are* decisions people
make — but with nothing measuring the wait, a record that had stalled looked
exactly like a record that was fine, and the first person to notice was
whoever eventually rang up. So: every record knows when it entered the state
it is in, every state has a target, and anything past its target is loud.

- **`state_since` is the field and `_state_stamp` is the only writer.** There
  is no single transition function here — states are written at more than
  thirty call sites, each with its own `from_state` precondition — so the
  stamp travels with the state rather than being applied centrally, and a
  structural test fails any `$set` that writes one without the other.
  `_state_stamp` takes the column name because the four clocked records do not
  agree on it (`STATE_CLOCK_FIELDS`): a collaboration has `state`, a campaign
  `status`, a brand `verification_state`, a creator `verification_status`.
- **`updated_at` is deliberately not the clock.** It moves when anybody writes
  anything — a note, a rate, a cover image — so a collaboration nobody has
  advanced in a fortnight would read as touched five minutes ago, which is the
  opposite of what an ageing display is for.
- **`_state_since` falls back to `updated_at`, and the fallback understates the
  age.** A row written before the field existed does not know when it last
  moved; `updated_at` is at or after the real transition, so the age it yields
  is a lower bound. That is the safe direction — an escalation that fires late
  is a nuisance, one that fires on a record that is fine teaches everybody to
  ignore the signal — and it self-corrects the first time the record moves.
- **The startup migrations are exempt and say so.** `clock-exempt:` marks
  them: a rename (`vetted` → `verified`) and a derivation
  (`verification_state` from a boolean) are not transitions, and stamping
  either would date every historical record to the deploy and make the whole
  platform read as "waiting since this morning". Exempted **by marker, not by
  line number** — a test that names a line breaks on the next import.

### What "too long" means, and who says

`SLA_DEFAULT_HOURS` holds the nine targets — creator and brand verification
48h, campaign review 24h, application response 72h, commercial agreement 72h,
slot booking 48h, draft review 48h, content submission 72h, payment 7 days.

**They are defaults, not constants.** Every one is an operating decision that
depends on how many people are working the queue this month, so a target that
needs a deploy to change is one that never changes — it gets argued about and
then lived with. `sla_targets()` lays stored overrides from `platform_settings`
over the table; `GET`/`PUT /admin/settings/sla` is the editor, **admin-only and
not `CONSOLE_ROLES`**, because somebody whose queue is being measured is the
wrong person to be able to move the line. Overrides are partial, so adding a
tenth target ships with a sensible number rather than being silently unset on
every install that ever saved the form.

- `_SLA_BY_COLLAB_STATE` maps a state to its target. **A state that is nobody's
  delay is absent**: `slot_booked` waits on a date in the future rather than on
  a person, and the terminal states are finished. Absent means "no clock",
  never "zero".
- **`_ageing_from` takes the instant, not the record**, because the clock does
  not always start when the state changed. A creator profile has been `pending`
  since the day they signed up; the wait somebody is answerable for starts at
  `submitted_for_review_at`. Ageing that queue off the state would report a
  fortnight of the creator's own half-finished profile as our delay, which is
  the kind of wrong that makes an operator dismiss the panel.
  `_creator_review_ageing`, `_brand_review_ageing` and `_campaign_review_ageing`
  each return `None` for a record that is not waiting on us — a verified
  creator is in no queue, and drawing a clock on them would invent one.
- **Four tones, not two** (`SLA_TONES`): calm, due at half the target, overdue,
  critical at double. "Fine" and "on fire" leaves nothing to say about the
  record that is *about* to become a problem, which is the only one somebody
  can still act on.

### Who sees the verdict

The age goes on every record. The *verdict* does not.

- Admin and staff surfaces get the whole block. So does the **brand**, on its
  own applicant board: where the wait is theirs, the target is a standard they
  are being held to and being told is the point.
- The **creator's own row carries the age and no target** (`_serialize_collab_row`
  passes no SLA). An SLA is the standard this operation holds itself to
  internally; it is not a promise made to the creator, and publishing "the
  brand is 4 days over target" would turn one into the other. What to do about
  it reaches them through the process flow's next action and, when it is theirs
  to move, through a WhatsApp reminder.
- `components/AgeBadge.jsx` is the one renderer, and it **draws what the server
  sent and computes nothing** — a test greps it for date arithmetic. It renders
  nothing without a block.
- **The browser holds no second definition of "too long".** The console had one
  — `isStale`, a flat 48 hours — and against nine real targets it was wrong in
  both directions: it called a payment overdue on day three of seven and a
  campaign review fine on day two of one. It is gone, and a test fails any
  threshold constant that reappears under `components/`.
- **Sorting is by the fraction of the allowance used**, `hours / sla_hours`, on
  both the server's overdue list and the queue's age column. A payment eight
  days into a seven-day target has used 1.14; a campaign review five days into
  a one-day target has used 5.0, and it is the one to look at first. The first
  version of the client-side key returned `1e12 + overdue_hours` for overdue
  rows and a millisecond timestamp for the rest — and a timestamp is ~1.76e12,
  so every un-overdue row outranked every overdue one. **Caught in a browser,
  not by a test**, which is why the test now names the arithmetic.

### Chasing, and letting things lapse

`run_lifecycle_chasers()` is one pass on a loop (`LIFECYCLE_INTERVAL_SECONDS`,
0 disables) and behind `POST /admin/jobs/lifecycle`. Five reminders, each to
the party who can actually move the thing: book a slot, a shoot tomorrow,
content due after attending, a draft nobody has reviewed, pitches nobody has
answered.

- **At most twice, and then never again.** Chasing somebody a third time about
  the same row is how a WhatsApp channel stops being read, and this operation
  runs entirely on that channel. A third would be nagging; the escalation is
  the answer to somebody who has ignored two.
- **The claim is the write**, exactly like the profile nudge, and it carries
  the state as a precondition — which is what makes "stops once the state
  advances" structural rather than remembered. `$lt` would skip a row that has
  never been reminded, because Mongo's comparison operators skip missing
  fields; `$not: {$gte: n}` matches it. Same absent-reads-safe trap as
  everywhere else here.
- **Escalation follows `execution_owner`** (`_escalate_to_whoever_runs_it`) —
  the same routing a new application takes, reusing the readers rather than
  writing a second rule. Weare-run goes to the WeAre team; brand-run goes to
  the brand manager **and copies admin**, because an overdue record is an
  operational fact about the platform as well as a job for the brand, and the
  brand going quiet is exactly the case somebody here needs to know about.
- Unanswered pitches are **one message per campaign, not per applicant**: five
  pitches on one brief is one job, and five WhatsApps about it is five reasons
  to mute us.
- Jobs credit `_SYSTEM_ACTOR` in the audit log — named rather than blank,
  because an audit line with no actor reads as a gap rather than as the system
  acting. Its `_id` is absent, so `actor_id` lands as `None` and nobody can
  mistake it for a person.

### Late delivery

**The SLA and the grace are two different things with two different
consequences**, and collapsing them would be unfair to the creator. Passing the
content target means we chase — somebody is waiting and a nudge is
proportionate. Passing the target *and* `CONTENT_GRACE_HOURS` on top is what
writes `content_overdue` on the record, escalates, and counts against on-time
delivery in `_delivery_history`. A mark on somebody's reliability should not be
the same event as a reminder.

The flag is set once and never cleared: delivering eventually does not make a
delivery not have been late, and this is the only signal a brand has about
whether somebody turns work in.

### Expiry

- **Invitations carry a deadline** (`INVITATION_RESPONSE_DAYS`, 7). Without
  one, an invitation is a brief the brand can never take off the table, and
  "invited, not answered" counts people who decided nothing months ago.
  `_invitation_lapsed` is **read on every serialize, not only swept** — the
  sweep keeps the database tidy, but the reader is the enforcement, or an
  Accept button's availability would depend on whether cron ran.
  `respond_by` is stored so moving the constant later cannot retroactively
  shorten an offer somebody is already holding, and derived from the send date
  for rows written before the field.
  `_refuse_unanswerable_invitation` is **one guard behind both answers**, or an
  invitation would be declinable a fortnight after it lapsed but not
  acceptable. The two refusals read differently: "you already answered" and
  "the offer ran out" are different facts.
- **`expired` is a fifth terminal state, and it is nobody's decision.** An
  application on a brief that started and was never actioned is not declined
  (nobody decided), not withdrawn (the creator did not take it back) and not
  cancelled (there was nothing to cancel) — and on a creator's history,
  "declined" and "nobody ever answered" are very different facts about them.
  The creator is told, and told plainly that it was not about them. Only
  campaigns that have actually begun; a brief that is merely old is still one
  somebody might answer tomorrow.
- **Drafts untouched for `DRAFT_STALE_DAYS` (30) are flagged, never tidied
  away.** It is the brand's own unpublished work, and a platform that deletes
  somebody's draft is one they stop trusting with a draft. `_draft_is_stale` is
  derived rather than stored — a stored flag needs clearing on every edit, and
  the edit that forgets is the bug.

## Health, activity and exports

The overview leads with **what is going wrong**, then what the business is
doing, then its own numbers, then the exports. A campaign quietly underfilling
four days before the shoot generates no notification and sits in no queue — it
is discovered when the brand rings up, unless something looks for it.

`GET /admin/health` runs nine checks. **The first is the catch-all**: every
record whose own clock says it is past its target, worst first — see "The
clock" above. A record can be missing from all eight of the others and still be
four days over, and "never let an overdue record be invisible" is the promise
that check keeps. Then: underfilling campaigns near their day,
accepted creators with no slot, content overdue after attendance, drafts nobody
has reviewed, payments sitting unpaid, brands waiting on our verification, and
profiles that stalled, deliveries past the grace, and drafts nobody has
touched in a month. The draft one has the shortest fuse
(`DRAFT_REVIEW_OVERDUE_DAYS`, 2) because it is the only row where the delay is
*ours*: the creator has done the work and cannot publish until somebody looks.
Every threshold is a named constant (`FILL_WARNING_RATIO`, `PAYMENT_OVERDUE_DAYS`
…) because each is a judgement about how much slack the operation has, and they
travel back in the response so the panel quotes the server's numbers rather than
a copy that drifts. **Every row carries an `href`** — a count tells you there
is a problem and then makes you go and find it — and the underfilling rows
carry **the numbers and the ways out**: how many slots short, how many days
left, and links to invite creators, extend the dates or ask for fewer. Naming a
problem with nothing to do about it is how a health panel becomes a list people
scroll past.

The row is a **stretched link, not a wrapping one**, because it now has its own
actions and an anchor inside an anchor is invalid markup browsers resolve by
dropping one of them — the same arrangement the campaign card uses. And **a
check that sorted itself keeps its order**: the panel's default is severity
then oldest-first, which is right for eight of the nine and actively wrong for
the overdue list, so that one sets `presorted`.

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

`/admin` is a **layout**, not a page (`pages/AdminConsole.jsx`): it owns the
sidebar and the badge counts and renders the matched route into an `<Outlet>`.
The URL is the state. It used to be one route with a `useState` tab, which made
every screen unaddressable — no deep link, no back button, and a reload always
landed on Overview.

- Fourteen list routes off the sidebar (`""` index, `queue`, `creator-reviews`,
  `campaign-reviews`, `brand-reviews`, `creators`, `campaigns`, `brands`,
  `performance`, `health`, `audit`, `team`, `deletions`, `settings`) and four
  detail routes:
  `/admin/campaigns/:id`, `/creators/:id`, `/brands/:id`,
  `/collaborations/:id`. `ADMIN_SECTIONS` in `components/admin/console/Sidebar.jsx`
  is both the navigation and the route table, re-exported as `ADMIN_TABS` under
  its old name because the router builds from it; a unit test fails a section
  that routes nowhere.
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

### The working surface

Everything above is the architecture. **How it looks and handles is a separate
set of decisions, and they are the ones a person notices after the fortieth
load.** The console was built like the rest of the product — cards, grain,
entrance motion, a horizontal tab strip — which is right for a page a creator
reads once and wrong for a tool somebody sits in front of for an hour.
`components/admin/console/` is the kit, and `tests/unit/test_admin_console.py`
holds every rule below.

- **A sidebar, not a tab strip.** Nine tabs across the top scrolled sideways on
  anything under a laptop, so half the sections and all of their badge counts
  were off-screen — you could not see that six brands were waiting without
  scrolling the navigation. It also spent the screen's widest dimension on
  chrome when the thing that needs width is a table. Collapse to icons persists
  (`localStorage`), because it is a preference rather than a per-visit choice,
  and **below `md` the icon rail is the only form** — 224px of a 390px screen
  spent on navigation leaves 166px for the table.
- **Tables, through one `DataTable`.** Cards are right when each item is a
  thing you look *at* and wrong when they are rows you look *across*: you
  cannot compare a follower count in card three with the one in card eleven,
  and a screen that fits nine cards fits about thirty rows. Sticky header,
  44px rows, right-aligned numerics in tabular figures, and **a column sorts
  on its `value`, not on what its `cell` prints** — sorting the formatted
  string is how "9k" ends up above "24k". Nullish sorts last in both
  directions: a row with no value is unknown, not smallest. Past
  `VIRTUALISE_ABOVE` (150) the body is windowed; below it everything stays in
  the DOM, because windowing forty rows costs more than it saves and breaks
  ⌘F. Measured: 400 rows render 31, and the page still scrolls at 390px.
  Cards survive in exactly one place — Overview's stat tiles, which are things
  you look at.
- **One density scale** (`tokens.js`): `DENSITY`, `ROW_H`/`ROW_PX` (which must
  agree — one renders, the other is what virtualisation measures with), and
  `TEXT`, where `text-xs` means *true* metadata. The console had 158 uses of
  it and was effectively set in 12px; a test now fails any `text-xs` that is
  not on an uppercase eyebrow.
- **One semantic colour per state, always with the word beside it.**
  `STATUS_TONE` is five tones, `TONE_BY_STATE` maps every wire value onto one,
  and `StatusTag` is the only thing that draws a state — the four `meta`
  objects it replaced are why a closed campaign read grey on one screen and
  red on the next. **Ember is never a status**: it is the primary action, and
  a status wearing it makes every row look like a call to action.
- **The console is calm.** No grain (the shared dialog primitive grains
  itself, so the three console dialogs turn it off at the call site), no
  entrance animation, 150ms colour transitions and nothing else. A list that
  animates in is a list you cannot read until it has finished. Skeletons stay:
  that is shape, not motion, and CLS measures 0.0000 with the API delayed.
- **The peek panel** (`PeekPanel`) is a row's detail without leaving the list —
  working a queue is "check this one, act, next", and a full-page round trip
  per row loses the filter, the sort and the scroll forty times an hour. It
  **always offers "Open full page"**: a peek that quietly became the only way
  to see something would be a detail page with less in it.
- **The keyboard is a faster way to the same actions, never a way around a
  confirmation.** `useTableKeys` binds ↑↓/kj, Enter, A, R, Esc and ?; A and R
  call the same handlers the buttons do, so R still opens the reason dialog —
  verified by pressing it and watching nothing POST until a reason was typed.
  **Typing is never intercepted**: every handler bails on an input, a textarea,
  a select, anything `contentEditable`, and anything inside a Radix dialog, so
  "j" in a search box is a letter. `ShortcutsOverlay` is generated from one
  `SHORTCUTS` list and a test checks the bindings it advertises exist.
- **Filters, sort and scroll persist per section** (`useListState`), in
  `sessionStorage` — a working context should survive a detail page and a
  refresh and be gone tomorrow. **Saved filter sets are the deliberate
  exception** and live in `localStorage`, appearing under their section in the
  sidebar; naming one is an explicit act, so it should still be there next
  week. The sidebar picks a new set up through a `weare:saved-filters` event
  rather than a prop drilled through the shell.
- **A row keeps the test id its screen already had.** `DataTable` takes a
  `rowTestId`, so the creator list's rows are still `admin-creator-tile-<id>`
  and a column header can carry the id its sort chip used to. Changing the
  layout is not a reason to break "the element for creator X".

#### On a phone it is not a table at all

A table earns its keep by letting you read *across*, and at 390px there is no
across: six columns become two and the rest — **including every action** — sit
behind a sideways scroll nobody finds. Measured on the action queue, whose
entire purpose is the approve/reject pair: both were off-screen. The first
attempt at a fix made it worse in a different way, squashing the name column to
nothing and overlapping two headers.

- **Below `md`, `DataTable` renders a stacked list of the same rows**, and the
  call site says which column goes where: `mobile: "primary" | "meta" |
  "trailing" | "action"`. No hint means desktop-only, which is the honest
  default — most columns exist to be compared, and comparison is the thing a
  phone cannot do. A test fails a list that declares no `primary`, and one
  with decisions that declares no `action`.
- `useWide()` reads `matchMedia` **synchronously on first render**, so neither
  form appears for a frame before being replaced. Only one of the two is in
  the DOM.
- **The phone list is not its own scroll container** — the page scrolls, which
  is what a phone expects, and a fixed-height box inside a short viewport is
  worse than the problem it solves. That means no windowing there: measured,
  400 rows all render. The lists that get long are paginated at 50 or capped
  at 200, so the ceiling is the audit log at 200 rows.
- `mobileCell` is the escape hatch for a value whose desktop form is a
  compromise with a column width — used once, for the queue's overdue marker,
  which is "!" in a 7rem column and "· overdue" where there is room.
- **The icon rail is not the phone's navigation.** 56px of a 390px screen is
  14% of the width spent on nine unlabelled glyphs, on a device with no hover
  to explain them — the `title` that carries the rail on a laptop is invisible
  under a finger. The rail is `hidden md:flex`; below that the sections are
  `AdminNavSheet`, opened from the console's own header. Both render the same
  `SectionLink`, so a phone cannot find a different set of sections from a
  laptop, and the badge is a number wherever there is room to read one.

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

## The internal team, and the console with a scope around it

WeAre runs campaigns for its own clients, and the people who do that are not
admins: they need the console, and they need it to end at the brands they are
on. `weare_team` is that role — **the same sidebar, action queue, review tabs,
entity pages, collaboration actions and exports, filtered server-side to
assigned brands.**

`CONSOLE_ROLES = ("admin", "weare_team")` is spread into `require_roles` on
every scoped console endpoint, exactly the way `BRAND_ROLES` is. `is_all_access`
is the one place "everything" is decided, and it is only ever `admin`.

- **`_console_brand_ids(user)` returns `None` for an admin and a list for
  everybody else, and that distinction is load-bearing.** `None` means no
  filter; a list — which may legitimately be empty, for somebody assigned
  nothing yet — means those brands and no others. An empty list reading as "no
  filter" would hand a new starter the whole platform on their first morning,
  and a test drives every list handler with exactly that user.
- `_console_brand_query`, `_console_campaign_query` and `_console_creator_ids`
  are the readers every scoped query spreads. Collaborations, payments, slots
  and question threads hang off a campaign rather than a brand, so the campaign
  ids are resolved once per request instead of joining on every query.
- **The scope is on the query, never on the rows.** Several of these lists sort
  and then cap; filtering afterwards would silently shorten a scoped queue to
  whatever survived somebody else's hundred.
- **Every door is the same door.** `_admin_campaign_or_404`, `_collab_or_404`,
  `_console_brand_or_404` and `_console_payment_or_404` take the caller and
  apply the scope, and a **404 — never a 403**, because whether a brand we do
  not work with exists is itself what the scope protects. A structural test
  fails any console handler that resolves a path id without going through one;
  it found five real gaps when it was written, the collaboration detail page
  and all four collaboration actions, each of which resolved its own id inline.
- **What stays admin-only**: the global creator directory and its review queue,
  the platform-wide instruments (`/admin/metrics`, `/admin/health`,
  `/admin/intelligence`), the audit log, the creator and audit exports
  (`ADMIN_ONLY_EXPORTS`), and the settings that hand out scope. A scoped role
  that could widen its own scope is not a scope, so `POST`/`DELETE
  /admin/brands/{id}/team` are admin-only while the `GET` beside them is not.
- Assignment is `$addToSet`/`$pull` on `assigned_brand_ids`, **from the brand's
  own page** — that is where the decision is made. Accounts are created under
  `/admin/team`; a team member can be on any number of brands.
- Every action audits under their own name like an admin's. `weare_team` **is**
  in `IMPERSONATABLE_ROLES`, for the reason `admin` is not: a scoped console is
  a view an admin cannot otherwise see, so "why is that brand missing from my
  list" is answered by looking.

The frontend half is a courtesy on top, never the enforcement.
`lib/consoleScope.js` mirrors the two roles with a drift test, `adminOnly` on a
section in `Sidebar.jsx` keeps it out of `sectionsFor(role)` — which feeds the
rail *and* the sheet, so a phone cannot find a different set from a laptop —
and the action queue simply does not ask for the two creator queues, because
one 403 inside its `Promise.all` would empty a queue that is otherwise entirely
theirs to work. `BrandFilter` writes `?brand=<id>` to the URL rather than to
state, so a narrowed console is a link somebody can send; it renders nothing
for somebody on one brand. **No screen filters by brand itself** — a test greps
the whole frontend for `assigned_brand_ids` and fails on a hit.

## What an admin may create

We are the operator as well as the platform. Some campaigns are ours to run,
some briefs are barter, and some brands and creators arrive through a
conversation rather than a signup form. Before `POST /admin/campaigns`,
`/admin/brands` and `/admin/creators` an admin could review, edit, publish and
close but never *create*, so an internal client had to be walked through a
signup screen for an account nobody would ever log into.

- **The campaign skips the review gate because we are the reviewer.**
  `pending_review` is not in `AdminCreateCampaignPayload`'s statuses at all —
  submitting a brief to ourselves and then approving it is a queue item that
  exists to be dismissed. `execution_owner` defaults to `weare` (the brand's
  own form defaults the other way for the same reason: the party posting is the
  party running it), and a weare-run brief still gets `_NO_CAMPAIGN_MANAGER`.
- **`_refuse_brand_barter` is deliberately not called** — the same asymmetry
  `admin_update_campaign` holds. Adding the guard here would make a barter
  brief impossible to *create*, leaving an edit as the only way to reach one. A
  unit test pins both halves.
- **Publishing still needs a verified brand**, the identical 409
  `approve_campaign` raises: creators are never reachable by a brand nobody has
  checked, and a new route is not a reason to lose that. A draft reaches
  nobody, so a draft is fine.
- **Admin-created brands and creators enter verified**, because verification is
  a check that has already happened offline and this is the record of it — the
  audit line names who made the call. The brand is otherwise identical to a
  self-registered one, `brand_id` pointing at itself so `_brand_scope` reads it
  without a special case; the creator's profile is a **stub, not a guess**, and
  lands in no review queue for somebody to dismiss.
- All three are **admin-only, not `CONSOLE_ROLES`**: minting a verified brand
  is a statement about a check, and a scoped console could otherwise create the
  brand it then gets assigned to.
- The UI is `components/admin/CreateDialogs.jsx`, three dialogs opened from the
  list each new row lands in. The campaign one carries what the payload
  requires and no more — everything else is editable on the campaign's own page
  a moment later, and a twenty-field dialog is a form somebody abandons. It is
  the second control in the product that can set barter (`CampaignEditDialog`
  is the other), and dates go out as instants the way the brand's form sends
  them. `lib/categories.js` holds the category list, which until this was
  written out twice and about to be a third time.

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

## The portal is IST, the database is UTC

**BSON has no time zone.** A value written as `datetime.now(timezone.utc)`
comes back from Mongo *naive*, and `datetime.isoformat()` on a naive value
emits no offset at all — so the same instant serialised two different ways
depending on whether it had been round tripped through the database, and
`new Date()` read the naive half as the reader's **local** time. That is 5½
hours here, and it is why the notification panel said "6h ago" about something
twenty minutes old. The relative-time arithmetic was always right; its input
was wrong.

Storage stays UTC. The API emits UTC *with its offset*. The conversion to IST
happens once on the way to a screen, and once on the way to a phone.

- **`_iso(value)` is the only way a datetime becomes a string.** It stamps a
  naive value as UTC — which states a fact rather than guessing, since every
  write goes through `datetime.now(timezone.utc)` — and leaves an aware one
  alone. `_jsonable` routes through it too, so the audit log's raw before/after
  blobs hold the same rule as the hand-written serializers. A unit test fails
  any bare `.isoformat()` outside `_iso` (a `date` has no time and so no zone;
  `.date().isoformat()` is exempt).
- **`_when_text` is the only human-facing time this server writes** — the
  WhatsApp messages telling a creator when to turn up. Formatting the stored
  UTC directly said 2:00 pm for a 7:30 pm sitting: the same 5½ hours arriving
  on a phone instead of on a screen. It goes through `_ist`, which reads a
  naive value as UTC for the same reason `_iso` does.
- `SHOOT_TZ` is a fixed +05:30 rather than a named zone, and that is correct:
  IST has no daylight saving, so there is no rule to look up.
- **`frontend/src/lib/time.js` is the only place the zone is named**, and every
  formatter in it passes `timeZone: IST`. A unit test walks every `.js`/`.jsx`
  under `src/` and fails a `toLocale*` call that carries date options without a
  `timeZone`, fails a second file spelling out `"Asia/Kolkata"`, and fails a
  file that formats dates without importing the zone. A manager opening the
  daysheet from another country reads the same times as the person at the door.
- **`dayKey` is how a day is bucketed**, via `en-CA` + the zone.
  `toISOString().slice(0, 10)` is the *UTC* day, which moves every evening
  shoot in India to the next date. `setHours(0, 0, 0, 0)` is banned for the
  same reason plus a second one — it mutates the Date it is called on, which in
  `ManagerHome`'s loop meant every campaign after the first with an end date
  was measured against midnight rather than now. Both are pinned by tests.
- `timeAgo` lives in `lib/time.js` and nowhere else. The console keeps its own
  `relative` in `admin/console/format.jsx` — "3h ago" where the app says "3h",
  and days for a month rather than weeks after a fortnight — deliberately, and
  with the reason in the file. A dead third copy in `admin/shared.jsx` is what
  the test now stops coming back.

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
  up. **`slots_pending` is the one exception and is raised whatever the date**:
  everything else there becomes a problem as the shoot approaches, while a
  creator holding a seat nobody has answered is a problem the moment they book.
- `shared.jsx` imports the zone helper as `startOfDay as istStartOfDay`, because
  the wrapper beside it keeps the shorter name. Without that alias the wrapper
  was a bare `ReferenceError`, thrown by `isToday` for every campaign in the
  list — **the manager's entire home page fell through to the route boundary on
  every render, and shipped that way.** Every test about this file read
  functions out of it rather than rendering the page, and an imported function
  still resolves its own module scope, so the missing name only bit at call
  time.

### Told about work you can do

The manager's screens and the manager's *jobs* drifted apart. The `/manager`
router grew endpoints, `notify_campaign_manager` grew events, and
`_question_staff_may_see` grew a `campaign_manager` branch, while the frontend
kept the three tabs it started with — so the role was **paged about work it had
no way to do**. Five routes had no caller anywhere; the notification for one of
them deep-linked to a page that showed neither the request nor a button.

`test_manager_experience.py` holds the line now: **every route on the manager
router must have a caller in the frontend**, and every new panel must be
rendered by a screen. The second half matters as much as the first — deleting
`<SlotAnswer />` from the campaign page left the route-has-a-caller check green,
because the component file still held the only `slot/confirm` call in the
repository. A caller with no mount is as unreachable as a route with no caller.

- **`SlotAnswer` is the second half of the booking handshake**, a band above
  everything on the campaign page rather than a tab: somebody is holding a seat
  waiting on an answer, which is not a section you go and look in. It renders
  nothing when nothing is waiting. `_roster_rows` emits `slot_pending` so a held
  booking is told apart from a settled one, and `_pending_slot_counts_for` puts
  the number on the home card.
- **`/manager/applications/:id` mounts the shared `ApplicationDetail`** — the
  third route onto one component, not a fourth copy of the screen.
  `get_application` had always accepted a `campaign_manager` and no URL reached
  it, which cost them the three things the server already lets them do: review a
  draft, answer a creator's question, and read the work notes. `slotBase` is the
  only prop that differs (`/manager` rather than `/brand`) — the component is
  *told* where to post, the way it is told about `entityLinks`, and still never
  asks what role is looking. The other actions are brand-owned transitions the
  server never offers a manager, so their buttons do not render.
- **`BriefPanel` is a tab, because no manager surface carried the brief at
  all.** The person running the day could see who was coming, when and where,
  and not one word of what the creators had been asked to produce. The roster
  payload carries `brief`, `deliverable_items` and the fee *with its
  compensation type beside it*; the panel renders through `DeliverableList` and
  `formatCompensation` rather than growing a fourth spelling of either.
- **`PerformanceSheet` records what the published work did**, from the roster
  row, and only on a collaboration that has actually delivered — before that the
  button opens a form nobody can fill in honestly. A blank field is omitted from
  the payload rather than sent as zero: unknown and none are different, and
  averaging the second is how a report starts lying.
- **All three day-of actions now survive the venue's wifi.** Check-in already
  queued; no-show and reschedule raised a Retry toast, which is the same manager
  in the same basement being asked to do the network's job — and a reschedule
  that silently failed is worse than a lost check-in, because the creator has
  been told a time nobody recorded. `shouldRetry` is exported so the call site
  and the flusher cannot disagree about what is worth keeping.
- The roster payload also carries `start_date`/`end_date`, which
  `ManagerCampaign` has always read off it. Without them the header said "Dates
  not set" on every personal table and `SlotEditor` validated a new slot against
  `undefined` — a test now walks the page for every `roster.*` it reads and
  fails any the endpoint does not send.

### The calendar, and checking yourself in

`GET /calendar` is every booked shoot between two dates. The campaign lists
already said who was booked on *this* brief; nothing said what next Tuesday
looks like across all of them, which is the question somebody asks before
agreeing to a date.

- **One endpoint, three scopes, one payload.** `_calendar_campaign_scope`
  builds the filter — a brand its own campaigns, a WeAre manager the ones
  assigned to them, an admin everything — and raises on anything else, so a
  role added later has to be given a scope rather than inheriting the admin's
  by omission. Filtering by a campaign outside the scope returns an **empty
  calendar, not a 403**, the same reasoning as the 404s elsewhere.
- **No entry carries a contact detail**, for any role. The roster and the
  daysheet are where a phone number lives and they are behind the staff role
  for a reason; a planning view needs a name and a time. A leak test plants
  values and searches the output.
- An exit is not a shoot: `declined` and `cancelled` keep the time they were
  booked for, and drawing them would put people on a calendar who are not
  coming.
- **The agenda is the view and the grid is the extra.** A month of
  centimetre-square cells on a 390px screen holds a number and nothing else,
  so the phone gets the grouped list and the grid appears at `md:`. Days are
  bucketed on the **local** date — `toISOString` would move an evening shoot
  to the next day for everybody in IST.

`POST /creator/check-in` is the QR path. `GET /manager/slots/{id}/check-in-code`
mints a short-lived signed code for the day-of screen; `CheckInQr` refreshes it
every 60s against a 90s life, which is the whole security property — a
photograph of the screen is stale before it can be passed around.

- **The code names the slot, never the creator.** One screen serves the whole
  queue; a per-creator code would be one QR per person, which is the problem
  this solves. So the code proves nothing about identity, and the route checks
  *this creator's own booking on that slot* — `creator_id` from the session,
  never from the code.
- Four checks, all server-side: signature and expiry, `typ == "checkin"` (every
  other token this app signs verifies with the same key, so without it an
  access token would work as a check-in code), the booking, and
  `_checkin_window_refusal` — which is what stops a screen photographed today
  being used next week.
- The refusal for "not your slot" **does not name the campaign**: a creator who
  scanned the wrong screen learns nothing about whose shoot it was.
- **Both paths go through `_check_in_collaboration` and write the same audit
  line**, differing only in `method` (`manual` / `self_qr`). Who is holding the
  clipboard depends on whether the campaign was reassigned and on whether the
  camera worked; "who was actually here" must be one question with one answer.
  The manual button is untouched and is **not a lesser path** — it is what
  works when the camera doesn't, and the failure page names it rather than
  leaving somebody tapping Retry.

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
