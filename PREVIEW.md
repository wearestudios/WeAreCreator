# Previewing the site

Run the whole stack locally with Docker, sign in as one of the seeded
personas, and click through the flows below.

---

## ⚠️ Read this first — WhatsApp sign-in changed

Sign-in used to fall back to "simulation mode" whenever the AiSensy credentials
were missing: it wrote the real login code into the server log and carried on.
That is a backdoor in any environment reachable from the internet, so the server
now **refuses to issue codes** unless simulation is explicitly permitted.

If your preview environment has no AiSensy credentials, set **one** of these or
login will return `503` and look broken:

```
ALLOW_OTP_SIMULATION=true
# or
APP_ENV=development
```

With simulation on, the 6-digit code is printed in the backend log — the login
screen tells you to look there. Admin sign-in at `/admin/login` uses email and
password and is unaffected either way.

---

## Running it

Needs Docker.

```bash
cp backend/.env.example backend/.env    # then edit ADMIN_PASSWORD and JWT_SECRET
docker compose up
```

Then open **http://localhost:3000**. First run takes a few minutes while
dependencies install; after that it's quick, and both servers hot-reload as you
edit.

Without Docker, run the three pieces yourself:

```bash
# MongoDB on :27017, then…

cd backend
# requirements.txt is the runtime set; -dev.txt pulls it in and adds pytest
# and the linters. Use -dev.txt on a machine you develop on.
pip install -r requirements-dev.txt
uvicorn server:app --reload --port 8001

cd frontend
npm ci
npm start
```

### What happens on the first boot against an existing database

Two migrations run automatically. Neither deletes anything, but take a snapshot
first if the database holds data you care about.

- **A data migration.** The creator approval concept has been called three
  things. The field `vetting_status` is renamed to `verification_status`, and
  the values `"approved"` and `"vetted"` are both rewritten to `"verified"`.
  Collaborations sitting in the `vetted` state move to `verified`. This is what
  makes approved creators visible to brands. One-way, and safe to re-run.
- **An index rebuild.** The unique index on `(campaign_id, creator_id)` is
  replaced with a partial one so a declined creator can apply again. Existing
  collaborations are backfilled with `active: true`.

---

## Test accounts, before AiSensy is live

Creators, brands and campaign managers sign in by WhatsApp OTP only, so until
AiSensy is configured there is no way into any of those accounts. Seed one per
persona:

```bash
cd backend
ALLOW_OTP_SIMULATION=true python seed_personas.py
```

It prints the numbers. Sign in at `/login`, then read the code off the server
log — simulation mode logs it instead of sending it:

```bash
docker compose logs -f api | grep -i "simulation mode"
```

| Number | Who |
|---|---|
| `+919900000001` | Verified creator — can apply, book, submit |
| `+919900000002` | Half-finished profile — for the builder and the apply gate |
| `+919900000003` | Awaiting review — sits in the admin creator queue |
| `+919900000004` | Verified brand manager — can publish, invite, see applicants |
| `+919900000005` | Unverified brand — for testing the verification gate |
| `+919900000006` | WeAre campaign manager, with a campaign assigned |

Admin signs in separately at `/admin/login` with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

The script is a script and not an endpoint on purpose: a route that mints
pre-verified accounts with known numbers is a backdoor whether or not it is
guarded, and it would sit in the route table in production. It refuses to run
unless OTP simulation is permitted — which is the honest condition, because
without simulation you could not read the code and the accounts would be
unusable. **These numbers are fake and must never reach production.**

## What to click, and in what order

A fresh database seeds four demo brands, seven open briefs and eight verified
creators, so most screens have something in them immediately.

**1. Signed out — the marketing site**
Go to `/`. Home is a router: the hero, a counted proof strip, one
problem-and-promise section, and two doors. Follow either into `/for-creators`
or `/for-brands`, then `/how-it-works` and `/why-weare` from the navbar. Try a
URL that does not exist — it lands on a designed 404 rather than silently
redirecting home, which is what it used to do.

Then **`/campaigns`** for the shop window: real open briefs from verified
brands. A visitor can read them without an account.

**2. Admin — `/admin/login`**
Sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`. You'll see:
- six metric tiles including **platform revenue** and **owed by brands**, which
  the console never reported before;
- a queue strip that should read zero when there's no work waiting;
- the verification queue split into **New / Edited since approval / Never finished** —
  the last tab is people who signed up and abandoned onboarding, who used to
  clutter the review list as nameless rows;
- **Brands to verify**, which had no interface at all before;
- the collaborations board, where steps the brand owns now say *"waiting on the
  brand"* instead of offering an Advance button the API refuses;
- **Who did what** — the audit trail.

**3. Creator — `/signup?role=creator`**
Note the terms checkbox: signup is refused without it, and the acceptance is
stored against the account. Complete onboarding, including the new **Getting
paid** section (UPI + PAN). Land on the dashboard and see the amber banner
explaining you can't pitch until you're approved. Try to open a brief — the
Apply button is replaced by the reason you can't.

Approve yourself from the admin console, reload, and the brief becomes
applicable.

**4. Brand — `/signup?role=brand`**
Post a campaign, then **Save as draft**. On the dashboard the draft now has
**Publish / Edit / Delete** — before this, a saved draft could never be
published, edited or removed.

Publish it, apply as your creator account, then vet the applicant from the admin
console. Now open **Applicants** on the brand dashboard: the pitch, the rate,
the profile, and Accept / Decline. That page is the half of the marketplace that
didn't exist.

**5. The full loop**
Accept → agree the fee → book a slot (a real date and time, which the creator
now sees) → mark attended → submit content as the creator → **approve or ask for
a change** as the brand → move to payment → record the payout with a reference.

Two things to try breaking on purpose:
- Double-click **Advance** on the admin board. The second click is refused
  instead of silently skipping a stage.
- Move a creator with no UPI/PAN to payment. It's refused, rather than marking a
  payout we have no way of sending.

---

## Configuration worth knowing

Three variables have no default, and the server **refuses to start** without
them rather than failing later: `MONGO_URL`, `DB_NAME` and `JWT_SECRET`. It
prints all of the missing ones at once and exits 1, so a half-filled `.env` is
one restart to fix rather than three. `JWT_SECRET` is the reason — without the
check a deploy missing it booted happily and only broke when somebody tried to
sign in.

`ADMIN_EMAIL`, `ADMIN_PASSWORD` and `CORS_ORIGINS` warn instead of stopping the
boot; set `APP_ENV=development` on a laptop to silence them.

| Variable | Effect |
| --- | --- |
| `ALLOW_OTP_SIMULATION` | Permits log-based login codes. Required in any environment without AiSensy. |
| `PLATFORM_FEE_PERCENT` | The margin charged to brands, previously hardcoded at 15% in a frontend dialog. Default 15. |
| `ADMIN_PASSWORD_RESET` | Set true for one boot to overwrite an existing admin password. Seeding is otherwise create-only. |
| `TERMS_VERSION` | Stamped onto accounts at signup. Bump it when the terms change. |
| `AISENSY_TEMPLATE_<EVENT>` | Per-event WhatsApp template. Events without one are still recorded in-app. |
| `INSTAGRAM_APP_ID` / `_SECRET` / `_REDIRECT_URI` | Meta app for official Instagram stats. All blank = feature off, connect button clearly disabled, counts stay self-reported. |
| `INSTAGRAM_TOKEN_KEY` | Fernet key encrypting access tokens at rest. Absent = feature stays off rather than storing tokens in the clear. |
| `INSTAGRAM_STATS_TTL_HOURS` | How long a cached reading counts as current. Default 12; never fetched on page load. |
| `PROFILE_NUDGE_AFTER_DAYS` | How long before an unfinished creator profile gets its one WhatsApp chase. Default 3. |
| `PRIVATE_UPLOAD_DIR` | Where brand verification documents land. Must not be `UPLOAD_DIR`, which is served as static files; these are reachable only through the audited admin route. Default `backend/private_uploads`. |
| `REACT_APP_GOOGLE_MAPS_API_KEY` (frontend) | Places autocomplete and the draggable map pin on the creator address field. Blank = the field is a plain textarea and everything still works; no pin is collected. Restrict the key by HTTP referrer in the Google Cloud console to your deployed origins, and to Maps JavaScript API + Places API + Static Maps API. |
| `REACT_APP_STUDIO_URL` (frontend) | Parent-studio link behind the "A WeAre Studios offering" endorsement in the nav and home footer. Blank renders the line as plain text rather than a dead link. |

Full list with comments: `backend/.env.example`.

### The three server-rendered pages, and the deploy step they need

> **This is a pending decision, not a finished setup.** Three paths in
> `frontend/vercel.json` currently point at `/index.html`, which is exactly
> what the catch-all below them already does — so today they are inert
> placeholders and those pages open the React app instead. The entries are
> there to be *repointed*, and this section is the record of why they exist.
> (They used to carry `"//"` keys explaining themselves inline; Vercel rejects
> unknown properties on a rewrite object, so the notes live here instead.)

Three pages are **server-rendered by the backend**, not by the React app, and
that is not a style choice: the crawlers that build a WhatsApp, Instagram or
Slack preview do not run JavaScript, so Open Graph tags the SPA sets at runtime
are tags nobody ever sees. The page a person opens and the page a crawler
scrapes are the same one, so the preview cannot promise something the link does
not show.

| Path | What it is |
| --- | --- |
| `/c/:id` | A live brief from a verified brand. What the Share button copies. |
| `/brands/:id` | The brand's own public page, linked from every campaign card and every shared brief. |
| `/sitemap.xml` | Every marketing page, public brand page and live brief, so a crawler has something to follow. `robots.txt` names it, so both have to resolve to the same host. |

It was five until the marketing site moved into the SPA. `/for-brands` and
`/for-creators` are ordinary React routes now — see below.

Repoint all three at your Railway URL; they must stay **above** the catch-all:

```json
{ "source": "/c/:id",       "destination": "https://your-api.up.railway.app/c/:id" },
{ "source": "/brands/:id",  "destination": "https://your-api.up.railway.app/brands/:id" },
{ "source": "/sitemap.xml", "destination": "https://your-api.up.railway.app/sitemap.xml" }
```

**All three or none.** They are one feature, and shipping part of it means a
link into a page that does not exist: the brief page links to the brand page,
the brand page lists the briefs, and the sitemap points at both.

The alternative, if you would rather not proxy: set `PUBLIC_SHARE_BASE_URL` to
the backend's own origin and links will point straight at it. That works
immediately but the URL is the API host, which is uglier to read out.

Until one of the two is done, a shared link opens the React app and previews as
the generic site card.

`frontend/src/setupProxy.js` is the same three paths for the dev server, so
`docker compose up` behaves like the deployed site. It does not exist in a
production build, so it cannot mask a missing rewrite.

### The marketing site, and the preview it gave up

Five pages — `/`, `/for-brands`, `/for-creators`, `/how-it-works`,
`/why-weare` — plus a designed 404. **All of them are React routes.**

Two of them used to be server-rendered HTML written by hand in `server.py`, for
the preview reason above. That had three costs, and they were the reason for
moving:

- a page the backend renders cannot be reached with a `<Link>`, so
  `/how-it-works` and `/why-weare` could not exist alongside them at all;
- the rewrites that would have pointed at them were never repointed, so in
  production both answered with the SPA's catch-all — the nav and footer links
  went nowhere;
- the copy existed only there, so the site's own pages could not reuse a word
  of it.

**What that traded away:** WhatsApp and other non-JS crawlers now read the
static tags in `public/index.html` rather than each page's own, so a marketing
link pasted into a chat previews with the site-wide card.
`frontend/src/components/marketing/PageMeta.jsx` says so at the top of the
file. To buy it back without moving the pages again, point the rewrites at a
prerender service, or add a Vercel `has` condition matching crawler
user-agents. `/c/:id` and `/brands/:id` stay server-rendered because there the
shared link *is* the preview, and the trade would not be worth making.

**Image slots.** Every marketing page has deliberate placements — hero,
alternating text-and-image sections, proof areas — and none of them fetches
anything. Each is a `PlaceholderImage`: a tint from the warm palette with the
site's grain over it, in a container that already occupies the space the
photograph will. Each carries a `PLACEHOLDER IMAGE:` comment saying what
belongs there, and `data-placeholder` on the element. Dropping a real image in
is one prop (`src`) and the layout does not move, so the photography can arrive
one slot at a time.

### Deploying the frontend to Vercel

`frontend/vercel.json` rewrites everything to `/index.html` so react-router
handles the URL. Vercel checks the filesystem before rewrites, so the hashed
bundles under `/static/` are still served as files — only paths with no file
behind them fall through to the app.

The rule excludes `/api/`. `API_BASE` is `` `${REACT_APP_BACKEND_URL}/api` ``,
so an unset or empty `REACT_APP_BACKEND_URL` makes the app call same-origin
`/api` — and a blanket catch-all would answer those with the HTML shell, which
surfaces as every request failing to parse rather than as the misconfiguration
it is. Excluded, they 404 honestly. Set `REACT_APP_BACKEND_URL` to the Railway
URL and the calls are absolute anyway.

---

## Still outstanding

- **`/terms` and `/privacy` are placeholders.** They describe what the product
  actually does with data, and say so, but they are not legal text. Replace
  them and bump `TERMS_VERSION`.
- **The admin password in git history.** It's out of `auth_testing.md`, but the
  old value is still in earlier commits. Treat it as compromised and rotate it.
- **No escrow.** The landing page no longer claims funds are held — closing that
  gap needs a payment gateway and a merchant account.
- **The integration suite hasn't been run** against a live server since it was
  updated; it needs a running backend and MongoDB. `cd backend && pytest tests/`
  once you have the stack up. The unit suite (`pytest tests/unit`) runs anywhere
  and is green.
