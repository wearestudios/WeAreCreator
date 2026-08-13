"""Backend tests for creator's POST /api/creator/collaborations/{id}/submit_content."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _rand_email(role):
    return f"test_{role}-{uuid.uuid4().hex[:10]}@example.com"


def _register(session, role):
    email = _rand_email(role)
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!",
        "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def admin():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture
def creator():
    s = requests.Session()
    email, _ = _register(s, "creator")
    return s, email


@pytest.fixture
def brand():
    s = requests.Session()
    email, _ = _register(s, "brand")
    return s, email


def _complete_creator(s):
    suf = uuid.uuid4().hex[:6]
    me = s.get(f"{BASE_URL}/auth/me").json()
    r = s.put(f"{BASE_URL}/creator/profile", json={
        "name": f"Creator {suf}",
        "instagram_handle": f"@c_{suf}",
        "instagram_profile_url": f"https://instagram.com/c_{suf}",
        "email": me.get("email"),
        "address": "Bengaluru",
        "niches": ["cafe"],
        "follower_count": 12000,
        "base_rate": 5000,
    })
    assert r.status_code == 200, r.text


def _seed_open_campaign(bs):
    bs.put(f"{BASE_URL}/brand/profile", json={
        "business_name": f"Br-{uuid.uuid4().hex[:5]}",
        "category": "fnb", "areas": ["Indiranagar"],
    })
    body = {
        "title": f"Camp-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
        "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
        "creators_needed": 3,
        "start_date": "2026-02-01T00:00:00Z", "end_date": "2026-03-01T00:00:00Z",
        "status": "open",
    }
    r = bs.post(f"{BASE_URL}/brand/campaigns", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _advance_to(admin_s, collab_id, target_state):
    """Advance a collab from applied all the way to target_state."""
    # order: applied->vetted->accepted->commercial_agreed(amt)->slot_booked->attended->content_submitted->in_payment(fee)->closed
    steps = [
        ("vetted", {}),
        ("accepted", {}),
        ("commercial_agreed", {"agreed_amount": 8500}),
        ("slot_booked", {}),
        ("attended", {}),
        ("content_submitted", {}),
        ("in_payment", {"platform_fee": 1500}),
        ("closed", {}),
    ]
    for state, body in steps:
        r = admin_s.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance", json=body
        )
        assert r.status_code == 200, f"failed to advance to {state}: {r.text}"
        if state == target_state:
            return
    raise AssertionError(f"unreachable state {target_state}")


def _make_collab_in_state(admin_s, brand_tuple, creator_tuple, target_state):
    """Register+complete creator, seed campaign, apply, advance admin-side to target_state."""
    bs, _ = brand_tuple
    cs, cemail = creator_tuple
    _complete_creator(cs)
    cid = _seed_open_campaign(bs)
    ar = cs.post(f"{BASE_URL}/campaigns/{cid}/apply", json={
        "pitch": "eager to collaborate with you all", "quoted_rate": 5500,
    })
    assert ar.status_code in (200, 201), ar.text
    rows = admin_s.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["applied"]
    collab_id = next(x["id"] for x in rows if x["creator"]["email"] == cemail)
    if target_state != "applied":
        _advance_to(admin_s, collab_id, target_state)
    return collab_id, cemail


# ---------- Auth guards ----------

class TestSubmitContentAuth:
    def test_anonymous_401(self):
        r = requests.post(
            f"{BASE_URL}/creator/collaborations/507f1f77bcf86cd799439011/submit_content",
            json={"content_url": "https://instagram.com/p/xyz"},
        )
        assert r.status_code == 401

    def test_brand_403(self, brand):
        bs, _ = brand
        r = bs.post(
            f"{BASE_URL}/creator/collaborations/507f1f77bcf86cd799439011/submit_content",
            json={"content_url": "https://instagram.com/p/xyz"},
        )
        assert r.status_code == 403

    def test_admin_403(self, admin):
        # Admin is not creator role => should be 403 by require_roles('creator')
        r = admin.post(
            f"{BASE_URL}/creator/collaborations/507f1f77bcf86cd799439011/submit_content",
            json={"content_url": "https://instagram.com/p/xyz"},
        )
        assert r.status_code == 403


# ---------- Validation ----------

class TestSubmitContentValidation:
    def test_invalid_url_scheme_422(self, admin, brand, creator):
        collab_id, _ = _make_collab_in_state(admin, brand, creator, "attended")
        cs, _ = creator
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/submit_content",
            json={"content_url": "foo.bar/xyz1234"},
        )
        assert r.status_code == 422, r.text
        assert "http://" in r.text and "https://" in r.text

    def test_not_attended_state_400(self, admin, brand, creator):
        # state='applied' should reject with 400
        collab_id, _ = _make_collab_in_state(admin, brand, creator, "applied")
        cs, _ = creator
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/submit_content",
            json={"content_url": "https://instagram.com/p/abc"},
        )
        assert r.status_code == 400, r.text
        assert "attended" in r.text.lower()

    def test_not_owner_404(self, admin, brand, creator):
        # Another creator tries to submit on someone else's collab
        collab_id, _ = _make_collab_in_state(admin, brand, creator, "attended")
        # Second creator session
        other = requests.Session()
        _register(other, "creator")
        r = other.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/submit_content",
            json={"content_url": "https://instagram.com/p/xyz"},
        )
        assert r.status_code == 404

    def test_invalid_object_id_404(self, creator):
        cs, _ = creator
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/not-a-real-id/submit_content",
            json={"content_url": "https://instagram.com/p/xyz"},
        )
        assert r.status_code == 404


# ---------- Happy path ----------

class TestSubmitContentHappyPath:
    def test_happy_path_and_persistence(self, admin, brand, creator):
        collab_id, cemail = _make_collab_in_state(admin, brand, creator, "attended")
        cs, _ = creator
        url = "https://instagram.com/p/happy_abc123"
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/submit_content",
            json={"content_url": url},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == collab_id
        assert body["state"] == "content_submitted"
        assert body["content_url"] == url

        # Verify via admin GET: appears in content_submitted group
        data = admin.get(f"{BASE_URL}/admin/collaborations").json()
        found = next(
            (x for x in data["by_state"]["content_submitted"] if x["id"] == collab_id),
            None,
        )
        assert found is not None, "collab not in content_submitted group after submission"
        assert found["state"] == "content_submitted"

        # Regression: creator dashboard applications rows include content_url
        dash = cs.get(f"{BASE_URL}/creator/dashboard").json()
        apps = dash.get("applications") or []
        row = next((x for x in apps if x.get("id") == collab_id), None)
        assert row is not None, f"application row for {collab_id} not found in dashboard"
        assert "content_url" in row, "content_url field missing from creator dashboard row"
        assert row["content_url"] == url

        # Cannot re-submit (state != attended now)
        r2 = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/submit_content",
            json={"content_url": "https://instagram.com/p/other"},
        )
        assert r2.status_code == 400
