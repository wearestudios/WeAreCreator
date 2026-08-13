"""Backend tests for /api/admin/* — vetting, collaborations, payments, metrics."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _rand_email(role):
    # Server lower-cases emails on register.
    return f"test_{role}-{uuid.uuid4().hex[:10]}@example.com"


def _register(session, role):
    email = _rand_email(role)
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
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
def anon():
    return requests.Session()


@pytest.fixture
def creator():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, user.get("id") or user.get("user_id") or user.get("_id"), email


@pytest.fixture
def brand():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email


def _complete_creator(s, handle_suffix=None):
    suf = handle_suffix or uuid.uuid4().hex[:6]
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
    return r.json()


# ---------- 1. Auth guards ----------
ADMIN_ENDPOINTS = [
    ("GET", "/admin/creators/pending"),
    ("GET", "/admin/collaborations"),
    ("GET", "/admin/metrics"),
]


class TestAdminAuth:
    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_anonymous_401(self, anon, method, path):
        r = anon.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 401, f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_creator_403(self, creator, method, path):
        s, _, _ = creator
        r = s.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 403, f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_brand_403(self, brand, method, path):
        s, _ = brand
        r = s.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 403, f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_admin_200(self, admin, method, path):
        r = admin.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}"


# ---------- 2. Pending creators list ----------

class TestPendingCreators:
    def test_pending_list_shape_and_filter(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        # This creator (pending) should be listed
        r = admin.get(f"{BASE_URL}/admin/creators/pending")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        row = next((x for x in rows if x.get("email") == email), None)
        assert row is not None, f"pending creator {email} not found"
        for field in ["user_id", "name", "email", "instagram_handle",
                      "instagram_profile_url", "niches", "follower_count",
                      "base_rate", "address"]:
            assert field in row, f"missing field {field}"
        assert row.get("vetting_status") == "pending"

    def test_rejected_and_vetted_not_in_pending(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        # find uid
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        row = next(x for x in rows if x["email"] == email)
        uid = row["user_id"]
        # approve
        r = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r.status_code == 200
        rows2 = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        assert not any(x["email"] == email for x in rows2)


# ---------- 3. Approve / Reject ----------

class TestApproveReject:
    def test_approve_sets_vetted_and_active_and_is_idempotent(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        uid = next(x["user_id"] for x in rows if x["email"] == email)

        r1 = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r1.status_code == 200
        assert r1.json()["vetting_status"] == "vetted"

        # /auth/me from creator session should now show status=active
        me = s.get(f"{BASE_URL}/auth/me")
        assert me.status_code == 200
        assert me.json().get("status") == "active"

        # Second call idempotent
        r2 = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r2.status_code == 200
        assert r2.json()["vetting_status"] == "vetted"

    def test_reject_sets_rejected(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        uid = next(x["user_id"] for x in rows if x["email"] == email)
        r = admin.post(f"{BASE_URL}/admin/creators/{uid}/reject")
        assert r.status_code == 200
        assert r.json()["vetting_status"] == "rejected"

    def test_approve_nonexistent_404(self, admin):
        # valid-looking ObjectId that shouldn't exist
        r = admin.post(f"{BASE_URL}/admin/creators/507f1f77bcf86cd799439011/approve")
        assert r.status_code == 404


# ---------- 4. Collaborations list ----------

def _seed_open_campaign(brand_session):
    brand_session.put(f"{BASE_URL}/brand/profile", json={
        "business_name": f"Br-{uuid.uuid4().hex[:5]}", "category": "fnb",
        "areas": ["Indiranagar"],
    })
    body = {
        "title": f"Camp-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
        "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
        "creators_needed": 3,
        "start_date": "2026-02-01T00:00:00Z", "end_date": "2026-03-01T00:00:00Z",
        "status": "open",
    }
    r = brand_session.post(f"{BASE_URL}/brand/campaigns", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"], body["title"]


class TestCollabList:
    def test_list_shape(self, admin, brand, creator):
        bs, _ = brand
        cs, _, cemail = creator
        _complete_creator(cs)
        cid, _ = _seed_open_campaign(bs)
        ar = cs.post(f"{BASE_URL}/campaigns/{cid}/apply", json={
            "pitch": "hi there really keen", "quoted_rate": 5500,
        })
        assert ar.status_code in (200, 201), ar.text

        r = admin.get(f"{BASE_URL}/admin/collaborations")
        assert r.status_code == 200
        data = r.json()
        assert "by_state" in data and "total" in data
        for st in ["applied","vetted","accepted","commercial_agreed","slot_booked",
                   "attended","content_submitted","in_payment","closed"]:
            assert st in data["by_state"]
        applied = data["by_state"]["applied"]
        row = next((x for x in applied if x["creator"]["email"] == cemail), None)
        assert row is not None
        assert row["quoted_rate"] == 5500
        assert row["next_state"] == "vetted"
        for k in ["id", "state", "campaign", "brand_name", "creator", "payment"]:
            assert k in row
        assert row["campaign"]["title"]


# ---------- 5. State machine end-to-end ----------

class TestStateMachine:
    def test_full_advance_flow(self, admin, brand, creator):
        bs, _ = brand
        cs, _, cemail = creator
        _complete_creator(cs)
        cid, _ = _seed_open_campaign(bs)
        cs.post(f"{BASE_URL}/campaigns/{cid}/apply", json={
            "pitch": "excellent fit for cafe cont ent", "quoted_rate": 6000,
        })
        rows = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["applied"]
        collab_id = next(x["id"] for x in rows if x["creator"]["email"] == cemail)

        def advance(body=None):
            return admin.post(
                f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
                json=body or {},
            )

        # applied -> vetted
        r = advance()
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "vetted"
        # vetted -> accepted
        r = advance()
        assert r.json()["state"] == "accepted"
        # accepted -> commercial_agreed without amount -> 422
        r = advance()
        assert r.status_code == 422
        assert "Agreed amount is required" in r.text
        # with amount
        r = advance({"agreed_amount": 8500})
        assert r.status_code == 200
        assert r.json()["state"] == "commercial_agreed"
        assert r.json()["agreed_amount"] == 8500
        # -> slot_booked
        assert advance().json()["state"] == "slot_booked"
        # -> attended
        assert advance().json()["state"] == "attended"
        # -> content_submitted
        assert advance().json()["state"] == "content_submitted"
        # -> in_payment without fee -> 422
        r = advance()
        assert r.status_code == 422
        assert "Platform fee is required" in r.text
        # with fee
        r = advance({"platform_fee": 1500})
        assert r.status_code == 200
        assert r.json()["state"] == "in_payment"

        # payment doc verification via /admin/collaborations
        all_c = admin.get(f"{BASE_URL}/admin/collaborations").json()
        row = next(x for x in all_c["by_state"]["in_payment"] if x["id"] == collab_id)
        pay = row["payment"]
        assert pay is not None
        assert pay["agreed_amount"] == 8500
        assert pay["platform_fee"] == 1500
        assert pay["creator_payout"] == 8500
        assert pay["state"] == "pending"

        # mark_paid
        mr = admin.post(f"{BASE_URL}/admin/payments/{pay['id']}/mark_paid")
        assert mr.status_code == 200
        md = mr.json()
        assert md["state"] == "paid"
        assert md["paid_at"]
        assert md["collaboration_id"] == collab_id

        # collab now closed
        all_c2 = admin.get(f"{BASE_URL}/admin/collaborations").json()
        assert any(x["id"] == collab_id for x in all_c2["by_state"]["closed"])

        # advancing from closed -> 400
        r = advance()
        assert r.status_code == 400
        assert "final state" in r.text.lower()

    def test_advance_from_in_payment_moves_to_closed_without_paying(
        self, admin, brand, creator
    ):
        bs, _ = brand
        cs, _, cemail = creator
        _complete_creator(cs)
        cid, _ = _seed_open_campaign(bs)
        cs.post(f"{BASE_URL}/campaigns/{cid}/apply", json={
            "pitch": "pitch text here for testing", "quoted_rate": 4000,
        })
        rows = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["applied"]
        collab_id = next(x["id"] for x in rows if x["creator"]["email"] == cemail)

        def advance(body=None):
            return admin.post(
                f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
                json=body or {},
            )
        advance(); advance()  # -> accepted
        advance({"agreed_amount": 3000})  # -> commercial_agreed
        advance(); advance(); advance()  # slot_booked, attended, content_submitted
        r = advance({"platform_fee": 500})
        assert r.json()["state"] == "in_payment"

        # advance again from in_payment -> closed but payment stays pending
        r = advance()
        assert r.status_code == 200
        assert r.json()["state"] == "closed"

        all_c = admin.get(f"{BASE_URL}/admin/collaborations").json()
        row = next(x for x in all_c["by_state"]["closed"] if x["id"] == collab_id)
        assert row["payment"] is not None
        assert row["payment"]["state"] == "pending"


# ---------- 6. Metrics ----------

class TestAdminMetrics:
    def test_metrics_shape_and_types(self, admin):
        r = admin.get(f"{BASE_URL}/admin/metrics")
        assert r.status_code == 200
        d = r.json()
        for k in ["open_campaigns", "vetted_creators", "total_paid_out"]:
            assert k in d
        assert isinstance(d["open_campaigns"], int)
        assert isinstance(d["vetted_creators"], int)
        assert isinstance(d["total_paid_out"], (int, float))

    def test_metrics_react_to_mark_paid(self, admin, brand, creator):
        before = admin.get(f"{BASE_URL}/admin/metrics").json()
        bs, _ = brand
        cs, _, cemail = creator
        _complete_creator(cs)
        cid, _ = _seed_open_campaign(bs)
        cs.post(f"{BASE_URL}/campaigns/{cid}/apply", json={
            "pitch": "pitch pitch pitch for real", "quoted_rate": 1000,
        })
        rows = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["applied"]
        collab_id = next(x["id"] for x in rows if x["creator"]["email"] == cemail)

        def advance(body=None):
            return admin.post(f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
                              json=body or {})
        advance(); advance()
        advance({"agreed_amount": 2500})
        advance(); advance(); advance()
        r = advance({"platform_fee": 300})
        assert r.status_code == 200
        pay_id = next(
            x["payment"]["id"]
            for x in admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["in_payment"]
            if x["id"] == collab_id
        )
        admin.post(f"{BASE_URL}/admin/payments/{pay_id}/mark_paid")
        after = admin.get(f"{BASE_URL}/admin/metrics").json()
        assert after["total_paid_out"] >= before["total_paid_out"] + 2500 - 0.01
        assert after["vetted_creators"] >= before["vetted_creators"]  # untouched here
