"""Backend tests for /api/campaigns router (list, filters, detail, apply w/ pitch+rate)."""
import os
import uuid
import pytest
import requests

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


@pytest.fixture
def creator_session():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, email, user


@pytest.fixture
def creator_session_2():
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


def test_detail_open_campaign_brand_allowed(brand_session, creator_session):
    s_c, _, _ = creator_session
    open_c = next(c for c in s_c.get(f"{BASE_URL}/campaigns").json() if c["status"] == "open")
    s_b, _, _ = brand_session
    r = s_b.get(f"{BASE_URL}/campaigns/{open_c['id']}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == open_c["id"]
    assert d.get("has_applied") in (False, None)


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
