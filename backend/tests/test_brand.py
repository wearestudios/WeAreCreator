"""Backend tests for the /api/brand/* router: profile, dashboard, campaigns list & post, cross-visibility."""
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


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def brand_session():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email, user


@pytest.fixture
def brand_session_2():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email, user


@pytest.fixture
def creator_session():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, email, user


@pytest.fixture
def admin_session():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


# ---------- profile ----------

class TestBrandProfile:
    def test_get_profile_stub_after_signup(self, brand_session):
        s, email, _ = brand_session
        r = s.get(f"{BASE_URL}/brand/profile")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "business_name" in data
        assert data.get("category") in (None, "fnb", "hospitality", "retail", "lifestyle")

    def test_get_profile_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.get(f"{BASE_URL}/brand/profile")
        assert r.status_code == 403

    def test_get_profile_forbidden_for_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/brand/profile")
        assert r.status_code == 403

    def test_put_profile_updates_and_mirrors_name(self, brand_session):
        s, email, _ = brand_session
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Cafe Aroma",
            "category": "fnb",
            "areas": ["Indiranagar", "Koramangala"],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["business_name"] == "Cafe Aroma"
        assert d["category"] == "fnb"
        assert d["areas"] == ["Indiranagar", "Koramangala"]

        # Mirrors business_name → users.name
        me = s.get(f"{BASE_URL}/auth/me")
        assert me.status_code == 200
        assert me.json()["name"] == "Cafe Aroma"

        # GET reflects persistence
        g = s.get(f"{BASE_URL}/brand/profile")
        assert g.status_code == 200
        assert g.json()["business_name"] == "Cafe Aroma"
        assert g.json()["areas"] == ["Indiranagar", "Koramangala"]

    def test_put_profile_wrong_category_422(self, brand_session):
        s, _, _ = brand_session
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "X", "category": "tech", "areas": ["Indiranagar"],
        })
        assert r.status_code == 422

    def test_put_profile_empty_areas_allowed(self, brand_session):
        s, _, _ = brand_session
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "X", "category": "retail", "areas": [],
        })
        assert r.status_code == 200
        assert r.json()["areas"] == []


# ---------- campaigns list & post ----------

class TestBrandCampaigns:
    def _seed_profile(self, s):
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Brand X", "category": "fnb", "areas": ["Indiranagar"],
        })
        assert r.status_code == 200, r.text

    def test_post_campaign_open_returns_row(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        body = {
            "title": "Weekend Reel", "brief": "Shoot a warm reel at our cafe.",
            "deliverables": "1 reel, 3 stories", "budget_per_creator": 5000,
            "category": "fnb", "area": "Indiranagar", "creators_needed": 3,
            "start_date": "2026-02-01T00:00:00Z", "end_date": "2026-02-15T00:00:00Z",
            "status": "open",
        }
        r = s.post(f"{BASE_URL}/brand/campaigns", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "open"
        assert d["applicant_count"] == 0
        assert d["title"] == "Weekend Reel"
        assert d["creators_needed"] == 3
        assert "id" in d

    def test_post_campaign_draft_allowed(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "Draft", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1, "status": "draft",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "draft"

    def test_post_campaign_invalid_category_422(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "tech", "area": "Indiranagar",
            "creators_needed": 1, "status": "open",
        })
        assert r.status_code == 422

    def test_post_campaign_end_before_start_422(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1,
            "start_date": "2026-02-15T00:00:00Z", "end_date": "2026-02-01T00:00:00Z",
            "status": "open",
        })
        assert r.status_code == 422
        assert "End date cannot be before start date" in r.text

    def test_post_campaign_needed_lt_1_422(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 0, "status": "open",
        })
        assert r.status_code == 422

    def test_list_only_own_and_newest_first(self, brand_session, brand_session_2):
        s1, _, _ = brand_session
        s2, _, _ = brand_session_2
        self._seed_profile(s1)
        self._seed_profile(s2)

        # brand1 posts two, brand2 posts one
        base = {"brief": "b", "deliverables": "d", "budget_per_creator": 100,
                "category": "fnb", "area": "Indiranagar", "creators_needed": 1}
        r1 = s1.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "B1-first", "status": "draft"})
        r2 = s1.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "B1-second", "status": "open"})
        r3 = s2.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "B2-only", "status": "open"})
        assert r1.status_code == r2.status_code == r3.status_code == 200

        lst = s1.get(f"{BASE_URL}/brand/campaigns")
        assert lst.status_code == 200
        rows = lst.json()
        titles = [r["title"] for r in rows]
        assert "B2-only" not in titles
        assert "B1-first" in titles and "B1-second" in titles
        # newest-first: B1-second created after B1-first
        assert titles.index("B1-second") < titles.index("B1-first")
        # includes draft
        statuses = {r["title"]: r["status"] for r in rows}
        assert statuses["B1-first"] == "draft"
        for row in rows:
            assert "applicant_count" in row

    def test_list_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.get(f"{BASE_URL}/brand/campaigns")
        assert r.status_code == 403

    def test_post_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1, "status": "open",
        })
        assert r.status_code == 403


# ---------- dashboard ----------

class TestBrandDashboard:
    def test_dashboard_shape_and_totals(self, brand_session, creator_session):
        s, _, _ = brand_session
        s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Brand D", "category": "hospitality",
            "areas": ["Whitefield"],
        })
        base = {"brief": "b", "deliverables": "d", "budget_per_creator": 100,
                "category": "hospitality", "area": "Whitefield", "creators_needed": 1}
        r_open = s.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "Open1", "status": "open"})
        r_draft = s.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "Draft1", "status": "draft"})
        open_id = r_open.json()["id"]

        # A creator applies to the open campaign → applicant_count should become 1
        cs, _, _ = creator_session
        # creator must complete onboarding to apply
        cs.put(f"{BASE_URL}/creator/profile", json={
            "name": "C", "instagram_handle": "@c",
            "instagram_profile_url": "https://instagram.com/c",
            "address": "Bengaluru", "niches": ["cafe"],
        })
        ar = cs.post(f"{BASE_URL}/campaigns/{open_id}/apply",
                     json={"pitch": "hi there really keen", "quoted_rate": 5000})
        assert ar.status_code in (200, 201), ar.text

        r = s.get(f"{BASE_URL}/brand/dashboard")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["profile"]["business_name"] == "Brand D"
        assert d["totals"]["total_campaigns"] == 2
        assert d["totals"]["live_campaigns"] == 1
        assert d["totals"]["draft_campaigns"] == 1
        assert d["totals"]["total_applications"] == 1
        by_title = {c["title"]: c for c in d["campaigns"]}
        assert by_title["Open1"]["applicant_count"] == 1
        assert by_title["Draft1"]["applicant_count"] == 0

    def test_dashboard_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.get(f"{BASE_URL}/brand/dashboard")
        assert r.status_code == 403

    def test_dashboard_forbidden_for_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/brand/dashboard")
        assert r.status_code == 403


# ---------- cross-visibility ----------

class TestCrossVisibility:
    def test_open_campaign_appears_on_creator_feed(self, brand_session, creator_session):
        s, _, _ = brand_session
        s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Feed Brand", "category": "retail", "areas": ["HSR Layout"],
        })
        title = f"OpenFeed-{uuid.uuid4().hex[:6]}"
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": title, "brief": "b", "deliverables": "d",
            "budget_per_creator": 200, "category": "retail", "area": "HSR Layout",
            "creators_needed": 2, "status": "open",
        })
        assert r.status_code == 200
        cid = r.json()["id"]

        cs, _, _ = creator_session
        feed = cs.get(f"{BASE_URL}/campaigns")
        assert feed.status_code == 200
        titles = [c["title"] for c in feed.json()]
        assert title in titles

        # filter by area
        f2 = cs.get(f"{BASE_URL}/campaigns", params={"area": "HSR Layout"})
        assert f2.status_code == 200
        assert title in [c["title"] for c in f2.json()]

        # filter by category
        f3 = cs.get(f"{BASE_URL}/campaigns", params={"category": "retail"})
        assert f3.status_code == 200
        assert title in [c["title"] for c in f3.json()]

        # detail visible to brand (creator too since it's open)
        det_brand = s.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_brand.status_code == 200
        det_creator = cs.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_creator.status_code == 200

    def test_draft_hidden_from_creator_visible_to_admin(
        self, brand_session, creator_session, admin_session
    ):
        s, _, _ = brand_session
        s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Draft Brand", "category": "lifestyle", "areas": ["Jayanagar"],
        })
        title = f"DraftHidden-{uuid.uuid4().hex[:6]}"
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": title, "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "lifestyle", "area": "Jayanagar",
            "creators_needed": 1, "status": "draft",
        })
        assert r.status_code == 200
        cid = r.json()["id"]

        cs, _, _ = creator_session
        feed = cs.get(f"{BASE_URL}/campaigns")
        assert feed.status_code == 200
        assert title not in [c["title"] for c in feed.json()]

        det_creator = cs.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_creator.status_code == 404

        det_admin = admin_session.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_admin.status_code == 200
