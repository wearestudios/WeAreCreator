# WeAre Creators — Auth Testing Playbook

Base URL: `${REACT_APP_BACKEND_URL}/api` (external). For pod-local: `http://localhost:8001/api`.

## Seeded admin
- Email: `creators@wearemonk.in`
- Password: `WeAreMonk@2026`

## MongoDB verification
```
mongosh mongodb://localhost:27017/test_database
db.users.find({role: "admin"}).pretty()
db.users.getIndexes()
```
Expect a document with `role: "admin"`, `password_hash` starting with `$2b$`, and a
unique index on `email`.

## API tests

Login as admin (external URL):
```
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
curl -c /tmp/cookies.txt -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"creators@wearemonk.in","password":"WeAreMonk@2026"}'
curl -b /tmp/cookies.txt "$API_URL/api/auth/me"
curl -b /tmp/cookies.txt "$API_URL/api/admin/ping"
```

Register a creator:
```
curl -c /tmp/c1.txt -X POST "$API_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"priya@studio.in","password":"testpass123","name":"Priya Rao","role":"creator"}'
```
Register a brand:
```
curl -c /tmp/b1.txt -X POST "$API_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"hello@toit.in","password":"testpass123","name":"Toit Brewpub","role":"brand"}'
```

Role guard: creator hitting admin route must return 403:
```
curl -b /tmp/c1.txt "$API_URL/api/admin/ping"
```

Logout:
```
curl -b /tmp/cookies.txt -X POST "$API_URL/api/auth/logout"
```
