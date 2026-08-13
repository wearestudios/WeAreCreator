# WeAre Creators — Auth Testing Playbook

Base URL: `${REACT_APP_BACKEND_URL}/api` (external). For pod-local: `http://localhost:8001/api`.

## Admin account

The admin is seeded on first boot from the environment:

| Variable | Purpose |
| --- | --- |
| `ADMIN_EMAIL` | Admin login email |
| `ADMIN_PASSWORD` | Password, used **only** when the account does not yet exist |
| `ADMIN_NAME` | Display name |
| `ADMIN_PASSWORD_RESET` | Set to `true` for one boot to overwrite an existing password |

Seeding is create-only. If the account already exists, the stored password wins
and the environment value is ignored — a password rotated in the product is not
silently reverted on the next deploy, and a leaked environment variable is not a
permanent backdoor. To reset a forgotten password, set `ADMIN_PASSWORD` to the
new value plus `ADMIN_PASSWORD_RESET=true`, boot once, then remove the reset flag.

> Never commit real credentials to this file. Read them from the deployment's
> environment. The previously documented password has been rotated and must not
> be reused.

```bash
# Read the admin credentials from your environment, never from source control.
: "${ADMIN_EMAIL:?set ADMIN_EMAIL}"
: "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}"
```

## WhatsApp OTP configuration

| Variable | Purpose |
| --- | --- |
| `AISENSY_API_KEY` | AiSensy API key |
| `AISENSY_CAMPAIGN_NAME` | Template used to deliver the login code |
| `ALLOW_OTP_SIMULATION` | `true` permits simulation mode (codes written to the log) |
| `APP_ENV` | `development` / `local` / `test` also permits simulation |

Without AiSensy credentials the server **refuses to issue codes** unless
simulation is explicitly permitted. Simulation writes live login codes to the
server log, so it must never be reachable in production.

Notification templates are configured per event as
`AISENSY_TEMPLATE_<EVENT>` — for example `AISENSY_TEMPLATE_SLOT_BOOKED`. Events
without a configured template are still recorded and visible in-app; they just
aren't pushed to WhatsApp. The full list is in `NOTIFY_EVENTS` in `server.py`.

## MongoDB verification

```
mongosh mongodb://localhost:27017/test_database
db.users.find({role: "admin"}).pretty()
db.users.getIndexes()
db.creator_profiles.find({verification_status: "verified"}).count()
db.collaborations.getIndexes()   # expect the partial "one_live_application" index
db.audit_log.find().sort({created_at: -1}).limit(5).pretty()
```

Expect an admin document with `role: "admin"`, a `password_hash` starting with
`$2b$`, and partial-unique indexes on `email` and `phone`.

There should be **no** creator profile left with `verification_status` of `"approved"` or `"vetted"` —
startup migrates any such rows to `verified`.

## API tests

Login as admin (external URL):
```
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
curl -c /tmp/cookies.txt -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
curl -b /tmp/cookies.txt "$API_URL/api/auth/me"
curl -b /tmp/cookies.txt "$API_URL/api/admin/ping"
```

Register a creator (note `accept_terms` — registration is refused without it):
```
curl -c /tmp/c1.txt -X POST "$API_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"priya@studio.in","password":"testpass123","name":"Priya Rao","role":"creator","accept_terms":true}'
```
Register a brand:
```
curl -c /tmp/b1.txt -X POST "$API_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"hello@toit.in","password":"testpass123","name":"Toit Brewpub","role":"brand","accept_terms":true}'
```

Role guard: creator hitting admin route must return 403:
```
curl -b /tmp/c1.txt "$API_URL/api/admin/ping"
```

Unauthenticated preview must work without a session:
```
curl "$API_URL/api/public/campaigns"
curl "$API_URL/api/public/stats"
```

Logout:
```
curl -b /tmp/cookies.txt -X POST "$API_URL/api/auth/logout"
```

## Process guardrails worth re-checking after any change

| Check | Expected |
| --- | --- |
| Unverified creator applies to a campaign | `403` — verification gates applying |
| Creator applies twice to one campaign | `409` |
| Creator re-applies after being declined | allowed |
| Advance a collaboration with a stale `from_state` | `409`, no state change |
| Advance to `in_payment` without creator payout details | `422` |
| Mark the same payment paid twice | `409` |
| Brand reads another brand's campaign | `404` |
| Campaign past its `end_date` | drops off the creator feed |
