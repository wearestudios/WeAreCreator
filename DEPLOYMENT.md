# Deploying WeAre Creators

Every environment variable the app reads, which of them the process refuses to
start without, and what a safe production value looks like.

`backend/.env.example` is the machine-checked list — `tests/unit/test_environment.py`
AST-walks the backend for `os.environ` reads and fails if one is undocumented,
in both directions. **This file is the operator's version of that list**: what
to set, what happens if you don't, and what goes wrong if you get it wrong.
When the two disagree, `.env.example` is the one the tests hold.

---

## The short version

```bash
# 1. Refuses to start without these four groups.
MONGO_URL=...  DB_NAME=...  JWT_SECRET=...            # database and sessions
S3_BUCKET=...  S3_REGION=...                          # file storage
S3_ACCESS_KEY_ID=...  S3_SECRET_ACCESS_KEY=...

# 2. Starts without these and something breaks later, loudly in the log.
ADMIN_EMAIL=...  ADMIN_PASSWORD=...  CORS_ORIGINS=...

# 3. Set this, or the app assumes production. That assumption is deliberate.
APP_ENV=production
```

Everything else has a default that is safe to deploy with.

---

## Two startup checks, and what each one catches

Both run at import, before the first request, and both name **everything**
missing at once — one boot and one list, rather than fixing them one restart at
a time.

### `validate_environment()` — the database and the cookie

Refuses to start without `MONGO_URL`, `DB_NAME` or `JWT_SECRET`. A blank string
counts as missing, because `JWT_SECRET=` in a half-filled `.env` is an empty
value rather than an absent key, and that is the shape a copied example
actually takes.

`JWT_SECRET` is why this check exists. The other two were read at import, so a
missing one crashed the boot — unhelpfully, but loudly. `JWT_SECRET` was read
per call, so a deploy without it **started cleanly, served the marketing page,
and 500'd the first person who tried to sign in.**

### `_refuse_ephemeral_storage()` — the uploads

Refuses to start on a production box that would write uploads to local disk.
This host's filesystem is ephemeral, so local storage in production is a
guarantee that the next redeploy destroys every verification document, profile
photo, campaign cover and unpublished draft — leaving the database rows
pointing at nothing, which is the worst shape of the failure. A brand reads
"GST certificate uploaded" and an admin opens a 410.

It is a refusal rather than a warning because a warning in a deploy log is a
line nobody reads until they are already looking for the cause.

**`APP_ENV` unset counts as production**, the same reading `_is_production()`
and `_simulation_allowed()` take everywhere else here. Guessing the other way
is exactly how a real deployment ends up silently writing to a disk that is
about to disappear.

---

## Required — the process will not start

| Variable | What it is | Safe production value |
| --- | --- | --- |
| `MONGO_URL` | MongoDB connection string | A managed cluster URI with credentials. Not a local `mongodb://localhost`. |
| `DB_NAME` | Database name | `wearecreators`. **Check this twice** — a typo here points a live deploy at an empty database that then fills up with real data. |
| `JWT_SECRET` | Signs the auth cookies | 32+ random bytes, e.g. `openssl rand -base64 48`. Rotating it signs everybody out; that is the intended way to do it. |

### File storage — also required, in production

| Variable | What it is | Safe production value |
| --- | --- | --- |
| `S3_BUCKET` | Where uploads go | A bucket **not** shared with anything else. |
| `S3_REGION` | Its region | `ap-south-1` for a Bengaluru-first operation. |
| `S3_ACCESS_KEY_ID` | Access key | A key scoped to this bucket and nothing else. |
| `S3_SECRET_ACCESS_KEY` | Its secret | — |
| `S3_ENDPOINT_URL` | For anything that is not AWS | R2: `https://<account>.r2.cloudflarestorage.com`. Spaces: `https://blr1.digitaloceanspaces.com`. Blank for AWS. |
| `S3_PUBLIC_BASE_URL` | A CDN in front of the public prefix | Worth setting: covers and profile photos are on every card of every list. |
| `S3_SIGNED_URL_TTL_SECONDS` | Life of a signed link to a private object | `120`. Clamped to 30–3600. |
| `STORAGE_BACKEND` | `s3` or `local` | Leave blank — it reads as `s3` when `S3_BUCKET` is set. |
| `UPLOAD_DIR`, `PRIVATE_UPLOAD_DIR` | Local directories | Only used by `STORAGE_BACKEND=local`. Leave blank. |
| `MAX_UPLOAD_MB` | Per-file ceiling, both backends | `5`. Clamped to 0.1–25. |

**`STORAGE_BACKEND=local` overrides the refusal.** It is right on a laptop and
right if the disk really is a mounted volume; it is never right on an ephemeral
container. It logs a warning every boot in production so it cannot be forgotten.

#### The bucket policy is half the security model

The bucket holds two prefixes and they are not the same kind of thing:

- **`public/`** — campaign covers, brand logos, creator profile photos. These
  have to render in a WhatsApp preview, where there is no session to
  authenticate with. Readable, cached hard, and that is by design.
- **`private/`** — brand verification documents, unpublished drafts, story
  proofs. A GST certificate carries a registered address and a director's
  name; a story screenshot routinely catches a viewer list or a DM
  notification. **Nothing here may be readable without a signature.**

Block public access at the bucket, then allow the public prefix back:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicPrefixOnly",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::YOUR-BUCKET/public/*"
    }
  ]
}
```

with **Block Public Access** left on for everything else. If your host does not
offer a per-prefix policy, use two buckets and point `S3_PUBLIC_BASE_URL` at the
public one — the private prefix being unreadable is the property that matters,
not how you achieve it.

Verify it before trusting it:

```bash
# Must be 403 or 404. A 200 here means every uploaded GST certificate is public.
curl -sI "https://YOUR-BUCKET.s3.ap-south-1.amazonaws.com/private/anything.pdf" | head -1
```

#### CORS, if you serve private files cross-origin

A private file is delivered as a 307 to a signed URL, so the browser fetches the
object from the bucket rather than from the API. The console fetches it as an
authenticated blob, so the bucket needs to allow that origin:

```json
[{
  "AllowedOrigins": ["https://your-frontend-domain"],
  "AllowedMethods": ["GET"],
  "AllowedHeaders": ["*"],
  "MaxAgeSeconds": 300
}]
```

Symptom if you skip it: documents and drafts fail to open in the browser with a
CORS error, while `curl` against the same signed URL works.

#### Moving the files you already have

**Before pointing production at S3, not after.** A box that starts on S3 with an
empty bucket serves 404s for every document and cover that already exists.

```bash
cd backend
python migrate_uploads_to_s3.py            # dry run: reports, touches nothing
python migrate_uploads_to_s3.py --apply
```

It rewrites no database rows, because there is nothing to rewrite — a stored
name is still a stored name and a public URL is still `/uploads/<name>`; only
where the bytes sit changed. It is idempotent, so an interrupted run is resumed
by running it again, and it deletes nothing from disk. Remove the local
directories by hand once you have checked the bucket.

---

## Warned about, not refused

Each has a default that lets the process run, and each silently breaks
something a person notices long after boot. They log a warning when `APP_ENV`
reads as production.

| Variable | What breaks without it |
| --- | --- |
| `ADMIN_EMAIL` | No admin account is seeded, so nobody can sign in at `/admin`. |
| `ADMIN_PASSWORD` | Same. Use a password manager; this is the account that can impersonate. |
| `CORS_ORIGINS` | The browser blocks every call from the frontend. Comma-separated exact origins, e.g. `https://wearecreators.in,https://www.wearecreators.in`. **Never `*`** — the session cookie is `SameSite=None`, so a wildcard origin is a wildcard on somebody's session. |

`ADMIN_NAME` is cosmetic. `ADMIN_PASSWORD_RESET=true` resets the seeded admin's
password on the next boot — set it once, then remove it, or every restart
rewrites the password.

---

## The OTP front door

Creators and brands sign in with a WhatsApp code; staff sign in with email and
password.

| Variable | Production value |
| --- | --- |
| `AISENSY_API_KEY` | Required to send a real code. Without it, nobody outside staff can sign in. |
| `AISENSY_CAMPAIGN_NAME` | The AiSensy campaign the OTP template sits in. |
| `ALLOW_OTP_SIMULATION` | **Leave unset.** |
| `OTP_TEST_CODE` | **Leave unset.** |
| `OTP_TTL_SECONDS`, `OTP_RESEND_COOLDOWN_SECONDS`, `OTP_HOURLY_LIMIT`, `OTP_MAX_ATTEMPTS` | Defaults are fine. |

### `ALLOW_OTP_SIMULATION` and `OTP_TEST_CODE` in production

Both are **refused when `APP_ENV` reads as production**, and that refusal does
not depend on getting anything else right.

`OTP_TEST_CODE` issues one fixed six-digit code for every request, so testing
signup on staging does not mean reading a code out of a deploy log each time.
It is a login bypass for anyone who knows a phone number, so it is fenced on
four sides and **all four must be open**:

1. the value is six digits;
2. `APP_ENV`/`ENV` is not `production` / `prod` / `live`;
3. no AiSensy credential is set;
4. `_simulation_allowed()`.

**The production check (2) is independent of (4)**, and that independence is the
point: `_simulation_allowed()` returns true for `ALLOW_OTP_SIMULATION=true`
whatever `APP_ENV` says, so leaning on it alone would let
`APP_ENV=production ALLOW_OTP_SIMULATION=true` hand out a fixed code to anyone
who asked. `tests/unit/test_fixed_test_otp.py::test_production_refuses_it_even_with_simulation_forced_on`
pins exactly that combination; the surrounding cases pin `prod`, `live`, mixed
case, whitespace, and the `ENV` alias.

Refusal is logged as an error, use is logged as a warning on *every* code, and
`warn_about_fixed_test_otp()` announces the state at the top of the boot log —
above the index maintenance, because the failure this guards against is a
staging setting riding quietly into production.

**Check the boot log on every deploy.** If you see

```
FIXED TEST OTP in use — never enable in production
```

on a production box, that box is handing out a fixed login code right now.

---

## Everything else

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_ENV` | *(unset reads as production)* | `production` on a deployed box. `development` / `local` / `test` elsewhere. |
| `ENV` | — | Fallback for hosts that set that name. `APP_ENV` wins where both are present. |
| `PUBLIC_SHARE_BASE_URL` | The frontend's origin | The origin shared `/c/{id}` links are built from. |
| `PLATFORM_FEE_PERCENT` | `15` | The floor only — a campaign's rate beats a brand's, and a brand's beats this. |
| `TERMS_VERSION` | — | Stamped onto each account at signup. Bump when the terms change. |
| `INSTAGRAM_APP_ID` | — | Absent is a supported state: the connect routes 503 with an explanation and follower counts stay self-reported. Never make anything else depend on it being on. |
| `INSTAGRAM_APP_SECRET` | — | Pairs with the app id. |
| `INSTAGRAM_REDIRECT_URI` | — | Must match the value registered on the Meta app exactly, including the scheme and any trailing slash. |
| `INSTAGRAM_TOKEN_KEY` | — | Fernet key encrypting stored tokens. **Rotating it orphans every stored token** and every creator has to reconnect. |
| `INSTAGRAM_STATS_TTL_HOURS` | `12` | The ceiling is 200 calls per user per hour and a reading costs three. |
| `INSTAGRAM_JOB_INTERVAL_SECONDS` | | `0` disables. |
| `PROFILE_NUDGE_AFTER_DAYS` | | How long a half-finished profile sits before its one nudge. |
| `PROFILE_NUDGE_INTERVAL_SECONDS` | | How often the job looks. `0` disables. |
| `LIFECYCLE_INTERVAL_SECONDS` | | The chasers. `0` disables; `POST /admin/jobs/lifecycle` runs one pass by hand. |
| `LEADERBOARD_REFRESH_INTERVAL_SECONDS` | daily | `0` disables. The homepage never computes it. |

### Frontend (build-time, baked into the bundle)

CRA inlines these at build time, so **anything here is public.** Changing one
means rebuilding.

| Variable | Notes |
| --- | --- |
| `REACT_APP_BACKEND_URL` | The API origin. Required. |
| `REACT_APP_SHARE_BASE_URL` | Origin for share links. |
| `REACT_APP_GOOGLE_MAPS_API_KEY` | A **browser** key — it is visible in the bundle by design. Referrer restrictions in the Google console are the actual protection. Absent is supported: the map is a plain textarea and no script is injected. |
| `REACT_APP_STUDIO_NAME`, `REACT_APP_STUDIO_URL` | The studio endorsement in the footer. |

---

## The Vercel rewrites

Five paths are server-rendered by the backend and **must** be proxied, or they
answer with the SPA's catch-all and preview as the generic site card:

`/c/*` · `/brands/:id` · `/work` · `/work/:slug` · `/sitemap.xml`

`PREVIEW.md` is the record and a test fails if the two lists drift. This was a
silent failure on `/for-brands` for months, which is why it is a test and not a
paragraph.

---

## Before you call it deployed

```bash
# The boot log names everything missing. Read it.
#   "Refusing to start: required environment variables are missing."
#   "Refusing to start: file storage is not configured."
#   "FIXED TEST OTP in use"        <- must NOT appear
#   "file storage: s3 (durable=True)"

# The private prefix is not public. Must be 403 or 404.
curl -sI "https://YOUR-BUCKET.s3.REGION.amazonaws.com/private/x.pdf" | head -1

# A cover renders, end to end.
#   post a campaign with a cover, then open /c/<id> and check og:image resolves

# A document round-trips.
#   upload a verification document as a brand, open it as an admin

# The five rewrites actually reach the backend.
curl -s https://your-domain/sitemap.xml | head -3
```

- [ ] `APP_ENV=production` is set explicitly, not left to the default
- [ ] `CORS_ORIGINS` names exact origins, no `*`
- [ ] `JWT_SECRET` is not the one from `.env.example`
- [ ] `ALLOW_OTP_SIMULATION` and `OTP_TEST_CODE` are unset
- [ ] `ADMIN_PASSWORD_RESET` is unset after the first boot
- [ ] Block Public Access is on, with `public/` allowed back
- [ ] `migrate_uploads_to_s3.py --apply` has run, if there were existing files
- [ ] The boot log says `file storage: s3 (durable=True)`
