"""Backend tests for /api/campaigns router (list, filters, detail, apply w/ pitch+rate)."""
import os
import uuid
import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")

APPLY_BODY = {"pitch": "I love this brief, would shoot a warm evening reel.", "quoted_rate": 8000}


def _rand_email(role):
    return f"TEST_{role}-{uuid.uuid4().hex[:10]}@example.com"


def _register(session, role):
    email = _rand_email(role)
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


def _admin_session():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return s


def _verified_creator():
    """A creator who can actually apply.

    Verification gates applying now, so a bare registration is no longer enough to
    exercise the apply endpoint.
    """
    s = requests.Session()
    email, user = _register(s, "creator")
    pipeline.complete_creator_profile(s)
    pipeline.verify_creator(_admin_session(), user["id"])
    return s, email, user


@pytest.fixture
def creator_session():
    return _verified_creator()


@pytest.fixture
def creator_session_2():
    return _verified_creator()


@pytest.fixture
def unverified_creator_session():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, email, user


@pytest.fixture
def brand_session():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email, user


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


# ---------- List endpoint ----------

def test_list_campaigns_only_open_and_upcoming(creator_session):
    s, _, _ = creator_session
    r = s.get(f"{BASE_URL}/campaigns")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    statuses = {c["status"] for c in data}
    assert statuses.issubset({"open", "upcoming"})
    titles = [c["title"] for c in data]
    assert "[Internal draft \u2014 should not appear]" not in titles
    assert "[Closed \u2014 should not appear]" not in titles


def test_list_campaigns_area_filter(creator_session):
    s, _, _ = creator_session
    r = s.get(f"{BASE_URL}/campaigns", params={"area": "Indiranagar"})
    assert r.status_code == 200
    assert all(c["area"] == "Indiranagar" for c in r.json())


def test_list_campaigns_requires_auth():
    r = requests.get(f"{BASE_URL}/campaigns")
    assert r.status_code == 401


def test_list_campaigns_brand_forbidden(brand_session):
    s, _, _ = brand_session
    assert s.get(f"{BASE_URL}/campaigns").status_code == 403


# ---------- Filters endpoint ----------

def test_filters_endpoint(creator_session):
    s, _, _ = creator_session
    r = s.get(f"{BASE_URL}/campaigns/filters")
    assert r.status_code == 200
    data = r.json()
    assert "Indiranagar" in data["areas"]
    assert "fnb" in data["categories"]


# ---------- Detail endpoint ----------

def test_detail_open_campaign_no_application(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    open_c = next(c for c in listing if c["status"] == "open")
    r = s.get(f"{BASE_URL}/campaigns/{open_c['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["has_applied"] is False
    assert d["application"] is None


def test_detail_draft_hidden_for_creator_visible_for_admin(creator_session, admin_session):
    from pymongo import MongoClient
    mc = MongoClient(os.environ["MONGO_URL"])
    draft = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Internal draft \u2014 should not appear]"})
    closed = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Closed \u2014 should not appear]"})
    assert draft and closed
    s, _, _ = creator_session
    assert s.get(f"{BASE_URL}/campaigns/{draft['_id']}").status_code == 404
    assert s.get(f"{BASE_URL}/campaigns/{closed['_id']}").status_code == 404
    assert admin_session.get(f"{BASE_URL}/campaigns/{draft['_id']}").status_code == 200
    assert admin_session.get(f"{BASE_URL}/campaigns/{closed['_id']}").status_code == 200


def test_detail_open_campaign_hidden_from_other_brands(brand_session, creator_session):
    """Changed deliberately: a brand used to be able to read every live brief,
    including a competitor's budget and deliverables."""
    s_c, _, _ = creator_session
    open_c = next(c for c in s_c.get(f"{BASE_URL}/campaigns").json() if c["status"] == "open")
    s_b, _, _ = brand_session
    assert s_b.get(f"{BASE_URL}/campaigns/{open_c['id']}").status_code == 404


def test_detail_draft_hidden_for_brand(brand_session):
    from pymongo import MongoClient
    mc = MongoClient(os.environ["MONGO_URL"])
    draft = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Internal draft \u2014 should not appear]"})
    closed = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Closed \u2014 should not appear]"})
    s, _, _ = brand_session
    assert s.get(f"{BASE_URL}/campaigns/{draft['_id']}").status_code == 404
    assert s.get(f"{BASE_URL}/campaigns/{closed['_id']}").status_code == 404


def test_apply_admin_forbidden(admin_session, creator_session):
    s_c, _, _ = creator_session
    cid = s_c.get(f"{BASE_URL}/campaigns").json()[0]["id"]
    r = admin_session.post(f"{BASE_URL}/campaigns/{cid}/apply", json=APPLY_BODY)
    assert r.status_code == 403


def test_detail_invalid_id_404(creator_session):
    s, _, _ = creator_session
    assert s.get(f"{BASE_URL}/campaigns/000000000000000000000000").status_code == 404


# ---------- Apply endpoint (new body-required contract) ----------

def test_apply_missing_body_422(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    cid = listing[0]["id"]
    r = s.post(f"{BASE_URL}/campaigns/{cid}/apply")
    assert r.status_code == 422, r.text


def test_apply_empty_pitch_422(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    cid = listing[0]["id"]
    r = s.post(f"{BASE_URL}/campaigns/{cid}/apply", json={"pitch": "", "quoted_rate": 5000})
    assert r.status_code == 422, r.text


def test_apply_negative_rate_422(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    cid = listing[0]["id"]
    r = s.post(f"{BASE_URL}/campaigns/{cid}/apply", json={"pitch": "hello", "quoted_rate": -1})
    assert r.status_code == 422, r.text


def test_apply_success_then_duplicate_and_detail_embeds_application(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    cid = listing[0]["id"]

    body = {"pitch": "  My warm two-line pitch  ", "quoted_rate": 7500}
    r1 = s.post(f"{BASE_URL}/campaigns/{cid}/apply", json=body)
    assert r1.status_code == 200, r1.text
    j = r1.json()
    assert j["state"] == "applied"
    assert j["pitch"] == "My warm two-line pitch"  # trimmed
    assert j["quoted_rate"] == 7500
    assert j["campaign_id"] == cid
    assert "id" in j and "created_at" in j

    d = s.get(f"{BASE_URL}/campaigns/{cid}").json()
    assert d["has_applied"] is True
    app = d["application"]
    assert app["state"] == "applied"
    assert app["pitch"] == "My warm two-line pitch"
    assert app["quoted_rate"] == 7500
    assert app["agreed_amount"] is None
    assert app["id"] == j["id"]

    r2 = s.post(f"{BASE_URL}/campaigns/{cid}/apply", json=body)
    assert r2.status_code == 409


def test_apply_brand_forbidden(brand_session, creator_session):
    s_c, _, _ = creator_session
    cid = s_c.get(f"{BASE_URL}/campaigns").json()[0]["id"]
    s_b, _, _ = brand_session
    r = s_b.post(f"{BASE_URL}/campaigns/{cid}/apply", json=APPLY_BODY)
    assert r.status_code == 403


def test_apply_unauthenticated_401(creator_session):
    s, _, _ = creator_session
    cid = s.get(f"{BASE_URL}/campaigns").json()[0]["id"]
    r = requests.post(f"{BASE_URL}/campaigns/{cid}/apply", json=APPLY_BODY)
    assert r.status_code == 401


def test_apply_draft_and_closed_404(creator_session):
    from pymongo import MongoClient
    mc = MongoClient(os.environ["MONGO_URL"])
    draft = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Internal draft \u2014 should not appear]"})
    closed = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Closed \u2014 should not appear]"})
    s, _, _ = creator_session
    assert s.post(f"{BASE_URL}/campaigns/{draft['_id']}/apply", json=APPLY_BODY).status_code == 404
    assert s.post(f"{BASE_URL}/campaigns/{closed['_id']}/apply", json=APPLY_BODY).status_code == 404


def test_apply_invalid_id_404(creator_session):
    s, _, _ = creator_session
    assert s.post(f"{BASE_URL}/campaigns/not-an-id/apply", json=APPLY_BODY).status_code == 404


def test_second_creator_can_apply_to_same_campaign(creator_session, creator_session_2):
    s1, _, _ = creator_session
    s2, _, _ = creator_session_2
    cid = s1.get(f"{BASE_URL}/campaigns").json()[-1]["id"]
    r = s2.post(f"{BASE_URL}/campaigns/{cid}/apply", json={"pitch": "me too", "quoted_rate": 100})
    assert r.status_code == 200


# ---------- Verification gates applying ----------

def test_unverified_creator_cannot_apply(unverified_creator_session, creator_session):
    """The 48-hour review used to be advisory — anyone could pitch on anything."""
    s, _, _ = unverified_creator_session
    live, _, _ = creator_session
    cid = live.get(f"{BASE_URL}/campaigns").json()[0]["id"]
    r = s.post(f"{BASE_URL}/campaigns/{cid}/apply", json=APPLY_BODY)
    assert r.status_code == 403, r.text
    assert "approved" in r.json()["detail"].lower()


def test_rejected_creator_is_told_why_they_cannot_apply(unverified_creator_session,
                                                        creator_session):
    s, _, user = unverified_creator_session
    pipeline.complete_creator_profile(s)
    admin = _admin_session()
    r = admin.post(f"{BASE_URL}/admin/creators/{user['id']}/reject")
    assert r.status_code == 200, r.text

    live, _, _ = creator_session
    cid = live.get(f"{BASE_URL}/campaigns").json()[0]["id"]
    r = s.post(f"{BASE_URL}/campaigns/{cid}/apply", json=APPLY_BODY)
    assert r.status_code == 403
    assert "wasn't approved" in r.json()["detail"].lower()


def test_detail_explains_why_apply_is_blocked(unverified_creator_session, creator_session):
    """The button and the API must agree — the page says why, up front."""
    s, _, _ = unverified_creator_session
    live, _, _ = creator_session
    cid = live.get(f"{BASE_URL}/campaigns").json()[0]["id"]

    d = s.get(f"{BASE_URL}/campaigns/{cid}").json()
    assert d["can_apply"] is False
    assert d["apply_blocked_reason"]

    d2 = live.get(f"{BASE_URL}/campaigns/{cid}").json()
    assert d2["can_apply"] is True
    assert d2["apply_blocked_reason"] is None


def test_brand_cannot_read_another_brands_brief(brand_session, creator_session):
    """A live brief carries a competitor's budget and deliverables."""
    s_b, _, _ = brand_session
    live, _, _ = creator_session
    cid = live.get(f"{BASE_URL}/campaigns").json()[0]["id"]
    assert s_b.get(f"{BASE_URL}/campaigns/{cid}").status_code == 404

    # Its own brief is readable in any state, including draft.
    s_b.put(f"{BASE_URL}/brand/profile", json={
        "business_name": f"Br-{uuid.uuid4().hex[:5]}",
        "category": "fnb", "areas": ["Indiranagar"],
    })
    own = s_b.post(f"{BASE_URL}/brand/campaigns", json={
        "title": f"Own-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
        "budget_per_creator": 4000, "category": "fnb", "area": "Indiranagar",
        "creators_needed": 1, "status": "draft",
    }).json()
    assert s_b.get(f"{BASE_URL}/campaigns/{own['id']}").status_code == 200


# ---------- Public preview ----------

def test_public_preview_needs_no_account():
    """The landing page promises "discover briefs"; a visitor can now see some."""
    r = requests.get(f"{BASE_URL}/public/campaigns")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "campaigns" in data and "total_open" in data
    for c in data["campaigns"]:
        # Enough to judge whether it's worth joining, and no more.
        for field in ["id", "title", "brand_name", "budget_per_creator", "teaser"]:
            assert field in c
        assert "brief" not in c, "the full brief stays behind the signup"
        assert "deliverables" not in c


def test_public_stats_needs_no_account():
    r = requests.get(f"{BASE_URL}/public/stats")
    assert r.status_code == 200
    for k in ["verified_creators", "open_campaigns", "cities"]:
        assert isinstance(r.json()[k], int)
