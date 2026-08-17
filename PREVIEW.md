# Previewing the site

Two ways: pull the branch into Emergent (fastest, the database and environment
already exist there), or run the whole stack locally.

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

## Option 1 — Preview on Emergent

Emergent doesn't take a push from here; it pulls from GitHub. The branch is
already on GitHub, so:

1. Open the project in Emergent.
2. Click the **GitHub** icon → select `wearestudios/WeAreCreator`.
3. Choose the branch **`claude/site-process-review-3f21az`** → **Import**.
4. Set `ALLOW_OTP_SIMULATION=true` in the environment (see the warning above).
5. Use the interactive preview to click through the app.

If the branch isn't offered, merge it into `main` first and import that instead.

Two things happen automatically on the first boot after importing:

- **A data migration.** The creator approval concept has been called three things.
  The field `vetting_status` is renamed to `verification_status`, and the values
  `"approved"` and `"vetted"` are both rewritten to `"verified"`. Collaborations
  sitting in the `vetted` state move to `verified`. This is what makes approved
  creators visible to brands. One-way, and safe to re-run.
- **An index rebuild.** The unique index on `(campaign_id, creator_id)` is
  replaced with a partial one so a declined creator can apply again. Existing
  collaborations are backfilled with `active: true`.

Neither deletes anything. Take a snapshot first if the preview database holds
data you care about.

---

## Option 2 — Run it locally

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
npm install --legacy-peer-deps
npm start
```

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

**1. Signed out — the shop window**
Go to `/`. Scroll to **"Briefs live on the platform today"**. Those are real
open campaigns from verified brands, pulled from `/api/public/campaigns`. This
is new: previously a visitor couldn't see a single brief without an account.

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
| `REACT_APP_STUDIO_URL` (frontend) | Parent-studio link behind the "A WeAre Studios offering" endorsement in the nav and home footer. Blank renders the line as plain text rather than a dead link. |

Full list with comments: `backend/.env.example`.

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
