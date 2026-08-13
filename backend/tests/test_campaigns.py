"""Backend tests for the /api/campaigns router (list, filters, detail, apply)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


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
    assert len(data) >= 5  # 5 seeded live
    statuses = {c["status"] for c in data}
    assert statuses.issubset({"open", "upcoming"})
    titles = [c["title"] for c in data]
    assert "[Internal draft — should not appear]" not in titles
    assert "[Closed — should not appear]" not in titles
    # Shape assertions on one campaign
    c = data[0]
    for key in ("id", "brand_id", "brand_name", "title", "brief", "deliverables",
                "budget_per_creator", "category", "area", "status"):
        assert key in c


def test_list_campaigns_area_filter(creator_session):
    s, _, _ = creator_session
    r = s.get(f"{BASE_URL}/campaigns", params={"area": "Indiranagar"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert all(c["area"] == "Indiranagar" for c in data)


def test_list_campaigns_category_filter(creator_session):
    s, _, _ = creator_session
    r = s.get(f"{BASE_URL}/campaigns", params={"category": "hospitality"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["category"] == "hospitality"


def test_list_campaigns_requires_auth():
    r = requests.get(f"{BASE_URL}/campaigns")
    assert r.status_code == 401


def test_list_campaigns_brand_forbidden(brand_session):
    s, _, _ = brand_session
    r = s.get(f"{BASE_URL}/campaigns")
    assert r.status_code == 403


# ---------- Filters endpoint ----------

def test_filters_endpoint(creator_session):
    s, _, _ = creator_session
    r = s.get(f"{BASE_URL}/campaigns/filters")
    assert r.status_code == 200
    data = r.json()
    assert data["areas"] == ["Indiranagar", "Koramangala", "MG Road", "Whitefield"]
    assert data["categories"] == ["fnb", "hospitality"]


# ---------- Detail endpoint ----------

def test_detail_open_campaign(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    open_c = next(c for c in listing if c["status"] == "open")
    r = s.get(f"{BASE_URL}/campaigns/{open_c['id']}")
    assert r.status_code == 200
    d = r.json()
    for key in ("brand_name", "brief", "deliverables", "budget_per_creator",
                "start_date", "end_date"):
        assert key in d
    assert d["has_applied"] is False


def test_detail_draft_hidden_for_creator_visible_for_admin(creator_session, admin_session):
    # Look up the seeded draft directly in Mongo to get its id.
    from pymongo import MongoClient
    mc = MongoClient(os.environ["MONGO_URL"])
    draft = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Internal draft — should not appear]"})
    closed = mc[os.environ["DB_NAME"]].campaigns.find_one({"title": "[Closed — should not appear]"})
    assert draft is not None and closed is not None
    draft_id = str(draft["_id"])
    closed_id = str(closed["_id"])
    s, _, _ = creator_session
    assert s.get(f"{BASE_URL}/campaigns/{draft_id}").status_code == 404
    assert s.get(f"{BASE_URL}/campaigns/{closed_id}").status_code == 404
    # Admin: 200
    assert admin_session.get(f"{BASE_URL}/campaigns/{draft_id}").status_code == 200
    assert admin_session.get(f"{BASE_URL}/campaigns/{closed_id}").status_code == 200


def test_detail_invalid_id_404(creator_session):
    # ... (defined below)
    s, _, _ = creator_session
    r = s.get(f"{BASE_URL}/campaigns/000000000000000000000000")
    assert r.status_code == 404


# ---------- Apply endpoint ----------

def test_apply_flow_creator_success_then_duplicate(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    cid = listing[0]["id"]

    r1 = s.post(f"{BASE_URL}/campaigns/{cid}/apply")
    assert r1.status_code == 200, r1.text
    assert r1.json()["state"] == "applied"

    # Detail now shows has_applied True
    d = s.get(f"{BASE_URL}/campaigns/{cid}").json()
    assert d["has_applied"] is True

    r2 = s.post(f"{BASE_URL}/campaigns/{cid}/apply")
    assert r2.status_code == 409
    assert "already applied" in r2.json().get("detail", "").lower()


def test_apply_brand_forbidden(brand_session, creator_session):
    s_c, _, _ = creator_session
    listing = s_c.get(f"{BASE_URL}/campaigns").json()
    cid = listing[0]["id"]
    s_b, _, _ = brand_session
    r = s_b.post(f"{BASE_URL}/campaigns/{cid}/apply")
    assert r.status_code == 403


def test_apply_unauthenticated_401(creator_session):
    s, _, _ = creator_session
    listing = s.get(f"{BASE_URL}/campaigns").json()
    cid = listing[0]["id"]
    r = requests.post(f"{BASE_URL}/campaigns/{cid}/apply")
    assert r.status_code == 401


def test_apply_invalid_id_404(creator_session):
    s, _, _ = creator_session
    r = s.post(f"{BASE_URL}/campaigns/not-an-id/apply")
    assert r.status_code == 404


def test_second_creator_can_apply_to_same_campaign(creator_session, creator_session_2):
    s1, _, _ = creator_session
    s2, _, _ = creator_session_2
    listing = s1.get(f"{BASE_URL}/campaigns").json()
    cid = listing[-1]["id"]  # different campaign
    r = s2.post(f"{BASE_URL}/campaigns/{cid}/apply")
    assert r.status_code == 200
    assert r.json()["state"] == "applied"
